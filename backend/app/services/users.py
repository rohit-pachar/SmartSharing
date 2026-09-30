from datetime import datetime

from pymongo.database import Database

from ..config import settings
from ..db import run_txn
from ..util import new_id, now_utc, slugify
from .wallet import create_wallet, move


def unique_handle(d: Database, full_name: str) -> str:
    base = slugify(full_name).replace("-", ".")[:24] or "user"
    h, i = base, 1
    while d.users.count_documents({"handle": h}, limit=1):
        i += 1
        h = f"{base}{i}"
    return h


def create_user(d: Database, *, full_name: str, email: str | None, password_hash: str | None,
                handle: str | None = None, is_demo: bool = False, profile: dict | None = None,
                at: datetime | None = None, opening_credits: int | None = None) -> dict:
    at = at or now_utc()
    user = {
        "_id": new_id("usr"),
        "full_name": full_name.strip(),
        "handle": handle or unique_handle(d, full_name),
        "password_hash": password_hash,
        "is_demo": is_demo,
        "is_creator": False,
        "is_system": False,
        "created_at": at,
        **(profile or {}),
    }
    if email:
        user["email"] = email.lower().strip()
    bonus = settings.signup_bonus_credits if opening_credits is None else opening_credits

    def _fn(s, d_):
        d_.users.insert_one(user, session=s)
        create_wallet(d_, user["_id"], at=at, session=s)
        if bonus > 0:
            move(s, d_, user["_id"], balance=bonus, kind="grant", ref_type="grant",
                 memo="Opening balance" if is_demo else "Welcome bonus", at=at, is_demo=is_demo)
        return user

    return run_txn(_fn, d)


def public_profile(u: dict) -> dict:
    return {
        "id": u["_id"],
        "handle": u["handle"],
        "full_name": u["full_name"],
        "role": u.get("role"),
        "city": u.get("city"),
        "country": u.get("country"),
        "bio": u.get("bio"),
        "is_creator": u.get("is_creator", False),
        "is_demo": u.get("is_demo", False),
        "joined": u["created_at"].isoformat(),
    }
