$ErrorActionPreference='Stop'
$taskRoot=Split-Path -Parent $PSScriptRoot
$taskStore='D:\Ai Models'
$taskOllama=Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
if (-not (Test-Path -LiteralPath $taskOllama)) { throw 'The installed Ollama runtime was not found.' }
$env:OLLAMA_MODELS=Join-Path $taskStore 'ollama'
$env:OLLAMA_HOST='127.0.0.1:11434'
$env:OLLAMA_MAX_LOADED_MODELS='1'
$env:OLLAMA_NUM_PARALLEL='1'
$env:OLLAMA_CONTEXT_LENGTH='8192'
$env:OLLAMA_NO_CLOUD='1'
$env:OLLAMA_LLM_LIBRARY='cuda_v13'
$env:OLLAMA_VULKAN='0'
$env:OLLAMA_IGPU_ENABLE='0'
$env:CUDA_VISIBLE_DEVICES='0'
$env:CUDA_CACHE_PATH=Join-Path $taskStore 'cache\cuda'
New-Item -ItemType Directory -Force -Path $env:CUDA_CACHE_PATH | Out-Null
# EAGER was tested and timed out during GPU discovery on this laptop. Keep
# normal loading and reduce the semantic model's host allocation instead.
$env:CUDA_MODULE_LOADING='LAZY'
$taskProcess=Start-Process -FilePath $taskOllama -ArgumentList 'serve' -WorkingDirectory $taskRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskStore 'logs\ollama-runtime.log') -RedirectStandardError (Join-Path $taskStore 'logs\ollama-runtime-errors.log') -PassThru
Write-Output ('Local model runtime process '+$taskProcess.Id)
