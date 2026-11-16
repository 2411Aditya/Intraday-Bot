# ==============================================================================
# scripts/windows/run_task.ps1
# Intraday-Bot: Windows Automation Task Runner
# ==============================================================================
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("preflight", "pre_market", "trading_cycle", "square_off", "square_off_backup", "post_market", "overnight", "worker_loop")]
    [string]$Task,

    [switch]$Force
)

$ErrorActionPreference = "Stop"

# 1. Resolve repository root relative to this script (no hardcoded usernames)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path "$ScriptDir\..\..").Path
Set-Location $RepoRoot

# 2. Ensure logs directory exists
$LogsDir = Join-Path $RepoRoot "logs"
if (-not (Test-Path $LogsDir)) {
    New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null
}

$TodayDate = (Get-Date).ToString("yyyy-MM-dd")
$Timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
$LogFile = Join-Path $LogsDir "${Task}_${TodayDate}.log"

function Write-TaskLog {
    param([string]$Message)
    $Line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Message"
    Write-Host $Line
    Add-Content -Path $LogFile -Value $Line -Encoding utf8
}

Write-TaskLog "=========================================================="
Write-TaskLog "Starting Intraday-Bot Task: $Task"
Write-TaskLog "Repository Root: $RepoRoot"

# 3. Locate Python executable (prefer .venv)
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
    $PythonExe = $VenvPython
    Write-TaskLog "Using Virtual Environment Python: $PythonExe"
} else {
    $PythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $PythonExe) {
        Write-TaskLog "ERROR: Python executable not found in .venv or system PATH."
        exit 1
    }
    Write-TaskLog "Using System Python: $PythonExe"
}

# 4. Verify .env file and enforce paper-trading safety guardrails
$EnvFile = Join-Path $RepoRoot ".env"
if (-not (Test-Path $EnvFile)) {
    Write-TaskLog "ERROR: .env file missing in $RepoRoot. Cannot proceed safely."
    exit 1
}

# Load environment variables into current process if not already set
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

# CRITICAL SAFETY CHECK: Never allow live trading
$LiveTrading = [Environment]::GetEnvironmentVariable("LIVE_TRADING_ENABLED")
$TradingMode = [Environment]::GetEnvironmentVariable("TRADING_MODE")
if ($LiveTrading -eq "true" -or $TradingMode -eq "live") {
    Write-TaskLog "CRITICAL SECURITY ERROR: LIVE_TRADING_ENABLED is true or TRADING_MODE is live. Execution blocked."
    exit 1
}
Write-TaskLog "Safety Verified: TRADING_MODE=$TradingMode, LIVE_TRADING_ENABLED=$LiveTrading"

# 5. Determine Python command arguments based on Task
$PyArgs = @()
switch ($Task) {
    "preflight" {
        $PyArgs = @("scripts/windows/preflight.py")
    }
    "pre_market" {
        $PyArgs = @("research/run_research.py", "--session", "pre_market")
        if ($Force) { $PyArgs += "--force" }
    }
    "trading_cycle" {
        $PyArgs = @("-m", "backend.app.worker", "--run-once")
        if ($Force) { $PyArgs += "--force-session" }
    }
    "square_off" {
        $PyArgs = @("-m", "backend.app.worker", "--run-once", "--close-only")
    }
    "square_off_backup" {
        $PyArgs = @("-m", "backend.app.worker", "--run-once", "--close-only")
    }
    "post_market" {
        $PyArgs = @("research/run_research.py", "--session", "post_market")
        if ($Force) { $PyArgs += "--force" }
    }
    "overnight" {
        $PyArgs = @("research/run_research.py", "--session", "overnight", "--catchup")
        if ($Force) { $PyArgs += "--force" }
    }
    "worker_loop" {
        $PyArgs = @("-m", "backend.app.worker", "--loop")
        if ($Force) { $PyArgs += "--force-session" }
    }
}

Write-TaskLog "Executing: $PythonExe $($PyArgs -join ' ')"

# 6. Execute process and stream output to log file
try {
    $ProcessInfo = New-Object System.Diagnostics.ProcessStartInfo
    $ProcessInfo.FileName = $PythonExe
    $ProcessInfo.Arguments = ($PyArgs -join " ")
    $ProcessInfo.WorkingDirectory = $RepoRoot
    $ProcessInfo.RedirectStandardOutput = $true
    $ProcessInfo.RedirectStandardError = $true
    $ProcessInfo.UseShellExecute = $false
    $ProcessInfo.CreateNoWindow = $true

    $Proc = New-Object System.Diagnostics.Process
    $Proc.StartInfo = $ProcessInfo

    $OutSb = New-Object System.Text.StringBuilder
    $ErrSb = New-Object System.Text.StringBuilder

    $OutEvent = Register-ObjectEvent -InputObject $Proc -EventName OutputDataReceived -Action {
        if ($EventArgs.Data) {
            $Line = $EventArgs.Data
            Write-Host $Line
            [System.IO.File]::AppendAllText($Event.MessageData, "$Line`r`n")
        }
    } -MessageData $LogFile

    $ErrEvent = Register-ObjectEvent -InputObject $Proc -EventName ErrorDataReceived -Action {
        if ($EventArgs.Data) {
            $Line = "[STDERR] $($EventArgs.Data)"
            Write-Host $Line
            [System.IO.File]::AppendAllText($Event.MessageData, "$Line`r`n")
        }
    } -MessageData $LogFile

    $Proc.Start() | Out-Null
    $Proc.BeginOutputReadLine()
    $Proc.BeginErrorReadLine()

    $Proc.WaitForExit()
    $ExitCode = $Proc.ExitCode

    Unregister-Event -SourceIdentifier $OutEvent.Name -ErrorAction SilentlyContinue
    Unregister-Event -SourceIdentifier $ErrEvent.Name -ErrorAction SilentlyContinue

    Write-TaskLog "Task $Task finished with exit code $ExitCode"
    Write-TaskLog "=========================================================="
    exit $ExitCode
} catch {
    Write-TaskLog "ERROR running task ${Task}: $_"
    exit 1
}
