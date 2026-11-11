$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskFolder = Join-Path $PSScriptRoot 'opencut-classic/apps/web'
$taskNode = 'C:/Program Files/nodejs/node.exe'
if (-not (Test-Path -LiteralPath (Join-Path $taskFolder 'node_modules/next/dist/bin/next'))) {
    throw 'The OpenCut evaluation dependencies are missing. Restore the isolated OpenCut installation first.'
}
if (Get-NetTCPConnection -LocalPort 8870 -State Listen -ErrorAction SilentlyContinue) {
    Write-Output 'Port 8870 is already in use. OpenCut was not started again. Existing address: http://127.0.0.1:8870/projects'
    return
}
$env:NEXT_TELEMETRY_DISABLED = '1'
Start-Process -FilePath $taskNode -ArgumentList 'node_modules/next/dist/bin/next','dev','--webpack','--hostname','127.0.0.1','--port','8870' -WorkingDirectory $taskFolder -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskRoot 'output/opencut-evaluation.stdout.log') -RedirectStandardError (Join-Path $taskRoot 'output/opencut-evaluation.stderr.log')
Write-Output 'OpenCut is starting at http://127.0.0.1:8870/projects'
