param([switch]$PairOnly)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Set-Location -LiteralPath $root
$python = Join-Path $root '.venv\Scripts\python.exe'
$tailscale = 'C:\Program Files\Tailscale\tailscale.exe'
try {
    if (-not (Test-Path -LiteralPath $python)) { throw 'The installed StoryLens Python environment is unavailable.' }
    if (-not (Test-Path -LiteralPath $tailscale)) { throw 'Install the official Tailscale Windows client and sign in first.' }
    $status = & $tailscale status --json | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or $status.BackendState -ne 'Running') { throw 'Sign into Tailscale on the laptop and phone with the same account, then connect both devices.' }
    $dns = ([string]$status.Self.DNSName).TrimEnd('.')
    if ($dns -notmatch '^[a-z0-9.-]+\.ts\.net$') { throw 'The private Tailscale hostname is unavailable. Check its DNS settings.' }
    $origin = 'https://' + $dns
    $engine = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/health' -TimeoutSec 4
    if ($null -eq $engine) { throw 'Open the existing StoryLens application first.' }
    $existing = $null
    try { $existing = Invoke-RestMethod -Uri 'http://127.0.0.1:8796/phone/health' -TimeoutSec 2 } catch { }
    if ($null -ne $existing -and $existing.service -ne 'storylens-phone') { throw 'Port 8796 belongs to another service. No process was replaced.' }
    $hash = [Security.Cryptography.SHA256]::Create()
    try { $installation = ([BitConverter]::ToString($hash.ComputeHash([Text.Encoding]::UTF8.GetBytes($root)))).Replace('-','').ToLowerInvariant().Substring(0,16) } finally { $hash.Dispose() }
    if ($null -ne $existing -and $existing.installation -ne $installation) { throw 'The phone companion belongs to another installation. It has not been replaced.' }
    $serve = & $tailscale serve status --json | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0) { throw 'Tailscale could not read the private HTTPS configuration.' }
    $hasHandlers = $false
    if ($null -ne $serve.Web) {
        foreach ($web in $serve.Web.PSObject.Properties) {
            foreach ($handler in $web.Value.Handlers.PSObject.Properties) {
                $hasHandlers = $true
                if ($web.Name -ne ($dns + ':443') -or $handler.Name -ne '/' -or $handler.Value.Proxy -ne 'http://127.0.0.1:8796') {
                    throw 'Another Tailscale web service is configured. It has not been changed; use a separate private port after review.'
                }
            }
        }
    }
    if (-not $hasHandlers) {
        & $tailscale serve --bg --https=443 --yes http://127.0.0.1:8796
        if ($LASTEXITCODE -ne 0) { throw 'Private HTTPS is not ready. Enable HTTPS with public Funnel OFF, then try again.' }
    }
    Write-Host ('Open on your Android phone: ' + $origin)
    if ($null -ne $existing -or $PairOnly) {
        & $python -m hinglish_app.phone_remote --root $root --origin $origin --pair-only
    } else {
        & $python -m hinglish_app.phone_remote --root $root --origin $origin
    }
    exit $LASTEXITCODE
} catch {
    Write-Host ('Phone connection not started: ' + $_.Exception.Message) -ForegroundColor Yellow
    exit 1
}
