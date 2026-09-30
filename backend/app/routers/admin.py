from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..db import get_db
from ..security import require_admin
from ..services.wallet import grant

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


class GrantIn(BaseModel):
    handle: str
    amount: int = Field(gt=0, le=1_000_000)
    memo: str | None = None


@router.post("/grant")
def admin_grant(body: GrantIn):
    d = get_db()
    u = d.users.find_one({"handle": body.handle})
    if not u:
        raise HTTPException(404, "User not found")
    w = grant(d, u["_id"], body.amount, kind="admin_grant", memo=body.memo, is_demo=u.get("is_demo", False))
    return {"handle": body.handle, "balance": w["balance"]}


@router.get("/integrity")
def integrity():
    """Credits are conserved: wallets total == minted total."""
    d = get_db()
    w = list(d.wallets.aggregate([{"$group": {"_id": None, "b": {"$sum": "$balance"}, "p": {"$sum": "$pending_out"}}}]))
    g = list(d.ledger.aggregate([{"$match": {"kind": {"$in": ["grant", "admin_grant"]}}},
                                 {"$group": {"_id": None, "t": {"$sum": "$amount"}}}]))
    pend = list(d.transfers.aggregate([{"$match": {"status": "pending"}},
                                       {"$group": {"_id": None, "t": {"$sum": "$amount"}}}]))
    bal, p = (w[0]["b"], w[0]["p"]) if w else (0, 0)
    minted = g[0]["t"] if g else 0
    pending_sum = pend[0]["t"] if pend else 0
    return {"wallet_balance": bal, "wallet_pending": p, "minted": minted, "pending_transfers_sum": pending_sum,
            "conserved": bal + p == minted, "pending_matches": p == pending_sum,
            "negative_wallets": d.wallets.count_documents({"$or": [{"balance": {"$lt": 0}}, {"pending_out": {"$lt": 0}}]})}
