import os

os.environ["MONGO_DB"] = "smartsharing_test"
os.environ["ADMIN_TOKEN"] = "test-admin"
os.environ["SIGNUP_BONUS_CREDITS"] = "0"
os.environ.setdefault("SS_STORAGE_DIR", "/home/ubuntu/.hermes/cache/scratch/ss_test_storage")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import ensure_indexes, ensure_platform_account, get_db  # noqa: E402


@pytest.fixture(scope="session")
def d():
    db = get_db("smartsharing_test")
    db.client.drop_database("smartsharing_test")
    ensure_indexes(db)
    ensure_platform_account(db)
    yield db
    db.client.drop_database("smartsharing_test")


@pytest.fixture(scope="session")
def client(d):
    from app.main import app
    with TestClient(app) as c:
        yield c
