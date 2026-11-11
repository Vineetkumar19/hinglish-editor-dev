$ErrorActionPreference='Stop'
$taskRoot=Split-Path -Parent $PSScriptRoot
$taskStore=[IO.Path]::GetFullPath('C:\Ai Models')
$taskCompletion=Get-Content -LiteralPath (Join-Path $taskStore 'logs\model-upgrade-completion.json') -Raw | ConvertFrom-Json
if ($taskCompletion.status -ne 'activated_cleanup_pending') { throw 'Validated activation receipt is required before retiring models.' }
$taskSelection=Get-Content -LiteralPath (Join-Path $taskRoot 'config.model_storage.local.json') -Raw | ConvertFrom-Json
if (-not $taskSelection.active -or $taskSelection.root -ne $taskStore) { throw 'C-drive model selection must be active first.' }
foreach ($taskRole in @('planner','meaning','embedding','asr','independent_asr','broll_vision','cutout')) {
    $taskProof=Get-Content -LiteralPath (Join-Path $taskStore ('logs\upgrade-validation-'+$taskRole+'.json')) -Raw | ConvertFrom-Json
    if (-not $taskProof.passed) { throw "Inference validation is missing: $taskRole" }
    if ($taskProof.model_path -ne $taskSelection.roles.$taskRole.path -or $taskProof.model_revision -ne $taskSelection.roles.$taskRole.revision) { throw "Inference validation identifies a different model: $taskRole" }
}
# This exact allowlist contains only weights replaced by the seven upgrades.
$taskRetire=@(
    'models--Oriserve--Whisper-Hindi2Hinglish-Swift',
    'models--dropbox-dash--faster-whisper-large-v3-turbo',
    'models--intfloat--multilingual-e5-small',
    'models--openai--clip-vit-base-patch32',
    'models--Qwen--Qwen2.5-1.5B-Instruct',
    'models--unsloth--Qwen3-4B-Instruct-2507-GGUF',
    'rembg\models\birefnet-general-lite',
    'rembg\models\isnet-general-use'
)
$taskBase=[IO.Path]::GetFullPath((Join-Path $taskStore 'editor-models'))
if ((Get-Item -LiteralPath $taskBase -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Retirement base cannot be a junction.' }
$taskRemoved=@()
foreach ($taskRelative in $taskRetire) {
    $taskTarget=[IO.Path]::GetFullPath((Join-Path $taskBase $taskRelative))
    if (-not $taskTarget.StartsWith($taskBase+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe retirement target.' }
    if (-not (Test-Path -LiteralPath $taskTarget)) { continue }
    if ((Get-Item -LiteralPath $taskTarget -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Refusing to recursively delete a redirected model folder.' }
    Remove-Item -LiteralPath $taskTarget -Recurse -Force
    $taskRemoved+=$taskTarget
}
$taskTags=(Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags').models.name
foreach ($taskTag in @('qwen3.5:9b','qwen3:8b','qwen3-embedding:0.6b','storylens-meaning:4b')) {
    if ($taskTags -contains $taskTag) {
        Invoke-RestMethod -Method Delete -Uri 'http://127.0.0.1:11434/api/delete' -ContentType 'application/json' -Body (@{model=$taskTag}|ConvertTo-Json) | Out-Null
        $taskRemoved+='Ollama: '+$taskTag
    }
}
# This downloaded recognizer was rejected by the actual Hinglish edit control.
# Remove it only after the different native-Hinglish recognizer has passed and
# become the active selection checked above.
if ($taskSelection.roles.asr.repo -eq 'Oriserve/Whisper-Hindi2Hinglish-Prime') {
    $taskRejectedFile=Join-Path $taskStore 'logs\rejected-qwen-asr-selection.json'
    if (Test-Path -LiteralPath $taskRejectedFile) {
        $taskRejected=Get-Content -LiteralPath $taskRejectedFile -Raw | ConvertFrom-Json
        $taskCandidateBase=[IO.Path]::GetFullPath((Join-Path $taskStore 'huggingface'))
        $taskRejectedTarget=[IO.Path]::GetFullPath((Join-Path $taskCandidateBase 'Qwen--Qwen3-ASR-1.7B'))
        if ($taskRejected.repo -ne 'Qwen/Qwen3-ASR-1.7B' -or [IO.Path]::GetFullPath($taskRejected.path) -ne $taskRejectedTarget) { throw 'Rejected ASR identity mismatch.' }
        if (-not $taskRejectedTarget.StartsWith($taskCandidateBase+'\',[StringComparison]::OrdinalIgnoreCase) -or $taskSelection.roles.asr.path -eq $taskRejectedTarget) { throw 'Unsafe rejected ASR retirement target.' }
        if ((Get-Item -LiteralPath $taskCandidateBase -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Candidate base cannot be redirected.' }
        if (Test-Path -LiteralPath $taskRejectedTarget) {
            if ((Get-Item -LiteralPath $taskRejectedTarget -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Rejected model cannot be redirected.' }
            Remove-Item -LiteralPath $taskRejectedTarget -Recurse -Force
            $taskRemoved+=$taskRejectedTarget
        }
    }
}
@{removed=$taskRemoved;storage_root=$taskStore;completed=(Get-Date).ToString('o')} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $taskStore 'logs\retired-models.json') -Encoding utf8
Write-Output 'REPLACED_OLD_MODELS_RETIRED'
