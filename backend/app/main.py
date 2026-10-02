from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi import Query
from fastapi.responses import Response

from .services.storage import STORAGE

from .config import settings
from .db import ensure_indexes, ensure_platform_account, get_db
from .routers import admin, auth, market, studio, wallet


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
    expose_headers=["Content-Disposition"],
)

for r in (auth.router, wallet.router, market.router, studio.router, admin.router):
    app.include_router(r, prefix="/api")


@app.get("/api/health")
def health():
    get_db().command("ping")
    return {"ok": True}


(STORAGE / "covers").mkdir(parents=True, exist_ok=True)
app.mount("/media/covers", StaticFiles(directory=STORAGE / "covers"), name="covers")


@app.get("/api/qr")
def qr(data: str = Query(..., max_length=600), scale: int = Query(8, ge=2, le=20)):
    """QR code (SVG) for share links, UTM links and payment requests."""
    import io

    import segno
    buf = io.BytesIO()
    segno.make(data, error="m").save(buf, kind="svg", scale=scale, border=2, dark="#0b0e13", light="#ffffff")
    return Response(buf.getvalue(), media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"})
