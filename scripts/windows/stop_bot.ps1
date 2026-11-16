# ==============================================================================
# scripts/windows/stop_bot.ps1
# Intraday-Bot: Gracefully Stop Active Local Worker Processes
# ==============================================================================
param(
    [switch]$Force
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path "$ScriptDir\..\..").Path
$LockFile = Join-Path $RepoRoot "logs\worker.lock"

Write-Host "==========================================================" -ForegroundColor Yellow
Write-Host "Stopping Intraday-Bot Local Processes" -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Yellow

$StoppedAny = $false

# 1. Check lock file
if (Test-Path $LockFile) {
    try {
        $LockContent = Get-Content $LockFile -Raw -ErrorAction SilentlyContinue
        $LockJson = $null
        $TargetPid = $null

        if ($LockContent -and $LockContent.Trim().StartsWith("{")) {
            $LockJson = ConvertFrom-Json $LockContent -ErrorAction SilentlyContinue
            $TargetPid = $LockJson.pid
        } elseif ($LockContent -and $LockContent.Trim() -match "^\d+$") {
            $TargetPid = [int]$LockContent.Trim()
        }

        if ($TargetPid) {
            Write-Host "Found active lock for PID $TargetPid (Mode: $($LockJson.mode))..." -NoNewline
            $Proc = Get-Process -Id $TargetPid -ErrorAction SilentlyContinue
            if ($Proc) {
                Stop-Process -Id $TargetPid -Force -ErrorAction SilentlyContinue
                Write-Host " [TERMINATED]" -ForegroundColor Green
                $StoppedAny = $true
            } else {
                Write-Host " [PROCESS NOT RUNNING]" -ForegroundColor Gray
            }
        }
    } catch {
        Write-Warning "Could not read lock file cleanly: $_"
    } finally {
        Remove-Item $LockFile -Force -ErrorAction SilentlyContinue
        Write-Host "Removed lock file: $LockFile" -ForegroundColor Gray
    }
} else {
    Write-Host "No active worker.lock file found." -ForegroundColor Gray
}

# 2. Stop running Task Scheduler tasks if active
$TaskNames = @(
    "IntradayBot_TradingCycle",
    "IntradayBot_PreMarket",
    "IntradayBot_SquareOff",
    "IntradayBot_SquareOffBackup",
    "IntradayBot_PostMarket"
)

foreach ($Name in $TaskNames) {
    & schtasks.exe /end /tn $Name 2>$null | Out-Null
}

Write-Host "`nAll Intraday-Bot automation processes stopped cleanly." -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Yellow
