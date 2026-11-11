$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Set-Location -LiteralPath $root
$python = Join-Path $root '.venv\Scripts\python.exe'
$runtime = Join-Path $root 'cache\phone-native\runtime.json'
try {
    if (-not (Test-Path -LiteralPath (Join-Path $root 'cache\phone-native\connection.dpapi'))) { throw 'Pairing setup is not configured on this Windows account yet.' }
    if (Test-Path -LiteralPath $runtime) {
        $saved = Get-Content -LiteralPath $runtime -Raw | ConvertFrom-Json
        $process = Get-CimInstance Win32_Process -Filter ('ProcessId=' + [int]$saved.pid) -ErrorAction SilentlyContinue
        if ($null -ne $process -and ([string]$process.CommandLine).Contains('hinglish_app.phone_native') -and ([string]$process.CommandLine).Contains($root)) {
            Write-Host 'The StoryLens Android connection is already running. Open the app on your phone.'
            exit 0
        }
    }
    Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/health' -TimeoutSec 5 | Out-Null
    & $python -m hinglish_app.phone_native --root $root
    exit $LASTEXITCODE
} catch {
    Write-Host ('Open StoryLens first. Native phone connection: ' + $_.Exception.Message) -ForegroundColor Yellow
    exit 1
}
