"""Creator Studio API: listings, files, discounts, licence keys, API keys, integrations, analytics, exports."""
import csv
import io
from datetime import timedelta
from typing import NoReturn

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from ..db import get_db
from ..security import create_download_token, current_user, read_download_token, session_user
from ..services import hooks, market, storage, tools
from ..util import clean, new_id, now_utc, public_name

router = APIRouter(tags=["studio"])


def _err(e: Exception, code=400) -> NoReturn:
    raise HTTPException(code, {"code": getattr(e, "code", "error"), "message": str(e)})


def _my_asset(d, user, asset_id):
    a = d.assets.find_one({"_id": asset_id, "creator_id": user["_id"]})
    if not a:
        raise HTTPException(404, "Asset not found in your studio")
    return a


# ---------------- listings ----------------
class AssetPatch(BaseModel):
    name: str | None = Field(None, min_length=3, max_length=70)
    description: str | None = Field(None, min_length=10, max_length=2000)
    price: int | None = Field(None, ge=0, le=100_000)
    format: str | None = Field(None, max_length=60)
    includes: list[str] | None = Field(None, max_length=12)
    status: str | None = Field(None, pattern="^(published|draft)$")
    affiliate_pct: int | None = Field(None, ge=0, le=50)
    tags: list[str] | None = Field(None, max_length=8)


@router.patch("/studio/assets/{asset_id}")
def update_asset(asset_id: str, body: AssetPatch, user: dict = Depends(current_user)):
    d = get_db()
    a = _my_asset(d, user, asset_id)
    upd = {k: v for k, v in body.model_dump().items() if v is not None}
    if upd.get("status") == "published" and not a.get("files") and a.get("kind") == "file":
        raise HTTPException(400, {"code": "no_files", "message": "Upload at least one file before publishing"})
    upd["updated_at"] = now_utc()
    d.assets.update_one({"_id": asset_id}, {"$set": upd})
    return _studio_asset(d.assets.find_one({"_id": asset_id}))


def _studio_asset(a):
    out = clean(a)
    out["license_options"] = market.license_options(a)
    out["files"] = [{"idx": i, "name": f["name"], "size": f["size"], "mime": f["mime"]} for i, f in enumerate(a.get("files", []))]
    return out


@router.get("/studio/assets")
def studio_assets(user: dict = Depends(current_user)):
    d = get_db()
    return {"items": [_studio_asset(a) for a in d.assets.find({"creator_id": user["_id"]}).sort("created_at", -1)]}


@router.post("/studio/assets/{asset_id}/files", status_code=201)
async def upload_file(asset_id: str, file: UploadFile = File(...), user: dict = Depends(current_user)):
    d = get_db()
    a = _my_asset(d, user, asset_id)
    if len(a.get("files", [])) >= 10:
        raise HTTPException(400, "Max 10 files per asset")
    data = await file.read(storage.MAX_BYTES + 1)
    try:
        meta = storage.save_bytes(asset_id, file.filename or "file", data)
    except ValueError as e:
        raise HTTPException(400, {"code": "bad_file", "message": str(e)})
    d.assets.update_one({"_id": asset_id}, {"$push": {"files": meta}, "$set": {"updated_at": now_utc()}})
    return {"name": meta["name"], "size": meta["size"]}


@router.delete("/studio/assets/{asset_id}/files/{idx}")
def delete_file(asset_id: str, idx: int, user: dict = Depends(current_user)):
    d = get_db()
    a = _my_asset(d, user, asset_id)
    files = a.get("files", [])
    if not 0 <= idx < len(files):
        raise HTTPException(404, "File not found")
    storage.delete(files[idx]["path"])
    files.pop(idx)
    d.assets.update_one({"_id": asset_id}, {"$set": {"files": files}})
    return {"ok": True}


# ---------------- buyer library + downloads ----------------
@router.get("/library")
def library(user: dict = Depends(session_user)):
    d = get_db()
    orders = list(d.orders.find({"buyer_id": user["_id"]}).sort("created_at", -1))
    assets = {a["_id"]: a for a in d.assets.find({"_id": {"$in": [o["asset_id"] for o in orders]}})}
    items = []
    for o in orders:
        a = assets.get(o["asset_id"], {})
        items.append({**clean(o), "image": a.get("image"), "creator": a.get("creator"), "kind": a.get("kind"),
                      "files": [{"idx": i, "name": f["name"], "size": f["size"]} for i, f in enumerate(a.get("files", []))]})
    return {"items": items}


