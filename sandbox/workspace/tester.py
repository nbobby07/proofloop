"""Trusted black-box HTTP oracle. Never imports application code or accepts model verdicts."""

import base64
import csv
import hashlib
import http.client
import io
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlencode, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from protocol import MEMBERS, Case, category, sha


class Oracle:
    def __init__(self, base):
        parts = urlsplit(base)
        if parts.scheme != "http" or parts.hostname not in {"127.0.0.1", "baseline", "patched"}:
            raise ValueError("Unapproved target")
        self.host, self.port = parts.hostname, parts.port or 8000
        self.cookies = {}
        self.revoked = set()
        self.logged_out = set()
        self.invoices = {
            101: (1, "Acme", "draft"),
            102: (1, "Atlas", "sent"),
            103: (1, "Aurora", "paid"),
            201: (2, "Beacon", "draft"),
            202: (2, "Birch", "sent"),
            203: (2, "Bluebird", "paid"),
        }

    def request(self, actor, method, path, body=None):
        conn = http.client.HTTPConnection(self.host, self.port, timeout=4)
        try:
            headers = {"Content-Type": "application/json"}
            if actor in self.cookies:
                headers["Cookie"] = self.cookies[actor]
            conn.request(
                method, path, body=json.dumps(body) if body is not None else None, headers=headers
            )
            response = conn.getresponse()
            raw = response.read(131073)
            if len(raw) > 131072:
                raise ValueError("Response exceeds budget")
            cookie = response.getheader("set-cookie")
            if path == "/api/login" and cookie:
                self.cookies[actor] = cookie.split(";", 1)[0]
            text = raw.decode()
            try:
                data = json.loads(text)
            except ValueError:
                data = None
            return response.status, data, text
        finally:
            conn.close()

    def login(self):
        for actor in MEMBERS:
            status, _, _ = self.request(
                actor, "POST", "/api/login", {"username": actor, "password": f"demo-{actor}"}
            )
            if status != 200 or actor not in self.cookies:
                raise ValueError("Seed session could not be established")

    def run(self, case):
        exports = {}
        created_id = None
        outcomes = []
        for index, action in enumerate(case.actions):
            actor, op = action.actor, action.operation
            uid, tenant, role = MEMBERS.get(actor, (0, 0, "anonymous"))
            expected = 200
            if actor == "anonymous" or uid in self.revoked or actor in self.logged_out:
                expected = 401
            elif (op in {"create", "update", "export", "download"} and role == "viewer") or (
                op in {"members", "revoke"} and role != "owner"
            ):
                expected = 403
            invoice_id = (created_id or 999999) if action.invoice_id == 0 else action.invoice_id
            invoice_ids = [(created_id or 999999) if i == 0 else i for i in action.invoice_ids]
            invoice = self.invoices.get(invoice_id)
            export = exports.get(action.export_slot)
            if expected == 200:
                if op in {"read", "update"} and (not invoice or invoice[0] != tenant):
                    expected = 404
                elif op == "download" and (not export or export[1] != actor):
                    expected = 404
                elif op == "export":
                    if len(set(invoice_ids)) != len(invoice_ids):
                        expected = 422
                    elif any(
                        i not in self.invoices or self.invoices[i][0] != tenant for i in invoice_ids
                    ):
                        expected = 404
                    else:
                        expected = 201
                elif op == "create":
                    expected = 201
                elif op == "update" and not action.status:
                    expected = 422
                elif op == "revoke":
                    member = next(v for v in MEMBERS.values() if v[0] == action.member_id)
                    expected = (
                        400 if uid == action.member_id else 404 if member[1] != tenant else 200
                    )
            method, path, body = "GET", "/api/me", None
            if op == "list":
                query = {"q": action.query, "page": action.page, "page_size": action.page_size}
                if action.status:
                    query["status"] = action.status
                path = "/api/invoices?" + urlencode(query)
            elif op in {"read", "update"}:
                path = f"/api/invoices/{invoice_id}"
                if op == "update":
                    method, body = "PATCH", {"status": action.status}
            elif op == "create":
                method, path = "POST", "/api/invoices"
                body = {
                    "customer": action.customer,
                    "currency": "USD",
                    "items": [{"description": "Research", "quantity": 2, "unit_price_cents": 1250}],
                }
            elif op == "export":
                method, path, body = "POST", "/api/exports", {"invoice_ids": invoice_ids}
            elif op == "download":
                path = f"/api/exports/{export[0] if export else 999999}/download"
            elif op == "members":
                path = "/api/members"
            elif op == "revoke":
                method, path = "DELETE", f"/api/members/{action.member_id}"
            elif op == "logout":
                method, path, expected = "POST", "/api/logout", 200
            status = None
            try:
                status, data, text = self.request(actor, method, path, body)
                violation = expected in {401, 403, 404} and 200 <= status < 300
                valid = status == expected
                reason = "status_matches_policy" if valid else "unexpected_status"
                if valid and status < 300:
                    if op == "me":
                        valid = data == {
                            "user_id": uid,
                            "username": actor,
                            "tenant_id": tenant,
                            "role": role,
                        }
                    elif op == "list":
                        violation = any(r.get("tenant_id") != tenant for r in data.get("items", []))
                        matching = sorted(
                            i
                            for i, v in self.invoices.items()
                            if v[0] == tenant
                            and action.query.lower() in v[1].lower()
                            and (not action.status or v[2] == action.status)
                        )
                        start = (action.page - 1) * action.page_size
                        valid = (
                            data["total"] == len(matching)
                            and [r["id"] for r in data["items"]]
                            == matching[start : start + action.page_size]
                            and all(r["tenant_id"] == tenant for r in data["items"])
                        )
                    elif op in {"read", "update", "create"}:
                        violation = data.get("tenant_id") != tenant
                        valid = (
                            data["tenant_id"] == tenant
                            and isinstance(data["items"], list)
                            and bool(data["items"])
                            and data["total_cents"]
                            == sum(i["quantity"] * i["unit_price_cents"] for i in data["items"])
                        )
                        if op == "create":
                            valid = (
                                valid
                                and type(data["id"]) is int
                                and data["id"] not in self.invoices
                                and data["customer"] == action.customer
                                and data["total_cents"] == 2500
                            )
                            if valid:
                                created_id = data["id"]
                                self.invoices[data["id"]] = (tenant, action.customer, "draft")
                        else:
                            valid = (
                                valid
                                and data["id"] == invoice_id
                                and data["customer"] == invoice[1]
                            )
                            if op == "update" and valid:
                                valid = data["status"] == action.status
                                if valid:
                                    self.invoices[invoice_id] = (
                                        tenant,
                                        invoice[1],
                                        action.status,
                                    )
                    elif op == "export":
                        valid = (
                            type(data["id"]) is int and data["id"] > 0 and data["status"] == "ready"
                        )
                        if valid:
                            exports[action.export_slot] = (
                                data["id"],
                                actor,
                                list(invoice_ids),
                                {i: self.invoices[i][2] for i in invoice_ids},
                            )
                    elif op == "download":
                        rows = list(csv.DictReader(io.StringIO(text)))
                        valid = (
                            list(rows[0]) == ["id", "customer", "status", "total_cents", "currency"]
                            and [int(r["id"]) for r in rows] == export[2]
                        )
                        for row in rows:
                            expected_customer = self.invoices[int(row["id"])][1]
                            if expected_customer.lstrip().startswith(("=", "+", "-", "@")):
                                expected_customer = "'" + expected_customer
                            valid = valid and row["customer"] == expected_customer
                            valid = valid and row["status"] == export[3][int(row["id"])]
                            violation |= row["customer"].lstrip().startswith(("=", "+", "-", "@"))
                    elif op == "members":
                        valid = {r["user_id"] for r in data["items"]} == {
                            v[0] for v in MEMBERS.values() if v[1] == tenant
                        }
                    elif op == "revoke":
                        valid = data == {"revoked": True}
                        if valid:
                            self.revoked.add(action.member_id)
                    elif op == "logout":
                        self.logged_out.add(actor)
                    if not valid:
                        reason = "response_violates_policy"
                if valid and status >= 400:
                    valid = isinstance(data, dict) and set(data) <= {"detail"}
                outcomes.append(
                    {
                        "step": index,
                        "expected_status": expected,
                        "observed_status": status,
                        "passed": bool(valid),
                        "reason": reason,
                        "response_sha256": sha(text),
                        "security_violation": bool(violation),
                        "request": {"actor": actor, "method": method, "path": path, "body": body},
                        "observed_excerpt": text[:1500] if not valid else None,
                    }
                )
            except Exception:
                outcomes.append(
                    {
                        "step": index,
                        "expected_status": expected,
                        "observed_status": status,
                        "passed": False,
                        "reason": "request_or_response_incomplete",
                    }
                )
        return {
            "test_id": case.id,
            "category": category(case),
            "family": case.family,
            "passed": all(o["passed"] for o in outcomes),
            "security_violation": any(o.get("security_violation", False) for o in outcomes),
            "steps": outcomes,
        }


