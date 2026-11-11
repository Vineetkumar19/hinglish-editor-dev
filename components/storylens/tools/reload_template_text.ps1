$ErrorActionPreference='Stop'
$root='D:\Full Drive\remove silence'
Set-Location -LiteralPath $root
& .venv/Scripts/python.exe tools/check_template_text_idle.py
if($LASTEXITCODE -ne 0){throw 'Idle check failed; service unchanged.'}
$listener=Get-NetTCPConnection -LocalPort 8765 -State Listen
$ownerIds=@($listener.OwningProcess|Sort-Object -Unique)
if($ownerIds.Count -ne 1){throw 'Expected one Storylens listener.'}
$proc=Get-CimInstance Win32_Process -Filter "ProcessId=$($ownerIds[0])"
if($proc.CommandLine -notmatch '-m hinglish_app' -or $proc.CommandLine -notmatch [regex]::Escape($root) -or $proc.CommandLine -notmatch '--port 8765' -or $proc.CommandLine -notmatch '--no-publisher-worker'){throw 'Listener flags differ; service unchanged.'}
$record=[ordered]@{old_listener=$proc.ProcessId;flags='--port 8765 --no-open --no-publisher-worker';native_verified=$false}
Stop-Process -Id $proc.ProcessId
$startArgs=@('-E','-X','utf8','-m','hinglish_app','--root',('"'+$root+'"'),'--port','8765','--no-open','--no-publisher-worker')
$launcher=Start-Process -FilePath "$root\.venv\Scripts\python.exe" -ArgumentList $startArgs -WindowStyle Hidden -WorkingDirectory $root -RedirectStandardOutput "$root\output\template-text-evidence\server-stdout.log" -RedirectStandardError "$root\output\template-text-evidence\server-stderr.log" -PassThru
$record.launcher=$launcher.Id
$ready=$false
for($i=0;$i -lt 40;$i++){try{$health=Invoke-RestMethod 'http://127.0.0.1:8765/api/health';if($health.ok){$ready=$true;break}}catch{};Start-Sleep -Milliseconds 500}
if(-not $ready){throw 'Storylens did not confirm startup. See saved logs.'}
$html=Invoke-WebRequest 'http://127.0.0.1:8765/editor-panel.html?host=aftereffects'
$script=Invoke-WebRequest 'http://127.0.0.1:8765/template-text.js?v=2'
$record.health=$health.ok;$record.new_assets_served=$html.Content.Contains('templateTextRun') -and $script.Content.Contains('template-text-start')
$record|ConvertTo-Json|Set-Content output/template-text-evidence/activation.json -Encoding utf8
Write-Output 'Storylens reloaded. Template Text controls are served; Adobe remains untouched.'
