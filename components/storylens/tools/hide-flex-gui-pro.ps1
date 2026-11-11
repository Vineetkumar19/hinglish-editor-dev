$ErrorActionPreference = 'Stop'
$source = 'C:\Program Files (x86)\Common Files\Adobe\CEP\extensions\Flex GUI Pro'
$destination = 'D:\Full Drive\remove silence\output\template-aliner-evidence\disabled-extra-panels\Flex GUI Pro'
$receipt = 'D:\Full Drive\remove silence\output\template-aliner-evidence\flex-gui-menu-removal.json'
try {
 if (-not (Test-Path -LiteralPath $source)) { throw 'The original Flex GUI Pro folder was not found.' }
 if ((Resolve-Path -LiteralPath $source).Path -ne $source) { throw 'Unexpected source directory.' }
 if ([IO.Path]::GetFullPath((Split-Path -Parent $destination)) -ne 'D:\Full Drive\remove silence\output\template-aliner-evidence\disabled-extra-panels') { throw 'Unexpected backup directory.' }
 if (Test-Path -LiteralPath $destination) {
  if (@(Get-ChildItem -LiteralPath $destination -Force).Count -ne 0) { throw 'The backup directory contains files; nothing was overwritten.' }
  Remove-Item -LiteralPath $destination
 }
 Move-Item -LiteralPath $source -Destination $destination
 @{ok=$true;source=$source;backup=$destination;restart_required=$true} | ConvertTo-Json | Set-Content -LiteralPath $receipt -Encoding utf8
} catch {
 @{ok=$false;message=$_.Exception.Message;source=$source} | ConvertTo-Json | Set-Content -LiteralPath $receipt -Encoding utf8
 exit 1
}
