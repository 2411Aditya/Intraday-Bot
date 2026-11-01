"""Market Data Provider Interface."""

from abc import ABC, abstractmethod
from datetime import datetime
from collections.abc import Callable
from backend.app.models.domain import Candle, MarketTick


class MarketDataProvider(ABC):
    """Abstract interface for streaming and historical market data."""

    @abstractmethod
    def get_historical_candles(
        self, symbol: str, timeframe: str, start: datetime, end: datetime
    ) -> list[Candle]:
        """Fetch historical candles for warm-up and analysis."""
        pass

    @abstractmethod
    def get_latest_candle(self, symbol: str, timeframe: str) -> Candle | None:
        """Fetch the most recently completed candle."""
        pass

    @abstractmethod
    def get_current_quote(self, symbol: str) -> MarketTick:
        """Fetch the latest bid-ask depth and LTP."""
        pass

    @abstractmethod
    def subscribe(self, symbols: list[str], callback: Callable[[MarketTick], None]) -> None:
        """Subscribe to real-time tick streaming."""
        pass

    @abstractmethod
    def is_healthy(self) -> bool:
        """Return connectivity health status."""
        pass

