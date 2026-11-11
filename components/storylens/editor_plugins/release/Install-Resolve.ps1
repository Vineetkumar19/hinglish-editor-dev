# Per-user installation, with a backup if an older script exists. No registry changes.
$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'plugins\davinci-resolve-studio\Hinglish Editor.py'
if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw 'Verified Resolve script not found.' }
$base = Join-Path $env:APPDATA 'Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility'
New-Item -ItemType Directory -Path $base -Force | Out-Null
$target = Join-Path $base 'Hinglish Editor.py'
if (Test-Path -LiteralPath $target) {
    Copy-Item -LiteralPath $target -Destination ($target + '.backup-' + (Get-Date -Format 'yyyyMMddHHmmss'))
}
Copy-Item -LiteralPath $source -Destination $target
Write-Output 'Resolve integration installed. Restart Resolve Studio, then Workspace > Scripts > Utility > Hinglish Editor.'
