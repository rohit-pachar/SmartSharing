# SmartSharing backend

FastAPI + MongoDB (Atlas). Off-chain credits: wallets, two-phase P2P transfers, asset licences.

## Layout
    app/            API (routers/, services/ wallet · transfers · market · users)
    seed/           demo data + seed_demo.py / purge_demo.py   (demo only)
    cron/           demo activity simulator + systemd units      (demo only, separate from app)
    tests/          pytest against the smartsharing_test database

## Run
    python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
    cp .env.example .env   # fill MONGO_URL, JWT_SECRET, ADMIN_TOKEN
    .venv/bin/uvicorn app.main:app --port 8000      # docs at /docs
    .venv/bin/pytest -q

## Credits model
- wallet: `balance` (spendable) + `pending_out` (locked in unaccepted transfers)
- transfer: create (balance→pending) → accept (pending→receiver) | reject/cancel/expire (refund)
- purchase: buyer −price, creator +88%, platform wallet +12% (PLATFORM_FEE_PCT)
- every change is a Mongo transaction + a `ledger` row; `GET /api/admin/integrity` checks conservation

## Endpoints (prefix /api)
    POST auth/register  auth/login   GET auth/me
    GET  wallet  wallet/ledger
    POST transfers  transfers/{id}/accept|reject|cancel   GET transfers?direction=in|out|all
    GET  categories  assets?q=&category=&sort=new|popular|price_asc|price_desc  assets/{id}
    POST assets  orders   GET me/purchases  me/sales  me/assets  users/{handle}
    GET  activity  stats      (public feed/counters; every item carries is_demo)
    POST admin/grant   GET admin/integrity     (header x-admin-token)

## Demo community
    .venv/bin/python -m seed.seed_demo --users 130 --avg-credits 5000 [--reset]
    ./cron/install.sh                     # API service + 3 timers
    ./cron/ctl.sh status|pause [min]|resume|logs [n]|uninstall

Timers: transfers every ~3 min (1–5 sends), accept every ~1 min, purchases every ~7 min (0–3 buys).
All demo users/assets/orders/transfers/ledger rows have `is_demo: true`, emails `@demo.smartsharing.in`,
and no password (they cannot log in). Before real launch:

    ./cron/ctl.sh uninstall && .venv/bin/python -m seed.purge_demo --yes
