# LedgerLite — authorized synthetic demonstration fixture

**Deliberately vulnerable; isolated demonstration only.** No real people, invoices,
money, payments, credentials, or external targets. All returned records retain
`source: fixture`. Observations from actually executed tests use `source: execution`
and explicitly label their data as synthetic.

```text
demo_target/
  __init__.py
  ledgerlite/
    __init__.py
    app.py                 # immutable vulnerable original; sole candidate patch path
    data.py                # immutable synthetic users and six nonconsecutive invoices
    reference_secure.py    # separate secure reference, never substituted for original
```

Alice (`alice`) and Bob (`bob`) own three invoices each. Administrator
(`administrator`) can read every invoice. `X-Synthetic-Identity` selects the
synthetic identity; it is intentionally NOT authentication. Missing, empty, unknown,
or differently cased selectors reaching the application return 401. Identity is
checked before invoice existence; authenticated requests for unknown IDs return 404. Correct behavior is
200 for owners and Administrator, 403 for other users, with no invoice disclosed.

Routes:

- `GET /health`: 200, `{status: "ok", service: "ledgerlite", source: "fixture"}`.
- `GET /invoices/{invoice_id}`: JSON `id`, `owner_id`, integer `amount_cents`,
  `currency` (`USD`), `status` (`open`/`paid`), and `source` (`fixture`).
- Errors: FastAPI JSON `{"detail": "Synthetic identity required"}`, `{"detail":
  "Invoice not found"}`, or (secure reference) `{"detail": "Invoice access denied"}`.

The original validates identity and invoice existence but **deliberately omits
object ownership authorization**. Alice requesting `inv-2047` receives Bob's
48,750-cent paid invoice with HTTP 200. The reference inserts a role/owner check and
returns 403 for the same request. Neither app writes data; integer cents avoid
floating-point amounts. Factory interface: `create_app() -> FastAPI`; each file
also exports `app` for uvicorn.

From the repository root with the root locked dependencies installed:

```sh
python -m uvicorn demo_target.ledgerlite.app:app --host 127.0.0.1 --port 8010
# Separate secure reference (use instead of the command above):
python -m uvicorn demo_target.ledgerlite.reference_secure:app --host 127.0.0.1 --port 8011
```

HTTP servers may strip optional leading/trailing header whitespace before the
application sees it. Thus `alice ` may arrive as valid `alice`; the fixture does
not promise rejection of whitespace removed by transport. The frozen v2 suite
uses the transport-stable invalid selector `alice bob`, whose embedded space
survives normalization and is rejected with 401.

Do not expose this fixture remotely. Prefer the in-process trusted test suite; it
uses no network server. The original hashes are pinned in
`verifier_tests/manifest.json`. Preserve that original and patch a disposable copy
of `demo_target/ledgerlite/app.py` only. See the verifier handoff in
`verifier_tests/README.md` for exact execution and trust requirements.
