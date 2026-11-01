"""Application Configuration and Security Settings."""

from enum import Enum
from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class TradingMode(str, Enum):
    PAPER = "paper"
    ACTUAL = "actual"


class AppEnv(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Central application configuration loaded from environment or .env file."""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent.parent.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Runtime Environment
    APP_ENV: AppEnv = AppEnv.DEVELOPMENT
    TIMEZONE: str = "Asia/Kolkata"
    API_PORT: int = 8000

    # Operational Mode & Hard Safety Gates
    TRADING_MODE: TradingMode = TradingMode.PAPER
    LIVE_TRADING_ENABLED: bool = False
    REGISTERED_STATIC_IP: str | None = None

    # Angel One Credentials (Optional in Paper Mode)
    ANGELONE_API_KEY: str | None = None
    ANGELONE_CLIENT_ID: str | None = None
    ANGELONE_PASSWORD: str | None = None
    ANGELONE_TOTP_SECRET: str | None = None

    # Supabase Credentials (Optional for local/offline testing)
    SUPABASE_URL: str | None = None
    SUPABASE_ANON_KEY: str | None = None
    SUPABASE_SERVICE_ROLE_KEY: str | None = None
    SUPABASE_DB_URL: str | None = None

    # Telegram Credentials (Optional)
    TELEGRAM_BOT_TOKEN: str | None = None
    TELEGRAM_CHAT_ID: str | None = None

    # Strategy & Risk Parameters
    RISK_PER_TRADE_PCT: float = Field(default=0.5, ge=0.1, le=2.0)
    MAX_DAILY_LOSS_PCT: float = Field(default=1.0, ge=0.5, le=5.0)
    MAX_TRADES_PER_DAY: int = Field(default=2, ge=1, le=10)
    MAX_OPEN_POSITIONS: int = Field(default=1, ge=1, le=5)
    DEFAULT_REWARD_RISK: float = Field(default=2.0, ge=1.5, le=10.0)
    VIRTUAL_STARTING_CAPITAL: float = Field(default=10000.0, ge=1000.0)
    MAX_SLIPPAGE_PCT: float = Field(default=0.05, ge=0.0, le=0.5)

    @field_validator("LIVE_TRADING_ENABLED")
    @classmethod
    def validate_live_safety(cls, v: bool, info) -> bool:
        """Enforces hard safeguard: Live trading cannot be enabled without explicit configuration."""
        if v and info.data.get("TRADING_MODE") != TradingMode.ACTUAL:
            raise ValueError("LIVE_TRADING_ENABLED cannot be true when TRADING_MODE is paper.")
        return v


# Global singleton instance
settings = Settings()

