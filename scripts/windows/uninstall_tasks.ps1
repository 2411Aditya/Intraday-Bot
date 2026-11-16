# ==============================================================================
# scripts/windows/uninstall_tasks.ps1
# Intraday-Bot: Remove Windows Task Scheduler Tasks
# ==============================================================================
param(
    [switch]$Force
)

$TaskNames = @(
    "IntradayBot_PreFlight",
    "IntradayBot_PreMarket",
    "IntradayBot_TradingCycle",
    "IntradayBot_SquareOff",
    "IntradayBot_SquareOffBackup",
    "IntradayBot_PostMarket"
)

Write-Host "==========================================================" -ForegroundColor Yellow
Write-Host "Removing Intraday-Bot Tasks from Windows Task Scheduler" -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Yellow

$RemovedCount = 0

foreach ($Name in $TaskNames) {
    Write-Host "Removing task [$Name]..." -NoNewline
    $Process = Start-Process -FilePath "schtasks.exe" -ArgumentList @("/delete", "/tn", $Name, "/f") -Wait -NoNewWindow -PassThru -ErrorAction SilentlyContinue

    if ($Process.ExitCode -eq 0) {
        Write-Host " [REMOVED]" -ForegroundColor Green
        $RemovedCount++
    } else {
        Write-Host " [NOT FOUND / SKIPPED]" -ForegroundColor Gray
    }
}

Write-Host "`nSummary: $RemovedCount tasks removed." -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Yellow
