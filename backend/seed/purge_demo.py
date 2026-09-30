"""Remove every demo record (is_demo=True). Real users, wallets and orders are untouched.

    python -m seed.purge_demo --yes

Run this before opening to real users so no demo data is ever mixed into production numbers.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import get_db  # noqa: E402


def purge(d) -> dict:
    ids = [u["_id"] for u in d.users.find({"is_demo": True}, {"_id": 1})]
    res = {
        "orders": d.orders.delete_many({"$or": [{"is_demo": True}, {"buyer_id": {"$in": ids}}]}).deleted_count,
        "transfers": d.transfers.delete_many({"$or": [{"is_demo": True}, {"from_user_id": {"$in": ids}},
                                                      {"to_user_id": {"$in": ids}}]}).deleted_count,
        "assets": d.assets.delete_many({"$or": [{"is_demo": True}, {"creator_id": {"$in": ids}}]}).deleted_count,
        "ledger": d.ledger.delete_many({"$or": [{"is_demo": True}, {"user_id": {"$in": ids}}]}).deleted_count,
        "wallets": d.wallets.delete_many({"_id": {"$in": ids}}).deleted_count,
        "users": d.users.delete_many({"_id": {"$in": ids}}).deleted_count,
    }
    # Platform fees collected from demo orders were demo credits -> recompute platform balance from remaining ledger.
    from app.db import PLATFORM_USER_ID
    left = list(d.ledger.aggregate([{"$match": {"user_id": PLATFORM_USER_ID}},
                                    {"$group": {"_id": None, "b": {"$sum": "$amount"}}}]))
    d.wallets.update_one({"_id": PLATFORM_USER_ID}, {"$set": {"balance": left[0]["b"] if left else 0}})
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    if not a.yes:
        sys.exit("Refusing without --yes")
    print(purge(get_db()))