@router.post("/library/{order_id}/files/{idx}/link")
def download_link(order_id: str, idx: int, user: dict = Depends(session_user)):
    d = get_db()
    o = d.orders.find_one({"_id": order_id, "buyer_id": user["_id"], "status": "completed"})
    if not o:
        raise HTTPException(404, "Purchase not found")
    a = d.assets.find_one({"_id": o["asset_id"]}, {"files": 1})
    if not a or not 0 <= idx < len(a.get("files", [])):
        raise HTTPException(404, "File not found")
    return {"url": f"/api/download?t={create_download_token(order_id, idx, user['_id'])}", "expires_in": 600}


@router.get("/download")
def download(t: str):
    p = read_download_token(t)
    d = get_db()
    o = d.orders.find_one({"_id": p["ord"], "buyer_id": p["sub"], "status": "completed"})
    if not o:
        raise HTTPException(404, "Purchase not found")
    a = d.assets.find_one({"_id": o["asset_id"]}, {"files": 1})
    files = (a or {}).get("files", [])
    if not 0 <= p["f"] < len(files):
        raise HTTPException(404, "File not found")
    f = files[p["f"]]
    d.orders.update_one({"_id": o["_id"]}, {"$inc": {"downloads": 1}, "$set": {"last_download_at": now_utc()}})
    return FileResponse(storage.abs_path(f["path"]), media_type=f["mime"], filename=f["name"])


# ---------------- discounts ----------------
class DiscountIn(BaseModel):
    code: str
    pct_off: int = Field(ge=1, le=90)
    asset_ids: list[str] = Field(default_factory=list)
    max_uses: int | None = Field(None, ge=1, le=100_000)
    expires_in_days: int | None = Field(None, ge=1, le=365)


@router.get("/studio/discounts")
def list_discounts(user: dict = Depends(current_user)):
    return {"items": [clean(x) for x in get_db().discounts.find({"creator_id": user["_id"]}).sort("created_at", -1)]}


@router.post("/studio/discounts", status_code=201)
def create_discount(body: DiscountIn, user: dict = Depends(current_user)):
    try:
        return clean(tools.create_discount(get_db(), user["_id"], **body.model_dump()))
    except tools.ToolError as e:
        _err(e)


@router.delete("/studio/discounts/{disc_id}")
def disable_discount(disc_id: str, user: dict = Depends(current_user)):
    r = get_db().discounts.update_one({"_id": disc_id, "creator_id": user["_id"]}, {"$set": {"active": False}})
    if not r.matched_count:
        raise HTTPException(404, "Not found")
    return {"ok": True}


@router.get("/discounts/check")
def check_discount(asset_id: str, code: str):
    d = get_db()
    a = d.assets.find_one({"_id": asset_id, "status": "published"})
    if not a:
        raise HTTPException(404, "Asset not found")
    try:
        disc = tools.find_discount(d, a["creator_id"], asset_id, code)
    except tools.ToolError as e:
        return {"valid": False, "message": str(e)}
    return {"valid": True, "code": disc["code"], "pct_off": disc["pct_off"],
            "options": [{**o, "discounted": tools.discounted(o["price"], disc["pct_off"])} for o in market.license_options(a)]}


# ---------------- licence keys (public verify API, Gumroad-compatible shape) ----------------
class VerifyIn(BaseModel):
    asset_id: str
    license_key: str
    increment_uses_count: bool = True


@router.post("/licenses/verify")
def verify_license(body: VerifyIn):
    return tools.verify_license(get_db(), body.asset_id, body.license_key, body.increment_uses_count)


# ---------------- API keys ----------------
class KeyIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)


@router.get("/studio/api-keys")
def list_keys(user: dict = Depends(session_user)):
    rows = get_db().api_keys.find({"user_id": user["_id"], "revoked": False}).sort("created_at", -1)
    return {"items": [{k: v for k, v in clean(r).items() if k != "hash"} for r in rows]}


@router.post("/studio/api-keys", status_code=201)
def create_key(body: KeyIn, user: dict = Depends(session_user)):
    try:
        doc, raw = tools.create_api_key(get_db(), user["_id"], body.name)
    except tools.ToolError as e:
        _err(e)
    return {"id": doc["_id"], "name": doc["name"], "key": raw, "prefix": doc["prefix"]}


@router.delete("/studio/api-keys/{key_id}")
def revoke_key(key_id: str, user: dict = Depends(session_user)):
    r = get_db().api_keys.update_one({"_id": key_id, "user_id": user["_id"]}, {"$set": {"revoked": True}})
    if not r.matched_count:
        raise HTTPException(404, "Not found")
    return {"ok": True}


