"""Research data models.

All data models used across research providers and the Supabase persistence layer.
"""

from __future__ import annotations

import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class DataStatus(str, Enum):
    OK = "OK"
    STALE = "STALE"
    BLOCKED = "BLOCKED"
    ERROR = "ERROR"


class ProviderResult(BaseModel):
    """Typed output of one data-source adapter call."""

    source: str                                # e.g. "yfinance:^GSPC"
    fetched_at: datetime.datetime              # UTC timestamp of actual network call
    status: DataStatus
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None                  # sanitized error message, no secrets

    @property
    def is_fresh(self) -> bool:
        """True when status is OK and data was fetched within the last 6 hours."""
        if self.status != DataStatus.OK:
            return False
        age = datetime.datetime.now(datetime.timezone.utc) - self.fetched_at
        return age.total_seconds() < 6 * 3600


class ResearchSnapshot(BaseModel):
    """Aggregated market-intelligence snapshot persisted to Supabase."""

    snapshot_id: str = Field(default_factory=lambda: f"RS-{__import__('uuid').uuid4().hex[:8].upper()}")
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    session_type: str                          # "overnight" | "pre_market" | "post_market"
    trading_date: str                          # "YYYY-MM-DD" in IST

    # Aggregated data blocks
    global_indices: dict[str, Any] = Field(default_factory=dict)
    gift_nifty: dict[str, Any] = Field(default_factory=dict)
    fx_commodities: dict[str, Any] = Field(default_factory=dict)
    institutional_flows: dict[str, Any] = Field(default_factory=dict)
    economic_events: dict[str, Any] = Field(default_factory=dict)
    nse_announcements: dict[str, Any] = Field(default_factory=dict)

    # Derived outputs
    market_outlook: str = "NEUTRAL"           # "BULLISH" | "BEARISH" | "NEUTRAL" | "HIGH_RISK"
    risk_warnings: list[str] = Field(default_factory=list)
    allowed_symbols: list[str] = Field(default_factory=list)   # Nifty 50 eligible list
    watchlist: list[dict[str, Any]] = Field(default_factory=list)  # ranked, with scores
    sector_scores: dict[str, float] = Field(default_factory=dict)

    # Provenance
    provider_statuses: dict[str, str] = Field(default_factory=dict)  # source -> DataStatus
    is_tradeable_session: bool = True
    no_trade_reason: str | None = None

