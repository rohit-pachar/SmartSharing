"""Creator tools: discount codes, license keys, API keys, view analytics."""
import hashlib
import re
import secrets
from datetime import datetime, timedelta

from pymongo import ReturnDocument
from pymongo.database import Database

from ..util import new_id, now_utc
from .wallet import WalletError


class ToolError(WalletError):
    code = "tool_error"


# ---------------- discount codes ----------------
CODE_RX = re.compile(r"^[A-Z0-9_-]{3,24}$")


def create_discount(d: Database, creator_id: str, *, code: str, pct_off: int, asset_ids: list[str] | None = None,
                    max_uses: int | None = None, expires_in_days: int | None = None) -> dict:
    code = code.strip().upper()
    if not CODE_RX.match(code):
        raise ToolError("code must be 3-24 chars: A-Z, 0-9, - or _")
    if not 1 <= pct_off <= 90:
        raise ToolError("pct_off must be 1-90")
    if asset_ids:
        owned = d.assets.count_documents({"_id": {"$in": asset_ids}, "creator_id": creator_id})
        if owned != len(set(asset_ids)):
            raise ToolError("discounts can only target your own assets")
    if d.discounts.count_documents({"creator_id": creator_id, "code": code}):
        raise ToolError("you already have a code with that name")
    now = now_utc()
    doc = {"_id": new_id("dsc"), "creator_id": creator_id, "code": code, "pct_off": pct_off,
           "asset_ids": asset_ids or [], "max_uses": max_uses, "uses": 0, "active": True,
           "expires_at": now + timedelta(days=expires_in_days) if expires_in_days else None, "created_at": now}
    d.discounts.insert_one(doc)
    return doc


def find_discount(d: Database, creator_id: str, asset_id: str, code: str | None, at: datetime | None = None) -> dict | None:
    if not code:
        return None
    at = at or now_utc()
    disc = d.discounts.find_one({"creator_id": creator_id, "code": code.strip().upper(), "active": True})
    if not disc:
        raise ToolError("invalid discount code")
    if disc.get("expires_at") and disc["expires_at"] <= at:
        raise ToolError("this discount code has expired")
    if disc.get("max_uses") is not None and disc["uses"] >= disc["max_uses"]:
        raise ToolError("this discount code has been fully used")
    if disc["asset_ids"] and asset_id not in disc["asset_ids"]:
        raise ToolError("this code does not apply to this asset")
    return disc


def consume_discount(s, d: Database, disc: dict):
    flt: dict = {"_id": disc["_id"], "active": True}
    if disc.get("max_uses") is not None:
        flt["uses"] = {"$lt": disc["max_uses"]}
    if d.discounts.find_one_and_update(flt, {"$inc": {"uses": 1}}, session=s,
                                       return_document=ReturnDocument.AFTER) is None:
        raise ToolError("this discount code has been fully used")


def discounted(price: int, pct_off: int) -> int:
    return max(1, round(price * (100 - pct_off) / 100))


# ---------------- license keys ----------------
def new_license_key() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "-".join("".join(secrets.choice(alphabet) for _ in range(5)) for _ in range(4))


def verify_license(d: Database, asset_id: str, license_key: str, increment: bool = True) -> dict:
    o = d.orders.find_one({"asset_id": asset_id, "license_key": license_key.strip().upper()})
    if not o or o.get("status") != "completed":
        return {"success": False, "message": "That license key does not exist for the provided asset."}
    if increment:
        o = d.orders.find_one_and_update({"_id": o["_id"]}, {"$inc": {"license_uses": 1},
                                                             "$set": {"license_last_verified_at": now_utc()}},
                                         return_document=ReturnDocument.AFTER)
    buyer = d.users.find_one({"_id": o["buyer_id"]}, {"handle": 1})
    return {"success": True, "uses": o.get("license_uses", 0),
            "purchase": {"id": o["_id"], "receipt": o["receipt"], "asset_id": o["asset_id"], "asset_name": o["asset_name"],
                         "license": o["license_name"], "license_id": o["license_id"], "price": o["price"],
                         "buyer_handle": buyer["handle"] if buyer else None, "created_at": o["created_at"].isoformat()}}


# ---------------- API keys ----------------
def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def create_api_key(d: Database, user_id: str, name: str) -> tuple[dict, str]:
    if d.api_keys.count_documents({"user_id": user_id, "revoked": False}) >= 10:
        raise ToolError("maximum of 10 active API keys")
    raw = "ssk_" + secrets.token_urlsafe(32)
    doc = {"_id": new_id("key"), "user_id": user_id, "name": name.strip()[:40] or "API key", "prefix": raw[:12],
           "hash": _hash(raw), "revoked": False, "created_at": now_utc(), "last_used_at": None}
    d.api_keys.insert_one(doc)
    return doc, raw


def user_for_api_key(d: Database, raw: str) -> dict | None:
    k = d.api_keys.find_one_and_update({"hash": _hash(raw), "revoked": False}, {"$set": {"last_used_at": now_utc()}})
    return d.users.find_one({"_id": k["user_id"]}) if k else None


# ---------------- analytics ----------------
def record_view(d: Database, asset_id: str, source: str | None = None):
    a = d.assets.find_one({"_id": asset_id}, {"creator_id": 1})
    if not a:
        return
    day = now_utc().strftime("%Y-%m-%d")
    src = (source or "direct")[:20]
    d.asset_views.update_one({"asset_id": asset_id, "day": day},
                             {"$inc": {"count": 1, f"sources.{src}": 1}, "$setOnInsert": {"creator_id": a["creator_id"]}},
                             upsert=True)
    d.assets.update_one({"_id": asset_id}, {"$inc": {"stats.views": 1}})
