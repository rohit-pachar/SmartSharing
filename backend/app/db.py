from functools import lru_cache

from pymongo import ASCENDING, DESCENDING, TEXT, MongoClient
from pymongo.database import Database

from .config import settings

PLATFORM_USER_ID = "usr_platform"


@lru_cache
def client() -> MongoClient:
    return MongoClient(
        settings.mongo_url,
        serverSelectionTimeoutMS=20_000,
        tz_aware=True,
        appname="smartsharing-api",
    )


def get_db(name: str | None = None) -> Database:
    return client()[name or settings.mongo_db]


def run_txn(fn, db: Database | None = None):
    """Run fn(session, db) inside a multi-document transaction (auto-retried on transient errors)."""
    d = db if db is not None else get_db()
    with d.client.start_session() as s:
        return s.with_transaction(lambda sess: fn(sess, d))


def ensure_indexes(d: Database | None = None) -> None:
    d = d if d is not None else get_db()
    d.users.create_index("email", unique=True, sparse=True)
    d.users.create_index("handle", unique=True)
    d.users.create_index([("is_demo", ASCENDING), ("is_creator", ASCENDING)])

    d.ledger.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    d.ledger.create_index([("ref_type", ASCENDING), ("ref_id", ASCENDING)])

    d.transfers.create_index([("to_user_id", ASCENDING), ("status", ASCENDING), ("created_at", DESCENDING)])
    d.transfers.create_index([("from_user_id", ASCENDING), ("created_at", DESCENDING)])
    d.transfers.create_index([("status", ASCENDING), ("expires_at", ASCENDING)])
    d.transfers.create_index([("status", ASCENDING), ("settled_at", DESCENDING)])
    d.transfers.create_index(
        [("from_user_id", ASCENDING), ("idempotency_key", ASCENDING)],
        unique=True,
        partialFilterExpression={"idempotency_key": {"$type": "string"}},
    )

    d.assets.create_index([("status", ASCENDING), ("category", ASCENDING), ("created_at", DESCENDING)])
    d.assets.create_index("creator_id")
    d.assets.create_index([("name", TEXT), ("description", TEXT), ("creator", TEXT), ("category", TEXT)])

    d.orders.create_index([("buyer_id", ASCENDING), ("asset_id", ASCENDING), ("license_id", ASCENDING)], unique=True)
    d.orders.create_index([("created_at", DESCENDING)])
    d.orders.create_index([("creator_id", ASCENDING), ("created_at", DESCENDING)])


def ensure_platform_account(d: Database | None = None) -> None:
    from datetime import datetime, timezone

    d = d if d is not None else get_db()
    now = datetime.now(timezone.utc)
    d.users.update_one(
        {"_id": PLATFORM_USER_ID},
        {"$setOnInsert": {"handle": "smartsharing", "full_name": "SmartSharing Platform", "is_system": True,
                          "is_demo": False, "is_creator": False, "created_at": now}},
        upsert=True,
    )
    d.wallets.update_one(
        {"_id": PLATFORM_USER_ID},
        {"$setOnInsert": {"balance": 0, "pending_out": 0, "created_at": now, "updated_at": now}},
        upsert=True,
    )
