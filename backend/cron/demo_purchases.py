"""Demo purchase loop: demo members buy licences for demo assets with credits.

    python cron/demo_purchases.py [--count N]

Buyer pays price; creator receives (100 - PLATFORM_FEE_PCT)%; the platform wallet gets the fee.
Popular assets are bought more often; buyers only buy what they can afford and don't already own.
"""
import argparse
import random
import time

from common import db, demo_users, ensure_activity_weights, setup_logging, single_instance, weighted_pick

from app.services.market import AlreadyOwned, license_options, purchase
from app.services.wallet import WalletError

log = setup_logging("demo-purchases")

LICENSE_WEIGHTS = {"personal": 6, "commercial": 3, "studio": 1, "week": 7, "month": 3}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=None, help="purchases this run (default random 0-3)")
    ap.add_argument("--max-frac", type=float, default=0.35, help="don't spend more than this share of balance")
    ap.add_argument("--jitter", type=float, default=20.0)
    args = ap.parse_args()

    rng = random.Random()
    d = db()
    ensure_activity_weights(d, rng)
    assets = list(d.assets.find({"status": "published", "is_demo": True}))
    buyers = demo_users(d, min_balance=200)
    if not assets or not buyers:
        log.warning("no demo assets/buyers; run seed/seed_demo.py first")
        return
    # stable per-asset popularity so some become bestsellers
    for a in assets:
        a["_w"] = random.Random(a["_id"]).paretovariate(1.3) + a.get("stats", {}).get("sales", 0) * 0.05

    n = args.count if args.count is not None else rng.choices([0, 1, 2, 3], weights=[2, 5, 3, 1])[0]
    ok = 0
    for i in range(n):
        for _attempt in range(6):
            b = weighted_pick(rng, buyers)[0]
            bal = d.wallets.find_one({"_id": b["_id"]})["balance"]
            a = rng.choices(assets, weights=[x["_w"] for x in assets])[0]
            if a["creator_id"] == b["_id"]:
                continue
            opts = [o for o in license_options(a) if o["price"] <= bal * args.max_frac]
            if not opts:
                continue
            opt = rng.choices(opts, weights=[LICENSE_WEIGHTS.get(o["id"], 1) for o in opts])[0]
            try:
                o = purchase(d, b["_id"], a["_id"], opt["id"])
                ok += 1
                log.info("%s bought %s (%s) for %d  receipt=%s", b["full_name"], a["name"], opt["name"],
                         o["price"], o["receipt"])
                break
            except AlreadyOwned:
                continue
            except WalletError as e:
                log.info("skip: %s", e.code)
                continue
        if i < n - 1 and args.jitter:
            time.sleep(rng.uniform(0, args.jitter))
    log.info("run complete: %d/%d purchases", ok, n)


if __name__ == "__main__":
    with single_instance("demo-purchases"):
        main()
