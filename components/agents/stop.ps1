$ErrorActionPreference = 'Stop'
$taskProcessFile = Join-Path $PSScriptRoot 'data\runtime-processes.json'
if (-not (Test-Path -LiteralPath $taskProcessFile)) { Write-Host 'No recorded background processes.'; return }
$taskRecords = @(Get-Content -LiteralPath $taskProcessFile -Raw | ConvertFrom-Json)
foreach ($taskRecord in $taskRecords) {
    $taskProcess = Get-Process -Id $taskRecord.pid -ErrorAction SilentlyContinue
    if ($taskProcess -and $taskProcess.Path -eq $taskRecord.executable -and
        $taskProcess.StartTime.ToUniversalTime().ToString('o') -eq $taskRecord.start) {
        Stop-Process -Id $taskProcess.Id
        Write-Host "Stopped suite process $($taskProcess.Id)."
    }
}
'[]' | Set-Content -LiteralPath $taskProcessFile -Encoding utf8
