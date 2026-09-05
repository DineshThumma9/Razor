


import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(_ENV_FILE, ".env"), extra="ignore")

    mistral_api_key: str = Field(default="", alias="MISTRAL_API_KEY")
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = Field(default="", alias="RAZORPAY_WEBHOOK_SECRET")
    eleven_api_key: str = Field(default="", alias="ELEVENLABS_API_KEY")
    twilo_account_sid: str = Field(default="", alias="TWILO_ACCOUNT_SID")
    twilo_auth_token: str = ""
    resend_api_key: str = ""
    twilo_whatsapp_number: str = ""
    model: str = ""
    max_discount: int = Field(default=30, alias="MAX_DISCOUNT_ALLOWED")
    min_discount: int = Field(default=5, alias="MIN_DISCOUNT_ALLOWED")
    redis_url: str = Field(default="", alias="REDIS_URL")
    postgres_url: str = ""
    database_url: str = ""
    db_pool_size: int = 50
    db_max_overflow: int = 50
    db_pool_timeout: int = 30
    db_pool_recycle: int = 1800
    db_checkpointer_pool_size: int = 20
    frontend_url: str = ""
    backend_url: str = ""
    demo_mode: bool = False
    port: int = 8000
    max_grace_period: int = 7


settings = Settings()
if settings.mistral_api_key and "MISTRAL_API_KEY" not in os.environ:
    os.environ["MISTRAL_API_KEY"] = settings.mistral_api_key