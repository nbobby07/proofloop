"""DELIBERATELY VULNERABLE ORIGINAL. Never expose outside an isolated demo.

BOLA: GET /invoices/{invoice_id} validates identity but omits the ownership
check. Alice can retrieve Bob's invoice. This omission is the patch target.
X-Synthetic-Identity is a demo selector, NOT authentication.
"""

from fastapi import FastAPI, Header, HTTPException

from demo_target.ledgerlite.data import INVOICES, USERS


def create_app() -> FastAPI:
    app = FastAPI(title="LedgerLite — SYNTHETIC VULNERABLE FIXTURE")

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "ledgerlite", "source": "fixture"}

    @app.get("/invoices/{invoice_id}")
    def invoice(invoice_id: str, x_synthetic_identity: str | None = Header(default=None)):
        if x_synthetic_identity not in USERS:
            raise HTTPException(status_code=401, detail="Synthetic identity required")
        record = INVOICES.get(invoice_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Invoice not found")
        # INTENTIONAL BOLA: authenticated synthetic users can access any owner's invoice.
        return {"id": invoice_id, **record, "source": "fixture"}

    return app


app = create_app()
