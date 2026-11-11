$ErrorActionPreference='Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskManifestPath = Join-Path $taskRoot 'models\meaning-upgrade.json'
$taskManifest = Get-Content -LiteralPath $taskManifestPath -Raw | ConvertFrom-Json
$taskWeight = $taskManifest.judge_path
if (-not (Test-Path -LiteralPath $taskWeight)) { throw 'Relocate/prepare the pinned semantic weights first.' }
$taskDefinition = Join-Path $taskRoot 'tools\llama\StorylensMeaning.Modelfile'
$taskContent = 'FROM "' + ($taskWeight -replace '\\','/') + '"' + "`nPARAMETER num_ctx 8192`nPARAMETER temperature 0`nPARAMETER seed 0`n"
[IO.File]::WriteAllText($taskDefinition, $taskContent, [Text.UTF8Encoding]::new($false))
& ollama create 'storylens-meaning:4b' -f $taskDefinition
if ($LASTEXITCODE -ne 0) { throw 'Ollama could not import the pinned semantic GGUF.' }
$taskVersion = (Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 10).version
foreach ($taskRelative in @('models\meaning-upgrade.json','models\meaning-models.json')) {
    $taskFile = Join-Path $taskRoot $taskRelative
    $taskData = Get-Content -LiteralPath $taskFile -Raw | ConvertFrom-Json
    if (-not (Test-Path -LiteralPath ($taskFile + '.before-ollama'))) { Copy-Item -LiteralPath $taskFile -Destination ($taskFile + '.before-ollama') }
    $taskData | Add-Member -NotePropertyName backend -NotePropertyValue 'ollama' -Force
    $taskData | Add-Member -NotePropertyName ollama_model -NotePropertyValue 'storylens-meaning:4b' -Force
    $taskData | Add-Member -NotePropertyName ollama_version -NotePropertyValue $taskVersion -Force
    [IO.File]::WriteAllText($taskFile, ($taskData | ConvertTo-Json -Depth 12), [Text.UTF8Encoding]::new($false))
}
Write-Output 'Pinned semantic model imported into the existing local Ollama GPU runtime.'
