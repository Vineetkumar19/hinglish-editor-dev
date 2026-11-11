param([string]$PythonPath = '')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not $PythonPath) {
    $taskBundled = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $taskBundled) { $PythonPath = $taskBundled }
    else { $PythonPath = (& py -3.12 -c 'import sys; print(sys.executable)') }
}
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    & $PythonPath -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create Python environment' }
}
& '.\.venv\Scripts\python.exe' -m pip install -r requirements-browser.txt
if ($LASTEXITCODE -ne 0) { throw 'Could not install browser support' }
& '.\.venv\Scripts\python.exe' -c 'import playwright.sync_api; import sys; print("Ready:", sys.version.split()[0])'
Write-Host 'Setup complete. Start with .\start.ps1'
