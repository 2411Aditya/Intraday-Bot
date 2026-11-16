# Windows Laptop Deployment for Intraday‑Bot

## Overview
This guide explains how to run the Intraday‑Bot locally on a Windows laptop using **PowerShell** and Windows **Task Scheduler**. It covers prerequisites, installation steps, the six scheduled‑task configurations, safety checks to keep trading in **paper‑only** mode, a cut‑over procedure for GitHub Actions, verification commands, troubleshooting tips, and rollback/uninstallation.

---

## 1. Prerequisites
| Item | Required version / notes |
|------|--------------------------|
| **Windows** | 10 / 11 (64‑bit). Laptop must stay powered on during market hours (08:00‑16:00 IST). |
| **PowerShell** | 5.1 or later (built‑in). |
| **Python** | 3.10 + (the project uses a virtual environment). |
| **Git** | Optional – for cloning the repo. |
| **Internet** | Needed to reach Supabase, Angel One, and GitHub (for CI). |
| **Virtual environment** | The project ships a `.venv` directory. If not present, run `python -m venv .venv` from the repository root. |
| **Environment file** | Copy `.env.example` → `.env` and fill in your Supabase credentials, Angel One API keys, and ensure:
```text
TRADING_MODE=paper
LIVE_TRADING_ENABLED=false
``` |
| **Permissions** | The user must be able to create scheduled tasks. If you encounter *Access denied* errors, run PowerShell **as Administrator** for the install step. |

---

## 2. Repository layout (relevant paths)
```
<repo-root>/                 # C:\Users\Aditya Kulkarni\Desktop\Projects\Intraday‑Bot
│
├─ scripts/windows/          # PowerShell helpers
│   ├─ install_tasks.ps1
│   ├─ uninstall_tasks.ps1
│   ├─ run_task.ps1
│   ├─ start_bot.ps1
│   ├─ stop_bot.ps1
│   └─ check_status.ps1
│
├─ backend/app/worker.py     # Contains the worker‑lock implementation
├─ backend/tests/            # pytest suite (already passing)
└─ docs/WINDOWS_LOCAL_DEPLOYMENT.md   # **THIS FILE**
```

---

## 3. Installation steps
1. **Open PowerShell** (preferably *Run as Administrator* for the first install). Navigate to the repo root:
   ```powershell
   cd "C:\Users\Aditya Kulkarni\Desktop\Projects\Intraday-Bot"
   ```
2. **Verify Python & virtual‑env**
   ```powershell
   .\.venv\Scripts\python.exe -V   # should show 3.13.5 (or compatible)
   ```
   If the `.venv` folder does not exist, create it:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\pip install -r requirements.txt
   ```
3. **Check environment configuration**
   ```powershell
   .\.venv\Scripts\python.exe -m pip install python-dotenv   # ensure dot‑env support
   .\.venv\Scripts\python.exe -c "import dotenv, os; print('env loaded')"
   ```
   Make sure `.env` contains the required keys and that `TRADING_MODE=paper` and `LIVE_TRADING_ENABLED=false`.
4. **Run a quick health check**
   ```powershell
   .\scripts\windows\check_status.ps1
   ```
   The script will:
   * Resolve the repository root.
   * Verify the virtual‑env Python executable.
   * Validate the presence of `.env`.
   * Confirm the paper‑only safety guard.
   * Report any existing `worker.lock` and whether any scheduled tasks are already registered.
5. **Install the six Intraday‑Bot scheduled tasks**
   ```powershell
   powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\install_tasks.ps1
   ```
   The script creates the following tasks (all **weekly** on Monday‑Friday):
   | Task name | Start time (IST) | Description |
   |-----------|------------------|-------------|
   | `IntradayBot_PreFlight` | 08:00 | Sanity‑check of environment, connectivity, and Supabase. |
   | `IntradayBot_PreMarket` | 08:15 | Runs the research engine (`pre_market` session). |
   | `IntradayBot_TradingCycle` | 09:15 | Executes the main worker (`trading_cycle`) and repeats every **5 min** until 15:30 (duration = 06:15). |
   | `IntradayBot_SquareOff` | 15:15 | Emergency square‑off – close‑only mode, never opens new positions. |
   | `IntradayBot_SquareOffBackup` | 15:20 | Backup square‑off (same as above, runs a few minutes later). |
   | `IntradayBot_PostMarket` | 15:45 | Post‑market research, audit, and reporting. |
6. **Verify task creation** (see section 5 for the exact command).

---

## 4. Paper‑only safety checks (built‑in)
* `run_task.ps1` loads `.env` and aborts if:
  * `LIVE_TRADING_ENABLED=true`
  * `TRADING_MODE=live`
* The worker’s **close‑only** tasks (`square_off` and `square_off_backup`) are invoked with `--close-only` and bypass the worker lock, guaranteeing they never open new trades.
* The lock file (`logs/worker.lock`) stores a JSON object `{"pid": <int>, "mode": "run-once"|"loop", "started_at": "ISO‑timestamp"}`. It prevents duplicate workers on the same machine. Stale locks are automatically cleaned up.

---

## 5. Verification commands
### 5.1 List scheduled Intraday‑Bot tasks (PowerShell)
```powershell
Get-ScheduledTask | Where-Object { $_.TaskName -like 'IntradayBot_*' } |
    Format-Table TaskName, State, @{Label='Triggers';Expression={($_.Triggers | ForEach-Object { $_.ToString() })}} -AutoSize
