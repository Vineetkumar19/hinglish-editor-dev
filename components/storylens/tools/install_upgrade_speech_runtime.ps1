$ErrorActionPreference='Stop'
$taskRoot=Split-Path -Parent $PSScriptRoot
$taskStore='C:\Ai Models'
$env:PYTHONPATH=''
$env:PIP_CACHE_DIR=Join-Path $taskStore 'runtimes\pip-cache'
$env:PIP_DEFAULT_TIMEOUT='120'
$taskTemporary=Join-Path $taskStore ('runtimes\tmp\speech-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $taskTemporary -Force | Out-Null
$env:TEMP=$taskTemporary
$env:TMP=$taskTemporary
$taskPython=Join-Path $taskRoot '.venv\Scripts\python.exe'
$taskWheel=Join-Path $taskStore 'runtimes\wheels\qwen_asr-0.0.6-py3-none-any.whl'
$taskPackage=if (Test-Path -LiteralPath $taskWheel) {$taskWheel} else {'qwen-asr==0.0.6'}
& $taskPython -E -X utf8 (Join-Path $taskRoot 'tools\prepare_speech_wheels.py')
if ($LASTEXITCODE -ne 0) { throw 'Speech dependency prefetch failed; partial files are retained.' }
& $taskPython -E -X utf8 -m pip install --no-index --no-build-isolation --find-links (Join-Path $taskStore 'runtimes\wheels') --constraint (Join-Path $taskRoot 'tools\model-upgrade-constraints.txt') --report (Join-Path $taskStore 'logs\speech-runtime-install.json') $taskPackage
if ($LASTEXITCODE -ne 0) { throw 'Speech runtime dependency installation failed; model downloads are unaffected.' }
& $taskPython -E -X utf8 -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Speech runtime dependency consistency check failed.' }
& $taskPython -E -X utf8 -c "import torch; from qwen_asr import Qwen3ASRModel; assert torch.__version__=='2.9.1+cu128'; assert torch.cuda.is_available(); print('QWEN_ASR_RUNTIME_READY')"
if ($LASTEXITCODE -ne 0) { throw 'Speech runtime import/CUDA check failed.' }
@{ready=$true;package='qwen-asr';version='0.0.6';torch='2.9.1+cu128'} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskStore 'logs\speech-runtime-ready.json') -Encoding utf8
