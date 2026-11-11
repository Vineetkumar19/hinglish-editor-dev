$ErrorActionPreference='Stop'
$taskRoot=Split-Path -Parent $PSScriptRoot
$taskStore=[IO.Path]::GetFullPath('C:\Ai Models')
if ($taskStore -ne 'C:\Ai Models') { throw 'Unexpected model store.' }
New-Item -ItemType Directory -Path $taskStore -Force | Out-Null
$taskMoves=@(
    @{source=(Join-Path $taskRoot 'models'); target=(Join-Path $taskStore 'editor-models')},
    @{source=(Join-Path $taskRoot 'tools\aigen\install\models'); target=(Join-Path $taskStore 'generation-models')},
    @{source=(Join-Path $env:USERPROFILE '.ollama\models'); target=(Join-Path $taskStore 'ollama')}
)
$taskResults=@()
foreach ($taskMove in $taskMoves) {
    $taskSource=[IO.Path]::GetFullPath($taskMove.source)
    $taskTarget=[IO.Path]::GetFullPath($taskMove.target)
    if (-not $taskTarget.StartsWith($taskStore+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Target escaped the selected model store.' }
    if (-not (Test-Path -LiteralPath $taskSource)) { continue }
    $taskItem=Get-Item -LiteralPath $taskSource -Force
    if ($taskItem.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        if ([IO.Path]::GetFullPath($taskItem.Target) -ne $taskTarget) { throw 'An existing model junction points elsewhere.' }
        Write-Output "Already redirected: $taskSource"
        continue
    }
    if ((Test-Path -LiteralPath $taskTarget) -and ((Get-Item -LiteralPath $taskTarget -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Migration target must be a real directory.' }
    Write-Output "Copying existing model files: $taskSource -> $taskTarget"
    & robocopy $taskSource $taskTarget /E /COPY:DAT /DCOPY:DAT /R:2 /W:1 /NFL /NDL /NJH /NJS
    if ($LASTEXITCODE -ge 8) { throw "Model copy failed: robocopy $LASTEXITCODE" }
    $taskFiles=Get-ChildItem -LiteralPath $taskSource -File -Recurse -Force
    $taskBytes=0L
    foreach ($taskFile in $taskFiles) {
        $taskRelative=[IO.Path]::GetRelativePath($taskSource,$taskFile.FullName)
        $taskCopied=Join-Path $taskTarget $taskRelative
        if (-not (Test-Path -LiteralPath $taskCopied) -or (Get-Item -LiteralPath $taskCopied).Length -ne $taskFile.Length) { throw "Incomplete copied model: $taskRelative" }
        if ((Get-FileHash -LiteralPath $taskFile.FullName -Algorithm SHA256).Hash -ne (Get-FileHash -LiteralPath $taskCopied -Algorithm SHA256).Hash) { throw "Copied model checksum failed: $taskRelative" }
        $taskBytes+=$taskFile.Length
    }
    # Every source is an explicitly enumerated model folder. Backups stay next
    # to that folder until the verified junction is installed and checked.
    $taskBackup=$taskSource+'-before-C-migration-'+(Get-Date -Format 'yyyyMMdd-HHmmss')
    $taskParent=[IO.Path]::GetDirectoryName($taskSource)
    if ([IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($taskBackup)) -ne $taskParent) { throw 'Unsafe backup target.' }
    if (Test-Path -LiteralPath $taskBackup) { throw 'Migration backup already exists.' }
    Move-Item -LiteralPath $taskSource -Destination $taskBackup
    try {
        New-Item -ItemType Junction -Path $taskSource -Target $taskTarget | Out-Null
        $taskLink=Get-Item -LiteralPath $taskSource -Force
        if (-not ($taskLink.Attributes -band [IO.FileAttributes]::ReparsePoint) -or [IO.Path]::GetFullPath($taskLink.Target) -ne $taskTarget) { throw 'The new model junction could not be verified.' }
        $taskCheckedBackup=[IO.Path]::GetFullPath($taskBackup)
        if ([IO.Path]::GetDirectoryName($taskCheckedBackup) -ne $taskParent -or -not $taskCheckedBackup.StartsWith($taskSource+'-before-C-migration-',[StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe model backup cleanup.' }
        Remove-Item -LiteralPath $taskCheckedBackup -Recurse -Force
    } catch {
        # Keep the source backup for recovery if installation/cleanup fails.
        throw
    }
    $taskResults+=@{source=$taskSource;target=$taskTarget;verified_files=$taskFiles.Count;bytes_relocated=$taskBytes}
    $taskResults | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $taskRoot 'downloads\model-storage-migration.json') -Encoding utf8
    Write-Output "VERIFIED_AND_REDIRECTED: $taskSource ($([math]::Round($taskBytes/1GB,2)) GiB)"
}
$taskVariables=@{HF_HOME='cache\huggingface';HF_HUB_CACHE='cache\huggingface\hub';TORCH_HOME='cache\torch';MODELSCOPE_CACHE='cache\modelscope';U2NET_HOME='rembg';OLLAMA_MODELS='ollama'}
foreach ($taskName in $taskVariables.Keys) {
    $taskValue=Join-Path $taskStore $taskVariables[$taskName]
    [Environment]::SetEnvironmentVariable($taskName,$taskValue,'User')
}
Write-Output 'EXISTING_MODEL_STORAGE_MIGRATION_COMPLETE'
