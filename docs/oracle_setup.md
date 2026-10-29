# Oracle Cloud Always Free Deployment & Infrastructure Guide

## 1. Why Oracle Cloud Always Free?
To satisfy the non-negotiable requirement of **24/7 continuous operation without relying on a personal laptop**, the backend trading worker requires persistent hosting. 

Oracle Cloud Infrastructure (OCI) offers an industry-leading **Always Free** tier that provides:
1. **Compute Choices:**
   - **Ampere A1 Compute (`VM.Standard.A1.Flex`):** Up to 4 OCPUs and 24 GB of RAM (can be allocated across 1 to 4 instances).
   - **AMD Micro Compute (`VM.Standard.E2.1.Micro`):** 1 OCPU, 1 GB RAM (up to 2 instances).
2. **Boot Volumes:** 200 GB of free storage.
3. **Bandwidth:** 10 TB per month outbound data transfer (free).
4. **Networking:** Free Reserved Static Public IPv4 Address (essential for Angel One static IP whitelisting!).

---

## 2. OCI Free Tier Constraints & Proactive Mitigations

### 2.1 Idle Instance Reclamation Policy
- **The Rule:** Oracle automatically stops or reclaims Always Free compute instances if average resource utilization remains below 20% across CPU, memory, and network over a rolling 7-day period.
- **System Safeguards:**
  1. **Option A (Safest & Recommended): Upgrade to Pay-As-You-Go (PAYG):** Upgrading an OCI account with a payment method permanently exempts the account from idle reclamation. As long as resources remain strictly within the Always Free envelope (4 OCPUs, 24 GB RAM, 200 GB disk), **monthly charges are ₹0.00**.
  2. **Option B (Operational Workload Activity):** The platform maintains active 24/7 scheduled tasks (overnight macro collection, pre-market candidate ranking, WebSocket data buffering, Supabase syncing, and hourly health telemetry). In addition, an internal background watchdog thread executes lightweight periodic benchmark checks to ensure active utilization reporting.

### 2.2 Memory Optimization
- Even on a 1 GB RAM AMD Micro VM (`VM.Standard.E2.1.Micro`), our modular Python service consumes only ~280 MB RAM by using async I/O (`uvloop`), streamed responses, and avoiding bloated local deep-learning frameworks.

---

## 3. Architecture on the Cloud Worker

```
+-------------------------------------------------------------+
|                      ORACLE CLUSTER / VM                    |
|                                                             |
|  +-------------------------------------------------------+  |
|  | systemd Service: intraday-bot.service                 |  |
|  | - Auto-restart on failure (Restart=always)            |  |
|  | - EnvironmentFile=/opt/intraday-bot/backend/.env      |  |
|  |                                                       |  |
|  |  +-------------------------------------------------+  |  |
|  |  | Python 3.11+ / FastAPI Application Engine       |  |  |
|  |  |                                                 |  |  |
|  |  |  [Thread 1] Uvicorn ASGI Server (REST API)       |  |  |
|  |  |  [Thread 2] APScheduler (24/7 Crons)            |  |  |
|  |  |  [Thread 3] SmartWebSocketV2 Stream Ingestion   |  |  |
|  |  |  [Thread 4] Watchdog & Telemetry Monitor        |  |  |
|  |  +-------------------------------------------------+  |  |
|  +-------------------------------------------------------+  |
|                                                             |
|  +-------------------------------------------------------+  |
|  | Outbound Fixed Static Public IPv4: 129.xxx.xxx.xxx    |  |
|  | -> Whitelisted in Angel One SmartAPI Developer Portal |  |
|  +-------------------------------------------------------+  |
+-------------------------------------------------------------+
```

---

## 4. Disaster Recovery & Process Supervision

- **Process Supervisor:** Managed by `systemd`. If the Python worker crashes or encounters an unhandled exception, `systemd` restarts it after a 5-second backoff.
- **Startup Reconciliation:** On every boot, the application executes a comprehensive bootstrap check:
  1. Validates `.env` and database connectivity.
  2. Pings Angel One and checks session validity.
  3. Reconciles open positions and orders from the database and broker.
  4. Resumes appropriate state (`PAPER_ACTIVE` or `LIVE_READY`). Duplicate orders are never fired upon restart.
