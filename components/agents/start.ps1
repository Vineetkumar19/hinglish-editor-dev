param([switch]$Background, [switch]$Scheduler, [switch]$Telegram, [switch]$NoOpen)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) { throw 'Run .\setup.ps1 first' }
$taskLogs = Join-Path $PSScriptRoot 'data\logs'
New-Item -ItemType Directory -Path $taskLogs -Force | Out-Null
$taskProcessFile = Join-Path $PSScriptRoot 'data\runtime-processes.json'
function Save-SuiteProcess($TaskProcess) {
    $taskRecords = @()
    if (Test-Path -LiteralPath $taskProcessFile) {
        $taskRecords = @(Get-Content -LiteralPath $taskProcessFile -Raw | ConvertFrom-Json)
    }
    $taskRecords += @{pid=$TaskProcess.Id; start=$TaskProcess.StartTime.ToUniversalTime().ToString('o'); executable=$taskPython}
    ConvertTo-Json -InputObject @($taskRecords) | Set-Content -LiteralPath $taskProcessFile -Encoding utf8
}
foreach ($taskWorker in @(@{Enabled=$Scheduler; Name='schedule'}, @{Enabled=$Telegram; Name='telegram'})) {
    if ($taskWorker.Enabled) {
        $taskProcess = Start-Process -FilePath $taskPython -ArgumentList @('run.py', $taskWorker.Name) -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskLogs ($taskWorker.Name + '.out.log')) -RedirectStandardError (Join-Path $taskLogs ($taskWorker.Name + '.err.log')) -PassThru
        Save-SuiteProcess $taskProcess
    }
}
$taskArgs = @('run.py', 'serve')
if (-not $NoOpen) { $taskArgs += '--open' }
if ($Background) {
    $taskProcess = Start-Process -FilePath $taskPython -ArgumentList $taskArgs -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskLogs 'console.out.log') -RedirectStandardError (Join-Path $taskLogs 'console.err.log') -PassThru
    Save-SuiteProcess $taskProcess
    Write-Host "Console started (PID $($taskProcess.Id)). Logs: $taskLogs"
} else { & $taskPython @taskArgs }
