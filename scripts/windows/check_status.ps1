# ==============================================================================
# scripts/windows/check_status.ps1
# Intraday-Bot: Comprehensive Local System Health and Status Checker
# ==============================================================================

$ErrorActionPreference = "Continue"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path "$ScriptDir\..\..").Path
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$PythonToUse = if (Test-Path $VenvPython) { $VenvPython } else { "python" }

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  INTRADAY-BOT LOCAL SYSTEM DIAGNOSTICS & HEALTH CHECK    " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Environment and Safety Checks
Write-Host "`n[1/5] Configuration & Safety Guardrails" -ForegroundColor White
$EnvFile = Join-Path $RepoRoot ".env"
if (Test-Path $EnvFile) {
    Write-Host "  .env File: PRESENT ($EnvFile)" -ForegroundColor Green
    
    Get-Content $EnvFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $idx = $line.IndexOf("=")
            $key = $line.Substring(0, $idx).Trim()
            $val = $line.Substring($idx + 1).Trim().Trim('"').Trim("'")
            if (-not [Environment]::GetEnvironmentVariable($key)) {
                [Environment]::SetEnvironmentVariable($key, $val, "Process")
            }
        }
    }

    $Mode = [Environment]::GetEnvironmentVariable("TRADING_MODE")
    $Live = [Environment]::GetEnvironmentVariable("LIVE_TRADING_ENABLED")
    $BotUser = [Environment]::GetEnvironmentVariable("BOT_USER_ID")
    if (-not $BotUser) { $BotUser = "00000000-0000-0000-0000-000000000002" }

    if ($Live -eq "false" -and $Mode -eq "paper") {
        Write-Host "  Trading Mode: PAPER (Live execution HARD-LOCKED disabled)" -ForegroundColor Green
    } else {
        Write-Host "  CRITICAL SAFETY VIOLATION: Mode=$Mode, Live=$Live" -ForegroundColor Red
    }
    $DisplayUser = if ($BotUser.Length -gt 8) { "..." + $BotUser.Substring($BotUser.Length - 8) } else { $BotUser }
    Write-Host "  Target Bot Account: $DisplayUser" -ForegroundColor Gray
} else {
    Write-Host "  .env File: MISSING! Create .env from .env.example" -ForegroundColor Red
}

# 2. Python Environment Check
Write-Host "`n[2/5] Python Runtime & Virtual Environment" -ForegroundColor White
if (Test-Path $VenvPython) {
    $PyVersion = & $VenvPython --version 2>&1
    Write-Host "  Virtual Environment (.venv): ACTIVE ($PyVersion)" -ForegroundColor Green
    Write-Host "  Python Binary: $VenvPython" -ForegroundColor Gray
} else {
    $SysPy = (Get-Command python -ErrorAction SilentlyContinue).Source
    Write-Host "  .venv Python: MISSING" -ForegroundColor Yellow
    Write-Host "  System Python: $SysPy" -ForegroundColor Gray
}

# 3. Market Session & Cloud Connectivity Diagnostics
Write-Host "`n[3/5] Exchange Session & Cloud Connectivity" -ForegroundColor White
$DiagScript = Join-Path $ScriptDir "diagnostics.py"
if (Test-Path $DiagScript) {
    $DiagLines = & $PythonToUse $DiagScript 2>&1
    foreach ($Line in $DiagLines) {
        if ($Line -match "^(.*?)=(.*)$") {
            $K = $Matches[1]
            $V = $Matches[2]
            $Color = "Gray"
            if ($K -eq "SESSION_STATUS" -and $V -eq "OPEN") { $Color = "Green" }
            elseif ($K -eq "DB_STATUS" -and $V -like "*CONNECTED*") { $Color = "Green" }
            elseif ($K -eq "ANGELONE_STATUS" -and $V -like "*READY*") { $Color = "Green" }
            elseif ($V -like "*FAILED*" -or $V -like "*ERROR*") { $Color = "Red" }
            Write-Host "  ${K}: $V" -ForegroundColor $Color
        }
    }
} else {
    Write-Host "  Diagnostics script missing at $DiagScript" -ForegroundColor Red
}

# 4. Local Worker Process Lock Status
Write-Host "`n[4/5] Local Worker Process Lock" -ForegroundColor White
$LockFile = Join-Path $RepoRoot "logs\worker.lock"
if (Test-Path $LockFile) {
    $LockContent = Get-Content $LockFile -Raw -ErrorAction SilentlyContinue
    Write-Host "  Lock File: PRESENT ($LockContent)" -ForegroundColor Yellow
} else {
    Write-Host "  Lock File: IDLE (No local worker currently holding process lock)" -ForegroundColor Green
}

# 5. Windows Task Scheduler Registration
Write-Host "`n[5/5] Windows Task Scheduler Registration" -ForegroundColor White
$TaskQuery = & schtasks.exe /query /fo TABLE 2>$null | Select-String "IntradayBot"
if ($TaskQuery) {
    $TaskQuery | ForEach-Object { Write-Host "  $_" -ForegroundColor Green }
} else {
    Write-Host "  No IntradayBot tasks found in Task Scheduler." -ForegroundColor Yellow
    Write-Host "  To install: powershell.exe -ExecutionPolicy Bypass -File .\scripts\windows\install_tasks.ps1" -ForegroundColor Gray
}

Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host "Diagnostics complete." -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
