$ErrorActionPreference='Stop'
$taskRoot=Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $taskRoot
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
$taskDeadline=(Get-Date).AddHours(24)
Write-Output 'Waiting for checked image weights and completed core GPU checks.'
while ($true) {
    if ((Get-Date) -gt $taskDeadline) { throw 'Image download wait timed out; the setup can be resumed.' }
    try {
        $taskModels=(Get-Content 'downloads/laptop-model-downloads.json' -Raw | ConvertFrom-Json).models
        $taskPreferences=Get-Content 'config.models.local.json' -Raw | ConvertFrom-Json
        if ($taskModels.'Tongyi-MAI/Z-Image-Turbo'.status -eq 'downloaded' -and
            $taskPreferences.device -eq 'cuda') { break }
    } catch { }
    Start-Sleep -Seconds 20
}
& '.\.venv\Scripts\python.exe' -E -X utf8 'tools/validate_laptop_generation.py' --image-only *> 'downloads/image-generation-inference-check.log'
if ($LASTEXITCODE -ne 0) { throw 'Image generation failed; see image-generation-inference.json and generation-worker.log.' }
'Core GPU checks and real image generation passed. RTX defaults are enabled. Video download and validation remain in progress. Eye Contact requires the NVIDIA SDK.' | Set-Content 'output/validation/new-laptop/SETUP_STATUS.md' -Encoding utf8
Write-Output 'REAL_IMAGE_GENERATION_VALIDATED'
