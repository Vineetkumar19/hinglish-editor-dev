param([ValidateSet('cpu','cuda')][string]$Device='cpu')
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskPython=Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    $pythonCommand=Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCommand) { throw 'Install 64-bit Python 3.12, then run setup again.' }
    & $pythonCommand.Source -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment.' }
}
# Pin a matched release with Blackwell support; CPU and CUDA can be switched later.
$wheelIndex=if ($Device -eq 'cuda') {'https://download.pytorch.org/whl/cu128'} else {'https://download.pytorch.org/whl/cpu'}
& $taskPython -m pip install --upgrade 'torch==2.9.1' 'torchaudio==2.9.1' --index-url $wheelIndex
if ($LASTEXITCODE -ne 0) { throw 'PyTorch installation failed.' }
& $taskPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& $taskPython -m hinglish_cut doctor --device $Device
if ($LASTEXITCODE -ne 0) { throw 'Dependency or GPU check failed. Review the diagnostics above.' }
Write-Host 'Setup complete. Add your videos and script, then use the matching Run launcher.'
