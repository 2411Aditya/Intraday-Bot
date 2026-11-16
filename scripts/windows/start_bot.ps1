# ==============================================================================
# scripts/windows/start_bot.ps1
# Intraday-Bot: Manual / Interactive Process Launcher
# ==============================================================================
param(
    [ValidateSet("run-once", "loop", "preflight", "pre_market", "post_market", "overnight", "square_off")]
    [string]$Mode = "run-once",

    [switch]$Force
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path "$ScriptDir\..\..").Path
$RunTaskScript = Join-Path $ScriptDir "run_task.ps1"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Intraday-Bot Interactive Launcher" -ForegroundColor Cyan
Write-Host "Selected Mode: $Mode" -ForegroundColor White
if ($Force) { Write-Host "Force Flag: ENABLED (Testing outside hours)" -ForegroundColor Yellow }
Write-Host "==========================================================" -ForegroundColor Cyan

$TaskMap = @{
    "run-once"     = "trading_cycle"
    "loop"         = "worker_loop"
    "preflight"    = "preflight"
    "pre_market"   = "pre_market"
    "post_market"  = "post_market"
    "overnight"    = "overnight"
    "square_off"   = "square_off"
}

$TargetTask = $TaskMap[$Mode]
$ArgsList = @("-File", "`"$RunTaskScript`"", "-Task", $TargetTask)
if ($Force) { $ArgsList += "-Force" }

& powershell.exe -ExecutionPolicy Bypass @ArgsList
$ExitCode = $LASTEXITCODE

Write-Host "`nLauncher finished with exit code $ExitCode" -ForegroundColor $(if ($ExitCode -eq 0) { "Green" } else { "Red" })
exit $ExitCode
