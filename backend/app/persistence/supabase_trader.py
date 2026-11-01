"""Supabase Trade Persistence Engine.

Persists strategy signals, risk decisions, order intents, orders, fills,
and position updates into Supabase PostgreSQL, linked to Research Snapshots.
"""

from __future__ import annotations

import datetime
import logging
import os
import uuid
from typing import Any

import psycopg2

logger = logging.getLogger("SupabaseTrader")


def get_db_connection():
    """Return an active psycopg2 connection to SUPABASE_DB_URL."""
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        raise RuntimeError("SUPABASE_DB_URL is not set in environment")
    conn = psycopg2.connect(db_url, connect_timeout=15)
    return conn


def ensure_trading_account(conn, user_id: str, mode: str = "paper", starting_capital: float = 10000.0) -> str:
    """Ensure a trading account exists for the user and return its UUID."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM trading_accounts WHERE user_id = %s AND mode = %s;",
            (user_id, mode),
        )
        row = cur.fetchone()
        if row:
            return str(row[0])

        account_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO trading_accounts (id, user_id, mode, cash_balance, created_at, updated_at)
            VALUES (%s, %s, %s, %s, now(), now());
            """,
            (account_id, user_id, mode, starting_capital),
        )
        conn.commit()
        return account_id


def persist_trade_cycle(
    conn,
    user_id: str,
    account_id: str,
    symbol: str,
    direction: str,  # 'long' or 'short'
    signal_price: float,
    fill_price: float,
    quantity: int,
    fees: float = 0.0,
    research_snapshot_id: str | None = None,
    signal_id: str | None = None,
    risk_id: str | None = None,
    intent_id: str | None = None,
    order_id: str | None = None,
    fill_id: str | None = None,
) -> dict[str, Any]:
    """Execute full transactional trade persistence into Supabase using pg_execute_trade_cycle."""
    sig_uuid = signal_id or str(uuid.uuid4())
    risk_uuid = risk_id or str(uuid.uuid4())
    intent_uuid = intent_id or str(uuid.uuid4())
    order_uuid = order_id or str(uuid.uuid4())
    fill_uuid = fill_id or str(uuid.uuid4())

    side = "buy" if direction.lower() in ("long", "buy") else "sell"

    with conn.cursor() as cur:
        # Set caller UID for auth.uid() in RLS and _validate_trade_chain
        cur.execute("SELECT set_config('request.jwt.claim.sub', %s, true);", (user_id,))

        # 1. Strategy Signal
        cur.execute(
            """
            INSERT INTO strategy_signals (id, user_id, symbol, signal_time, direction, price, research_snapshot_id)
            VALUES (%s, %s, %s, now(), %s, %s, %s);
            """,
            (sig_uuid, user_id, symbol, "long" if side == "buy" else "short", signal_price, research_snapshot_id),
        )

        # 2. Risk Decision
        cur.execute(
            """
            INSERT INTO risk_decisions (id, signal_id, account_id, decision, created_at)
            VALUES (%s, %s, %s, 'approved', now());
            """,
            (risk_uuid, sig_uuid, account_id),
        )

        # 3. Order Intent
        cur.execute(
            """
            INSERT INTO order_intents (id, risk_id, account_id, mode, symbol, quantity, side, limit_price, created_at)
            VALUES (%s, %s, %s, 'paper', %s, %s, %s, %s, now());
            """,
            (intent_uuid, risk_uuid, account_id, symbol, quantity, side, signal_price),
        )

        # 4. Call authoritative RPC: pg_execute_trade_cycle
        cur.execute(
            """
            SELECT pg_execute_trade_cycle(%s, %s, %s, %s, %s, %s, %s, %s);
            """,
            (sig_uuid, risk_uuid, intent_uuid, order_uuid, fill_uuid, fill_price, quantity, fees),
        )

        # 5. Query updated account & position
        cur.execute(
            "SELECT cash_balance, deployed_margin FROM trading_accounts WHERE id = %s;",
            (account_id,),
        )
        acct_row = cur.fetchone()

        cur.execute(
            """
            SELECT id, quantity, avg_entry_price, direction, status, realized_pnl
            FROM positions
            WHERE account_id = %s AND symbol = %s
            ORDER BY created_at DESC LIMIT 1;
            """,
            (account_id, symbol),
        )
        pos_row = cur.fetchone()

    conn.commit()

    return {
        "signal_id": sig_uuid,
        "risk_id": risk_uuid,
        "intent_id": intent_uuid,
        "order_id": order_uuid,
        "fill_id": fill_uuid,
        "cash_balance": float(acct_row[0]) if acct_row else None,
        "deployed_margin": float(acct_row[1]) if acct_row else None,
        "position": {
            "id": str(pos_row[0]),
            "quantity": pos_row[1],
            "avg_entry_price": float(pos_row[2]),
            "direction": pos_row[3],
            "status": pos_row[4],
            "realized_pnl": float(pos_row[5]),
        } if pos_row else None,
    }


