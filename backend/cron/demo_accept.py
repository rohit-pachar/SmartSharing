"""Demo accept loop: accept pending transfers addressed to demo members; expire stale ones.

    python cron/demo_accept.py [--min-age 30] [--reject-rate 0.02]

Run at least as often as demo_transfers.py or pending credit piles up locked in senders' pending_out.
A small random delay (min-age) makes accepts look like a person opening the app, not instant.
"""
import argparse
import random
from datetime import timedelta

from common import db, setup_logging, single_instance

from app.services.transfers import TransferNotFound, accept_transfer, expire_stale, reject_transfer
from app.util import now_utc

log = setup_logging("demo-accept")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-age", type=int, default=30, help="only accept transfers older than N seconds")
    ap.add_argument("--reject-rate", type=float, default=0.02, help="fraction of transfers declined")
    ap.add_argument("--limit", type=int, default=200)
    args = ap.parse_args()

    rng = random.Random()
    d = db()
    now = now_utc()
    demo_ids = [u["_id"] for u in d.users.find({"is_demo": True}, {"_id": 1})]
    q = {"status": "pending", "is_demo": True, "to_user_id": {"$in": demo_ids},
         "created_at": {"$lte": now - timedelta(seconds=args.min_age)}}
    accepted = rejected = 0
    for t in d.transfers.find(q).sort("created_at", 1).limit(args.limit):
        try:
            if rng.random() < args.reject_rate:
                reject_transfer(d, t["_id"], t["to_user_id"])
                rejected += 1
            else:
                accept_transfer(d, t["_id"], t["to_user_id"])
                accepted += 1
        except TransferNotFound:
            continue
    expired = expire_stale(d)
    left = d.transfers.count_documents({"status": "pending", "is_demo": True})
    log.info("accepted=%d rejected=%d expired=%d still_pending=%d", accepted, rejected, expired, left)


if __name__ == "__main__":
    with single_instance("demo-accept"):
        main()
