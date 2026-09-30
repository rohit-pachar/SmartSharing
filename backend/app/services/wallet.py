"""Wallet + append-only ledger.

Every balance change goes through `move()` inside a Mongo transaction and writes one ledger row.
Wallet fields:
  balance      spendable credits
  pending_out  credits locked in outgoing transfers awaiting the receiver's accept
Invariant: sum(balance + pending_out) over all wallets == sum of all 'grant' ledger amounts.
"""
from datetime import datetime

from pymongo import ReturnDocument
from pymongo.client_session import ClientSession
from pymongo.database import Database

from ..util import new_id, now_utc


class WalletError(Exception):
    code = "wallet_error"


class InsufficientFunds(WalletError):
    code = "insufficient_funds"


class WalletNotFound(WalletError):
    code = "wallet_not_found"


def create_wallet(d: Database, user_id: str, at: datetime | None = None, session: ClientSession | None = None):
    at = at or now_utc()
    d.wallets.insert_one({"_id": user_id, "balance": 0, "pending_out": 0, "created_at": at, "updated_at": at},
                         session=session)


def move(
    s: ClientSession,
    d: Database,
    user_id: str,
    *,
    balance: int = 0,
    pending: int = 0,
    kind: str,
    ref_type: str | None = None,
    ref_id: str | None = None,
    memo: str | None = None,
    counterparty_id: str | None = None,
    at: datetime | None = None,
    is_demo: bool = False,
) -> dict:
    """Apply a balance/pending delta atomically (guarded against going negative) and log it."""
    if not isinstance(balance, int) or not isinstance(pending, int):
        raise TypeError("credit amounts must be integers")
    at = at or now_utc()
    flt: dict = {"_id": user_id}
    if balance < 0:
        flt["balance"] = {"$gte": -balance}
    if pending < 0:
        flt["pending_out"] = {"$gte": -pending}
    w = d.wallets.find_one_and_update(
        flt,
        {"$inc": {"balance": balance, "pending_out": pending}, "$set": {"updated_at": at}},
        return_document=ReturnDocument.AFTER,
        session=s,
    )
    if w is None:
        if d.wallets.count_documents({"_id": user_id}, session=s) == 0:
            raise WalletNotFound(user_id)
        raise InsufficientFunds(user_id)
    entry = {
        "_id": new_id("led"),
        "user_id": user_id,
        "kind": kind,
        "amount": balance,
        "pending_delta": pending,
        "balance_after": w["balance"],
        "pending_after": w["pending_out"],
        "ref_type": ref_type,
        "ref_id": ref_id,
        "counterparty_id": counterparty_id,
        "memo": memo,
        "is_demo": is_demo,
        "created_at": at,
    }
    d.ledger.insert_one(entry, session=s)
    return w


def grant(d: Database, user_id: str, amount: int, *, kind: str = "grant", memo: str | None = None,
          at: datetime | None = None, is_demo: bool = False, session: ClientSession | None = None) -> dict:
    """Mint credits into a wallet (signup bonus, demo seeding, admin top-up)."""
    if amount <= 0:
        raise ValueError("grant amount must be positive")

    def _fn(s, d_):
        return move(s, d_, user_id, balance=amount, kind=kind, ref_type="grant", memo=memo, at=at, is_demo=is_demo)

    if session is not None:
        return _fn(session, d)
    from ..db import run_txn
    return run_txn(_fn, d)


def get_wallet(d: Database, user_id: str) -> dict | None:
    return d.wallets.find_one({"_id": user_id})
