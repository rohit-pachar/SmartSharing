import re

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..db import get_db
from ..security import current_user, session_user
from ..services import market
from ..services.users import public_profile
from ..util import clean, public_name

router = APIRouter(tags=["market"])


def asset_out(a: dict) -> dict:
    out = clean(a)
    files = a.get("files") or []
    out.pop("files", None)
    out["file_count"] = len(files)
    out["file_names"] = [f["name"] for f in files]
    out["total_size"] = sum(f["size"] for f in files)
    out["license_options"] = market.license_options(a)
    return out


@router.get("/categories")
def categories():
    return {"items": ["All assets", *market.CATEGORIES]}


@router.get("/assets")
def list_assets(q: str | None = None, category: str | None = None, creator: str | None = None,
                sort: str = Query("new", pattern="^(new|popular|price_asc|price_desc)$"), source: str | None = Query(None, pattern="^(official|community)$"), include_demo: bool = False,
                limit: int = Query(24, le=100), offset: int = Query(0, ge=0)):
    d = get_db()
    flt: dict = {"status": "published"}
    if not include_demo:
        flt["is_demo"] = {"$ne": True}  # demo listings have no deliverable files; keep them out of the marketplace
    if category and category not in ("All assets", "All"):
        flt["category"] = category
    if creator:
        flt["creator_handle"] = creator
    if source == "official":
        flt["is_official"] = True
    elif source == "community":
        flt["is_official"] = {"$ne": True}
    if q and q.strip():
        rx = re.compile(re.escape(q.strip()), re.I)
        flt["$or"] = [{"name": rx}, {"description": rx}, {"creator": rx}, {"category": rx}]
    order = {"new": [("is_official", -1), ("created_at", -1)], "popular": [("is_official", -1), ("stats.sales", -1), ("created_at", -1)],
             "price_asc": [("price", 1)], "price_desc": [("price", -1)]}[sort]
    total = d.assets.count_documents(flt)
    rows = d.assets.find(flt).sort(order).skip(offset).limit(limit)
    return {"total": total, "items": [asset_out(a) for a in rows]}


@router.get("/assets/{asset_id}")
def get_asset(asset_id: str):
    a = get_db().assets.find_one({"_id": asset_id, "status": "published"})
    if not a:
        raise HTTPException(404, "Asset not found")
    return asset_out(a)


class AssetIn(BaseModel):
    name: str = Field(min_length=3, max_length=70)
    category: str
    description: str = Field(min_length=10, max_length=2000)
    price: int = Field(ge=0, le=100_000)
    kind: str = Field("file", pattern="^(file|hosted)$")
    format: str = Field("", max_length=60)
    includes: list[str] = Field(default_factory=list, max_length=10)


@router.post("/assets", status_code=201)
def create_asset(body: AssetIn, user: dict = Depends(current_user)):
    try:
        a = market.create_asset(get_db(), user, **body.model_dump(),
                                status="draft" if body.kind == "file" else "published")
    except market.MarketError as e:
        raise HTTPException(400, {"code": e.code, "message": str(e)})
    out = asset_out(a)
    out["files"] = []
    return out


class BuyIn(BaseModel):
    asset_id: str
    license_id: str
    discount_code: str | None = Field(None, max_length=24)
    ref: str | None = Field(None, max_length=40)


@router.post("/orders", status_code=201)
def buy(body: BuyIn, user: dict = Depends(session_user)):
    try:
        o = market.purchase(get_db(), user["_id"], body.asset_id, body.license_id,
                            discount_code=body.discount_code, ref=body.ref)
    except market.AlreadyOwned as e:
        raise HTTPException(409, {"code": e.code, "message": str(e)})
    except market.WalletError as e:
        raise HTTPException(400, {"code": e.code, "message": str(e)})
    return clean(o)


@router.get("/me/purchases")
def my_purchases(user: dict = Depends(current_user), limit: int = Query(50, le=200)):
    rows = get_db().orders.find({"buyer_id": user["_id"]}).sort("created_at", -1).limit(limit)
    return {"items": [clean(r) for r in rows]}


