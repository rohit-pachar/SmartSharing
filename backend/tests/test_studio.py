"""Creator tools: discounts, affiliates, licence keys, files/downloads, API keys, integrations, analytics."""
import hashlib
import hmac
import io
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from app.services import hooks
from app.services.users import create_user
from app.services.wallet import grant


def reg(client, name, email):
    r = client.post("/api/auth/register", json={"full_name": name, "email": email, "password": "supersecret1"})
    assert r.status_code == 201, r.text
    return r.json()


def H(t):
    return {"Authorization": f"Bearer {t['access_token'] if isinstance(t, dict) else t}"}


def test_creator_flow(client, d):
    c = reg(client, "Ananya Iyer", "ananya@example.com")
    b = reg(client, "Rahul Verma", "rahul@example.com")
    aff = reg(client, "Kabir Shah", "kabir@example.com")
    grant(d, b["user"]["id"], 5000)

    # listing starts as draft (no files) and can't be published empty
    a = client.post("/api/assets", headers=H(c), json={"name": "Wedding LUTs", "category": "Motion & video",
                                                      "description": "Warm grades for wedding films", "price": 400}).json()
    assert a["status"] == "draft"
    assert client.patch(f"/api/studio/assets/{a['id']}", headers=H(c), json={"status": "published"}).status_code == 400
    assert client.get(f"/api/assets/{a['id']}").status_code == 404  # drafts are private

    # upload a file, then publish with affiliate 25%
    r = client.post(f"/api/studio/assets/{a['id']}/files", headers=H(c), files={"file": ("grades.zip", io.BytesIO(b"PK\x03\x04demo"), "application/zip")})
    assert r.status_code == 201, r.text
    bad = client.post(f"/api/studio/assets/{a['id']}/files", headers=H(c), files={"file": ("x.exe", io.BytesIO(b"MZ"), "application/octet-stream")})
    assert bad.status_code == 400
    r = client.patch(f"/api/studio/assets/{a['id']}", headers=H(c), json={"status": "published", "affiliate_pct": 25})
    assert r.status_code == 200 and r.json()["status"] == "published"
    pub = client.get(f"/api/assets/{a['id']}").json()
    assert pub["file_count"] == 1 and "files" not in pub  # no storage paths leak

    # discount code
    assert client.post("/api/studio/discounts", headers=H(c), json={"code": "launch20", "pct_off": 20, "max_uses": 1}).status_code == 201
    chk = client.get("/api/discounts/check", params={"asset_id": a["id"], "code": "LAUNCH20"}).json()
    assert chk["valid"] and chk["options"][0]["discounted"] == 320
    assert client.get("/api/discounts/check", params={"asset_id": a["id"], "code": "NOPE"}).json()["valid"] is False

    # API key can read studio but cannot buy
    k = client.post("/api/studio/api-keys", headers=H(c), json={"name": "ci"}).json()["key"]
    assert client.get("/api/studio/overview", headers=H(k)).status_code == 200
    assert client.post("/api/orders", headers=H(k), json={"asset_id": a["id"], "license_id": "personal"}).status_code == 403
    assert client.post("/api/studio/api-keys", headers=H(k), json={"name": "x"}).status_code == 403

    # purchase with discount + affiliate ref
    r = client.post("/api/orders", headers=H(b), json={"asset_id": a["id"], "license_id": "personal", "discount_code": "launch20",
                                                     "ref": aff["user"]["handle"]})
    assert r.status_code == 201, r.text
    o = r.json()
    # 320 paid; fee 38; creator share 282 -> affiliate 25% = 70 -> creator 212
    assert (o["price"], o["platform_fee"], o["affiliate_amount"], o["creator_amount"]) == (320, 38, 70, 212)
    assert len(o["license_key"]) == 23
    assert d.ledger.find_one({"user_id": aff["user"]["id"], "kind": "affiliate_commission"})["amount"] == 70
    # code is now used up
    assert client.get("/api/discounts/check", params={"asset_id": a["id"], "code": "LAUNCH20"}).json()["valid"] is False

    # licence verify (public, Gumroad-shaped)
    v = client.post("/api/licenses/verify", json={"asset_id": a["id"], "license_key": o["license_key"]}).json()
    assert v["success"] and v["uses"] == 1 and v["purchase"]["license_id"] == "personal"
    assert client.post("/api/licenses/verify", json={"asset_id": a["id"], "license_key": "AAAAA-BBBBB-CCCCC-DDDDD"}).json()["success"] is False

    # library + signed download
    lib = client.get("/api/library", headers=H(b)).json()["items"]
    assert lib[0]["files"][0]["name"] == "grades.zip"
    link = client.post(f"/api/library/{o['id']}/files/0/link", headers=H(b)).json()["url"]
    dl = client.get(link)
    assert dl.status_code == 200 and dl.content == b"PK\x03\x04demo"
    assert client.post(f"/api/library/{o['id']}/files/0/link", headers=H(c)).status_code == 404  # not the buyer
    assert client.get("/api/download", params={"t": "garbage"}).status_code == 403

    # analytics + exports
    client.post(f"/api/assets/{a['id']}/view", params={"src": "instagram"})
    ov = client.get("/api/studio/overview", headers=H(c)).json()
    assert ov["sales"] == 1 and ov["revenue"] == 212 and ov["views"] >= 1 and ov["sources"][0]["source"] == "instagram"
    csv = client.get("/api/studio/export/sales.csv", headers=H(c))
    assert csv.status_code == 200 and "LAUNCH20" in csv.text
    assert client.get("/api/studio/customers", headers=H(c)).json()["items"][0]["orders"] == 1

    # free asset flow
    f = client.post("/api/assets", headers=H(c), json={"name": "Free Calendar", "category": "Templates", "description": "A free planner for all",
                                                      "price": 0, "kind": "hosted"}).json()
    r = client.post("/api/orders", headers=H(aff), json={"asset_id": f["id"], "license_id": "free"})
    assert r.status_code == 201 and r.json()["price"] == 0

    integ = client.get("/api/admin/integrity", headers={"x-admin-token": "test-admin"}).json()
    assert integ["conserved"] and integ["negative_wallets"] == 0, integ


def test_webhook_delivery_signed(client, d, monkeypatch):
    got = {}

    class H_(BaseHTTPRequestHandler):
        def do_POST(self):
            got["body"] = self.rfile.read(int(self.headers["Content-Length"]))
            got["sig"] = self.headers["X-SmartSharing-Signature"]
            self.send_response(200)
            self.end_headers()

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H_)
    threading.Thread(target=srv.handle_request, daemon=True).start()
    u = create_user(d, full_name="Hook Tester", email=None, password_hash=None)
    integ = {"_id": "int_test", "user_id": u["_id"], "type": "webhook",
             "config": {"url": f"http://127.0.0.1:{srv.server_port}/h", "secret": "whsec_x"}, "events": ["sale.completed"], "active": True}
    d.integrations.insert_one(integ)
    rec = hooks.send_test(d, integ)
    assert rec["ok"], rec
    expect = "sha256=" + hmac.new(b"whsec_x", got["body"], hashlib.sha256).hexdigest()
    assert got["sig"] == expect and json.loads(got["body"])["event"] == "test.ping"
    # SSRF guard rejects private / non-https URLs when configuring
    import pytest
    for url in ("http://example.com/x", "https://127.0.0.1/x", "https://localhost/x"):
        with pytest.raises(hooks.IntegrationError):
            hooks.validate_config("webhook", {"url": url})
