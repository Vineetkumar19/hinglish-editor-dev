$ErrorActionPreference='Stop'
$taskRoot=Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $taskRoot
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
$taskActive=Get-CimInstance Win32_Process | Where-Object {
    $_.ProcessId -ne $PID -and (
        ($_.Name -eq 'python.exe' -and
            ($_.CommandLine -like '*prepare_laptop_models.py*' -or $_.CommandLine -like '*prefetch_laptop_dependencies.py*' -or
             $_.CommandLine -like '*validate_laptop_models.py*' -or $_.CommandLine -like '*validate_laptop_generation.py*' -or
             $_.CommandLine -like '*prepare_laptop_cutouts.py*')) -or
        ($_.Name -in @('pwsh.exe','powershell.exe') -and
            ($_.CommandLine -like '*finish_laptop_environment.ps1*' -or $_.CommandLine -like '*verify_laptop_after_setup.ps1*')))
}
if ($taskActive) {
    Write-Output 'Laptop model setup is already running. See downloads/huggingface-model-setup.log and downloads/package-prefetch.log.'
    exit 0
}
$taskPython=Join-Path $taskRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) { throw 'The new Python environment is missing. Run Setup RTX 5070.bat first.' }
$env:PIP_CACHE_DIR=Join-Path $taskRoot 'cache\pip'
$env:PYTHONIOENCODING='utf-8'
$taskOllamaBin=Join-Path $env:LOCALAPPDATA 'Programs\Ollama'
if (Test-Path -LiteralPath (Join-Path $taskOllamaBin 'ollama.exe')) { $env:Path=$taskOllamaBin+';'+$env:Path }
try { $null=Invoke-RestMethod 'http://127.0.0.1:11434/api/version' -TimeoutSec 5 }
catch {
    Start-Process -FilePath 'ollama.exe' -ArgumentList 'serve' -WindowStyle Hidden
    Start-Sleep -Seconds 5
}
$taskTags=(Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 15).models.name
foreach ($taskModel in @('qwen3.5:9b','qwen3:8b','qwen3-embedding:0.6b')) {
    if ($taskModel -notin $taskTags) {
        & ollama pull $taskModel
        if ($LASTEXITCODE -ne 0) { throw "Could not download $taskModel" }
    }
}
& $taskPython -E (Join-Path $PSScriptRoot 'prefetch_laptop_dependencies.py') *>> 'downloads\package-prefetch.log'
if ($LASTEXITCODE -ne 0) { throw 'Package prefetch failed. See downloads/package-prefetch.log.' }
& $taskPython -E (Join-Path $PSScriptRoot 'ranged_download.py') 'https://download.pytorch.org/whl/cu128/torch-2.9.1%2Bcu128-cp313-cp313-win_amd64.whl' --output 'downloads\wheels\torch-2.9.1+cu128-cp313-cp313-win_amd64.whl' --index-url 'https://download.pytorch.org/whl/cu128/torch/' *>> 'downloads\torch-wheel-download.log'
if ($LASTEXITCODE -ne 0) { throw 'CUDA wheel download failed.' }
& (Join-Path $PSScriptRoot 'finish_laptop_environment.ps1') *>> 'downloads\finish-environments-isolated.log'
if ($LASTEXITCODE -ne 0) { throw 'Environment setup failed.' }
& $taskPython -E -X utf8 (Join-Path $PSScriptRoot 'prepare_laptop_cutouts.py') *>> 'downloads\cutout-model-setup.log'
if ($LASTEXITCODE -ne 0) { throw 'Background-removal model download failed.' }
& $taskPython -E (Join-Path $PSScriptRoot 'prepare_laptop_models.py') --group all *>> 'downloads\huggingface-model-setup.log'
if ($LASTEXITCODE -ne 0) { throw 'Model download failed.' }
& (Join-Path $PSScriptRoot 'import_laptop_meaning.ps1') *>> 'downloads\meaning-ollama-import.log'
if ($LASTEXITCODE -ne 0) { throw 'Meaning model import failed.' }
& (Join-Path $PSScriptRoot 'verify_laptop_after_setup.ps1') *>> 'downloads\verification-coordinator.log'
