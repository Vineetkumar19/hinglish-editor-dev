"""Add only Template Text named dispatch to the current installed Storylens shell."""
from pathlib import Path
import datetime,hashlib,json
root=Path(__file__).resolve().parents[1];out=root/'output/template-text-evidence';out.mkdir(parents=True,exist_ok=True)
installed=Path.home()/'AppData/Roaming/Adobe/CEP/extensions/Storylens-after-effects-cep';target=installed/'js/main.js'
if not target.is_file():raise RuntimeError('Existing Storylens AE panel is required.')
original=target.read_text('utf8');before=hashlib.sha256(target.read_bytes()).hexdigest();code=original;edits=[]
if "calls.templateText='storylensPanelTemplateText'" not in code:
    replacements=[
      ("calls.templateAlign='storylensPanelTemplateAlign';","calls.templateText='storylensPanelTemplateText';calls.templateAlign='storylensPanelTemplateAlign';"),
      ("['templateAlign','copyPaste','templateImport','imageDownload'].includes(message.action)","['templateText','templateAlign','copyPaste','templateImport','imageDownload'].includes(message.action)"),
      ("const runtimeError=message.action==='imageDownload'?","const runtimeError=message.action==='templateText'?{error:'Template Text could not load. Reopen Storylens and retry; your project is unchanged.',code:'template_text_native'}:message.action==='imageDownload'?"),
      ("const files=message.action==='imageDownload'?","const files=message.action==='templateText'?['editor_plugins/template-text/model.js','editor_plugins/template-text/host.jsx']:message.action==='imageDownload'?"),
      ("||message.action==='templateImport'&&!result.running","||message.action==='templateText'&&payload.action==='apply'||message.action==='templateImport'&&!result.running")]
    for old,new in replacements:
        if code.count(old)!=1:raise RuntimeError('Installed bridge differs; coordinate before patching: '+old)
        code=code.replace(old,new,1);edits.append((old,new))
    reverse=code
    for old,new in reversed(edits):reverse=reverse.replace(new,old,1)
    if reverse!=original:raise RuntimeError('Refusing a patch that changes existing Copy Paste or other dispatch code.')
old="const path=require('path'),cleanup=require(path.join(window.HINGLISH_APP_ROOT,'editor_plugins','shared','project-folder-cleanup.cjs'));"
new="const path=require('path'),cleanupFile=path.join(window.HINGLISH_APP_ROOT,'editor_plugins','shared','project-folder-cleanup.cjs');\n     if(message.action==='templateText')delete require.cache[require.resolve(cleanupFile)];\n     const cleanup=require(cleanupFile);"
if 'cleanupFile' not in code:
    if code.count(old)!=1:raise RuntimeError('Folder helper bridge differs; coordinate before installing.')
    code=code.replace(old,new,1);edits.append((old,new))
reverse=code
for old,new in reversed(edits):reverse=reverse.replace(new,old,1)
if reverse!=original:raise RuntimeError('Refusing changes to existing bridge behavior outside named Template Text additions.')
if 'editor_plugins/template-text/host.jsx' not in code:raise RuntimeError('Template Text hot-load was not prepared.')
protected={str(p.relative_to(installed)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [installed/'js/config.js',installed/'jsx/host.jsx'] if p.is_file()}
backup=out/'installed-before'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S')/'main.js';backup.parent.mkdir(parents=True,exist_ok=True);backup.write_bytes(target.read_bytes())
if hashlib.sha256(target.read_bytes()).hexdigest()!=before:raise RuntimeError('Another chat changed the bridge during preparation. No write performed.')
target.write_text(code,encoding='utf8')
for name,digest in protected.items():
    if hashlib.sha256((installed/name).read_bytes()).hexdigest()!=digest:raise RuntimeError('Configuration or startup host changed concurrently.')
receipt={'installed':str(installed),'files':['js/main.js'],'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'installation':'reversible Template Text dispatch insertions and scoped fresh folder helper only','config_and_startup_host_preserved':True,'existing_bridge_code_preserved_by_reverse_patch':True,'native_verified':False,'zip_rebuilt':False}
(out/'install.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
print('Installed only Template Text action dispatch. Existing bridge, configuration and native files preserved.')
