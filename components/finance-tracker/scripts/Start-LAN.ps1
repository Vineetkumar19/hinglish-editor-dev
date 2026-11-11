param([int]$Port = 4313)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'dist/index.html'))) { throw 'Build the app first: npm run build' }
$secret = Read-Host 'Choose an access token of at least 24 characters' -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
try {
 $env:DAYBOOK_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
 if ($env:DAYBOOK_TOKEN.Length -lt 24) { throw 'Use at least 24 characters.' }
 $env:DAYBOOK_LAN = '1'; $env:PORT = "$Port"; $env:DAYBOOK_NO_SCHEDULER = '1'
 Write-Output "LAN access is enabled on port $Port while this terminal is running. Use only on your trusted private network. No firewall changes are made. HTTP is not encrypted; use a trusted VPN or HTTPS proxy for untrusted networks."
 node server/index.mjs
} finally {
 [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
 Remove-Item Env:DAYBOOK_TOKEN -ErrorAction SilentlyContinue
 Remove-Item Env:DAYBOOK_LAN -ErrorAction SilentlyContinue
 Remove-Item Env:DAYBOOK_NO_SCHEDULER -ErrorAction SilentlyContinue
 Remove-Item Env:PORT -ErrorAction SilentlyContinue
}