# ---------------- integrations ----------------
class IntegrationIn(BaseModel):
    type: str
    name: str = Field("", max_length=40)
    config: dict
    events: list[str] = Field(default_factory=lambda: ["sale.completed"])


def _integ_out(i):
    out = clean(i)
    out["config"] = hooks.masked(i["config"])
    return out


@router.get("/studio/integrations")
def list_integrations(user: dict = Depends(session_user)):
    d = get_db()
    return {"items": [_integ_out(i) for i in d.integrations.find({"user_id": user["_id"]}).sort("created_at", -1)]}


@router.post("/studio/integrations", status_code=201)
def create_integration(body: IntegrationIn, user: dict = Depends(session_user)):
    d = get_db()
    if d.integrations.count_documents({"user_id": user["_id"]}) >= 20:
        raise HTTPException(400, "Max 20 integrations")
    evs = [e for e in body.events if e in hooks.EVENTS]
    if not evs:
        raise HTTPException(400, f"events must include one of {sorted(hooks.EVENTS)}")
    try:
        cfg = hooks.validate_config(body.type, body.config)
    except hooks.IntegrationError as e:
        _err(e)
    doc = {"_id": new_id("int"), "user_id": user["_id"], "type": body.type, "name": body.name or body.type.title(),
           "config": cfg, "events": evs, "active": True, "created_at": now_utc(), "last_delivery": None}
    d.integrations.insert_one(doc)
    out = _integ_out(doc)
    if body.type == "webhook":
        out["signing_secret"] = cfg["secret"]  # shown once
    return out


@router.post("/studio/integrations/{integ_id}/test")
def test_integration(integ_id: str, user: dict = Depends(session_user)):
    d = get_db()
    i = d.integrations.find_one({"_id": integ_id, "user_id": user["_id"]})
    if not i:
        raise HTTPException(404, "Not found")
    rec = hooks.send_test(d, i)
    return {"ok": rec["ok"], "status": rec["status"], "error": rec["error"]}


@router.patch("/studio/integrations/{integ_id}")
def toggle_integration(integ_id: str, active: bool, user: dict = Depends(session_user)):
    r = get_db().integrations.update_one({"_id": integ_id, "user_id": user["_id"]}, {"$set": {"active": active}})
    if not r.matched_count:
        raise HTTPException(404, "Not found")
    return {"ok": True}


@router.delete("/studio/integrations/{integ_id}")
def delete_integration(integ_id: str, user: dict = Depends(session_user)):
    r = get_db().integrations.delete_one({"_id": integ_id, "user_id": user["_id"]})
    if not r.deleted_count:
        raise HTTPException(404, "Not found")
    return {"ok": True}


@router.get("/studio/integrations/{integ_id}/deliveries")
def deliveries(integ_id: str, user: dict = Depends(session_user)):
    rows = get_db().integration_deliveries.find({"integration_id": integ_id, "user_id": user["_id"]}).sort("created_at", -1).limit(20)
    return {"items": [clean(r) for r in rows]}


# ---------------- analytics ----------------
@router.post("/assets/{asset_id}/view", status_code=204)
def track_view(asset_id: str, src: str | None = Query(None, max_length=20)):
    tools.record_view(get_db(), asset_id, src)