```
You should see six tasks, each with a **Weekly** trigger on `MON,TUE,WED,THU,FRI`. The `IntradayBot_TradingCycle` entry will also display:
```
Repeat: Every: 5 Minute(s)
Duration: 06:15
```
### 5.2 Inspect a single task in detail
```powershell
schtasks /query /tn IntradayBot_TradingCycle /fo LIST /v
```
Look for the lines:
```
Schedule Type: Weekly
Days: MON,TUE,WED,THU,FRI
Repeat: Every: 5 Minute(s)
Duration: 06:15
```
### 5.3 Test a task manually
```powershell
# Example: run the pre‑flight check immediately
schtasks /run /tn IntradayBot_PreFlight
```
Check the log file under `logs/` – e.g. `preflight_2026-11-16.log` – for a line containing `Safety Verified:`.
### 5.4 Verify the worker lock
```powershell
# After starting a loop worker, the lock file should exist and contain JSON
Get-Content .\logs\worker.lock | ConvertFrom-Json
```
The output will show the current PID, mode (`loop`), and a timestamp.

---

## 6. GitHub Actions cut‑over procedure
1. **Disable the CI schedules** while you are validating the laptop execution:
   * Open the repository on GitHub.
   * Navigate to *Settings → Actions → Workflow permissions*.
   * Either **disable** the `research.yml` and `paper_trading.yml` files by adding `#` before the `on:` block, or use the UI to **disable the workflow** temporarily.
2. **Run the laptop tasks** for at least one full market day.
3. **Observe** the dashboard (Vercel) to ensure signals, orders and P&L are updating.
4. **Re‑enable** the GitHub‑Actions schedules **only** if you later want the CI runner to take over again.
   * The lock file is local to the machine, so there is no risk of overlap when the CI is disabled.

---

## 7. Troubleshooting
| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `powershell.exe -File install_tasks.ps1` fails with *Access denied* | Insufficient rights to create scheduled tasks | Run PowerShell **as Administrator** for the install step. |
| Task never runs – no log file appears | Scheduler is set to *Run only when user is logged on* but you are logged off during market hours. | In `install_tasks.ps1` you can change `/ru` to `SYSTEM` or keep the laptop logged on (lock screen is fine). |
| Log shows `CRITICAL SECURITY ERROR: LIVE_TRADING_ENABLED is true` | `.env` incorrectly set. | Ensure `LIVE_TRADING_ENABLED=false` and `TRADING_MODE=paper`. |
| `worker.lock` remains after a crash | Stale lock not cleaned (PID no longer exists). | The next acquisition automatically removes stale locks; you can also delete `logs\worker.lock` manually. |
| `Get‑ScheduledTask` returns nothing | Tasks were not created or were created under a different user. | Verify you installed tasks under the same Windows account you are currently using. Re‑run `install_tasks.ps1`. |

---

## 8. Rollback / Uninstallation
To remove all Intraday‑Bot scheduled tasks and clean up artefacts:
```powershell
# Remove tasks
powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\uninstall_tasks.ps1

# Delete lock file (if any)
Remove-Item -Path .\logs\worker.lock -ErrorAction SilentlyContinue

# Optionally delete logs folder
Remove-Item -Recurse -Force -Path .\logs
```
After running the above, no Intraday‑Bot tasks will remain in the Windows Task Scheduler.

---

## 9. Quick reference cheat‑sheet
| Command | Purpose |
|---------|---------|
| `check_status.ps1` | Validate environment, Python, lock, and task registration. |
| `install_tasks.ps1` | Create all six scheduled tasks. |
| `uninstall_tasks.ps1` | Remove the six tasks. |
| `start_bot.ps1 -Mode loop` | Manually start a continuous worker (bypasses scheduler). |
| `stop_bot.ps1` | Gracefully stop a running worker and remove the lock file. |
| `Get‑ScheduledTask …` | List and inspect tasks. |
| `schtasks /run /tn <Task>` | Trigger a task immediately for testing. |

---

*You are now ready to run Intraday‑Bot on your Windows laptop in a safe, paper‑only configuration.*