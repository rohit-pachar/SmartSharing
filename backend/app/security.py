from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings
from .db import get_db

_bearer = HTTPBearer(auto_error=False)


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    return bcrypt.checkpw(pw.encode(), hashed.encode())


def create_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": user_id, "typ": "session", "iat": now, "exp": now + timedelta(hours=settings.jwt_ttl_hours)}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def create_download_token(order_id: str, file_idx: int, user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": user_id, "typ": "dl", "ord": order_id, "f": file_idx, "exp": now + timedelta(minutes=10)}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def read_download_token(tok: str) -> dict:
    try:
        p = jwt.decode(tok, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Download link expired. Request a new one from your library.")
    if p.get("typ") != "dl":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid download link")
    return p


def _user_from_token(tok: str, allow_api_key: bool) -> dict:
    d = get_db()
    user = None
    if tok.startswith("ssk_"):
        if not allow_api_key:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "API keys cannot perform this action; log in instead")
        from .services.tools import user_for_api_key
        user = user_for_api_key(d, tok)
    else:
        try:
            payload = jwt.decode(tok, settings.jwt_secret, algorithms=["HS256"])
        except jwt.PyJWTError:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
        if payload.get("typ", "session") != "session":
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
        user = d.users.find_one({"_id": payload.get("sub")})
    if not user or user.get("is_system") or user.get("disabled"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    """Session JWT or creator API key (ssk_...). For reads and studio management."""
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    return _user_from_token(creds.credentials, allow_api_key=True)


def session_user(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    """Session JWT only. For anything that moves credits or manages credentials."""
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    return _user_from_token(creds.credentials, allow_api_key=False)


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    if not settings.admin_token or x_admin_token != settings.admin_token:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin token required")
