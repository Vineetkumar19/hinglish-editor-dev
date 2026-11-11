$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Set-Location -LiteralPath $root
$python = Join-Path $root '.venv\Scripts\python.exe'
$runtimeFile = Join-Path $root 'cache\phone-remote\runtime.json'
$tailscale = 'C:\Program Files\Tailscale\tailscale.exe'
try {
    if (-not (Test-Path -LiteralPath $runtimeFile)) { throw 'No recorded phone companion process is available. The main editor was not changed.' }
    $runtime = Get-Content -LiteralPath $runtimeFile -Raw | ConvertFrom-Json
    if ([string]$runtime.root -ne $root) { throw 'The saved companion belongs to a different project.' }
    $ownerPid = [int]$runtime.pid
    $process = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $ownerPid) -ErrorAction SilentlyContinue
    if ($null -ne $process -and (-not ([string]$process.CommandLine).Contains('hinglish_app.phone_remote') -or -not ([string]$process.CommandLine).Contains($root))) {
        throw 'The saved process identity changed. No process was stopped.'
    }
    & $python -m hinglish_app.phone_remote --root $root --origin ([string]$runtime.origin) --revoke-all
    if ($LASTEXITCODE -ne 0) { throw 'Phone session revocation did not finish. Check the companion state before stopping it.' }
    if (Test-Path -LiteralPath $tailscale) {
        $serve = & $tailscale serve status --json | ConvertFrom-Json
        $dns = ([Uri]([string]$runtime.origin)).Host
        $current = $serve.Web.PSObject.Properties | Where-Object { $_.Name -eq ($dns + ':443') }
        if ($null -ne $current -and ($current.Value.Handlers.'/').Proxy -eq 'http://127.0.0.1:8796') {
            & $tailscale serve --https=443 off
        }
    }
    if ($null -ne $process) { Stop-Process -Id $ownerPid -ErrorAction Stop }
    Write-Host 'Private phone access stopped. The main editor and its running tasks were left alone.'
} catch {
    Write-Host ('Phone connection needs attention: ' + $_.Exception.Message) -ForegroundColor Yellow
    exit 1
}
