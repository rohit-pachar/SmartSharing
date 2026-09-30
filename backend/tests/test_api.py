from app.services import transfers as T
from app.services.market import create_asset, purchase, AlreadyOwned
from app.services.users import create_user
from app.services.wallet import InsufficientFunds
import pytest


def reg(client, name, email):
    r = client.post("/api/auth/register", json={"full_name": name, "email": email, "password": "supersecret1"})
    assert r.status_code == 201, r.text
    return r.json()


def H(tok):
    return {"Authorization": f"Bearer {tok['access_token']}"}


def integrity(client):
    r = client.get("/api/admin/integrity", headers={"x-admin-token": "test-admin"}).json()
    assert r["conserved"] and r["pending_matches"] and r["negative_wallets"] == 0, r
    return r


def test_full_flow(client, d):
    a = reg(client, "Priya Sharma", "priya@example.com")
    b = reg(client, "Liam Carter", "liam@example.com")
    assert client.post("/api/auth/login", json={"email": "priya@example.com", "password": "nope-nope"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "priya@example.com", "password": "supersecret1"}).status_code == 200

    # fund via admin
    assert client.post("/api/admin/grant", json={"handle": a["user"]["handle"], "amount": 1000}).status_code == 403
    r = client.post("/api/admin/grant", json={"handle": a["user"]["handle"], "amount": 1000},
                    headers={"x-admin-token": "test-admin"})
    assert r.json()["balance"] == 1000

    # two-phase transfer
    r = client.post("/api/transfers", json={"to": b["user"]["handle"], "amount": 300, "memo": "hi"}, headers=H(a))
    assert r.status_code == 201, r.text
    tid = r.json()["id"]
    w = client.get("/api/wallet", headers=H(a)).json()
    assert (w["balance"], w["pending_out"]) == (700, 300)
    assert client.get("/api/wallet", headers=H(b)).json()["balance"] == 0
    integrity(client)
    # sender cannot accept own transfer
    assert client.post(f"/api/transfers/{tid}/accept", headers=H(a)).status_code == 404
    assert client.post(f"/api/transfers/{tid}/accept", headers=H(b)).status_code == 200
    assert client.post(f"/api/transfers/{tid}/accept", headers=H(b)).status_code == 404  # no double accept
    assert client.get("/api/wallet", headers=H(b)).json()["balance"] == 300
    w = client.get("/api/wallet", headers=H(a)).json()
    assert (w["balance"], w["pending_out"]) == (700, 0)

    # overspend blocked
    r = client.post("/api/transfers", json={"to": b["user"]["handle"], "amount": 701}, headers=H(a))
    assert r.status_code == 400 and r.json()["detail"]["code"] == "insufficient_funds"

    # reject refunds
    tid = client.post("/api/transfers", json={"to": b["user"]["handle"], "amount": 100}, headers=H(a)).json()["id"]
    client.post(f"/api/transfers/{tid}/reject", headers=H(b))
    assert client.get("/api/wallet", headers=H(a)).json()["balance"] == 700

    # idempotency
    body = {"to": b["user"]["handle"], "amount": 50, "idempotency_key": "k1"}
    t1 = client.post("/api/transfers", json=body, headers=H(a)).json()
    t2 = client.post("/api/transfers", json=body, headers=H(a)).json()
    assert t1["id"] == t2["id"]
    client.post(f"/api/transfers/{t1['id']}/cancel", headers=H(a))

    # marketplace: b lists, a buys
    r = client.post("/api/assets", headers=H(b), json={"name": "Test LUT Pack", "category": "Motion & video",
                                                       "description": "Ten lovely LUTs for testing", "price": 200})
    assert r.status_code == 201, r.text
    aid = r.json()["id"]
    assert [o["id"] for o in r.json()["license_options"]] == ["personal", "commercial", "studio"]
    r = client.post("/api/orders", json={"asset_id": aid, "license_id": "commercial"}, headers=H(a))
    assert r.status_code == 201, r.text
    o = r.json()
    assert (o["price"], o["creator_amount"], o["platform_fee"]) == (400, 352, 48)
    assert client.get("/api/wallet", headers=H(a)).json()["balance"] == 300
    assert client.get("/api/wallet", headers=H(b)).json()["balance"] == 652
    assert client.post("/api/orders", json={"asset_id": aid, "license_id": "commercial"}, headers=H(a)).status_code == 409
    assert client.post("/api/orders", json={"asset_id": aid, "license_id": "personal"}, headers=H(b)).status_code == 400
    assert client.post("/api/orders", json={"asset_id": aid, "license_id": "studio"}, headers=H(a)).status_code == 400

    assert client.get("/api/assets", params={"q": "lut"}).json()["total"] == 1
    assert client.get("/api/activity").json()["items"][0]["type"] == "purchase"
    assert len(client.get("/api/wallet/ledger", headers=H(a)).json()["items"]) >= 5
    integrity(client)


def test_expiry_and_concurrency(d, client):
    from datetime import timedelta
    from concurrent.futures import ThreadPoolExecutor
    from app.util import now_utc
    from app.services.wallet import grant

    x = create_user(d, full_name="Kavya Iyer", email=None, password_hash=None, is_demo=True, opening_credits=500)
    y = create_user(d, full_name="Hana Takahashi", email=None, password_hash=None, is_demo=True, opening_credits=0)
    t = T.create_transfer(d, x["_id"], y["_id"], 100)
    assert t["is_demo"]
    assert T.expire_stale(d, now=now_utc() + timedelta(days=10)) == 1
    assert d.wallets.find_one({"_id": x["_id"]})["balance"] == 500

    # 20 concurrent 50-credit sends from a 500 balance -> exactly 10 succeed, never negative
    def send(_):
        try:
            T.create_transfer(d, x["_id"], y["_id"], 50)
            return 1
        except InsufficientFunds:
            return 0
    with ThreadPoolExecutor(8) as ex:
        assert sum(ex.map(send, range(20))) == 10
    w = d.wallets.find_one({"_id": x["_id"]})
    assert (w["balance"], w["pending_out"]) == (0, 500)
    integrity(client)
