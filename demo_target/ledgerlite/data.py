"""Synthetic records, shared by the original and separate secure reference."""

USERS = {
    "alice": {"name": "Alice", "role": "user"},
    "bob": {"name": "Bob", "role": "user"},
    "administrator": {"name": "Administrator", "role": "administrator"},
}
INVOICES = {
    "inv-1001": {"owner_id": "alice", "amount_cents": 12500, "currency": "USD", "status": "open"},
    "inv-2047": {"owner_id": "bob", "amount_cents": 48750, "currency": "USD", "status": "paid"},
    "inv-7319": {"owner_id": "alice", "amount_cents": 9900, "currency": "USD", "status": "paid"},
    "inv-8523": {"owner_id": "bob", "amount_cents": 30100, "currency": "USD", "status": "open"},
    "inv-9013": {"owner_id": "alice", "amount_cents": 100, "currency": "USD", "status": "open"},
    "inv-9907": {"owner_id": "bob", "amount_cents": 725, "currency": "USD", "status": "paid"},
}
