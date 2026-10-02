"""Remove QA/test accounts (emails like qa+…@example.com / qa.*@example.com) and everything they created.

    python -m seed.purge_qa            # dry run
    python -m seed.purge_qa --yes      # delete

Reverses credits those accounts paid to creators / platform so the ledger stays balanced.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import PLATFORM_USER_ID, get_db  # noqa: E402
from app.services import storage  # noqa: E402

QA_RX = r"^qa[.+].*@example\.com$"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true")
    yes = ap.parse_args().yes
    d = get_db()
    users = list(d.users.find({"email": {"$regex": QA_RX}}))
    ids = [u["_id"] for u in users]
    print("QA accounts:", [u["email"] for u in users])
    if not ids:
        return
    orders_by = list(d.orders.find({"buyer_id": {"$in": ids}}))
    orders_of = list(d.orders.find({"creator_id": {"$in": ids}, "buyer_id": {"$nin": ids}}))
    assets = list(d.assets.find({"creator_id": {"$in": ids}}))
    transfers = list(d.transfers.find({"$or": [{"from_user_id": {"$in": ids}}, {"to_user_id": {"$in": ids}}]}))
    print(f"orders bought={len(orders_by)} sold-to-others={len(orders_of)} assets={len(assets)} transfers={len(transfers)}")
    if not yes:
        print("dry run — re-run with --yes")
        return
    # 1. reverse money that left QA accounts to real creators/platform/affiliates
    for o in orders_by:
        if o["creator_id"] not in ids:
            d.wallets.update_one({"_id": o["creator_id"]}, {"$inc": {"balance": -o["creator_amount"]}})
            d.assets.update_one({"_id": o["asset_id"]}, {"$inc": {"stats.sales": -1, "stats.revenue": -o["price"]}})
        if o.get("affiliate_id") and o["affiliate_id"] not in ids:
            d.wallets.update_one({"_id": o["affiliate_id"]}, {"$inc": {"balance": -o.get("affiliate_amount", 0)}})
        d.wallets.update_one({"_id": PLATFORM_USER_ID}, {"$inc": {"balance": -o["platform_fee"]}})
    # 2. reverse transfers between QA and others
    for t in transfers:
        other_from = t["from_user_id"] not in ids
        other_to = t["to_user_id"] not in ids
        if t["status"] == "pending" and other_from:
            d.wallets.update_one({"_id": t["from_user_id"]}, {"$inc": {"balance": t["amount"], "pending_out": -t["amount"]}})
        elif t["status"] == "accepted" and other_to:
            d.wallets.update_one({"_id": t["to_user_id"]}, {"$inc": {"balance": -t["amount"]}})
        elif t["status"] == "accepted" and other_from:
            d.wallets.update_one({"_id": t["from_user_id"]}, {"$inc": {"balance": t["amount"]}})
    order_ids = [o["_id"] for o in orders_by + orders_of]
    tr_ids = [t["_id"] for t in transfers]
    for a in assets:
        for f in a.get("files", []):
            storage.delete(f["path"])
    d.ledger.delete_many({"$or": [{"user_id": {"$in": ids}}, {"ref_id": {"$in": order_ids + tr_ids}}]})
    d.orders.delete_many({"_id": {"$in": order_ids}})
    d.transfers.delete_many({"_id": {"$in": tr_ids}})
    d.assets.delete_many({"creator_id": {"$in": ids}})
    for c in ("discounts", "asset_views"):
        d[c].delete_many({"creator_id": {"$in": ids}})
    d.api_keys.delete_many({"user_id": {"$in": ids}})
    d.integrations.delete_many({"user_id": {"$in": ids}})
    d.integration_deliveries.delete_many({"user_id": {"$in": ids}})
    d.wallets.delete_many({"_id": {"$in": ids}})
    d.users.delete_many({"_id": {"$in": ids}})
    # 3. recompute the platform wallet from its remaining ledger so it stays exact
    left = list(d.ledger.aggregate([{"$match": {"user_id": PLATFORM_USER_ID}}, {"$group": {"_id": None, "b": {"$sum": "$amount"}}}]))
    d.wallets.update_one({"_id": PLATFORM_USER_ID}, {"$set": {"balance": left[0]["b"] if left else 0}})
    print("removed", len(ids), "QA accounts")


if __name__ == "__main__":
    main()
