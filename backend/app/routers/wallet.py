from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..db import get_db
from ..security import session_user as current_user
from ..services import transfers as tsvc
from ..util import clean

router = APIRouter(tags=["wallet"])


@router.get("/wallet")
def my_wallet(user: dict = Depends(current_user)):
    w = get_db().wallets.find_one({"_id": user["_id"]})
    return {"user_id": user["_id"], "balance": w["balance"], "pending_out": w["pending_out"],
            "updated_at": w["updated_at"].isoformat()}


@router.get("/wallet/ledger")
def my_ledger(user: dict = Depends(current_user), limit: int = Query(50, le=200), before: str | None = None):
    q: dict = {"user_id": user["_id"]}
    if before:
        q["_id"] = {"$lt": before}
    rows = list(get_db().ledger.find(q).sort("created_at", -1).limit(limit))
    return {"items": [clean(r) for r in rows]}


class TransferIn(BaseModel):
    to: str = Field(description="recipient handle or user id")
    amount: int = Field(gt=0)
    memo: str | None = Field(default=None, max_length=140)
    idempotency_key: str | None = Field(default=None, max_length=64)


def _resolve(d, who: str) -> dict:
    u = d.users.find_one({"$or": [{"_id": who}, {"handle": who.lstrip("@").lower()}], "is_system": {"$ne": True}})
    if not u:
        raise HTTPException(404, "Recipient not found")
    return u


@router.post("/transfers", status_code=201)
def send(body: TransferIn, user: dict = Depends(current_user)):
    d = get_db()
    to = _resolve(d, body.to)
    try:
        t = tsvc.create_transfer(d, user["_id"], to["_id"], body.amount, memo=body.memo,
                                 idempotency_key=body.idempotency_key)
    except tsvc.WalletError as e:
        raise HTTPException(400, {"code": e.code, "message": str(e)})
    return clean(t)


@router.get("/transfers")
def list_transfers(user: dict = Depends(current_user), direction: str = Query("all", pattern="^(in|out|all)$"),
                   status: str | None = None, limit: int = Query(50, le=200)):
    uid = user["_id"]
    q: dict = {"in": {"to_user_id": uid}, "out": {"from_user_id": uid},
               "all": {"$or": [{"to_user_id": uid}, {"from_user_id": uid}]}}[direction]
    if status:
        q["status"] = status
    rows = list(get_db().transfers.find(q).sort("created_at", -1).limit(limit))
    return {"items": [clean(r) for r in rows]}


def _act(fn, transfer_id: str, user: dict):
    try:
        return clean(fn(get_db(), transfer_id, user["_id"]))
    except tsvc.TransferNotFound:
        raise HTTPException(404, "No pending transfer with that id for you")
    except tsvc.WalletError as e:
        raise HTTPException(400, {"code": e.code, "message": str(e)})


@router.post("/transfers/{transfer_id}/accept")
def accept(transfer_id: str, user: dict = Depends(current_user)):
    return _act(tsvc.accept_transfer, transfer_id, user)


@router.post("/transfers/{transfer_id}/reject")
def reject(transfer_id: str, user: dict = Depends(current_user)):
    return _act(tsvc.reject_transfer, transfer_id, user)


@router.post("/transfers/{transfer_id}/cancel")
def cancel(transfer_id: str, user: dict = Depends(current_user)):
    return _act(tsvc.cancel_transfer, transfer_id, user)
