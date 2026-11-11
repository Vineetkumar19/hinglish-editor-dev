$ErrorActionPreference='Stop'
$taskRoot=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$taskPython=Join-Path $taskRoot '.venv\Scripts\python.exe'
$taskEyePython='C:\Ai Models\runtimes\eyecontact\Scripts\python.exe'
$taskWheel='C:\Ai Models\eyecontact\onnxruntime_gpu-1.26.0-cp313-cp313-win_amd64.whl'
& $taskPython -E -X utf8 tools\ranged_download.py 'https://files.pythonhosted.org/packages/67/3f/59f1777a394625ecc9a85636de57dc47c25dbb5f888da050f1463955a0ce/onnxruntime_gpu-1.26.0-cp313-cp313-win_amd64.whl' --output $taskWheel --sha256 '6ab9f9c741d2e239b2e321ab0d389c04329d4ab7f11e3b92dd3aa7db1c59dee4'
if ($LASTEXITCODE -ne 0) {throw 'CUDA runtime download failed; configured CPU backend remains available'}
& $taskEyePython -E -X utf8 -m pip install --no-index --no-deps $taskWheel
if ($LASTEXITCODE -ne 0) {throw 'Isolated CUDA runtime install failed'}
$env:MPLCONFIGDIR='C:\Ai Models\runtimes\eyecontact\matplotlib-cache'
& $taskEyePython -E -X utf8 tools\validate_open_eyecontact.py --provider CUDAExecutionProvider --output output\validation\new-laptop\eyecontact-cuda
if ($LASTEXITCODE -ne 0) {throw 'CUDA benchmark failed; configured CPU backend is unchanged'}
& $taskEyePython -E -X utf8 tools\validate_open_eyecontact.py --provider CPUExecutionProvider --output output\validation\new-laptop\eyecontact-cpu-benchmark
if ($LASTEXITCODE -ne 0) {throw 'CPU comparison failed; configuration is unchanged'}
$taskGpu=Get-Content -LiteralPath 'output\validation\new-laptop\eyecontact-cuda\real-inference.json' -Raw | ConvertFrom-Json
$taskCpu=Get-Content -LiteralPath 'output\validation\new-laptop\eyecontact-cpu-benchmark\real-inference.json' -Raw | ConvertFrom-Json
$taskProvider=if ($taskGpu.passed -and $taskGpu.seconds -lt $taskCpu.seconds) {'CUDAExecutionProvider'} else {'CPUExecutionProvider'}
$taskConfigPath=Join-Path $taskRoot 'config.eyecontact.open.local.json'
$taskConfig=Get-Content -LiteralPath $taskConfigPath -Raw | ConvertFrom-Json
$taskConfig | Add-Member -NotePropertyName provider -NotePropertyValue $taskProvider -Force
$taskConfig | ConvertTo-Json | Set-Content -LiteralPath $taskConfigPath -Encoding utf8
@{selected_provider=$taskProvider;cpu_seconds=$taskCpu.seconds;cuda_seconds=$taskGpu.seconds;cuda_quality_passed=$taskGpu.passed} | ConvertTo-Json | Set-Content -LiteralPath 'C:\Ai Models\eyecontact\provider-benchmark.json' -Encoding utf8
Write-Output ('SELECTED_EYECONTACT_PROVIDER '+$taskProvider)
