from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import ensure_indexes, ensure_platform_account, get_db
from .routers import admin, auth, market, wallet


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_indexes()
    ensure_platform_account()
    yield


app = FastAPI(title="SmartSharing API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_origin_regex=settings.cors_origin_regex or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (auth.router, wallet.router, market.router, admin.router):
    app.include_router(r, prefix="/api")


@app.get("/api/health")
def health():
    get_db().command("ping")
    return {"ok": True}
