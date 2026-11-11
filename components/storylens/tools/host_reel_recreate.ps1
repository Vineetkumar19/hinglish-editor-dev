$ErrorActionPreference='Stop'
$taskRoot=Split-Path -Parent $PSScriptRoot
$taskPython=Join-Path $taskRoot '.venv\Scripts\python.exe'
if(-not (Test-Path -LiteralPath $taskPython)){throw 'Storylens Python runtime is missing.'}
$env:PYTHONPATH=''
$env:HF_HOME='C:\Ai Models\cache\huggingface'
$env:HF_HUB_CACHE='C:\Ai Models\cache\huggingface\hub'
$env:TORCH_HOME='C:\Ai Models\cache\torch'
$env:U2NET_HOME='C:\Ai Models\editor-models\rembg'
$env:OLLAMA_MODELS='D:\Ai Models\ollama'
try{
    $health=Invoke-RestMethod 'http://127.0.0.1:8894/api/health' -TimeoutSec 2
    if($health.ok){Write-Output 'Reel Recreate is already available at http://127.0.0.1:8894/';exit 0}
}catch{}
$taskArgs=@('-E','-X','utf8','-m','hinglish_app','--root',('"'+$taskRoot+'"'),
            '--port','8894','--no-open','--no-publisher-worker','--no-publish-bridge','--no-supervisor')
$taskProcess=Start-Process -FilePath $taskPython -ArgumentList $taskArgs -WorkingDirectory $taskRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskRoot 'output\reel-recreate-8894.stdout.log') -RedirectStandardError (Join-Path $taskRoot 'output\reel-recreate-8894.stderr.log') -PassThru
for($attempt=0;$attempt -lt 20;$attempt++){
    Start-Sleep -Milliseconds 500
    try{if((Invoke-RestMethod 'http://127.0.0.1:8894/api/health' -TimeoutSec 2).ok){Write-Output ('Reel Recreate ready on port 8894 (process '+$taskProcess.Id+').');exit 0}}catch{}
}
throw 'Reel Recreate did not become ready. Check output\reel-recreate-8894.stderr.log.'
