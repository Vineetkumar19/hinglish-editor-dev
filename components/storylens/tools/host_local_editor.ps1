$ErrorActionPreference='Stop'
$taskRoot=Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH=''
$env:HF_HOME='C:\Ai Models\cache\huggingface'
$env:HF_HUB_CACHE='C:\Ai Models\cache\huggingface\hub'
$env:TORCH_HOME='C:\Ai Models\cache\torch'
$env:U2NET_HOME='C:\Ai Models\editor-models\rembg'
$env:OLLAMA_MODELS='D:\Ai Models\ollama'
$taskPython=Join-Path $taskRoot '.venv\Scripts\python.exe'
$taskArguments=@('-E','-X','utf8','-m','hinglish_app','--root',('"'+$taskRoot+'"'),
                 '--port','8765','--no-open','--no-publisher-worker')
$taskProcess=Start-Process -FilePath $taskPython -ArgumentList $taskArguments -WindowStyle Hidden -WorkingDirectory $taskRoot -RedirectStandardOutput (Join-Path $taskRoot 'downloads\localhost-editor.log') -RedirectStandardError (Join-Path $taskRoot 'downloads\localhost-editor-errors.log') -PassThru
Write-Output ('Editor process '+$taskProcess.Id+'; http://127.0.0.1:8765/')
