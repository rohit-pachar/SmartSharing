"""Two-phase peer-to-peer credit transfers.

create  -> sender balance -X, pending_out +X ; transfer.status = pending
accept  -> sender pending_out -X ; receiver balance +X ; status = accepted
reject  -> (receiver) sender pending_out -X, balance +X ; status = rejected
cancel  -> (sender)   same refund ; status = cancelled
expire  -> (system, after expires_at) same refund ; status = expired
"""
from datetime import datetime, timedelta

from pymongo import ReturnDocument
from pymongo.database import Database

from ..config import settings
from ..db import PLATFORM_USER_ID, run_txn
from ..util import new_id, now_utc
from .wallet import WalletError, move


class TransferError(WalletError):
    code = "transfer_error"


class TransferNotFound(TransferError):
    code = "transfer_not_found"


def create_transfer(d: Database, from_user_id: str, to_user_id: str, amount: int, *, memo: str | None = None,
                    idempotency_key: str | None = None, at: datetime | None = None) -> dict:
    if not isinstance(amount, int) or amount <= 0:
        raise TransferError("amount must be a positive integer")
    if amount > settings.max_transfer_credits:
        raise TransferError(f"amount exceeds max of {settings.max_transfer_credits}")
    if from_user_id == to_user_id:
        raise TransferError("cannot transfer to yourself")
    if PLATFORM_USER_ID in (from_user_id, to_user_id):
        raise TransferError("platform account cannot take part in P2P transfers")
    at = at or now_utc()

    if idempotency_key:
        existing = d.transfers.find_one({"from_user_id": from_user_id, "idempotency_key": idempotency_key})
        if existing:
            return existing

    sender = d.users.find_one({"_id": from_user_id})
    receiver = d.users.find_one({"_id": to_user_id})
    if not sender or not receiver or receiver.get("disabled"):
        raise TransferError("unknown sender or receiver")
    is_demo = bool(sender.get("is_demo") and receiver.get("is_demo"))

    t = {
        "_id": new_id("trf"),
        "from_user_id": from_user_id,
        "to_user_id": to_user_id,
        "amount": amount,
        "memo": (memo or "")[:140] or None,
        "status": "pending",
        "idempotency_key": idempotency_key,
        "is_demo": is_demo,
        "created_at": at,
        "expires_at": at + timedelta(hours=settings.transfer_expiry_hours),
        "settled_at": None,
    }

    def _fn(s, d_):
        move(s, d_, from_user_id, balance=-amount, pending=amount, kind="transfer_out_pending",
             ref_type="transfer", ref_id=t["_id"], counterparty_id=to_user_id, memo=t["memo"], at=at, is_demo=is_demo)
        d_.transfers.insert_one(t, session=s)
        return t

    return run_txn(_fn, d)


def _settle(d: Database, transfer_id: str, *, match: dict, new_status: str, at: datetime | None) -> dict:
    at = at or now_utc()

    def _fn(s, d_):
        t = d_.transfers.find_one_and_update(
            {"_id": transfer_id, "status": "pending", **match},
            {"$set": {"status": new_status, "settled_at": at}},
            return_document=ReturnDocument.AFTER,
            session=s,
        )
        if t is None:
            raise TransferNotFound(transfer_id)
        amt, demo = t["amount"], t.get("is_demo", False)
        if new_status == "accepted":
            move(s, d_, t["from_user_id"], pending=-amt, kind="transfer_out_settled", ref_type="transfer",
                 ref_id=t["_id"], counterparty_id=t["to_user_id"], memo=t.get("memo"), at=at, is_demo=demo)
            move(s, d_, t["to_user_id"], balance=amt, kind="transfer_in", ref_type="transfer",
                 ref_id=t["_id"], counterparty_id=t["from_user_id"], memo=t.get("memo"), at=at, is_demo=demo)
        else:
            move(s, d_, t["from_user_id"], balance=amt, pending=-amt, kind=f"transfer_{new_status}_refund",
                 ref_type="transfer", ref_id=t["_id"], counterparty_id=t["to_user_id"], at=at, is_demo=demo)
        return t

    return run_txn(_fn, d)


def accept_transfer(d: Database, transfer_id: str, by_user_id: str, at: datetime | None = None) -> dict:
    return _settle(d, transfer_id, match={"to_user_id": by_user_id}, new_status="accepted", at=at)


def reject_transfer(d: Database, transfer_id: str, by_user_id: str, at: datetime | None = None) -> dict:
    return _settle(d, transfer_id, match={"to_user_id": by_user_id}, new_status="rejected", at=at)


def cancel_transfer(d: Database, transfer_id: str, by_user_id: str, at: datetime | None = None) -> dict:
    return _settle(d, transfer_id, match={"from_user_id": by_user_id}, new_status="cancelled", at=at)


def expire_stale(d: Database, now: datetime | None = None, limit: int = 500) -> int:
    now = now or now_utc()
    n = 0
    for t in d.transfers.find({"status": "pending", "expires_at": {"$lte": now}}, {"_id": 1}).limit(limit):
        try:
            _settle(d, t["_id"], match={}, new_status="expired", at=now)
            n += 1
        except TransferNotFound:
            pass  # settled concurrently
    return n
