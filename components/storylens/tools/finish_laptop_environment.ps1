$ErrorActionPreference='Stop'
# Bootstrap tests use preserved Python 3.12 packages. They must never leak into
# pip or the new Python 3.13 interpreter, even when setup follows those tests.
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
$taskRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $taskRoot
$env:PIP_CACHE_DIR = Join-Path $taskRoot 'cache\pip'
$env:PIP_FIND_LINKS = 'downloads/wheels'
$env:PIP_NO_INDEX = '1'
$taskConstraints = Join-Path $taskRoot 'downloads\laptop-resolved-constraints.txt'
if (Test-Path -LiteralPath $taskConstraints) { $env:PIP_CONSTRAINT = 'downloads/laptop-resolved-constraints.txt' }
$env:PYTHONIOENCODING = 'utf-8'
$taskWheel = Join-Path $taskRoot 'downloads\wheels\torch-2.9.1+cu128-cp313-cp313-win_amd64.whl'
$taskPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
$taskDeadline = (Get-Date).AddHours(6)
Write-Output 'Waiting for the checksum-verified PyTorch wheel.'
while (-not (Test-Path -LiteralPath $taskWheel)) {
    if ((Get-Date) -gt $taskDeadline) { throw 'PyTorch download did not finish within six hours. Resume it before rerunning setup.' }
    Start-Sleep -Seconds 15
}
& $taskPython -m pip install --no-deps $taskWheel
if ($LASTEXITCODE -ne 0) { throw 'Local PyTorch wheel installation failed.' }
& (Join-Path $taskRoot 'setup.ps1') -Device cuda
if ($LASTEXITCODE -ne 0) { throw 'Main GPU setup failed.' }
& $taskPython -m pip install -r requirements-saas.txt -r requirements-publish.txt
if ($LASTEXITCODE -ne 0) { throw 'Website/publishing dependency setup failed.' }
& $taskPython -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Main environment has dependency conflicts.' }
Write-Output 'CORE_GPU_ENVIRONMENT_READY'

$taskInstall = Join-Path $taskRoot 'tools\aigen\install'
$taskGenerationPython = Join-Path $taskInstall 'venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskGenerationPython)) {
    & $taskPython -m venv (Join-Path $taskInstall 'venv')
    if ($LASTEXITCODE -ne 0) { throw 'Generation environment could not be created.' }
}
& $taskGenerationPython -m pip install --no-deps $taskWheel
if ($LASTEXITCODE -ne 0) { throw 'Generation PyTorch installation failed.' }
& (Join-Path $taskRoot 'tools\aigen\setup_aigen.ps1') -Target $taskInstall -Models all -SkipDownload
if ($LASTEXITCODE -ne 0) { throw 'Generation dependency setup failed.' }
& $taskGenerationPython -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Generation environment has dependency conflicts.' }
Write-Output 'GENERATION_GPU_ENVIRONMENT_READY'
