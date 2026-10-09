"""Frozen desired behavior. The original MUST fail cross-account cases.

No imports of target data/policies: a target patch cannot change this oracle.
"""

import pytest

ACCOUNTS = ("alice", "bob", "administrator")
RECORDS = (
    ("inv-1001", "alice", 12500, "open"),
    ("inv-2047", "bob", 48750, "paid"),
    ("inv-7319", "alice", 9900, "paid"),
    ("inv-8523", "bob", 30100, "open"),
    ("inv-9013", "alice", 100, "open"),
    ("inv-9907", "bob", 725, "paid"),
)
RECORD_IDS = [record[0] for record in RECORDS]


def headers(identity):
    return {"X-Synthetic-Identity": identity}


def expected_record(record):
    invoice_id, owner, amount, status = record
    return {
        "id": invoice_id,
        "owner_id": owner,
        "amount_cents": amount,
        "currency": "USD",
        "status": status,
        "source": "fixture",
    }


@pytest.mark.parametrize("record", RECORDS, ids=RECORD_IDS)
def test_owner_access(client, record):
    response = client.get(f"/invoices/{record[0]}", headers=headers(record[1]))
    assert response.status_code == 200
    assert response.json() == expected_record(record)


@pytest.mark.parametrize("record", RECORDS, ids=RECORD_IDS)
def test_cross_account_denied(client, record):
    identity = "bob" if record[1] == "alice" else "alice"
    response = client.get(f"/invoices/{record[0]}", headers=headers(identity))
    assert response.status_code == 403, (
        f"BOLA: {identity} accessing {record[0]} owned by {record[1]}: "
        f"expected 403, observed {response.status_code}; body={response.json()}"
    )
    assert response.json() == {"detail": "Invoice access denied"}


@pytest.mark.parametrize("record", RECORDS, ids=RECORD_IDS)
def test_administrator_access(client, record):
    response = client.get(f"/invoices/{record[0]}", headers=headers("administrator"))
    assert response.status_code == 200
    assert response.json() == expected_record(record)


@pytest.mark.parametrize("identity", ACCOUNTS)
@pytest.mark.parametrize("invoice_id", ("inv-missing", "inv-0000", "inv-1002"))
def test_nonexistent_invoice(client, identity, invoice_id):
    response = client.get(f"/invoices/{invoice_id}", headers=headers(identity))
    assert response.status_code == 404
    assert response.json() == {"detail": "Invoice not found"}


# Embedded whitespace survives HTTP header normalization; trailing OWS does not.
@pytest.mark.parametrize("identity", (None, "", "mallory", "Administrator", "alice bob"))
@pytest.mark.parametrize("invoice_id", ("inv-1001", "inv-2047", "inv-missing"))
def test_invalid_identity(client, identity, invoice_id):
    response = client.get(
        f"/invoices/{invoice_id}", headers={} if identity is None else headers(identity)
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Synthetic identity required"}


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "ledgerlite", "source": "fixture"}


def test_access_sequence_preserves_functionality(client):
    # A denial must not poison later authorized requests or alter invoice content.
    for identity, invoice_id, status in (
        ("alice", "inv-2047", 403),
        ("bob", "inv-2047", 200),
        ("administrator", "inv-2047", 200),
        ("alice", "inv-1001", 200),
        ("bob", "inv-1001", 403),
        ("alice", "inv-1001", 200),
    ):
        response = client.get(f"/invoices/{invoice_id}", headers=headers(identity))
        assert response.status_code == status
        if status == 200:
            record = next(record for record in RECORDS if record[0] == invoice_id)
            assert response.json() == expected_record(record)
        else:
            assert response.json() == {"detail": "Invoice access denied"}