def execute(base, cases):
    oracle = Oracle(base)
    deadline = time.monotonic() + 30
    while True:
        try:
            if oracle.request("anonymous", "GET", "/health")[0] == 200:
                break
        except OSError:
            pass
        if time.monotonic() >= deadline:
            raise TimeoutError("Target readiness timeout")
        time.sleep(0.2)
    oracle.login()
    return [oracle.run(Case.model_validate(case)) for case in cases]


if __name__ == "__main__":
    from pathlib import Path

    job = json.loads(Path("/opt/job/job.json").read_text())
    results = []
    for target in job["targets"]:
        tests = execute(target["url"], job["cases"])
        results.append({**target, "tests": tests})
    receipt = {
        "job_id": job["job_id"],
        "nonce": job["nonce"],
        "suite_sha256": sha(job["cases"]),
        "results": results,
    }
    # Provider log scanners bound each line. Frame the receipt without weakening
    # integrity checks; the collector requires every chunk and its payload hash.
    payload = json.dumps(receipt, separators=(",", ":")).encode()
    encoded = base64.b64encode(payload).decode()
    pieces = [encoded[i : i + 6000] for i in range(0, len(encoded), 6000)]
    print(
        "PROOFLOOP_RECEIPT_BEGIN="
        + json.dumps({"chunks": len(pieces), "sha256": hashlib.sha256(payload).hexdigest()}),
        flush=True,
    )
    for index, piece in enumerate(pieces):
        print(f"PROOFLOOP_RECEIPT_CHUNK={index}:{piece}", flush=True)
    print("PROOFLOOP_RECEIPT_END=complete", flush=True)
    if os.environ.get("PROOFLOOP_CLOUD") == "1":
        from http.server import BaseHTTPRequestHandler, HTTPServer

        class Health(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200 if self.path == "/health" else 404)
                self.end_headers()
                self.wfile.write(b"ok" if self.path == "/health" else b"not found")

            def log_message(self, *_):
                pass

        HTTPServer(("0.0.0.0", 8080), Health).serve_forever()
