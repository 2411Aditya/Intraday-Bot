"""Supabase persistence for research snapshots.

Table: research_snapshots
Columns: id (uuid pk), snapshot_id, session_type, trading_date, created_at,
         snapshot_json (jsonb), market_outlook, is_tradeable_session

The table is created by migration 0003_research_schema.sql.
"""

from __future__ import annotations

import datetime
import json
import logging
import os

from research.models import ResearchSnapshot

logger = logging.getLogger("research.persistence")

_STALENESS_HOURS = 6  # snapshots older than this are considered stale


def _get_conn():
    """Return a psycopg2 connection or raise RuntimeError."""
    try:
        import psycopg2
    except ImportError:
        raise RuntimeError("psycopg2-binary not installed")
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        raise RuntimeError("SUPABASE_DB_URL not set")
    return psycopg2.connect(db_url, connect_timeout=10)


def save_snapshot(snapshot: ResearchSnapshot) -> None:
    """Persist a ResearchSnapshot to Supabase research_snapshots table."""
    is_test_env = bool(
        os.getenv("PYTEST_CURRENT_TEST")
        or os.getenv("ENV") == "test"
        or os.getenv("APP_ENV") == "test"
    )
    if is_test_env and snapshot.session_type != "test":
        raise RuntimeError(
            f"Test isolation violation: Test runner attempted to persist snapshot with session_type='{snapshot.session_type}'. "
            "Tests must mock persistence or use session_type='test' to prevent production research contamination."
        )

    snapshot_json = snapshot.model_dump_json()
    sql = """
        INSERT INTO research_snapshots
            (snapshot_id, session_type, trading_date, created_at, snapshot_json,
             market_outlook, is_tradeable_session)
        VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s)
        ON CONFLICT (snapshot_id) DO UPDATE
            SET snapshot_json = EXCLUDED.snapshot_json,
                market_outlook = EXCLUDED.market_outlook,
                is_tradeable_session = EXCLUDED.is_tradeable_session;
    """
    conn = _get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(sql, (
                snapshot.snapshot_id,
                snapshot.session_type,
                snapshot.trading_date,
                snapshot.created_at,
                snapshot_json,
                snapshot.market_outlook,
                snapshot.is_tradeable_session,
            ))
        logger.info("Saved snapshot %s to Supabase", snapshot.snapshot_id)
    finally:
        conn.close()


def load_latest_snapshot(
    session_type: str | None = None,
    trading_date: datetime.date | str | None = None,
) -> ResearchSnapshot | None:
    """Return the most recent ResearchSnapshot from Supabase, or None if none exist."""
    conditions = []
    params = []
    if session_type:
        conditions.append("session_type = %s")
        params.append(session_type)
    if trading_date:
        conditions.append("trading_date = %s")
        params.append(str(trading_date))

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"""
        SELECT snapshot_json FROM research_snapshots
        {where}
        ORDER BY created_at DESC
        LIMIT 1;
    """
    conn = _get_conn()
    try:
        with conn, conn.cursor() as cur:
            if params:
                cur.execute(sql, tuple(params))
            else:
                cur.execute(sql)
            row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        return None
    val = row[0]
    if isinstance(val, dict):
        return ResearchSnapshot.model_validate(val)
    return ResearchSnapshot.model_validate_json(val)


def is_snapshot_fresh(snapshot: ResearchSnapshot | None) -> bool:
    """Return True when snapshot exists and is less than _STALENESS_HOURS old."""
    if snapshot is None:
        return False
    age = datetime.datetime.now(datetime.timezone.utc) - snapshot.created_at
    return age.total_seconds() < _STALENESS_HOURS * 3600

