"""Managed Akash deployments with durable ownership, budget reservations and pinned TLS."""

import base64
import json
import os
import re
import socket
import sqlite3
import ssl
import threading
import time
from datetime import UTC, datetime
from urllib.parse import urlencode, urlsplit

from backend.providers.http import JsonHttpClient
from sandbox.workspace.runner import parse_receipt

API = "https://console-api.akash.network"
CHAIN = "https://api.akashnet.net"
CAP_USD = 20.0


class Budget:
    """Conservative reservations are never mislabeled as measured provider charges."""

    def __init__(self, path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS reservations(id TEXT PRIMARY KEY, provider TEXT, "
                "usd REAL, state TEXT, dseq TEXT, name TEXT)"
            )
        path.chmod(0o600)

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def reserve(self, job_id, provider, usd):
        if not 0 < usd <= 2:
            raise ValueError("Invalid reservation")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if (
                provider == "akash_compute"
                and db.execute(
                    "SELECT count(*) FROM reservations WHERE provider='akash_compute' "
                    "AND state!='closed'"
                ).fetchone()[0]
            ):
                raise ValueError("An Akash deployment requires cleanup first")
            spent = db.execute("SELECT coalesce(sum(usd),0) FROM reservations").fetchone()[0]
            if spent + usd > CAP_USD:
                raise ValueError("Validation budget exhausted")
            db.execute(
                "INSERT INTO reservations VALUES(?,?,?,'reserved',NULL,?)",
                (job_id, provider, usd, "proofloop-" + job_id),
            )

    def update(self, job_id, state, dseq=None):
        with self.connect() as db:
            db.execute(
                "UPDATE reservations SET state=?,dseq=coalesce(?,dseq) WHERE id=?",
                (state, dseq, job_id),
            )

    def pending(self):
        with self.connect() as db:
            return db.execute(
                "SELECT id,dseq,name FROM reservations WHERE provider='akash_compute' "
                "AND state!='closed'"
            ).fetchall()

    def summary(self):
        with self.connect() as db:
            used = db.execute("SELECT coalesce(sum(usd),0) FROM reservations").fetchone()[0]
        return {
            "cap_usd": CAP_USD,
            "reserved_usd": used,
            "remaining_usd": CAP_USD - used,
            "basis": "conservative reservations, not measured charges",
        }


def sdl(images):
    if set(images) != {"baseline", "patched", "tester"} or any(
        not re.fullmatch(r"[a-z0-9./_-]+@sha256:[0-9a-f]{64}", i) for i in images.values()
    ):
        raise ValueError("Digest-pinned three-service inventory required")
    services = {
        name: {"image": image, "expose": [{"port": 8000, "to": [{"service": "tester"}]}]}
        for name, image in images.items()
    }
    services["tester"]["expose"] = [{"port": 8080, "as": 80, "to": [{"global": True}]}]
    services["tester"]["env"] = ["PROOFLOOP_CLOUD=1"]
    document = {
        "version": "2.0",
        "services": services,
        "profiles": {
            "compute": {
                name: {
                    "resources": {
                        "cpu": {"units": 1},
                        "memory": {"size": "512Mi"},
                        "storage": [{"size": "2Gi"}],
                    }
                }
                for name in images
            },
            "placement": {
                "akash": {"pricing": {name: {"denom": "uact", "amount": 100} for name in images}}
            },
        },
        "deployment": {name: {"akash": {"profile": name, "count": 1}} for name in images},
    }
    return json.dumps(document)  # JSON is valid YAML; no source or model text enters SDL.


def pinned_context(provider, http):
    """Use valid on-chain self-signed certificates as trust anchors, never CERT_NONE."""
    from cryptography import x509
    from cryptography.x509.oid import NameOID

    if not re.fullmatch(r"akash1[a-z0-9]{38}", provider):
        raise ValueError("Invalid provider address")
    query = urlencode(
        {"filter.owner": provider, "filter.state": "valid", "pagination.limit": "100"}
    )
    result = http.request("GET", CHAIN + "/akash/cert/v1/certificates/list?" + query, {})
    certs, fingerprints = [], set()
    for entry in result.get("certificates", []):
        raw = entry["certificate"]["cert"]
        pem = raw.encode() if raw.startswith("-----BEGIN") else base64.b64decode(raw)
        cert = x509.load_pem_x509_certificate(pem)
        names = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        now = datetime.now(UTC)
        if (
            len(names) != 1
            or names[0].value != provider
            or cert.subject != cert.issuer
            or not cert.not_valid_before_utc <= now <= cert.not_valid_after_utc
        ):
            continue
        cert.verify_directly_issued_by(cert)
        certs.append(pem.decode())
        from cryptography.hazmat.primitives import hashes

        fingerprints.add(cert.fingerprint(hashes.SHA256()))
    if not certs:
        raise ValueError("No valid on-chain provider certificate")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False  # Identity is the checked chain wallet, not DNS SAN.
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_verify_locations(cadata="\n".join(certs))
    return context, fingerprints


class Compute:
    def __init__(self, budget, *, key=None, http=None):
        self.key = key or os.getenv("AKASH_CONSOLE_API_KEY")
        self.http = http or JsonHttpClient("akash_compute", timeout=45, retries=0)
        self.budget = budget

    def api(self, method, path, payload=None):
        if not self.key:
            raise ValueError("Akash Console is not configured")
        result = self.http.request(
            method, API + path, {"x-api-key": self.key, "Content-Type": "application/json"}, payload
        )
        return result.get("data", result)

    def close(self, dseq):
        if not re.fullmatch(r"[1-9][0-9]{0,25}", str(dseq)):
            raise ValueError("Invalid deployment ID")
        current = self.api("GET", f"/v1/deployments/{dseq}")
        if current["deployment"]["state"] == "closed":
            return current
        self.api("DELETE", f"/v1/deployments/{dseq}")
        for _ in range(15):
            result = self.api("GET", f"/v1/deployments/{dseq}")
            if result["deployment"]["state"] == "closed":
                return result
            time.sleep(3)
        raise RuntimeError("Deployment closure unconfirmed")

    def reconcile(self):
        """Only close deployment IDs or exact unique names owned by this journal."""
        for job_id, dseq, name in self.budget.pending():
            if not dseq:
                listed = self.api(
                    "GET", "/v1/deployments?" + urlencode({"search": name, "limit": 100})
                )
                matching = [d for d in listed["deployments"] if d.get("name") == name]
                if not matching:
                    # Unknown create outcomes remain reserved; never duplicate the create.
                    continue
                if len(matching) != 1:
                    raise RuntimeError("Ambiguous deployment ownership")
                dseq = matching[0]["deployment"]["id"]["dseq"]
                self.budget.update(job_id, "closing", dseq)
            self.close(dseq)
            self.budget.update(job_id, "closed")

    def logs(self, lease):
        from websockets.sync.client import connect

        provider = lease["provider"]
        # Resolve from chain, not a model response or untrusted redirect.
        record = self.http.request(
            "GET", CHAIN + "/akash/provider/v1beta4/providers/" + provider, {}
        )
        uri = record["provider"].get("host_uri") or record["provider"].get("hostUri")
        parts = urlsplit(uri)
        if (
            parts.scheme != "https"
            or parts.username
            or parts.password
            or parts.path not in {"", "/"}
        ):
            raise ValueError("Invalid provider URI")
        import ipaddress

        addresses = socket.getaddrinfo(parts.hostname, parts.port or 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise ValueError("Provider must have public addresses")
        # Some providers publish Web-PKI certificates on their chain-registered host.
        # Try normal hostname verification first; otherwise require the exact wallet cert.
        import hashlib

        endpoint = (addresses[0][4][0], parts.port or 443)
        context = ssl.create_default_context()
        try:
            with socket.create_connection(endpoint, timeout=15) as raw:
                with context.wrap_socket(raw, server_hostname=parts.hostname) as peer:
                    fingerprints = {hashlib.sha256(peer.getpeercert(binary_form=True)).digest()}
        except ssl.SSLCertVerificationError:
            context, fingerprints = pinned_context(provider, self.http)
            with socket.create_connection(endpoint, timeout=15) as raw:
                with context.wrap_socket(raw, server_hostname=parts.hostname) as peer:
                    if (
                        hashlib.sha256(peer.getpeercert(binary_form=True)).digest()
                        not in fingerprints
                    ):
                        raise ValueError("Provider certificate pin mismatch") from None
        jwt = self.api(
            "POST",
            "/v1/create-jwt-token",
            {"data": {"ttl": 600, "leases": {"access": "scoped", "scope": ["logs", "status"]}}},
        )["token"]
        url = f"wss://{parts.netloc}/lease/{lease['dseq']}/{lease['gseq']}/{lease['oseq']}/logs?follow=true&tail=200&service=tester"
        with connect(
            url,
            ssl=context,
            sock=socket.create_connection(endpoint, timeout=15),
            server_hostname=parts.hostname,
            additional_headers={"Authorization": "Bearer " + jwt},
            open_timeout=20,
            close_timeout=2,
            max_size=512_000,
            proxy=None,
        ) as stream:
            import hashlib

            if (
                hashlib.sha256(stream.socket.getpeercert(binary_form=True)).digest()
                not in fingerprints
            ):
                raise ValueError("Certificate pin mismatch")
            chunks, size = [], 0
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                raw = stream.recv(timeout=max(0.1, deadline - time.monotonic()))
                text = raw.decode() if isinstance(raw, bytes) else raw
                size += len(text)
                if size > 512_000:
                    raise ValueError("Provider logs exceed budget")
                # Provider may wrap each service log line in a JSON envelope.
                try:
                    envelope = json.loads(text)
                    if isinstance(envelope, dict):
                        text = envelope.get("message", envelope.get("Message", text))
                except ValueError:
                    pass
                chunks.append(text)
                joined = "\n".join(chunks)
                if "PROOFLOOP_RECEIPT_END=complete" in joined or "PROOFLOOP_RECEIPT=" in joined:
                    return joined
        raise RuntimeError("Remote receipt unavailable")

    def run(self, images, job, progress=lambda *_: None, cancelled=None):
        manifest = sdl(images)
        if cancelled and cancelled.is_set():
            raise RuntimeError("Job cancelled")
        self.budget.reserve(job["job_id"], "akash_compute", 2.0)
        dseq, timer, result = None, None, None
        try:
            progress("deploying", {"job_id": job["job_id"], "cost_reservation_usd": 2.0})
            created = self.api(
                "POST",
                "/v1/deployments",
                {
                    "data": {
                        "name": "proofloop-" + job["job_id"],
                        "sdl": manifest,
                        "runtimeLimitHours": 1,
                    }
                },
            )
            dseq = str(created["dseq"])
            self.budget.update(job["job_id"], "deploying", dseq)
            # Ten-minute application watchdog; Console's minimum one-hour TTL is a backup.
            timer = threading.Timer(600, self.close, [dseq])
            timer.daemon = True
            timer.start()
            deadline = time.monotonic() + 120
            chosen = None
            while time.monotonic() < deadline:
                if cancelled and cancelled.is_set():
                    raise RuntimeError("Job cancelled")
                bids = self.api("GET", "/v1/bids?" + urlencode({"dseq": dseq}))
                eligible = [
                    b["bid"]
                    for b in bids
                    if b["bid"]["state"] == "open"
                    and b["bid"]["price"]["denom"] == "uact"
                    and 0 < float(b["bid"]["price"]["amount"]) <= 100
                ]
                if eligible:
                    chosen = min(eligible, key=lambda b: float(b["price"]["amount"]))
                    break
                time.sleep(4)
            if not chosen:
                raise RuntimeError("No provider bid within the budget")
            lease = {k: chosen["id"][k] for k in ("dseq", "gseq", "oseq", "provider")}
            self.api("POST", "/v1/leases", {"leases": [lease]})
            self.budget.update(job["job_id"], "running")
            progress(
                "starting",
                {"dseq": dseq, "provider": lease["provider"], "price_per_block": chosen["price"]},
            )
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                if cancelled and cancelled.is_set():
                    raise RuntimeError("Job cancelled")
                status = self.api("GET", f"/v1/deployments/{dseq}")
                ready = status.get("leases", [{}])[0].get("status") or {}
                services = ready.get("services", {})
                if all(
                    services.get(n, {}).get(
                        "available", services.get(n, {}).get("ready_replicas", 0)
                    )
                    >= 1
                    for n in images
                ):
                    break
                time.sleep(4)
            else:
                raise RuntimeError("Remote readiness timeout")
            progress("testing", {"dseq": dseq})
            result = parse_receipt(self.logs(lease), job)
            result.update(
                {
                    "environment": "akash",
                    "dseq": dseq,
                    "provider": lease["provider"],
                    "images": images,
                    "price_per_block": chosen["price"],
                    "cost_reservation_usd": 2.0,
                    "trust": (
                        "Provider-host integrity is trusted; this is not hardware attestation."
                    ),
                }
            )
        except Exception as exc:
            progress("failed", {"failure_type": type(exc).__name__, "dseq": dseq})
            raise
        finally:
            if timer:
                timer.cancel()
            if dseq:
                progress("closing", {"dseq": dseq})
                self.budget.update(job["job_id"], "closing")
                closed = self.close(dseq)
                self.budget.update(job["job_id"], "closed")
                progress("closed", {"dseq": dseq})
                if result:
                    result["closed"] = True
                    result["settlement"] = (
                        closed.get("escrow_account", {}).get("state", {}).get("transferred", [])
                    )
        return result
