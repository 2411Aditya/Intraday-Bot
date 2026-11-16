# Test XML repetition for TradingCycle
$ErrorActionPreference='Stop'
$repoRoot = (Resolve-Path 'C:\Users\Aditya Kulkarni\Desktop\Projects\Intraday-Bot').Path
$runTask = Join-Path $repoRoot 'scripts\windows\run_task.ps1'
$actionArgs = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$runTask`" -Task trading_cycle"
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $actionArgs
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek @('Monday','Tuesday','Wednesday','Thursday','Friday') -At '09:15'
$tempName = 'TempTest_TradingCycle'
# Register temporary task
Register-ScheduledTask -TaskName $tempName -Action $action -Trigger $trigger -Force
# Export XML
$xml = Export-ScheduledTask -TaskName $tempName | Out-String
[xml]$xmlDoc = $xml
$ns = $xmlDoc.DocumentElement.NamespaceURI
$triggerNode = $xmlDoc.GetElementsByTagName('CalendarTrigger')[0]
if (-not $triggerNode) { Write-Error 'CalendarTrigger not found' }
# Build Repetition element
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
$finalXml = $xmlDoc.OuterXml
# Register final task with XML under new name
$finalName = 'TempTest_TradingCycle_Final'
Register-ScheduledTask -Xml $finalXml -TaskName $finalName -Force
# Export final XML for verification
$finalExport = Export-ScheduledTask -TaskName $finalName | Out-String
Write-Output $finalExport
# Cleanup
Unregister-ScheduledTask -TaskName $tempName -Confirm:$false
Unregister-ScheduledTask -TaskName $finalName -Confirm:$false