@router.get("/me/sales")
def my_sales(user: dict = Depends(current_user), limit: int = Query(50, le=200)):
    rows = get_db().orders.find({"creator_id": user["_id"]}).sort("created_at", -1).limit(limit)
    return {"items": [clean(r) for r in rows]}


@router.get("/me/assets")
def my_assets(user: dict = Depends(current_user)):
    rows = get_db().assets.find({"creator_id": user["_id"]}).sort("created_at", -1)
    return {"items": [asset_out(a) for a in rows]}


@router.get("/users/{handle}")
def user_profile(handle: str):
    d = get_db()
    u = d.users.find_one({"handle": handle, "is_system": {"$ne": True}})
    if not u:
        raise HTTPException(404, "User not found")
    assets = [asset_out(a) for a in d.assets.find({"creator_id": u["_id"], "status": "published"})]
    return {**public_profile(u), "bio": u.get("bio"), "website": u.get("website"), "links": u.get("links") or {},
            "is_official": u.get("is_official", False), "assets": assets,
            "sales": d.orders.count_documents({"creator_id": u["_id"]})}


@router.get("/activity")
def activity(limit: int = Query(20, le=100)):
    """Public marketplace feed: recent purchases + settled transfers (first name + initial only)."""
    d = get_db()
    orders = list(d.orders.find({}, {"buyer_id": 1, "asset_id": 1, "asset_name": 1, "license_name": 1, "price": 1,
                                     "is_demo": 1, "created_at": 1}).sort("created_at", -1).limit(limit))
    trs = list(d.transfers.find({"status": "accepted"}, {"from_user_id": 1, "to_user_id": 1, "amount": 1,
                                                         "is_demo": 1, "settled_at": 1}).sort("settled_at", -1).limit(limit))
    ids = {o["buyer_id"] for o in orders} | {t["from_user_id"] for t in trs} | {t["to_user_id"] for t in trs}
    names = {u["_id"]: public_name(u["full_name"]) for u in d.users.find({"_id": {"$in": list(ids)}}, {"full_name": 1})}

    def name(uid):
        return names.get(uid, "Someone")

    items = []
    for o in orders:
        items.append({"type": "purchase", "at": o["created_at"], "buyer": name(o["buyer_id"]),
                      "asset_id": o["asset_id"], "asset": o["asset_name"], "license": o["license_name"],
                      "price": o["price"], "is_demo": o.get("is_demo", False)})
    for t in trs:
        items.append({"type": "transfer", "at": t["settled_at"], "from": name(t["from_user_id"]),
                      "to": name(t["to_user_id"]), "amount": t["amount"], "is_demo": t.get("is_demo", False)})
    items.sort(key=lambda x: x["at"], reverse=True)
    for i in items:
        i["at"] = i["at"].isoformat()
    return {"items": items[:limit]}


@router.get("/stats")
def stats():
    d = get_db()
    agg = list(d.orders.aggregate([{"$group": {"_id": None, "n": {"$sum": 1}, "vol": {"$sum": "$price"}}}]))
    tagg = list(d.transfers.aggregate([{"$match": {"status": "accepted"}},
                                       {"$group": {"_id": None, "n": {"$sum": 1}, "vol": {"$sum": "$amount"}}}]))
    return {
        "members": d.users.count_documents({"is_system": {"$ne": True}}),
        "demo_members": d.users.count_documents({"is_demo": True}),
        "creators": d.users.count_documents({"is_creator": True}),
        "assets": d.assets.count_documents({"status": "published"}),
        "orders": agg[0]["n"] if agg else 0,
        "order_volume": agg[0]["vol"] if agg else 0,
        "transfers": tagg[0]["n"] if tagg else 0,
        "transfer_volume": tagg[0]["vol"] if tagg else 0,
        "pending_transfers": d.transfers.count_documents({"status": "pending"}),
    }
