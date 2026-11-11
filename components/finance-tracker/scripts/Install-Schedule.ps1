$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$nodeExe = (Get-Command node).Source
$userId = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
if ((Get-TimeZone).Id -ne 'India Standard Time') { throw 'These task times require Windows to use India Standard Time. The in-app scheduler itself always uses IST.' }
$launcher = Join-Path $PSScriptRoot 'Run-Daybook-Scheduled.vbs'
$wscript = Join-Path $env:SystemRoot 'System32/wscript.exe'
$action = New-ScheduledTaskAction -Execute $wscript -Argument ('//B //NoLogo "' + $launcher + '" "' + $nodeExe + '" worker') -WorkingDirectory $projectRoot
$triggers = @((New-ScheduledTaskTrigger -Daily -At '16:00'), (New-ScheduledTaskTrigger -Daily -At '18:00'), (New-ScheduledTaskTrigger -Daily -At '23:15'))
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId $userId -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName 'Daybook Daily Valuation' -Action $action -Trigger $triggers -Settings $settings -Principal $principal -Description 'Refresh the local Finance Tracker ledger at 16:00, 18:00 and 23:15 IST; catch up missed runs.' -Force | Out-Null
$startup = New-ScheduledTaskAction -Execute $wscript -Argument ('//B //NoLogo "' + $launcher + '" "' + $nodeExe + '" bootstrap') -WorkingDirectory $projectRoot
$serverSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName 'Daybook Local Server' -Action $startup -Trigger (New-ScheduledTaskTrigger -AtLogOn -User $userId) -Settings $serverSettings -Principal $principal -Description 'Start the local-only Finance Tracker server after sign-in.' -Force | Out-Null
Write-Output 'Installed Finance Tracker valuation and startup schedules for the current Windows user. No firewall rules changed.'
