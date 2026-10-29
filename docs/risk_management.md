# Comprehensive Risk Management & Compliance Engine Specification

## 1. Core Mandate: Capital Preservation Above All

The Independent Risk Management Engine is an autonomous subsystem that sits between the Strategy Signal Engine and the Execution Layer.

**Fundamental Principle:** The Risk Management Engine possesses absolute, un-overrideable veto authority. A trading strategy may propose an order, but the order is never transmitted to any broker (virtual or live) without unconditional approval from the risk engine.

---

## 2. Risk Matrix & Failure Mode Mitigation

| Risk Category | Threat Vector | System Safeguard & Automated Mitigation |
|---|---|---|
| **Regulatory & Broker** | Non-compliance with SEBI 2025/2026 algo circular; un-whitelisted IP order attempts. | Mandatory static IP binding check before live adapter initialization; daily TOTP 2FA; automatic order rejection if outbound IP deviates from registered static IP. |
| **Market Data** | Feed freeze, delayed ticks, or WebSocket drop resulting in phantom breakouts. | Staleness Watchdog: every tick timestamp is evaluated. If gap between last tick and current time $> 15$ seconds, data feed is flagged `STALE` and all new entries are immediately suspended. |
| **Execution Slippage** | Violent price jumps or thin order books causing fill at adverse price. | Limit & Stop-Limit orders only. Market orders without price bounds are banned. Simulated paper execution adds 0.05% adverse slippage penalty. |
| **Circuit Breakers** | Stock hits exchange upper or lower 10%/20% price band, locking liquidity. | Stock Selection Engine checks daily price proximity to circuit filters. Instruments within 2% of price bands are blacklisted. |
| **Event Shocks** | Sudden RBI policy rate change, quarterly earnings miss, or geopolitical news. | Morning Economic & Corporate News Engine blacklists any stock with scheduled announcements within $\pm 24$ hours. |
| **Over-Trading** | Revenge trading or continuous churn during choppy market days. | Strict daily trade cap: Maximum 2 completed trades per day. Maximum 1 concurrent open position. |
| **Capital Erosion** | Consecutive losses on small capital accounts. | Hard daily stop: Maximum 1.0% portfolio loss. If reached, bot halts all operations until the next trading day. |
| **Overnight Gap Risk** | Severe overnight gap against open position. | Hard time-based square-off starting at 15:00 IST. The system carries **zero overnight positions**. |
| **Infrastructure Failure** | Cloud worker reboot, crash, or memory overflow. | Stateless recovery protocol: On restart, reconciles open orders/positions from database and broker. Duplicate orders are never fired. |

---

## 3. Independent Risk Checklist (The 12 Veto Gates)

Before an order intent is dispatched to execution, it must pass 12 sequential checks:

```python
def evaluate_risk_guardrails(order_intent: OrderIntent, context: RiskContext) -> RiskDecision:
    # 1. Trading Session Validity
    if not (time(9, 30) <= context.current_time_ist <= time(11, 30)):
        return RiskDecision.reject("ENTRY_WINDOW_CLOSED")

    # 2. Market Data Freshness
    if context.data_feed_latency_seconds > 15:
        return RiskDecision.reject("MARKET_DATA_STALE")

    # 3. Maximum Trades Per Day Cap
    if context.trades_executed_today >= 2:
        return RiskDecision.reject("MAX_DAILY_TRADES_REACHED")

    # 4. Maximum Open Positions Concurrency
    if context.active_open_positions >= 1:
        return RiskDecision.reject("MAX_CONCURRENT_POSITIONS_REACHED")

    # 5. Daily Realized Loss Circuit Breaker
    if context.daily_realized_loss_pct >= 1.0:
        return RiskDecision.reject("DAILY_LOSS_LIMIT_BREACHED")

    # 6. Weekly Drawdown Circuit Breaker
    if context.weekly_drawdown_pct >= 6.0:
        return RiskDecision.reject("STRATEGY_SUSPENDED_DRAWDOWN")

    # 7. Spread Viability Check
    if context.bid_ask_spread_pct > 0.10:
        return RiskDecision.reject("EXCESSIVE_BID_ASK_SPREAD")

    # 8. Event Blackout Check
    if context.has_pending_corporate_event(order_intent.symbol):
        return RiskDecision.reject("CORPORATE_EVENT_BLACKOUT")

    # 9. Stop-Loss Validation
    if order_intent.stop_distance_pct > (1.5 * context.symbol_atr_pct):
        return RiskDecision.reject("STOP_DISTANCE_EXCEEDS_MAX_VOLATILITY")

    # 10. Position Sizing & Cash Adequacy
    if order_intent.quantity < 1:
        return RiskDecision.reject("INSUFFICIENT_CAPITAL_FOR_MIN_QUANTITY")

    # 11. Economic Cost Drag Check
    if order_intent.estimated_fees / order_intent.projected_gross_profit > 0.15:
        return RiskDecision.reject("UNECONOMICAL_TRANSACTION_COSTS")

    # 12. Mode Authorization Gate
    if order_intent.mode == TradingMode.ACTUAL and not context.is_live_authorized():
        return RiskDecision.reject("UNAUTHORIZED_LIVE_EXECUTION_ATTEMPT")

    return RiskDecision.approve()
```

---

## 4. Emergency Procedures & Fail-Safe Protocol

### 4.1 Manual Emergency Stop (`/api/v1/risk/emergency-stop`)
- Triggered by user via dashboard button or backend command.
- Instantly cancels all open pending orders across all instruments.
- Executes market-protective square-off on all open positions.
- Transitions system state to `EMERGENCY_STOP`.
- Dispatches high-priority Telegram alert.

### 4.2 Automated End-of-Day Square-Off Protocol (15:00 IST)
1. **15:00:00 IST:** Workflow engine triggers EOD square-off phase.
2. **15:00:05 IST:** All unfilled limit/stop orders are cancelled.
3. **15:00:10 IST:** For any remaining open position, a closing order is submitted with a limit price set to CMP $\pm 0.10\%$ buffer to guarantee execution.
4. **15:15:00 IST:** Position reconciliation verifies Net Quantity is $0$ for all symbols.
5. **15:20:00 IST:** End-of-day P&L report is persisted and transmitted to Telegram.
