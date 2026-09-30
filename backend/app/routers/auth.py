from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field
from pymongo.errors import DuplicateKeyError

from ..db import get_db
from ..security import create_token, current_user, hash_password, verify_password
from ..services.users import create_user, public_profile
from fastapi import Depends

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


def _token_response(u: dict) -> dict:
    return {"access_token": create_token(u["_id"]), "token_type": "bearer", "user": public_profile(u)}


@router.post("/register", status_code=201)
def register(body: RegisterIn):
    d = get_db()
    try:
        u = create_user(d, full_name=body.full_name, email=body.email, password_hash=hash_password(body.password))
    except DuplicateKeyError:
        raise HTTPException(409, "An account with this email already exists")
    return _token_response(u)


@router.post("/login")
def login(body: LoginIn):
    u = get_db().users.find_one({"email": body.email.lower()})
    if not u or u.get("is_system") or not verify_password(body.password, u.get("password_hash")):
        raise HTTPException(401, "Invalid email or password")
    return _token_response(u)


@router.get("/me")
def me(user: dict = Depends(current_user)):
    return {**public_profile(user), "email": user.get("email")}