@router.get("/studio/overview")
def overview(days: int = Query(30, ge=7, le=90), user: dict = Depends(current_user)):
    d = get_db()
    uid = user["_id"]
    since = now_utc() - timedelta(days=days)
    sales = list(d.orders.find({"creator_id": uid, "created_at": {"$gte": since}}))
    aff = list(d.orders.find({"affiliate_id": uid, "created_at": {"$gte": since}}, {"affiliate_amount": 1}))
    views = list(d.asset_views.find({"creator_id": uid, "day": {"$gte": since.strftime("%Y-%m-%d")}}))
    by_day = {}
    for i in range(days):
        k = (since + timedelta(days=i + 1)).strftime("%Y-%m-%d")
        by_day[k] = {"day": k, "revenue": 0, "sales": 0, "views": 0}
    for o in sales:
        k = o["created_at"].strftime("%Y-%m-%d")
        if k in by_day:
            by_day[k]["revenue"] += o["creator_amount"]
            by_day[k]["sales"] += 1
    sources = {}
    for v in views:
        if v["day"] in by_day:
            by_day[v["day"]]["views"] += v["count"]
        for s, n in (v.get("sources") or {}).items():
            sources[s] = sources.get(s, 0) + n
    per_asset = {}
    for o in sales:
        p = per_asset.setdefault(o["asset_id"], {"asset_id": o["asset_id"], "name": o["asset_name"], "sales": 0, "revenue": 0})
        p["sales"] += 1
        p["revenue"] += o["creator_amount"]
    total_views = sum(x["views"] for x in by_day.values())
    w = d.wallets.find_one({"_id": uid}) or {"balance": 0, "pending_out": 0}
    recent = sorted(sales, key=lambda o: o["created_at"], reverse=True)[:8]
    return {
        "days": days,
        "revenue": sum(o["creator_amount"] for o in sales),
        "gross": sum(o["price"] for o in sales),
        "sales": len(sales),
        "views": total_views,
        "conversion": round(len(sales) / total_views * 100, 2) if total_views else 0,
        "affiliate_earnings": sum(o.get("affiliate_amount", 0) for o in aff),
        "customers": len({o["buyer_id"] for o in sales}),
        "balance": w["balance"],
        "series": list(by_day.values()),
        "top_assets": sorted(per_asset.values(), key=lambda x: -x["revenue"])[:5],
        "sources": sorted(({"source": k, "views": v} for k, v in sources.items()), key=lambda x: -x["views"]),
        "recent_sales": [{"receipt": o["receipt"], "asset": o["asset_name"], "license": o["license_name"],
                          "amount": o["creator_amount"], "discount_code": o.get("discount_code"),
                          "buyer": public_name(o["buyer_name"]), "at": o["created_at"].isoformat()} for o in recent],
        "listings": d.assets.count_documents({"creator_id": uid}),
    }


@router.get("/studio/customers")
def customers(user: dict = Depends(current_user)):
    d = get_db()
    agg = d.orders.aggregate([
        {"$match": {"creator_id": user["_id"]}},
        {"$group": {"_id": "$buyer_id", "name": {"$first": "$buyer_name"}, "orders": {"$sum": 1},
                    "spent": {"$sum": "$price"}, "last": {"$max": "$created_at"}}},
        {"$sort": {"last": -1}}, {"$limit": 500}])
    rows = list(agg)
    handles = {u["_id"]: u["handle"] for u in d.users.find({"_id": {"$in": [r["_id"] for r in rows]}}, {"handle": 1})}
    return {"items": [{"handle": handles.get(r["_id"]), "name": public_name(r["name"]), "orders": r["orders"],
                       "spent": r["spent"], "last_order": r["last"].isoformat()} for r in rows]}


# ---------------- exports ----------------
def _csv(rows: list[list], header: list[str], filename: str):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows(rows)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/studio/export/sales.csv")
def export_sales(user: dict = Depends(current_user)):
    rows = [[o["created_at"].isoformat(), o["receipt"], o["asset_name"], o["license_name"], o.get("list_price", o["price"]),
             o["price"], o.get("discount_code") or "", o["platform_fee"], o.get("affiliate_amount", 0), o["creator_amount"]]
            for o in get_db().orders.find({"creator_id": user["_id"]}).sort("created_at", -1)]
    return _csv(rows, ["date", "receipt", "asset", "license", "list_price", "paid", "discount_code", "platform_fee",
                       "affiliate_commission", "your_earnings"], "smartsharing-sales.csv")


@router.get("/studio/export/ledger.csv")
def export_ledger(user: dict = Depends(session_user)):
    rows = [[r["created_at"].isoformat(), r["kind"], r["amount"], r["balance_after"], r.get("memo") or "", r.get("ref_id") or ""]
            for r in get_db().ledger.find({"user_id": user["_id"]}).sort("created_at", -1)]
    return _csv(rows, ["date", "type", "amount", "balance_after", "memo", "reference"], "smartsharing-wallet.csv")


# ---------------- profile ----------------
class ProfileIn(BaseModel):
    full_name: str | None = Field(None, min_length=2, max_length=80)
    role: str | None = Field(None, max_length=40)
    bio: str | None = Field(None, max_length=400)
    city: str | None = Field(None, max_length=40)
    website: str | None = Field(None, max_length=120)
    links: dict[str, str] | None = None


@router.patch("/me")
def update_me(body: ProfileIn, user: dict = Depends(session_user)):
    upd = {k: v for k, v in body.model_dump().items() if v is not None}
    if "links" in upd:
        upd["links"] = {k[:20]: v[:200] for k, v in list(upd["links"].items())[:8] if v.startswith("https://")}
    if upd:
        get_db().users.update_one({"_id": user["_id"]}, {"$set": upd})
    u = get_db().users.find_one({"_id": user["_id"]})
    return {k: u.get(k) for k in ("full_name", "handle", "role", "bio", "city", "website", "links")}
