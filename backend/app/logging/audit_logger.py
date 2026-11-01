"""Trade and Audit Logging Engine with Resilient Supabase & Local Fallback."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
import httpx
from backend.app.core.config import TradingMode, settings
from backend.app.models.domain import (
    AuditLogEntry,
    Order,
    Position,
    Signal,
)

logger = logging.getLogger("IntradayBot.Audit")


class AuditLogger:
    """Manages audit trail persistence to Supabase with local in-memory & file fallback."""

    def __init__(self, log_dir: Path | None = None):
        self._memory_logs: list[AuditLogEntry] = []
        self._log_dir = log_dir or Path(__file__).resolve().parent.parent.parent / "logs"
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._file_path = self._log_dir / "audit_trail.jsonl"

    def log_event(
        self, event_type: str, mode: TradingMode, details: dict, symbol: str | None = None
    ) -> AuditLogEntry:
        """Persists an audit event locally and asynchronously transmits to Supabase if configured."""
        entry = AuditLogEntry(
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            mode=mode,
            symbol=symbol,
            details=details,
        )

        # 1. Store in memory buffer (bounded to 1000 items)
        self._memory_logs.append(entry)
        if len(self._memory_logs) > 1000:
            self._memory_logs.pop(0)

        # 2. Append to local JSON Lines audit log
        try:
            with open(self._file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry.model_dump(), default=str) + "\n")
        except Exception as e:
            logger.warning(f"Failed to append to local audit log file: {e}")

        # 3. Synchronize to Supabase if credentials are provided
        if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
            self._post_to_supabase(entry)

        return entry

    def log_signal(self, signal: Signal, mode: TradingMode) -> AuditLogEntry:
        return self.log_event(
            event_type="SIGNAL_GENERATED",
            mode=mode,
            symbol=signal.symbol,
            details=signal.model_dump(),
        )

    def log_rejection(self, symbol: str, reason: str, mode: TradingMode, details: dict | None = None) -> AuditLogEntry:
        payload = {"reason": reason}
        if details:
            payload.update(details)
        return self.log_event(
            event_type="SIGNAL_OR_ORDER_REJECTED",
            mode=mode,
            symbol=symbol,
            details=payload,
        )

    def log_order(self, order: Order) -> AuditLogEntry:
        return self.log_event(
            event_type=f"ORDER_{order.status.value}",
            mode=order.mode,
            symbol=order.symbol,
            details=order.model_dump(),
        )

    def log_fill(self, order: Order, position: Position) -> AuditLogEntry:
        return self.log_event(
            event_type="POSITION_OPENED",
            mode=position.mode,
            symbol=position.symbol,
            details={
                "order": order.model_dump(),
                "position": position.model_dump(),
            },
        )

    def get_recent_logs(self, limit: int = 50) -> list[AuditLogEntry]:
        return self._memory_logs[-limit:]

    def _post_to_supabase(self, entry: AuditLogEntry) -> None:
        """Best-effort HTTP post to Supabase REST endpoint without blocking."""
        endpoint = f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/audit_logs"
        headers = {
            "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        }
        payload = {
            "log_id": entry.log_id,
            "timestamp": entry.timestamp.isoformat(),
            "event_type": entry.event_type,
            "execution_mode": entry.mode.value,
            "symbol": entry.symbol,
            "details": entry.details,
        }

        try:
            # Short timeout to avoid hanging trading loops if network has high latency
            with httpx.Client(timeout=2.0) as client:
                resp = client.post(endpoint, headers=headers, json=payload)
                if resp.status_code not in (200, 201):
                    logger.debug(f"Supabase audit log sync response: {resp.status_code}")
        except Exception as e:
            logger.debug(f"Supabase audit log sync skipped (offline/unreachable): {e}")


# Singleton instance
audit_logger = AuditLogger()

