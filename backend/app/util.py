import re
import secrets
from datetime import datetime, timezone


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:60] or "item"


def initials(full_name: str) -> str:
    parts = [p for p in full_name.replace(".", " ").split() if p]
    if not parts:
        return "?"
    return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()


def public_name(full_name: str) -> str:
    """'Aarav Mehta' -> 'Aarav M.' for activity feeds."""
    parts = full_name.split()
    return parts[0] if len(parts) == 1 else f"{parts[0]} {parts[-1][0]}."


def clean(doc: dict | None) -> dict | None:
    """Mongo doc -> JSON-friendly dict (_id -> id, datetimes -> ISO strings)."""
    if doc is None:
        return None
    out = {}
    for k, v in doc.items():
        if k in ("password_hash",):
            continue
        key = "id" if k == "_id" else k
        if isinstance(v, datetime):
            v = v.astimezone(timezone.utc).isoformat()
        elif isinstance(v, dict):
            v = clean(v)
        out[key] = v
    return out
