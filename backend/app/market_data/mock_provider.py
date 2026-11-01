"""Mock and Historical Market Data Provider."""

from datetime import datetime, time, timedelta
import zoneinfo
from collections.abc import Callable
from backend.app.market_data.interface import MarketDataProvider
from backend.app.models.domain import Candle, MarketTick


class MockMarketDataProvider(MarketDataProvider):
    """Provides deterministic or simulated historical & real-time market data for testing and local operation."""

    def __init__(self):
        self._candles: dict[str, list[Candle]] = {}
        self._quotes: dict[str, MarketTick] = {}
        self._subscribers: list[Callable[[MarketTick], None]] = []
        self._is_healthy: bool = True

    def set_candles(self, symbol: str, candles: list[Candle]) -> None:
        """Load deterministic candle history for testing."""
        self._candles[symbol] = sorted(candles, key=lambda c: c.timestamp)

    def set_quote(self, symbol: str, quote: MarketTick) -> None:
        """Set current mock quote."""
        self._quotes[symbol] = quote

    def get_historical_candles(
        self, symbol: str, timeframe: str, start: datetime, end: datetime
    ) -> list[Candle]:
        candles = self._candles.get(symbol, [])
        return [
            c
            for c in candles
            if c.timeframe == timeframe and start <= c.timestamp <= end and c.is_completed
        ]

    def get_latest_candle(self, symbol: str, timeframe: str) -> Candle | None:
        candles = self._candles.get(symbol, [])
        matching = [c for c in candles if c.timeframe == timeframe and c.is_completed]
        return matching[-1] if matching else None

    def get_current_quote(self, symbol: str) -> MarketTick:
        if symbol in self._quotes:
            return self._quotes[symbol]

        # Generate realistic default quote based on latest candle
        latest = self.get_latest_candle(symbol, "5m")
        price = latest.close if latest else 1000.0
        return MarketTick(
            symbol=symbol,
            ltp=price,
            bid=round(price - 0.05, 2),
            ask=round(price + 0.05, 2),
            volume=latest.volume if latest else 10000,
        )

    def subscribe(self, symbols: list[str], callback: Callable[[MarketTick], None]) -> None:
        self._subscribers.append(callback)

    def is_healthy(self) -> bool:
        return self._is_healthy

    def set_health(self, healthy: bool) -> None:
        self._is_healthy = healthy

    @classmethod
    def generate_synthetic_session(
        cls,
        symbol: str = "SBIN",
        base_price: float = 800.0,
        pattern: str = "BULLISH_BREAKOUT",
        date: datetime | None = None,
    ) -> list[Candle]:
        """Generates a complete synthetic 5-minute session adhering to NSE trading hours (09:15 - 15:30 IST).

        Supported patterns:
        - BULLISH_BREAKOUT: 15-min ORB established, clean breakout on candle 4 with 2.0x volume & 60% body.
        - BEARISH_BREAKDOWN: 15-min ORB established, clean breakdown on candle 4 with 2.0x volume & 60% body.
        - LOW_VOLUME_BREAKOUT: Breakout on candle 4 but volume < 1.0x SMA (triggers rejection).
        - REJECTION_WICK: High breaks ORB High, but candle closes inside with long upper wick.
        """
        ist = zoneinfo.ZoneInfo("Asia/Kolkata")
        if date is None:
            now = datetime.now(ist)
            session_date = now.date()
        else:
            session_date = date.astimezone(ist).date()

        start_dt = datetime.combine(session_date, time(9, 20), tzinfo=ist)
        candles: list[Candle] = []

        # 1. Warm-up candles (prior 10 candles before 09:15 or opening)
        # Average volume will be ~10,000
        warmup_start = start_dt - timedelta(minutes=50)
        for i in range(10):
            ts = warmup_start + timedelta(minutes=i * 5)
            p = base_price + (i * 0.2)
            candles.append(
                Candle(
                    symbol=symbol,
                    timestamp=ts,
                    open=p,
                    high=p + 0.5,
                    low=p - 0.5,
                    close=p + 0.1,
                    volume=10000,
                    timeframe="5m",
                    is_completed=True,
                )
            )

        # 2. First 15 minutes of trading: 3 candles (09:15-09:20, 09:20-09:25, 09:25-09:30)
        # Candle 1 (09:20 close)
        c1 = Candle(
            symbol=symbol,
            timestamp=datetime.combine(session_date, time(9, 20), tzinfo=ist),
            open=base_price,
            high=base_price + 3.0,
            low=base_price - 1.0,
            close=base_price + 2.0,
            volume=12000,
            timeframe="5m",
            is_completed=True,
        )
        # Candle 2 (09:25 close)
        c2 = Candle(
            symbol=symbol,
            timestamp=datetime.combine(session_date, time(9, 25), tzinfo=ist),
            open=base_price + 2.0,
            high=base_price + 4.0,  # ORB High = base_price + 4.0
            low=base_price + 0.5,
            close=base_price + 3.0,
            volume=11000,
            timeframe="5m",
            is_completed=True,
        )
        # Candle 3 (09:30 close)
        c3 = Candle(
            symbol=symbol,
            timestamp=datetime.combine(session_date, time(9, 30), tzinfo=ist),
            open=base_price + 3.0,
            high=base_price + 3.8,
            low=base_price - 2.0,  # ORB Low = base_price - 2.0
            close=base_price + 1.0,
            volume=10500,
            timeframe="5m",
            is_completed=True,
        )
        candles.extend([c1, c2, c3])
        # Summary ORB: High = base_price + 4.0, Low = base_price - 2.0

        # Candle 4 (09:35 close): Execution Candle
        c4_ts = datetime.combine(session_date, time(9, 35), tzinfo=ist)

        if pattern == "BULLISH_BREAKOUT":
            # Decisive breakout above ORB High (804.0) -> High 806.0, Close 805.5, Vol 25000 (2.5x SMA), Body 75%
            c4 = Candle(
                symbol=symbol,
                timestamp=c4_ts,
                open=base_price + 2.5,
                high=base_price + 6.0,
                low=base_price + 2.0,
                close=base_price + 5.5,
                volume=25000,
                timeframe="5m",
                is_completed=True,
            )
        elif pattern == "BEARISH_BREAKDOWN":
            # Decisive breakdown below ORB Low (798.0) -> Low 795.0, Close 795.5, Vol 25000, Body 75%
            c4 = Candle(
                symbol=symbol,
                timestamp=c4_ts,
                open=base_price - 0.5,
                high=base_price - 0.2,
                low=base_price - 5.0,
                close=base_price - 4.5,
                volume=25000,
                timeframe="5m",
                is_completed=True,
            )
        elif pattern == "LOW_VOLUME_BREAKOUT":
            # Price breaks out, but volume is weak (8,000 < 10,000 SMA)
            c4 = Candle(
                symbol=symbol,
                timestamp=c4_ts,
                open=base_price + 2.5,
                high=base_price + 6.0,
                low=base_price + 2.0,
                close=base_price + 5.5,
                volume=8000,
                timeframe="5m",
                is_completed=True,
            )
        elif pattern == "REJECTION_WICK":
            # Price spikes above ORB High but pulls back and closes inside with a long upper wick
            c4 = Candle(
                symbol=symbol,
                timestamp=c4_ts,
                open=base_price + 2.0,
                high=base_price + 6.0,
                low=base_price + 1.5,
                close=base_price + 2.5,  # Close is inside ORB, body is tiny
                volume=25000,
                timeframe="5m",
                is_completed=True,
            )
        else:
            # Consolidation
            c4 = Candle(
                symbol=symbol,
                timestamp=c4_ts,
                open=base_price + 1.0,
                high=base_price + 2.5,
                low=base_price + 0.5,
                close=base_price + 1.8,
                volume=10000,
                timeframe="5m",
                is_completed=True,
            )

        candles.append(c4)
        return candles

