param([ValidateSet('cpu','cuda')][string]$Device='cpu')
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskPython=Join-Path $PSScriptRoot '.venv\Scripts\python.exe'

# PyTorch 2.9.1 supports Python 3.10-3.13; 3.12 is the tested one. The plain "python" command can be the
# Microsoft Store shortcut or a newer Python, so the official "py" launcher is asked first.
function Find-Python {
    $tries = @(@('py', '-3.12'), @('py', '-3.11'), @('py', '-3.13'), @('py', '-3.10'), @('python'), @('python3'))
    foreach ($try in $tries) {
        $command = Get-Command $try[0] -ErrorAction SilentlyContinue
        if (-not $command) { continue }
        $extra = @($try | Select-Object -Skip 1)
        try {
            $version = & $command.Source @extra -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        } catch { continue }
        if ($LASTEXITCODE -ne 0 -or -not $version) { continue }
        if (@('3.10', '3.11', '3.12', '3.13') -contains $version.Trim()) {
            return @{ exe = $command.Source; args = $extra; version = $version.Trim() }
        }
    }
    return $null
}

if (-not (Test-Path -LiteralPath $taskPython)) {
    $python = Find-Python
    if (-not $python) {
        throw 'Install 64-bit Python 3.12 from python.org (tick "Add python.exe to PATH"), then run setup again.'
    }
    Write-Host "Using Python $($python.version)"
    & $python.exe @($python.args) -m venv .venv
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
