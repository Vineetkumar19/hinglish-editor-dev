param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'node_modules'))) { npm ci; if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' } }
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'dist/index.html'))) { npm run build; if ($LASTEXITCODE -ne 0) { throw 'Build failed.' } }
$running = $false
try { $health = Invoke-RestMethod 'http://127.0.0.1:4310/api/health' -TimeoutSec 2; $running = ($health.service -eq 'finance-tracker' -or $health.name -eq 'Daybook') } catch {}
if (-not $running) {
 New-Item -ItemType Directory -Force -Path (Join-Path $projectRoot 'data') | Out-Null
 $nodeExe = (Get-Command node).Source
 Start-Process -FilePath $nodeExe -ArgumentList 'server/bootstrap.mjs' -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $projectRoot 'data/server.log') -RedirectStandardError (Join-Path $projectRoot 'data/server-error.log') | Out-Null
 for ($attempt = 0; $attempt -lt 20; $attempt++) {
  try { $health = Invoke-RestMethod 'http://127.0.0.1:4310/api/health' -TimeoutSec 2; if (($health.service -eq 'finance-tracker' -or $health.name -eq 'Daybook')) { $running = $true; break } } catch {}
  Start-Sleep -Milliseconds 300
 }
 if (-not $running) { throw 'Finance Tracker did not start. Check data/server-error.log.' }
}
Write-Output 'Finance Tracker is running at http://127.0.0.1:4310'
if (-not $NoBrowser) { Start-Process 'http://127.0.0.1:4310' }
