$ErrorActionPreference = 'Stop'
$taskDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ready = $false
try { $null = Invoke-WebRequest 'http://127.0.0.1:43820/' -UseBasicParsing -TimeoutSec 2; $ready = $true } catch {}
if (-not $ready) {
    Start-Process -FilePath 'C:\Program Files\nodejs\node.exe' -ArgumentList ('"' + (Join-Path $taskDir 'server.cjs') + '"') -WorkingDirectory $taskDir -WindowStyle Hidden
    Start-Sleep -Seconds 2
}
Start-Process 'http://127.0.0.1:43820/'
