param([switch]$EnableUnsignedPanels)
$ErrorActionPreference='Stop'
$sourceRoot=$PSScriptRoot
$extensionRoot=Join-Path $env:APPDATA 'Adobe/CEP/extensions'
$destination=Join-Path $extensionRoot 'com.storylens.templateassembler'
New-Item -ItemType Directory -Path $extensionRoot -Force | Out-Null
if(Test-Path -LiteralPath $destination){
  $backup=$destination+'.backup-'+(Get-Date -Format 'yyyyMMdd-HHmmss')
  Copy-Item -LiteralPath $destination -Destination $backup -Recurse
}
New-Item -ItemType Directory -Path $destination -Force | Out-Null
Get-ChildItem -LiteralPath $sourceRoot | Where-Object {$_.Name -ne 'Install.ps1'} | Copy-Item -Destination $destination -Recurse -Force
if($EnableUnsignedPanels){
  foreach($version in 11,12){$key="HKCU:/Software/Adobe/CSXS.$version";New-Item -Path $key -Force | Out-Null;New-ItemProperty -Path $key -Name PlayerDebugMode -Value '1' -PropertyType String -Force | Out-Null}
}
Write-Output "Installed source panel: $destination"
Write-Output 'Open Window > Extensions (Legacy) > Storylens Template Assembler in After Effects or Premiere.'
Write-Output 'This development panel requires Adobe unsigned CEP loading. EnableUnsignedPanels changes that per-user setting only when explicitly selected.'
