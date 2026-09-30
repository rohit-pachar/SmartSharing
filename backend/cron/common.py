"""Shared helpers for the demo activity simulator. Operates ONLY on is_demo=True users."""
import fcntl
import logging
import os
import random
import sys
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import get_db  # noqa: E402

LOCK_DIR = Path(os.environ.get("SIM_LOCK_DIR", "/tmp"))


def setup_logging(name: str) -> logging.Logger:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s", stream=sys.stdout)
    return logging.getLogger(name)


@contextmanager
def single_instance(name: str):
    """Skip this run if the previous one is still going (timer overlap)."""
    path = LOCK_DIR / f"smartsharing-{name}.lock"
    fh = open(path, "w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print(f"{name}: previous run still active, skipping")
        sys.exit(0)
    try:
        yield
    finally:
        fcntl.flock(fh, fcntl.LOCK_UN)
        fh.close()


def demo_users(d, min_balance: int = 0) -> list[dict]:
    ids = [u["_id"] for u in d.users.find({"is_demo": True}, {"_id": 1})]
    if not ids:
        return []
    wallets = {w["_id"]: w for w in d.wallets.find({"_id": {"$in": ids}, "balance": {"$gte": min_balance}})}
    users = list(d.users.find({"_id": {"$in": list(wallets)}}))
    for u in users:
        u["_wallet"] = wallets[u["_id"]]
    return users


def weighted_pick(rng: random.Random, users: list[dict], key="activity", k: int = 1) -> list[dict]:
    """Some members are more active than others -> Pareto-ish weights stored on the user."""
    weights = [u.get(key) or 1.0 for u in users]
    return rng.choices(users, weights=weights, k=k)


def ensure_activity_weights(d, rng: random.Random):
    for u in d.users.find({"is_demo": True, "activity": {"$exists": False}}, {"_id": 1}):
        d.users.update_one({"_id": u["_id"]}, {"$set": {"activity": round(rng.paretovariate(1.6), 3)}})


db = get_db
