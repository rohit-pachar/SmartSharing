from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    mongo_url: str
    mongo_db: str = "smartsharing"

    jwt_secret: str
    jwt_ttl_hours: int = 72
    admin_token: str = ""

    # Marketplace economics (credits are integers; 1 credit is displayed like 1 INR in the UI)
    platform_fee_pct: int = 12
    signup_bonus_credits: int = 0
    max_transfer_credits: int = 100_000
    transfer_expiry_hours: int = 72

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000,https://smartsharing.in,https://www.smartsharing.in"
    cors_origin_regex: str = r"https://smartsharing(-[a-z0-9-]+)?\.vercel\.app"


settings = Settings()
