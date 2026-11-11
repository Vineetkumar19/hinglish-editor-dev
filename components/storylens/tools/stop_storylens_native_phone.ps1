$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$runtime = Join-Path $root 'cache\phone-native\runtime.json'
try {
    if (-not (Test-Path -LiteralPath $runtime)) { Write-Host 'No recorded native phone connection is running.'; exit 0 }
    $saved = Get-Content -LiteralPath $runtime -Raw | ConvertFrom-Json
    $ownerPid = [int]$saved.pid
    $process = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $ownerPid) -ErrorAction SilentlyContinue
    if ($null -eq $process) { Write-Host 'The native phone connection has already stopped.'; exit 0 }
    if ([string]$saved.root -ne $root -or -not ([string]$process.CommandLine).Contains('hinglish_app.phone_native') -or -not ([string]$process.CommandLine).Contains($root)) { throw 'Process identity changed. No process was stopped.' }
    Stop-Process -Id $ownerPid -ErrorAction Stop
    Write-Host 'Native phone connection stopped. Laptop editor tasks remain running. No VPN or public port is used.'
} catch {
    Write-Host ('Native phone connection: ' + $_.Exception.Message) -ForegroundColor Yellow
    exit 1
}
