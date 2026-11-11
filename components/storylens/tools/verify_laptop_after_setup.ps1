param([switch]$GenerationOnly)
$ErrorActionPreference='Stop'
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
$taskRoot=Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $taskRoot
$env:PYTHONIOENCODING='utf-8'
$taskPython=Join-Path $taskRoot '.venv\Scripts\python.exe'
$taskEnvironmentLog=Join-Path $taskRoot 'downloads\finish-environments-isolated.log'
$taskModelState=Join-Path $taskRoot 'downloads\laptop-model-downloads.json'
$taskDeadline=(Get-Date).AddHours(24)
$taskStatus=Join-Path $taskRoot 'output\validation\new-laptop\SETUP_STATUS.md'
if (-not $GenerationOnly) {
$taskOllama=Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
try { $null=Invoke-RestMethod 'http://127.0.0.1:11434/api/version' -TimeoutSec 5 }
catch {
    if (-not (Test-Path -LiteralPath $taskOllama)) { throw 'The installed Ollama application could not be found.' }
    Start-Process -FilePath $taskOllama -ArgumentList 'serve' -WindowStyle Hidden
    $taskOllamaReady=$false
    for ($taskAttempt=0; $taskAttempt -lt 30; $taskAttempt++) {
        Start-Sleep -Seconds 1
        try {
            $null=Invoke-RestMethod 'http://127.0.0.1:11434/api/version' -TimeoutSec 2
            $taskOllamaReady=$true; break
        } catch { }
    }
    if (-not $taskOllamaReady) { throw 'Ollama did not become ready for local inference.' }
}
}
function Wait-For($test, $description) {
    Write-Output "Waiting for $description."
    while (-not (& $test)) {
        if ((Get-Date) -gt $taskDeadline) { throw "Timed out waiting for $description. Downloads can be resumed." }
        Start-Sleep -Seconds 20
    }
}
if ($GenerationOnly) {
    $taskCore=Get-Content -LiteralPath (Join-Path $taskRoot 'output\validation\new-laptop\core-inference.json') -Raw -Encoding utf8 | ConvertFrom-Json
    $taskRequired=@('cuda_arithmetic','hinglish_speech_vad_and_alignment','independent_turbo_speech',
        'fixed_e5_retrieval_encoder','clip_broll_ranking','clap_audio_ranking','bundled_qwen_structured_output',
        'yunet_face_location','background_removal_onnx')
    foreach ($taskCheck in $taskRequired) {
        if ($taskCore.$taskCheck.passed -ne $true) { throw "No passing saved core check for $taskCheck; run the full verification." }
    }
    Write-Output 'USING_SAVED_PASSING_CORE_CHECKS'
} else {
Wait-For { (Test-Path -LiteralPath $taskEnvironmentLog) -and
    (Select-String -LiteralPath $taskEnvironmentLog -SimpleMatch 'CORE_GPU_ENVIRONMENT_READY' -Quiet) } 'the isolated core GPU environment'
& $taskPython -E -X utf8 (Join-Path $taskRoot 'tools\validate_laptop_models.py') --phase core *> 'downloads\core-inference-check.log'
if ($LASTEXITCODE -ne 0) {
    'Core inference needs attention. See core-inference.json and downloads/core-inference-check.log. Generation downloads continue separately.' | Set-Content -LiteralPath $taskStatus -Encoding utf8
    throw 'Core inference failed; GPU defaults were not activated.'
}
@'
import json,shutil
from pathlib import Path
root=Path.cwd()
checks=json.loads((root/'output/validation/new-laptop/core-inference.json').read_text(encoding='utf-8'))
required={'cuda_arithmetic','hinglish_speech_vad_and_alignment','independent_turbo_speech',
          'fixed_e5_retrieval_encoder','clip_broll_ranking','clap_audio_ranking',
          'bundled_qwen_structured_output','yunet_face_location','background_removal_onnx'}
assert required <= checks.keys() and all(row['passed'] for row in checks.values())
for relative in ('config.models.local.json','config.phase2.json','config.rtx5070.json'):
 p=root/relative;b=p.with_suffix('.json.before-gpu-activation')
 if p.exists() and not b.exists():shutil.copy2(p,b)
 data=json.loads(p.read_text(encoding='utf-8-sig')) if p.exists() else {}
 data['device']='cuda'
 if relative!='config.models.local.json':data['cpu_threads']=8
 p.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
'@ | & $taskPython -E -X utf8 -
if ($LASTEXITCODE -ne 0) { throw 'Could not activate validated GPU defaults.' }
'Core GPU inference passed. NVIDIA RTX defaults enabled. Image/video downloads and validation remain in progress. Eye Contact requires the NVIDIA SDK.' | Set-Content -LiteralPath $taskStatus -Encoding utf8
Write-Output 'CORE_INFERENCE_VALIDATED_AND_GPU_DEFAULTS_ENABLED'
}
Wait-For { (Select-String -LiteralPath $taskEnvironmentLog -SimpleMatch 'GENERATION_GPU_ENVIRONMENT_READY' -Quiet) } 'the isolated generation environment'
Wait-For {
    try {
        $taskModels=(Get-Content -LiteralPath $taskModelState -Raw | ConvertFrom-Json).models
        $taskModels.'Tongyi-MAI/Z-Image-Turbo'.status -eq 'downloaded' -and $taskModels.'Wan-AI/Wan2.2-TI2V-5B-Diffusers'.status -eq 'downloaded'
    } catch { $false }
} 'verified image and video model weights'
& $taskPython -E -X utf8 (Join-Path $taskRoot 'tools\validate_laptop_generation.py') *> 'downloads\generation-inference-check.log'
if ($LASTEXITCODE -ne 0) {
    'Core GPU checks passed and NVIDIA RTX defaults are enabled. Generation needs attention: see generation-inference.json and its worker_log path. Eye Contact requires the NVIDIA SDK.' | Set-Content -LiteralPath $taskStatus -Encoding utf8
    throw 'Generation inference failed; see the validation receipt.'
}
'Core GPU checks and bounded image/video generation passed. NVIDIA RTX defaults are enabled. These are small runtime controls; production-resolution performance has not been measured. Eye Contact remains pending the NVIDIA SDK.' | Set-Content -LiteralPath $taskStatus -Encoding utf8
Write-Output 'LOCAL_MODEL_INFERENCE_VALIDATION_COMPLETE'
