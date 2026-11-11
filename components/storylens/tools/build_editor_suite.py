"""Build the shared Storylens panels; installation is an explicit separate step."""
from pathlib import Path
import json
import shutil
import xml.etree.ElementTree as ET
import zipfile


def build(root):
    root=Path(root).resolve();plugins=root/'editor_plugins';shared=plugins/'shared';static=root/'hinglish_app/static'
    target=root/'output/editor-suite-20261025';target.mkdir(parents=True,exist_ok=True)
    (static/'panel-model.js').write_bytes((shared/'panel-model.js').read_bytes())
    (static/'copy-paste.js').write_bytes((plugins/'copy-paste/ui.js').read_bytes())
    for host,package in [('premiere','premiere-cep'),('aftereffects','after-effects-cep')]:
        source=plugins/package;backup=target/'previous-panels'/package
        if not backup.exists():shutil.copytree(source,backup)
        css='html,body{margin:0;width:100%;height:100%;overflow:hidden;background:#171a1f;color:#edf1f6;font:13px Segoe UI,sans-serif}iframe{width:100%;height:calc(100% - 32px);border:0}#reconnect{height:28px;background:#303944;color:white;border:1px solid #536171;border-radius:5px;margin:2px 8px}p{padding:16px;line-height:1.6}[hidden]{display:none!important}'
        if host=='aftereffects':css=css.replace('height:calc(100% - 32px);border:0','height:100%;border:0')+'#reconnect:not([hidden])~iframe{height:calc(100% - 32px)}'
        (source/'panel.css').write_text(css,encoding='utf-8')
        (source/'index.html').write_text('<!doctype html><html lang="en" data-host="'+host+'"><head><meta charset="utf-8"><title>Storylens</title><link rel="stylesheet" href="panel.css"></head><body><button id="reconnect">Reconnect</button><p id="shellStatus">Connecting to Storylens…</p><iframe id="storylensPanel" title="Storylens editor tools" hidden></iframe><script src="js/config.js"></script><script src="js/main.js"></script></body></html>',encoding='utf-8')
        (source/'js/main.js').write_bytes((shared/'cep-shell.js').read_bytes())
        (source/'js/config.js').write_text('window.HINGLISH_BRIDGE="http://127.0.0.1:8765";window.HINGLISH_APP_ROOT='+json.dumps(str(root))+';\n',encoding='utf-8')
        (source/'jsx/panel.jsx').write_bytes((shared/(host+'-panel.jsx')).read_bytes())
        (source/'jsx/photo-import.jsx').write_bytes((shared/'photo-import.jsx').read_bytes())
        if host=='aftereffects':
            (source/'jsx/template-model.js').write_bytes((plugins/'template-assembler/model.js').read_bytes())
            (source/'jsx/template-aliner-model.js').write_bytes((shared/'template-aliner-model.js').read_bytes())
            (source/'jsx/template-aliner.jsx').write_bytes((shared/'aftereffects-template-aliner.jsx').read_bytes())
            (source/'jsx/copy-paste-model.js').write_bytes((plugins/'copy-paste/model.js').read_bytes())
            (source/'jsx/copy-paste-framing.jsx').write_bytes((plugins/'copy-paste/framing.jsx').read_bytes())
            (source/'jsx/copy-paste-framing-model.js').write_bytes((plugins/'copy-paste/framing-model.js').read_bytes())
            (source/'jsx/copy-paste.jsx').write_bytes((plugins/'copy-paste/host.jsx').read_bytes())
            (source/'jsx/template-import-model.js').write_bytes((shared/'template-import-model.js').read_bytes())
            (source/'jsx/template-import.jsx').write_bytes((shared/'aftereffects-template-import.jsx').read_bytes())
        hostfile=source/'jsx/host.jsx';text=hostfile.read_text(encoding='utf-8')
        if '#include "panel.jsx"' not in text:hostfile.write_text(text+'\n#include "panel.jsx"\n',encoding='utf-8')
        text=hostfile.read_text(encoding='utf-8')
        if '#include "photo-import.jsx"' not in text:hostfile.write_text(text+'\n#include "photo-import.jsx"\n',encoding='utf-8')
        if host=='aftereffects':
            text=hostfile.read_text(encoding='utf-8')
            for include in ('template-model.js','template-aliner-model.js','template-aliner.jsx','copy-paste-model.js','copy-paste.jsx','template-import-model.js','template-import.jsx'):
                if '#include "'+include+'"' not in text:text+='\n#include "'+include+'"\n'
            hostfile.write_text(text,encoding='utf-8')
        manifest=source/'CSXS/manifest.xml';tree=ET.parse(manifest);node=tree.getroot()
        node.set('ExtensionBundleVersion','1.0.0');node.find('ExtensionList/Extension').set('Version','1.0.0')
        node.find('ExecutionEnvironment/HostList/Host').set('Version','[24.0,26.9]' if host=='aftereffects' else '[22.0,26.9]')
        node.find('.//Geometry/MinSize/Width').text='280';node.find('.//Geometry/MinSize/Height').text='350'
        ET.indent(tree);tree.write(manifest,encoding='utf-8',xml_declaration=True)
        dest=target/package
        if dest.exists():shutil.copytree(source,dest,dirs_exist_ok=True)
        else:shutil.copytree(source,dest)
        with zipfile.ZipFile(target/(package+'.zip'),'w',zipfile.ZIP_DEFLATED) as archive:
            for file in dest.rglob('*'):
                if file.is_file():archive.write(file,Path(package)/file.relative_to(dest))
    uxp=plugins/'premiere-uxp';backup=target/'previous-panels/premiere-uxp'
    if not backup.exists():shutil.copytree(uxp,backup)
    (uxp/'main.js').write_bytes((shared/'uxp-shell.js').read_bytes())
    (uxp/'index.html').write_text('<!doctype html><html><head><meta charset="utf-8"><title>Storylens</title><style>html,body{height:100%;margin:0;background:#171a1f}webview{width:100%;height:100%}</style></head><body><webview id="storylensPanel" width="100%" height="100%"></webview><script src="main.js"></script></body></html>',encoding='utf-8')
    manifest=json.loads((uxp/'manifest.json').read_text(encoding='utf-8'));manifest['version']='1.0.0'
    manifest['requiredPermissions']['webview']={'allow':'yes','domains':['http://127.0.0.1:8765'],'enableMessageBridge':'localAndRemote'}
    manifest['entrypoints'][0]['minimumSize']={'width':280,'height':350}
    (uxp/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    shutil.copytree(uxp,target/'premiere-uxp',dirs_exist_ok=True)
    with zipfile.ZipFile(target/'premiere-uxp-source.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for file in (target/'premiere-uxp').rglob('*'):
            if file.is_file():archive.write(file,Path('premiere-uxp')/file.relative_to(target/'premiere-uxp'))
    installer='''param([switch]$Install)
$ErrorActionPreference = 'Stop'
if (-not $Install) { Write-Host 'Run with -Install to copy the prepared panels into your Adobe user extension folder. No security preferences are changed.'; exit }
$destination = Join-Path $env:APPDATA 'Adobe\\CEP\\extensions'
New-Item -ItemType Directory -Path $destination -Force | Out-Null
foreach ($panel in @('premiere-cep','after-effects-cep')) {
 $source = Join-Path $PSScriptRoot $panel
 $target = Join-Path $destination ('Storylens-' + $panel)
 if (Test-Path -LiteralPath $target) {
  $backupRoot = Join-Path $env:APPDATA 'Storylens\\Panel Backups'
  New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
  $backup = Join-Path $backupRoot ($panel + '-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
  Copy-Item -LiteralPath $target -Destination $backup -Recurse
 }
 New-Item -ItemType Directory -Path $target -Force | Out-Null
 Copy-Item -Path (Join-Path $source '*') -Destination $target -Recurse -Force
}
Write-Host 'Panels copied. Restart the host after saving its project, then open Window > Extensions > Storylens. Unsigned development loading, if needed, requires a separate explicit choice.'
'''
    (target/'Install-Storylens-Panels.ps1').write_text(installer,encoding='utf-8-sig')
    (target/'Open-CapCut-Companion.cmd').write_text('@echo off\r\nstart "Storylens CapCut" msedge --app=http://127.0.0.1:8765/editor-panel.html?host=capcut\r\n',encoding='utf-8')
    (target/'README.txt').write_text('''Storylens editor panels - local development build

Premiere Pro and After Effects 2026: CEP panels are installed by
Install-Storylens-Panels.ps1 -Install. Open Window > Extensions > Storylens.
Save your project before restarting an Adobe application. The installer never
closes, saves or restarts the host. Existing panels are backed up outside the
Adobe extensions directory to avoid duplicate extension IDs.

The running Storylens engine is required at http://127.0.0.1:8765.
No browser window is required for the Adobe panels themselves.
Paste one shared script at the top. Use current timeline, then choose a tool.
Clean and Script Edit accept straight footage cuts with linked camera audio.
Unsupported effects, gaps, nested sequences or transforms stop clearly.

Premiere UXP is optional source for UXP Developer Tool, not a signed CCX.
Its active-timeline XML capture needs Premiere 26.2 or newer. The CEP build
provides the complete shared photo and beat host adapters.

CapCut has a companion window and saved-project handoff, not a native plugin.
Open-CapCut-Companion.cmd opens the companion. Keep the local engine running.

Installation and test results do not establish native workflow acceptance.
See docs/plugin-work-in-progress-2026-10-25.md and the validation report for
current checks, unfinished native validation and known limitations.
''',encoding='utf-8')
    return target


if __name__=='__main__':print(build(Path(__file__).resolve().parents[1]))
