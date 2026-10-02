"""Marketplace: assets, license options, purchases (credit settlement with creator/platform split)."""
from datetime import datetime

from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from ..config import settings
from ..db import PLATFORM_USER_ID, run_txn
from ..util import initials, new_id, now_utc, slugify
from .wallet import WalletError, move

CATEGORIES = ["3D & design", "AI workflows", "Motion & video", "Templates", "Business & finance"]
CATEGORY_IMAGE = {"3D & design": "/art/prism.webp", "AI workflows": "/art/flowstate.webp",
                  "Motion & video": "/art/fluid.webp", "Templates": "/art/prism.webp", "Business & finance": "/art/flowstate.webp"}


class MarketError(WalletError):
    code = "market_error"


class AlreadyOwned(MarketError):
    code = "already_owned"


def license_options(asset: dict) -> list[dict]:
    """Mirrors licenseOptions() in the frontend (app/market-data.ts)."""
    p = asset["price"]
    if p == 0:
        return [{"id": "free", "name": "Free licence", "detail": "Personal and commercial use · attribution appreciated", "price": 0}]
    if asset.get("kind") == "hosted":
        return [
            {"id": "week", "name": "7-day pass", "detail": "50 runs · one user", "price": p},
            {"id": "month", "name": "30-day pass", "detail": "250 runs · one user", "price": p * 3},
        ]
    return [
        {"id": "personal", "name": "Personal", "detail": "One user · non-commercial projects", "price": p},
        {"id": "commercial", "name": "Commercial", "detail": "One user · client and commercial work", "price": p * 2},
        {"id": "studio", "name": "Studio", "detail": "Up to 5 users · commercial work", "price": p * 4},
    ]


def split(price: int) -> tuple[int, int]:
    fee = round(price * settings.platform_fee_pct / 100)
    return price - fee, fee


def create_asset(d: Database, creator: dict, *, name: str, category: str, description: str, price: int,
                 kind: str = "file", format: str = "", includes: list[str] | None = None, tag: str | None = None,
                 image: str | None = None, at: datetime | None = None, asset_id: str | None = None,
                 status: str = "published", files: list[dict] | None = None, affiliate_pct: int = 0) -> dict:
    if category not in CATEGORIES:
        raise MarketError(f"category must be one of {CATEGORIES}")
    if kind not in ("file", "hosted"):
        raise MarketError("kind must be 'file' or 'hosted'")
    if not (price == 0 or 49 <= price <= 100_000):
        raise MarketError("price must be 0 (free) or between 49 and 100000 credits")
    at = at or now_utc()
    base = asset_id or slugify(name)
    asset_id = base
    while d.assets.count_documents({"_id": asset_id}, limit=1):
        asset_id = f"{base}-{new_id('x')[-4:]}"
    doc = {
        "_id": asset_id,
        "name": name.strip()[:70],
        "category": category,
        "creator_id": creator["_id"],
        "creator": creator["full_name"],
        "creator_handle": creator["handle"],
        "initials": initials(creator["full_name"]),
        "role": creator.get("role") or "Creator",
        "price": int(price),
        "image": image or CATEGORY_IMAGE[category],
        "format": format,
        "description": description.strip()[:2000],
        "includes": includes or [],
        "kind": kind,
        "tag": tag or f"THE {category.split()[0].upper()} EDIT",
        "status": status,
        "files": files or [],
        "affiliate_pct": affiliate_pct,
        "stats": {"sales": 0, "revenue": 0, "saves": 0, "views": 0},
        "is_demo": bool(creator.get("is_demo")),
        "is_official": bool(creator.get("is_official")),
        "created_at": at,
        "updated_at": at,
    }
    d.assets.insert_one(doc)
    d.users.update_one({"_id": creator["_id"]}, {"$set": {"is_creator": True}})
    return doc


