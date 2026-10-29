# Angel One SmartAPI Integration & SEBI Compliance Guide

## 1. Overview
Angel One’s **SmartAPI** provides programmatic access to the National Stock Exchange of India (NSE) for market data streaming and order routing.

In our architecture:
- **Phase 1 to Phase 15:** Market data feeds (quotes, historical candles, and live WebSocket ticks) are consumed for technical analysis and the **Virtual Paper Trading Engine**.
- **Phase 16 to 17:** The live transactional order adapter is implemented, strictly locked behind static IP whitelisting, multi-step authorization, and regulatory compliance.

---

## 2. Regulatory Standards: SEBI Retail Algorithmic Guidelines

In accordance with SEBI circular `SEBI/HO/MIRSD/MIRSD-PoD/P/CIR/2025/0000013` (*"Safer participation of retail investors in Algorithmic trading"*):

1. **Mandatory Static IP Whitelisting:**
   - Any client API key executing transactional order routes (`placeOrder`, `modifyOrder`, `cancelOrder`) must be registered to a fixed, static IPv4 address.
   - Orders originating from un-whitelisted dynamic IPs are automatically rejected at the broker gateway.
2. **Daily Two-Factor Authentication (2FA):**
   - Sessions cannot run indefinitely. The system must generate a fresh session once every trading morning using Client Code, MPIN/Password, and a TOTP token generated via `pyotp`.
3. **Algo Tagging & Order Identifiers:**
   - Orders are tagged with an algorithmic identifier and a unique client correlation ID (`correlation_id`).
4. **Order Type Protection:**
   - Unconstrained market orders are avoided to prevent execution slippage in thin books. The system utilizes `LIMIT` or `STOP-LOSS LIMIT` orders with broker price protection.
5. **Rate Limiting:**
   - SmartAPI enforces a threshold of 10 requests per second per exchange segment. The platform implements an internal token bucket rate limiter to guarantee zero rate-limit rejections.

---

## 3. Authentication & Session Flow (Python SDK)

```python
import pyotp
from smartapi import SmartConnect

def authenticate_angel_one(api_key: str, client_code: str, pin: str, totp_secret: str):
    smart_api = SmartConnect(api_key=api_key)
    
    # Generate 6-digit time-based OTP
    totp = pyotp.TOTP(totp_secret).now()
    
    session_data = smart_api.generateSession(client_code, pin, totp)
    if not session_data or not session_data.get("status"):
        raise ConnectionError(f"Angel One Login Failed: {session_data}")
        
    auth_token = session_data["data"]["jwtToken"]
    feed_token = smart_api.getfeedToken()
    refresh_token = session_data["data"]["refreshToken"]
    
    return {
        "smart_api": smart_api,
        "auth_token": auth_token,
        "feed_token": feed_token,
        "refresh_token": refresh_token
    }
```

---

## 4. Live Market Data Streaming (SmartWebSocketV2)

The platform utilizes `SmartWebSocketV2` for high-throughput streaming:

- **Protocol:** Binary WebSocket feed over TLS.
- **Modes:** Mode 2 (`QUOTE` mode — provides LTP, volume, open, high, low, close, and 5-level market depth).
- **Exchange Segment:** `1` for `NSE_CM` (National Stock Exchange Capital Market).
- **Subscription List:** Dynamically updated at 09:00 IST with the 3–5 candidate stocks shortlisted by the Dynamic Stock Selection Engine.
- **Watchdog:** If no tick is received for $> 15$ seconds during 09:15–15:30 IST, the connection watchdog triggers an immediate auto-reconnect sequence.

---

## 5. Historical Candlestick Retrieval

- **Endpoint:** `smart_api.getCandleData()`
- **Parameters:**
  - `exchange`: `"NSE"`
  - `symboltoken`: Scrip token (e.g. `"3045"` for SBIN)
  - `interval`: `"FIVE_MINUTE"`, `"FIFTEEN_MINUTE"`, or `"ONE_DAY"`
  - `fromdate`: `"YYYY-MM-DD HH:MM"`
  - `todate`: `"YYYY-MM-DD HH:MM"`
- **Warm-Up Requirement:** Historical data engine fetches 30 days of daily candles and 10 days of 5-minute candles before market open (07:30 IST) to prime 20 EMA, ATR-14, and volume moving averages.
