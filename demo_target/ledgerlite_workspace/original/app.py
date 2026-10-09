import csv
import hashlib
import hmac
import io
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from typing import Optional

from fastapi import Cookie, Depends, FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field, constr

DB_PATH = os.environ.get("LEDGERLITE_DB", "/tmp/ledgerlite.sqlite3")
SESSION_SECONDS = 3600
app = FastAPI()


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def password_hash(password: str, salt: Optional[bytes] = None) -> tuple[bytes, bytes]:
    salt = salt or secrets.token_bytes(16)
    return salt, hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)


def initialize():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS tenants(id INTEGER PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, tenant_id INTEGER NOT NULL REFERENCES tenants(id),
            role TEXT NOT NULL CHECK(role IN ('owner','analyst','viewer')), active INTEGER NOT NULL DEFAULT 1,
            salt BLOB NOT NULL, password_hash BLOB NOT NULL);
        CREATE TABLE IF NOT EXISTS invoices(
            id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL REFERENCES tenants(id),
            customer TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('draft','sent','paid')),
            currency TEXT NOT NULL, total_cents INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS invoice_items(
            id INTEGER PRIMARY KEY AUTOINCREMENT, invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
            description TEXT NOT NULL, quantity INTEGER NOT NULL, unit_price_cents INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(
            token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            expires_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS exports(
            id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL REFERENCES tenants(id),
            user_id INTEGER NOT NULL REFERENCES users(id), created_at TEXT NOT NULL, snapshot TEXT NOT NULL);
        """)
        c.execute("INSERT OR IGNORE INTO tenants(id,name) VALUES(1,'Northstar Studio'),(2,'Harbor Labs')")
        seeds = [(1,'alice',1,'owner'),(2,'amy',1,'analyst'),(3,'ava',1,'viewer'),
                 (4,'bob',2,'owner'),(5,'ben',2,'analyst'),(6,'bea',2,'viewer')]
        for uid, username, tenant, role in seeds:
            salt, hashed = password_hash('demo-' + username)
            c.execute("INSERT OR IGNORE INTO users(id,username,tenant_id,role,active,salt,password_hash) VALUES(?,?,?,?,1,?,?)",
                      (uid, username, tenant, role, salt, hashed))
        invoice_seeds = [
            (101,1,'Acme','draft',[('Design services',2,12500)]),
            (102,1,'Atlas','sent',[('Consulting',3,8000)]),
            (103,1,'Aurora','paid',[('Hosting',1,25000)]),
            (201,2,'Beacon','draft',[('Research',2,18000)]),
            (202,2,'Birch','sent',[('Development',4,9500)]),
            (203,2,'Bluebird','paid',[('Support',2,6000)]),
        ]
        for iid, tenant, customer, status, items in invoice_seeds:
            exists = c.execute("SELECT 1 FROM invoices WHERE id=?", (iid,)).fetchone()
            if not exists:
                total = sum(q * price for _, q, price in items)
                c.execute("INSERT INTO invoices(id,tenant_id,customer,status,currency,total_cents) VALUES(?,?,?,?,?,?)",
                          (iid,tenant,customer,status,'USD',total))
                c.executemany("INSERT INTO invoice_items(invoice_id,description,quantity,unit_price_cents) VALUES(?,?,?,?)",
                              [(iid, d, q, p) for d,q,p in items])


@app.on_event("startup")
def startup():
    initialize()


def fail(status: int, detail: str):
    raise HTTPException(status_code=status, detail=detail)


def current_user(ledger_session: Optional[str] = Cookie(default=None)):
    if not ledger_session:
        fail(401, "Authentication required")
    token_hash = hashlib.sha256(ledger_session.encode()).hexdigest()
    now = int(time.time())
    with db() as c:
        row = c.execute("""SELECT u.id AS user_id,u.username,u.tenant_id,u.role,u.active,s.expires_at
                           FROM sessions s JOIN users u ON u.id=s.user_id
                           WHERE s.token_hash=?""", (token_hash,)).fetchone()
        if not row or row['expires_at'] <= now or not row['active']:
            if row:
                c.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash,))
            fail(401, "Authentication required")
        return dict(row)


def authorize(user, roles=None):
    # Membership is deliberately re-read from persistent state on every request.
    with db() as c:
        row = c.execute("SELECT id,username,tenant_id,role,active FROM users WHERE id=?", (user['user_id'],)).fetchone()
    if not row or not row['active']:
        fail(401, "Authentication required")
    u = dict(row)
    if roles and u['role'] not in roles:
        fail(403, "Insufficient role")
    return u


def invoice_dict(c, row, include_items=True):
    out = {"id": row['id'], "customer": row['customer'], "status": row['status'],
           "currency": row['currency'], "total_cents": row['total_cents']}
    if 'tenant_id' in row.keys():
        out['tenant_id'] = row['tenant_id']
    if include_items:
        items = c.execute("SELECT description,quantity,unit_price_cents FROM invoice_items WHERE invoice_id=? ORDER BY id", (row['id'],)).fetchall()
        out['items'] = [dict(x) for x in items]
    return out


@app.get("/health")
def health():
    return {"status": "ok"}


class LoginBody(BaseModel):
    username: constr(min_length=1, max_length=80)
    password: constr(min_length=1, max_length=200)


@app.post("/api/login")
def login(body: LoginBody, response: Response):
    with db() as c:
        row = c.execute("SELECT id,username,tenant_id,role,active,salt,password_hash FROM users WHERE username=?", (body.username,)).fetchone()
        if not row or not row['active']:
            fail(401, "Invalid credentials")
        candidate = hashlib.pbkdf2_hmac("sha256", body.password.encode(), row['salt'], 200_000)
        if not hmac.compare_digest(candidate, row['password_hash']):
            fail(401, "Invalid credentials")
        token = secrets.token_urlsafe(32)
        digest = hashlib.sha256(token.encode()).hexdigest()
        c.execute("INSERT INTO sessions(token_hash,user_id,expires_at) VALUES(?,?,?)",
                  (digest,row['id'],int(time.time())+SESSION_SECONDS))
        response.set_cookie("ledger_session", token, httponly=True, samesite="strict", secure=False,
                            max_age=SESSION_SECONDS, path="/")
        return {"user_id":row['id'],"username":row['username'],"tenant_id":row['tenant_id'],"role":row['role']}


@app.post("/api/logout")
def logout(response: Response, ledger_session: Optional[str] = Cookie(default=None)):
    if ledger_session:
        with db() as c:
            c.execute("DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(ledger_session.encode()).hexdigest(),))
    response.delete_cookie("ledger_session", path="/", httponly=True, samesite="strict")
    return {"status":"ok"}


@app.get("/api/me")
def me(user=Depends(current_user)):
    u = authorize(user)
    return {"user_id":u['id'],"username":u['username'],"tenant_id":u['tenant_id'],"role":u['role']}


@app.get("/api/invoices")
def list_invoices(q: constr(max_length=120) = "", status: Optional[str] = None,
                 page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=50),
                 user=Depends(current_user)):
    u = authorize(user)
    if status is not None and status not in ('draft','sent','paid'):
        fail(422, "Invalid status")
    clauses = ["tenant_id=?"]
    args = [u['tenant_id']]
    if q:
        clauses.append("customer LIKE ? ESCAPE '\\'")
        escaped = q.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
        args.append('%' + escaped + '%')
    if status:
        clauses.append("status=?")
        args.append(status)
    where = " AND ".join(clauses)
    with db() as c:
        total = c.execute("SELECT COUNT(*) FROM invoices WHERE " + where, args).fetchone()[0]
        rows = c.execute("SELECT * FROM invoices WHERE " + where + " ORDER BY id LIMIT ? OFFSET ?",
                         args + [page_size,(page-1)*page_size]).fetchall()
        return {"items":[invoice_dict(c, r, False) for r in rows],"total":total,"page":page}


@app.get("/api/invoices/{invoice_id}")
def get_invoice(invoice_id: int, user=Depends(current_user)):
    u = authorize(user)
    with db() as c:
        row = c.execute("SELECT * FROM invoices WHERE id=? AND tenant_id=?", (invoice_id,u['tenant_id'])).fetchone()
        if not row:
            fail(404, "Invoice not found")
        return invoice_dict(c,row,True)


class InvoiceItem(BaseModel):
    description: constr(min_length=1, max_length=200)
    quantity: int = Field(..., ge=1, le=1_000_000)
    unit_price_cents: int = Field(..., ge=0, le=2_000_000_000)


class InvoiceCreate(BaseModel):
    customer: constr(min_length=1, max_length=200)
    currency: constr(min_length=3, max_length=3) = "USD"
    items: list[InvoiceItem] = Field(..., min_items=1, max_items=30)


@app.post("/api/invoices", status_code=201)
def create_invoice(body: InvoiceCreate, user=Depends(current_user)):
    u = authorize(user, ('owner','analyst'))
    if not body.currency.isalpha() or not body.currency.isupper():
        fail(422, "Invalid currency")
    total = sum(x.quantity*x.unit_price_cents for x in body.items)
    if total > 9_000_000_000_000_000:
        fail(422, "Invoice total too large")
    with db() as c:
        cur = c.execute("INSERT INTO invoices(tenant_id,customer,status,currency,total_cents) VALUES(?,?,'draft',?,?)",
                        (u['tenant_id'],body.customer,body.currency,total))
        iid = cur.lastrowid
        c.executemany("INSERT INTO invoice_items(invoice_id,description,quantity,unit_price_cents) VALUES(?,?,?,?)",
                      [(iid,x.description,x.quantity,x.unit_price_cents) for x in body.items])
        row = c.execute("SELECT * FROM invoices WHERE id=?", (iid,)).fetchone()
        return invoice_dict(c,row,True)


class StatusBody(BaseModel):
    status: str


@app.patch("/api/invoices/{invoice_id}")
def update_invoice(invoice_id: int, body: StatusBody, user=Depends(current_user)):
    u = authorize(user, ('owner','analyst'))
    if body.status not in ('draft','sent','paid'):
        fail(422, "Invalid status")
    with db() as c:
        row = c.execute("SELECT * FROM invoices WHERE id=? AND tenant_id=?", (invoice_id,u['tenant_id'])).fetchone()
        if not row:
            fail(404, "Invoice not found")
        c.execute("UPDATE invoices SET status=? WHERE id=? AND tenant_id=?", (body.status,invoice_id,u['tenant_id']))
        row = c.execute("SELECT * FROM invoices WHERE id=? AND tenant_id=?", (invoice_id,u['tenant_id'])).fetchone()
        return invoice_dict(c,row,True)


def csv_safe(value):
    text = str(value)
    if text.lstrip().startswith(('=','+','-','@','\t','\r')):
        return "'" + text
    return text


class ExportBody(BaseModel):
    invoice_ids: list[int] = Field(..., min_items=1, max_items=30)


def csv_snapshot(rows):
    buf = io.StringIO(newline='')
    writer = csv.writer(buf, lineterminator='\r\n')
    writer.writerow(['id','customer','status','total_cents','currency'])
    for row in rows:
        writer.writerow([row['id'],csv_safe(row['customer']),csv_safe(row['status']),row['total_cents'],csv_safe(row['currency'])])
    return buf.getvalue()


@app.post("/api/exports", status_code=201)
def create_export(body: ExportBody, user=Depends(current_user)):
    u = authorize(user, ('owner','analyst'))
    ids = body.invoice_ids
    if len(set(ids)) != len(ids):
        fail(422, "Invoice IDs must be unique")
    placeholders = ','.join('?' for _ in ids)
    with db() as c:
        rows = c.execute(f"SELECT id,customer,status,total_cents,currency FROM invoices WHERE tenant_id=? AND id IN ({placeholders})",
                          [u['tenant_id']] + ids).fetchall()
        if len(rows) != len(ids):
            fail(404, "Invoice not found")
        by_id = {r['id']:r for r in rows}
        ordered = [by_id[i] for i in ids]
        snapshot = csv_snapshot(ordered)
        created = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        cur = c.execute("INSERT INTO exports(tenant_id,user_id,created_at,snapshot) VALUES(?,?,?,?)",
                        (u['tenant_id'],u['id'],created,snapshot))
        return {"id":cur.lastrowid,"status":"ready"}


@app.get("/api/exports")
def list_exports(user=Depends(current_user)):
    u = authorize(user, ('owner','analyst'))
    with db() as c:
        rows = c.execute("SELECT id,created_at,snapshot FROM exports WHERE tenant_id=? AND user_id=? ORDER BY id DESC",
                          (u['tenant_id'],u['id'])).fetchall()
        items=[]
        for r in rows:
            count = max(0, len(r['snapshot'].splitlines())-1)
            items.append({"id":r['id'],"status":"ready","invoice_count":count,"created_at":r['created_at']})
        return {"items":items}


@app.get("/api/exports/{export_id}/download")
def download_export(export_id: int, user=Depends(current_user)):
    u = authorize(user, ('owner','analyst'))
    with db() as c:
        row = c.execute("SELECT snapshot FROM exports WHERE id=? AND tenant_id=? AND user_id=?",
                         (export_id,u['tenant_id'],u['id'])).fetchone()
        if not row:
            fail(404, "Export not found")
        content = row['snapshot']
    return StreamingResponse(iter([content]), media_type='text/csv',
                             headers={"Content-Disposition":f'attachment; filename="export-{export_id}.csv"'})


@app.get("/api/members")
def members(user=Depends(current_user)):
    u = authorize(user, ('owner',))
    with db() as c:
        rows = c.execute("SELECT id,username,role,active FROM users WHERE tenant_id=? ORDER BY id", (u['tenant_id'],)).fetchall()
        return {"items":[{"user_id":r['id'],"username":r['username'],"role":r['role'],"active":bool(r['active'])} for r in rows]}


@app.delete("/api/members/{user_id}")
def revoke_member(user_id: int, user=Depends(current_user)):
    u = authorize(user, ('owner',))
    if user_id == u['id']:
        fail(400, "Cannot revoke yourself")
    with db() as c:
        target = c.execute("SELECT id FROM users WHERE id=? AND tenant_id=?", (user_id,u['tenant_id'])).fetchone()
        if not target:
            fail(404, "Member not found")
        c.execute("UPDATE users SET active=0 WHERE id=? AND tenant_id=?", (user_id,u['tenant_id']))
        c.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
    return {"revoked":True}


@app.get("/")
def index():
    path = "/opt/ui/index.html"
    if os.path.isfile(path):
        return FileResponse(path, media_type="text/html")
    raise HTTPException(status_code=404, detail="Not found")
