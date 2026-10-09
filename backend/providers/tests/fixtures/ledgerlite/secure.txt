"""Separate reference implementation; never replaces the vulnerable original."""

from fastapi import FastAPI, Header, HTTPException

from demo_target.ledgerlite.data import INVOICES, USERS


def create_app() -> FastAPI:
    app = FastAPI(title="LedgerLite — SYNTHETIC SECURE REFERENCE")

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
        user = USERS[x_synthetic_identity]
        if user["role"] != "administrator" and record["owner_id"] != x_synthetic_identity:
            raise HTTPException(status_code=403, detail="Invoice access denied")
        return {"id": invoice_id, **record, "source": "fixture"}

    return app


app = create_app()
