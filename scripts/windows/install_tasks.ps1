# ===============================================================================
# scripts/windows/install_tasks.ps1
# Intraday-Bot: Install Windows Task Scheduler Automation (XML repetition for TradingCycle)
# ===============================================================================
param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"

# Resolve repository root and helper script paths
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path "$ScriptDir\..\..").Path
$RunTaskScript = Join-Path $RepoRoot "scripts\windows\run_task.ps1"

if (-not (Test-Path $RunTaskScript)) {
    Write-Error "Launcher script not found at $RunTaskScript"
    exit 1
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Installing Intraday-Bot Tasks into Windows Task Scheduler" -ForegroundColor Cyan
Write-Host "Repository Root: $RepoRoot" -ForegroundColor Gray
Write-Host "==========================================================" -ForegroundColor Cyan

# ---------------------------------------------------------------------------
# Task definitions (Mon‑Fri, Asia/Kolkata timezone)
# ---------------------------------------------------------------------------
$Tasks = @(
    @{ Name = "IntradayBot_PreFlight";        Time = "08:00"; Days = "MON,TUE,WED,THU,FRI"; TaskParam = "preflight";        Repeat = $null; Duration = $null; Description = "Daily 08:00 AM IST startup sanity, environment, and connectivity check" },
    @{ Name = "IntradayBot_PreMarket";        Time = "08:15"; Days = "MON,TUE,WED,THU,FRI"; TaskParam = "pre_market";        Repeat = $null; Duration = $null; Description = "Daily 08:15 AM IST pre‑market macro research, screening, and watchlist generation" },
    @{ Name = "IntradayBot_TradingCycle";    Time = "09:15"; Days = "MON,TUE,WED,THU,FRI"; TaskParam = "trading_cycle";    Repeat = "5";  Duration = "06:15"; Description = "Intraday 5‑minute evaluation cycles (09:15‑15:30 IST) for watchlist symbols" },
    @{ Name = "IntradayBot_SquareOff";       Time = "15:15"; Days = "MON,TUE,WED,THU,FRI"; TaskParam = "square_off";       Repeat = $null; Duration = $null; Description = "Compulsory 15:15 IST emergency square‑off (close‑only mode, exits remaining positions)" },
    @{ Name = "IntradayBot_SquareOffBackup";Time = "15:20"; Days = "MON,TUE,WED,THU,FRI"; TaskParam = "square_off_backup";Repeat = $null; Duration = $null; Description = "Independent 15:20 IST backup emergency square‑off (close‑only mode)" },
    @{ Name = "IntradayBot_PostMarket";      Time = "15:45"; Days = "MON,TUE,WED,THU,FRI"; TaskParam = "post_market";      Repeat = $null; Duration = $null; Description = "Daily 15:45 IST post‑market research, trade auditing, and reporting" }
)

$InstalledCount = 0

foreach ($t in $Tasks) {
    $TaskName   = $t.Name
    $StartTime  = $t.Time
    $Days       = $t.Days
    $Param      = $t.TaskParam

    # Build the Action: call powershell.exe with hidden window, executing run_task.ps1
    $ActionArguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$RunTaskScript`" -Task $Param"
    $Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $ActionArguments

    # Build the Trigger (weekly, Monday‑Friday)
    $DaysArray = $Days -split ","
    $Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $DaysArray -At $StartTime

    Write-Host "Creating task [$TaskName] at $StartTime IST (Days: $Days)..." -NoNewline

    if ($TaskName -eq "IntradayBot_TradingCycle" -and $t.Repeat -and $t.Duration) {
        # Register a temporary task first, export its XML, inject <Repetition>, then register final task via XML
        $TempName = "${TaskName}_Temp"
        try {
            Register-ScheduledTask -TaskName $TempName -Action $Action -Trigger $Trigger -Description $t.Description -Force -ErrorAction Stop
            $xml = Export-ScheduledTask -TaskName $TempName | Out-String
            # Load XML and add Repetition element to the CalendarTrigger
            [xml]$xmlDoc = $xml
            $ns = $xmlDoc.DocumentElement.NamespaceURI
            $triggerNode = $xmlDoc.GetElementsByTagName('CalendarTrigger').Item(0)
            if ($null -eq $triggerNode) {
                throw "CalendarTrigger not found in exported Task Scheduler XML."
            }
            if ($triggerNode) {
                $repNode = $xmlDoc.CreateElement('Repetition', $ns)
                $intervalNode = $xmlDoc.CreateElement('Interval', $ns)
                $intervalNode.InnerText = 'PT5M'
                $durationNode = $xmlDoc.CreateElement('Duration', $ns)
                $durationNode.InnerText = 'PT6H15M'
                $stopNode = $xmlDoc.CreateElement('StopAtDurationEnd', $ns)
                $stopNode.InnerText = 'true'
                $repNode.AppendChild($intervalNode) | Out-Null
                $repNode.AppendChild($durationNode) | Out-Null
                $repNode.AppendChild($stopNode) | Out-Null
                $triggerNode.AppendChild($repNode) | Out-Null
            }
            $finalXml = $xmlDoc.OuterXml
            Register-ScheduledTask -Xml $finalXml -TaskName $TaskName -Force -ErrorAction Stop
            Write-Host " [OK]" -ForegroundColor Green
            $InstalledCount++
        }
        catch {
            Write-Host " [FAILED]" -ForegroundColor Red
            Write-Error $_
        }
        finally {
            # Clean up temporary task if it exists
            if (Get-ScheduledTask -TaskName $TempName -ErrorAction SilentlyContinue) {
                Unregister-ScheduledTask -TaskName $TempName -Confirm:$false
            }
        }
    }
    else {
        try {
            Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Description $t.Description -Force -ErrorAction Stop
            Write-Host " [OK]" -ForegroundColor Green
            $InstalledCount++
        }
        catch {
            Write-Host " [FAILED]" -ForegroundColor Red
            Write-Error $_
        }
    }
}

Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host "Installation Summary: $InstalledCount of $($Tasks.Count) tasks registered successfully." -ForegroundColor $(if ($InstalledCount -eq $Tasks.Count) { "Green" } else { "Yellow" })
Write-Host "To verify tasks anytime: Get-ScheduledTask | Where-Object { $_.TaskName -like 'IntradayBot_*' }" -ForegroundColor Gray
Write-Host "To check overall bot health: .\scripts\windows\check_status.ps1" -ForegroundColor Gray
Write-Host "==========================================================" -ForegroundColor Cyan


if ($InstalledCount -ne $Tasks.Count) {
    Write-Host "ERROR: Only $InstalledCount of $($Tasks.Count) tasks installed." -ForegroundColor Red
    exit 1
}

Write-Host "SUCCESS: All six scheduled tasks registered." -ForegroundColor Green
exit 0