"""Seed the SmartSharing demo community.

    python -m seed.seed_demo                      # 130 users, ~5000 credits each, demo assets
    python -m seed.seed_demo --users 130 --avg-credits 5000 --reset

Every user, wallet grant, asset, order and transfer created here or by the simulator has is_demo=True,
and demo emails use the reserved @demo.smartsharing.in domain. `--reset` deletes ONLY is_demo records.
Real users are never touched. To remove demo data before going live, see seed/purge_demo.py.
"""
import argparse
import random
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import ensure_indexes, ensure_platform_account, get_db  # noqa: E402
from app.services.market import create_asset  # noqa: E402
from app.services.users import create_user  # noqa: E402
from app.util import now_utc, slugify  # noqa: E402
from seed import data  # noqa: E402
from seed.purge_demo import purge  # noqa: E402

DEMO_EMAIL_DOMAIN = "demo.smartsharing.in"

# Keep the three original frontend creators attached to their launch assets.
LAUNCH_CREATORS = {"Prism Material Kit": ("Aarav Mehta", "3D designer", "Bengaluru", "India"),
                   "Brand-to-Content Engine": ("Mira Sen", "Workflow creator", "Kolkata", "India"),
                   "Fluid Motion Vol. 01": ("Rohan Das", "Motion artist", "Pune", "India")}
LAUNCH_IDS = {"Prism Material Kit": "prism", "Brand-to-Content Engine": "flowstate", "Fluid Motion Vol. 01": "fluid"}


def gen_people(n: int, rng: random.Random) -> list[dict]:
    people, seen = [], set()
    for first, last, _, _ in [(*v[0].split(), v[2], v[3]) for v in LAUNCH_CREATORS.values()]:
        seen.add(f"{first} {last}")
    n_intl = max(1, round(n * 0.15))
    intl = rng.sample(data.INTERNATIONAL, min(n_intl, len(data.INTERNATIONAL)))
    for first, last, city, country in intl:
        people.append({"full_name": f"{first} {last}", "city": city, "country": country})
        seen.add(f"{first} {last}")
    while len(people) < n:
        first = rng.choice(data.INDIAN_FIRST_M if rng.random() < 0.52 else data.INDIAN_FIRST_F)
        last = rng.choice(data.INDIAN_LAST)
        name = f"{first} {last}"
        if name in seen:
            continue
        seen.add(name)
        city, _state = rng.choice(data.INDIAN_CITIES)
        people.append({"full_name": name, "city": city, "country": "India"})
    rng.shuffle(people)
    return people


def credit_amounts(n: int, avg: int, rng: random.Random) -> list[int]:
    """Varied balances (roughly 40%–160% of avg, rounded to 50) that sum to exactly n*avg."""
    raw = [rng.lognormvariate(0, 0.35) for _ in range(n)]
    scale = avg * n / sum(raw)
    vals = [max(500, int(round(r * scale / 50) * 50)) for r in raw]
    diff = avg * n - sum(vals)
    i = 0
    while diff != 0:
        step = 50 if diff > 0 else -50
        if abs(diff) < 50:
            step = diff
        if vals[i % n] + step >= 500:
            vals[i % n] += step
            diff -= step
        i += 1
    return vals


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--users", type=int, default=130)
    ap.add_argument("--avg-credits", type=int, default=5000, help="average opening balance per demo wallet")
    ap.add_argument("--creators", type=int, default=30, help="how many demo users list assets")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--reset", action="store_true", help="delete existing demo data first")
    args = ap.parse_args()

    d = get_db()
    ensure_indexes(d)
    ensure_platform_account(d)
    rng = random.Random(args.seed)

    if d.users.count_documents({"is_demo": True}):
        if not args.reset:
            print("Demo data already exists. Re-run with --reset to rebuild it.")
            return
        print("Purging existing demo data:", purge(d))

    now = now_utc()
    n_launch = len(LAUNCH_CREATORS)
    people = gen_people(args.users - n_launch, rng)
    credits = credit_amounts(args.users, args.avg_credits, rng)

    users = []
    # launch creators first
    for asset_name, (name, role, city, country) in LAUNCH_CREATORS.items():
        people.insert(0, {"full_name": name, "city": city, "country": country, "role": role, "_launch": asset_name})

    for i, p in enumerate(people[: args.users]):
        joined = now - timedelta(days=rng.randint(3, 75), hours=rng.randint(0, 23), minutes=rng.randint(0, 59))
        handle_base = slugify(p["full_name"]).replace("-", ".")
        u = create_user(
            d,
            full_name=p["full_name"],
            email=f"{handle_base}.{i}@{DEMO_EMAIL_DOMAIN}",
            password_hash=None,  # demo accounts cannot log in
            is_demo=True,
            at=joined,
            opening_credits=credits[i],
            profile={"city": p["city"], "country": p["country"], "role": p.get("role") or rng.choice(data.MEMBER_ROLES)},
        )
        u["_launch"] = p.get("_launch")
        users.append(u)

    # --- creators & assets ---
    launch_by_asset = {u["_launch"]: u for u in users if u.get("_launch")}
    pool = [u for u in users if not u.get("_launch")]
    creators = list(launch_by_asset.values()) + rng.sample(pool, min(args.creators - n_launch, len(pool)))
    by_cat: dict[str, list] = {c: [] for c in data.CREATOR_ROLES}
    for idx, c in enumerate(creators[n_launch:]):
        cat = list(data.CREATOR_ROLES)[idx % 3]
        role = rng.choice(data.CREATOR_ROLES[cat])
        d.users.update_one({"_id": c["_id"]}, {"$set": {"role": role}})
        c["role"] = role
        by_cat[cat].append(c)

    n_assets = 0
    for name, cat, kind, price, fmt, desc, inc in data.ASSETS:
        creator = launch_by_asset.get(name) or rng.choice(by_cat[cat])
        listed = max(creator["created_at"] + timedelta(hours=2),
                     now - timedelta(days=rng.randint(1, 60), hours=rng.randint(0, 23)))
        create_asset(d, creator, name=name, category=cat, description=desc, price=price, kind=kind, format=fmt,
                     includes=inc, at=listed, asset_id=LAUNCH_IDS.get(name))
        n_assets += 1

    total = sum(w["balance"] for w in d.wallets.find({"_id": {"$in": [u["_id"] for u in users]}}))
    intl = sum(1 for u in users if u.get("country") != "India")
    print(f"Seeded {len(users)} demo users ({intl} international), {len(creators)} creators, {n_assets} assets.")
    print(f"Total demo credits: {total:,}  (avg {total // len(users):,}, min {min(credits):,}, max {max(credits):,})")


if __name__ == "__main__":
    main()
