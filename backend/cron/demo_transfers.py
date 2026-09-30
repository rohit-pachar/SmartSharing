"""Demo transfer loop: each run, a few demo members send small credit amounts to other demo members.

    python cron/demo_transfers.py [--count N] [--max-frac 0.05]

Transfers are two-phase: this creates PENDING transfers; cron/demo_accept.py accepts them.
Amounts are a small fraction of the sender's balance so wallets never drain.
"""
import argparse
import random
import time

from common import db, demo_users, ensure_activity_weights, setup_logging, single_instance, weighted_pick

from app.services.transfers import create_transfer
from app.services.wallet import WalletError
from seed.data import TRANSFER_MEMOS

log = setup_logging("demo-transfers")


def pick_amount(rng: random.Random, balance: int, max_frac: float) -> int:
    cap = max(10, int(balance * max_frac))
    # people send round-ish numbers
    raw = rng.choice([rng.randint(10, 100), rng.randint(50, 300), rng.randint(100, cap)])
    step = 50 if raw >= 200 else 10 if raw >= 50 else 5
    return max(5, min(cap, int(round(raw / step) * step)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=None, help="transfers this run (default random 1-5)")
    ap.add_argument("--max-frac", type=float, default=0.05, help="max fraction of sender balance per transfer")
    ap.add_argument("--min-balance", type=int, default=300, help="senders need at least this balance")
    ap.add_argument("--jitter", type=float, default=20.0, help="max seconds to wait between sends")
    args = ap.parse_args()

    rng = random.Random()
    d = db()
    ensure_activity_weights(d, rng)
    senders = demo_users(d, min_balance=args.min_balance)
    everyone = demo_users(d)
    if len(everyone) < 2 or not senders:
        log.warning("not enough demo users with balance; run seed/seed_demo.py first")
        return

    n = args.count if args.count is not None else rng.randint(1, 5)
    ok = 0
    for i in range(n):
        s = weighted_pick(rng, senders)[0]
        # prefer repeat counterparties a bit (friends/collaborators) via a stable per-user circle
        circle_rng = random.Random(s["_id"])
        circle = circle_rng.sample(everyone, min(12, len(everyone)))
        pool = circle if rng.random() < 0.7 else everyone
        r = rng.choice([u for u in pool if u["_id"] != s["_id"]])
        bal = d.wallets.find_one({"_id": s["_id"]})["balance"]
        amt = pick_amount(rng, bal, args.max_frac)
        try:
            t = create_transfer(d, s["_id"], r["_id"], amt, memo=rng.choice(TRANSFER_MEMOS))
            ok += 1
            log.info("sent %s -> %s  %d credits  (%s)", s["full_name"], r["full_name"], amt, t["_id"])
        except WalletError as e:
            log.info("skip %s -> %s %d: %s", s["full_name"], r["full_name"], amt, e.code)
        if i < n - 1 and args.jitter:
            time.sleep(rng.uniform(0, args.jitter))
    log.info("run complete: %d/%d transfers created", ok, n)


if __name__ == "__main__":
    with single_instance("demo-transfers"):
        main()
