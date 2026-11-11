$ErrorActionPreference='Stop'
$taskRoot=Split-Path -Parent $PSScriptRoot
$taskPython=Join-Path $taskRoot '.venv\Scripts\python.exe'
$taskWheel='C:\Ai Models\runtimes\wheels\torchvision-0.24.1+cu128-cp313-cp313-win_amd64.whl'
$env:PIP_CACHE_DIR='C:\Ai Models\cache\pip'
$env:PYTHONPATH=''
& $taskPython -E -X utf8 (Join-Path $taskRoot 'tools\ranged_download.py') 'https://download.pytorch.org/whl/cu128/torchvision-0.24.1%2Bcu128-cp313-cp313-win_amd64.whl' --output $taskWheel --index-url 'https://download.pytorch.org/whl/cu128/torchvision/'
if ($LASTEXITCODE -ne 0) { throw 'Torchvision wheel verification failed.' }
& $taskPython -E -m pip install --no-index --no-deps $taskWheel
if ($LASTEXITCODE -ne 0) { throw 'Torchvision installation failed.' }
& $taskPython -E -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Vision runtime dependency check failed.' }
& $taskPython -E -c 'import torch,torchvision; print(torch.__version__,torchvision.__version__); assert torch.__version__=="2.9.1+cu128"; assert torchvision.__version__=="0.24.1+cu128"; print(torchvision.ops.nms(torch.tensor([[0.,0.,10.,10.]],device="cuda"),torch.tensor([1.],device="cuda"),.5))'
if ($LASTEXITCODE -ne 0) { throw 'Torchvision CUDA control failed.' }
Write-Output 'VISION_RUNTIME_READY'
