$ErrorActionPreference='Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskRuntime = Join-Path $taskRoot 'tools\llama\b11011-cuda13'
$taskArchives = @(
    @{Name='llama-b11011-bin-win-cuda-13.4-x64.zip'; Hash='27b5f337db85f1c23716c9752497b363e4d4be4cdb5eee557b775f5c2554847a'},
    @{Name='cudart-llama-bin-win-cuda-13.4-x64.zip'; Hash='738f8c251ac22b70c3ae6f83a10cf222725df0395246a2cf58f32bdb85fbe668'}
)
New-Item -ItemType Directory -Force -Path $taskRuntime | Out-Null
foreach ($taskAsset in $taskArchives) {
    $taskArchive = Join-Path $taskRuntime $taskAsset.Name
    if (-not (Test-Path -LiteralPath $taskArchive) -or (Get-FileHash -LiteralPath $taskArchive -Algorithm SHA256).Hash -ne $taskAsset.Hash) {
        Write-Output "Downloading $($taskAsset.Name)"
        & (Join-Path $taskRoot '.venv\Scripts\python.exe') (Join-Path $taskRoot 'tools\ranged_download.py') `
            ('https://github.com/ggml-org/llama.cpp/releases/download/b11011/' + $taskAsset.Name) `
            --output $taskArchive --sha256 $taskAsset.Hash
        if ($LASTEXITCODE -ne 0) { throw 'CUDA runtime download failed; rerun to resume.' }
    }
    if ((Get-FileHash -LiteralPath $taskArchive -Algorithm SHA256).Hash -ne $taskAsset.Hash) { throw 'llama.cpp archive checksum mismatch' }
    Expand-Archive -LiteralPath $taskArchive -DestinationPath $taskRuntime -Force
}
$taskServer = Get-ChildItem -LiteralPath $taskRuntime -Recurse -Filter llama-server.exe | Select-Object -First 1
if (-not $taskServer) { throw 'CUDA llama-server.exe is missing' }
$taskDevices = & $taskServer.FullName --list-devices 2>&1 | Out-String
Write-Output $taskDevices
if ($LASTEXITCODE -ne 0 -or $taskDevices -notmatch 'RTX 5070') { throw 'The CUDA runtime did not detect the RTX GPU; existing runtime configuration was preserved.' }
$taskRuntimeFile = Join-Path $taskRoot 'tools\llama\runtime.json'
foreach ($taskRelative in @('tools\llama\runtime.json','models\meaning-upgrade.json','models\meaning-models.json')) {
    $taskFile = Join-Path $taskRoot $taskRelative
    if (-not (Test-Path -LiteralPath $taskFile)) { continue }
    $taskBackup = $taskFile + '.before-cuda'
    if (-not (Test-Path -LiteralPath $taskBackup)) { Copy-Item -LiteralPath $taskFile -Destination $taskBackup }
    $taskData = Get-Content -LiteralPath $taskFile -Raw | ConvertFrom-Json
    $taskData | Add-Member -NotePropertyName server_path -NotePropertyValue $taskServer.FullName -Force
    $taskData | Add-Member -NotePropertyName gpu_layers -NotePropertyValue 99 -Force
    $taskData | Add-Member -NotePropertyName runtime_sha256 -NotePropertyValue $taskArchives[0].Hash -Force
    [IO.File]::WriteAllText($taskFile, ($taskData | ConvertTo-Json -Depth 12), [Text.UTF8Encoding]::new($false))
}
Write-Output 'Pinned CUDA llama.cpp runtime installed. Existing CPU runtime remains available as a backup.'