def purchase(d: Database, buyer_id: str, asset_id: str, license_id: str, at: datetime | None = None,
             discount_code: str | None = None, ref: str | None = None) -> dict:
    """Buy a licence. Optional discount code (creator's) and affiliate ref (handle of a referrer)."""
    from .tools import consume_discount, discounted, find_discount, new_license_key
    at = at or now_utc()
    asset = d.assets.find_one({"_id": asset_id, "status": "published"})
    if not asset:
        raise MarketError("asset not found")
    opt = next((o for o in license_options(asset) if o["id"] == license_id), None)
    if not opt:
        raise MarketError("invalid license option")
    if asset["creator_id"] == buyer_id:
        raise MarketError("you cannot buy your own asset")
    buyer = d.users.find_one({"_id": buyer_id})
    if not buyer:
        raise MarketError("unknown buyer")
    if d.orders.count_documents({"buyer_id": buyer_id, "asset_id": asset_id, "license_id": license_id}, limit=1):
        raise AlreadyOwned("you already hold this license")

    disc = find_discount(d, asset["creator_id"], asset_id, discount_code, at)
    list_price = opt["price"]
    price = discounted(list_price, disc["pct_off"]) if disc else list_price
    creator_amt, fee = split(price)

    # affiliate: creator opts in with a commission %, paid out of the creator's share
    affiliate, aff_amt = None, 0
    aff_pct = int(asset.get("affiliate_pct") or 0)
    if ref and aff_pct > 0:
        affiliate = d.users.find_one({"handle": ref.lstrip("@").lower(), "is_system": {"$ne": True}})
        if affiliate and affiliate["_id"] not in (buyer_id, asset["creator_id"]):
            aff_amt = round(creator_amt * aff_pct / 100)
            creator_amt -= aff_amt
        else:
            affiliate = None

    is_demo = bool(buyer.get("is_demo") and asset.get("is_demo"))
    order = {
        "_id": new_id("ord"),
        "receipt": "SS-" + new_id("r")[-8:].upper(),
        "buyer_id": buyer_id,
        "buyer_name": buyer["full_name"],
        "creator_id": asset["creator_id"],
        "asset_id": asset_id,
        "asset_name": asset["name"],
        "category": asset["category"],
        "license_id": license_id,
        "license_name": opt["name"],
        "list_price": list_price,
        "price": price,
        "discount_code": disc["code"] if disc else None,
        "affiliate_id": affiliate["_id"] if affiliate else None,
        "affiliate_amount": aff_amt,
        "creator_amount": creator_amt,
        "platform_fee": fee,
        "license_key": new_license_key(),
        "license_uses": 0,
        "status": "completed",
        "is_demo": is_demo,
        "created_at": at,
    }
    memo = f"{asset['name']} · {opt['name']}"

    def _fn(s, d_):
        if disc:
            consume_discount(s, d_, disc)
        move(s, d_, buyer_id, balance=-price, kind="purchase", ref_type="order", ref_id=order["_id"],
             counterparty_id=asset["creator_id"], memo=memo, at=at, is_demo=is_demo)
        move(s, d_, asset["creator_id"], balance=creator_amt, kind="sale", ref_type="order", ref_id=order["_id"],
             counterparty_id=buyer_id, memo=memo, at=at, is_demo=is_demo)
        if aff_amt:
            move(s, d_, affiliate["_id"], balance=aff_amt, kind="affiliate_commission", ref_type="order",
                 ref_id=order["_id"], counterparty_id=asset["creator_id"], memo=memo, at=at, is_demo=is_demo)
        if fee:
            move(s, d_, PLATFORM_USER_ID, balance=fee, kind="platform_fee", ref_type="order", ref_id=order["_id"],
                 at=at, is_demo=is_demo)
        d_.orders.insert_one(order, session=s)
        d_.assets.update_one({"_id": asset_id}, {"$inc": {"stats.sales": 1, "stats.revenue": price}}, session=s)
        return order

    try:
        out = run_txn(_fn, d)
    except DuplicateKeyError:
        raise AlreadyOwned("you already hold this license")

    from .hooks import emit
    from ..util import public_name
    emit(d, asset["creator_id"], "sale.completed", {
        "order_id": out["_id"], "receipt": out["receipt"], "asset_id": asset_id, "asset_name": asset["name"],
        "license_name": opt["name"], "price": price, "creator_amount": creator_amt, "discount_code": order["discount_code"],
        "buyer": public_name(buyer["full_name"]), "created_at": at.isoformat()})
    return out
