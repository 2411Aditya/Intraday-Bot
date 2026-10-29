# Trading Mode Management & Paper/Live Separation Architecture

## 1. Absolute Isolation Invariant

The platform operates on a fundamental security principle: **Paper Trading and Actual Trading are completely isolated, non-interchangeable execution regimes.**

1. **Zero Shared Order Execution:** The Virtual Broker engine never calls Angel One transactional order endpoints.
2. **Zero Shared State:** Virtual accounts, orders, positions, fills, and ledger balances reside in dedicated `virtual_*` tables, completely partitioned from `live_*` tables.
3. **No Dynamic Runtime Conversion:** A paper position can NEVER be converted into a live position, nor vice versa.
4. **Independent Ledger & P&L:** Virtual P&L has no connection to actual broker funds.
5. **Fail-Safe Default:** On boot, reboot, or configuration reset, the system defaults to `PAPER_ACTIVE` or `LIVE_LOCKED`. `ACTUAL` trading is never automatically activated.

---

## 2. Execution Mode State Machine

```
                              +-----------------------+
                              |      SYSTEM BOOT      |
                              +-----------+-----------+
                                          |
                                          v
                              +-----------------------+
                  +---------> |      PAPER_ACTIVE     | <---------+
                  |           +-----------+-----------+           |
                  |                       |                       |
            User  |                 User  |  Daily Limit          | Paper
            Resume|                 Pause |  or Outage            | Square-off
                  |                       v                       | Complete
                  |           +-----------------------+           |
                  +---------- |      PAPER_PAUSED     | ----------+
                              +-----------------------+

================================ HARD ISOLATION BOUNDARY ================================

                              +-----------------------+
                              |      LIVE_LOCKED      |  (Default for Live Mode)
                              +-----------+-----------+
                                          |
                                          | Multi-step Manual Authorization +
                                          | Static IP Verified + Session 2FA +
                                          | Broker Reconciliation Clean
                                          v
                              +-----------------------+
                  +---------> |       LIVE_READY      | <---------+
                  |           +-----------+-----------+           |
                  |                       |                       |
                  |                 User  | Confirm               | User
                  |                 Arm   | Mode                  | Disarm
                  |                       v                       |
                  |           +-----------------------+           |
                  +---------- |      LIVE_ACTIVE      | ----------+
                              +-----------+-----------+
                                          |
                                          | Risk Limit Breached / Broker Disconnect /
                                          | Manual Emergency Trigger
                                          v
                              +-----------------------+
                              |    EMERGENCY_STOP     |
                              | (Cancel All, Squaroff)|
                              +-----------------------+
```

---

## 3. State Definitions & Permitted Transitions

| State | Execution Target | Order Placement Permitted? | Description |
|---|---|---|---|
| `PAPER_ACTIVE` | Virtual Broker Engine | Yes (Simulated) | Default operational state. Real market data processed, strategy signals evaluated, orders simulated conservatively. |
| `PAPER_PAUSED` | Virtual Broker Engine | No | Paper trading temporarily paused (e.g. daily loss cap reached, max trades reached, user pause). |
| `LIVE_LOCKED` | None | No | Live execution engine is physically blocked and uninstantiated. Initial state for live subsystem. |
| `LIVE_READY` | Angel One Broker Adapter | No (Armed only) | Configuration, Static IP, Angel One TOTP session, account funds, and risk engine all verified clean. Awaiting final user key. |
| `LIVE_ACTIVE` | Angel One Broker Adapter | Yes (Real Capital) | Fully authorized live trading. Real orders routed to NSE via Angel One SmartAPI from registered static IP. |
| `LIVE_PAUSED` | Angel One Broker Adapter | No | Live trading paused. Existing positions managed, but no new live entries allowed. |
| `EMERGENCY_STOP` | Angel One Broker Adapter | Exit Only | Catastrophic halt: cancels all pending orders, places protective square-off orders, and sends high-priority Telegram alerts. |

---

## 4. Hard Authorization Checklist for Live Activation

Before transitioning from `LIVE_LOCKED` to `LIVE_READY` or `LIVE_ACTIVE`, the backend enforces the following programmatic assertions:

```python
def verify_live_activation_prerequisites() -> LiveReadinessCheck:
    # 1. Environment Flag Check
    assert settings.LIVE_TRADING_ENABLED is True, "LIVE_TRADING_ENABLED env var is false"
    
    # 2. Broker Credentials Check
    assert settings.ANGELONE_API_KEY and settings.ANGELONE_CLIENT_ID, "Angel One credentials missing"
    
    # 3. Static IP Verification
    public_ip = fetch_outbound_public_ip()
    assert public_ip == settings.REGISTERED_STATIC_IP, f"Public IP {public_ip} does not match registered static IP"
    
    # 4. Active Broker Session Check (2FA TOTP)
    session = angel_one_client.get_session_status()
    assert session.is_authenticated, "Angel One 2FA session expired or unauthenticated"
    
    # 5. Verified Account Funds Check
    broker_funds = angel_one_client.get_rms_funds()
    assert broker_funds.available_cash > 0, "No available trading cash in Angel One account"
    
    # 6. Open Order & Position Reconciliation
    reconciliation = reconcile_live_positions()
    assert reconciliation.is_clean, "Discrepancy in live broker order book or positions"
    
    # 7. Independent Risk Engine Online
    assert risk_engine.is_healthy(), "Risk engine health check failed"
    
    # 8. Completed Paper Trading Validation
    stats = get_paper_trading_audit_stats()
    assert stats.completed_trades >= 50, "At least 50 forward paper trades required prior to live consideration"
    
    # 9. Explicit Cryptographic User Token
    assert user_auth_token.is_valid_live_token(), "Explicit live authorization token missing"
    
    return LiveReadinessCheck(passed=True)
```

---

## 5. Visual Identification Standards on Dashboard

Every user-facing screen, component, and log entry must display prominent, un-missable mode indicators:

1. **Paper Trading Display:**
   - Badge: `[PAPER TRADING - SIMULATED]` in emerald green or blue.
   - Trade ID Prefix: `PAPER-ORD-XXXXX`.
   - Clear banner stating: *Virtual Capital Deployed — No Real Money at Risk.*

2. **Actual Trading Display:**
   - Badge: `[ACTUAL TRADING - REAL CAPITAL AT RISK]` in high-visibility amber/red.
   - Trade ID Prefix: `LIVE-ORD-XXXXX`.
   - Angel One Broker Order ID displayed alongside internal ID.
   - Prominent sticky warning banner at top of viewport.
