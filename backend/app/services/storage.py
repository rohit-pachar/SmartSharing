"""Deliverable file storage on local disk (backend/storage/). Swap for S3/R2 later behind the same functions."""
import hashlib
import mimetypes
import os
import re
from pathlib import Path

from ..config import BACKEND_DIR

STORAGE = Path(os.environ.get("SS_STORAGE_DIR", BACKEND_DIR / "storage"))
MAX_BYTES = 50 * 1024 * 1024
ALLOWED_EXT = {".zip", ".pdf", ".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".mp4", ".mov", ".cube", ".xmp",
               ".json", ".csv", ".xlsx", ".docx", ".txt", ".md", ".psd", ".ai", ".fig", ".blend", ".glb", ".fbx",
               ".ttf", ".otf", ".woff2", ".lut", ".aep", ".prproj", ".mogrt", ".drx", ".abr", ".brushset"}


def safe_name(name: str) -> str:
    base = os.path.basename(name or "file")
    base = re.sub(r"[^A-Za-z0-9._ -]+", "_", base).strip(" .")[:120]
    return base or "file"


def check_ext(name: str) -> None:
    ext = os.path.splitext(name)[1].lower()
    if ext not in ALLOWED_EXT:
        raise ValueError(f"file type {ext or '(none)'} not allowed")


def save_bytes(asset_id: str, name: str, data: bytes) -> dict:
    if len(data) > MAX_BYTES:
        raise ValueError("file is larger than 50 MB")
    name = safe_name(name)
    check_ext(name)
    digest = hashlib.sha256(data).hexdigest()
    rel = Path(asset_id) / f"{digest[:16]}-{name}"
    path = STORAGE / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {"name": name, "path": str(rel), "size": len(data), "sha256": digest,
            "mime": mimetypes.guess_type(name)[0] or "application/octet-stream"}


def abs_path(rel: str) -> Path:
    p = (STORAGE / rel).resolve()
    if STORAGE.resolve() not in p.parents:
        raise ValueError("bad path")
    return p


def delete(rel: str) -> None:
    try:
        abs_path(rel).unlink(missing_ok=True)
    except ValueError:
        pass