def get_last_processed_candle_ts(
    conn, symbol: str, trading_date: datetime.date
) -> datetime.datetime | None:
    """Retrieves the timestamp of the last processed candle for a symbol on a trading date."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT last_processed_candle_ts
            FROM worker_candle_state
            WHERE symbol = %s AND trading_date = %s;
            """,
            (symbol, trading_date),
        )
        row = cur.fetchone()
        return row[0] if row else None


def save_last_processed_candle_ts(
    conn,
    symbol: str,
    trading_date: datetime.date,
    candle_ts: datetime.datetime,
    signal_id: str | None = None,
) -> None:
    """Persists or updates the last processed candle timestamp for idempotency and resume."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO worker_candle_state (symbol, trading_date, last_processed_candle_ts, last_evaluated_signal_id, updated_at)
            VALUES (%s, %s, %s, %s, now())
            ON CONFLICT (symbol, trading_date)
            DO UPDATE SET
                last_processed_candle_ts = EXCLUDED.last_processed_candle_ts,
                last_evaluated_signal_id = EXCLUDED.last_evaluated_signal_id,
                updated_at = now();
            """,
            (symbol, trading_date, candle_ts, signal_id),
        )
    conn.commit()


def is_symbol_traded_today(
    conn, account_id: str, symbol: str, trading_date: datetime.date
) -> bool:
    """Checks whether an order has already been executed or reserved for symbol today in this account."""
    with conn.cursor() as cur:
        # 1. Check atomic trade reservations first
        cur.execute(
            """
            SELECT count(*)
            FROM trade_reservations
            WHERE account_id = %s
              AND symbol = %s
              AND trading_date = %s;
            """,
            (account_id, symbol, trading_date),
        )
        res_row = cur.fetchone()
        if res_row and res_row[0] > 0:
            return True

        # 2. Check orders and order_intents
        cur.execute(
            """
            SELECT count(*)
            FROM order_intents i
            JOIN orders o ON o.intent_id = i.id
            WHERE i.account_id = %s
              AND i.symbol = %s
              AND DATE(i.created_at AT TIME ZONE 'Asia/Kolkata') = %s
              AND o.status IN ('filled', 'partial', 'pending');
            """,
            (account_id, symbol, trading_date),
        )
        row = cur.fetchone()
        return bool(row and row[0] > 0)


def reserve_trade_slot(
    conn,
    account_id: str,
    symbol: str,
    trading_date: datetime.date,
    worker_id: str,
) -> bool:
    """Atomically reserves a trade slot for a symbol on a trading date.

    Uses PostgreSQL row locking to guarantee that among N concurrent workers,
    only the first one succeeds (returns True), and all other workers are safely rejected (returns False).
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT reserve_trade_slot(%s, %s, %s, %s);",
            (account_id, symbol, trading_date, worker_id),
        )
        row = cur.fetchone()
    conn.commit()
    return bool(row and row[0])



