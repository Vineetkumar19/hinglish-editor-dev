"""Apply only the viewport wrapper/lifecycle patch; preserve the current shell."""
from pathlib import Path
import hashlib
import json
import os

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/copy-paste-evidence/scroll-speed'
OUT.mkdir(parents=True, exist_ok=True)
files = [ROOT/'editor_plugins/shared/cep-shell.js', ROOT/'editor_plugins/after-effects-cep/js/main.js',
         Path(os.environ['APPDATA'])/'Adobe/CEP/extensions/Storylens-after-effects-cep/js/main.js']
old_start = '   let projectView=null,viewHelper=null;'
old_end = '   finally{if(projectView?.ok)try{await viewHelper.restore(window.HINGLISH_APP_ROOT,projectView);}catch(_){}}'
new = '''   const pasteStarted=Date.now();let projectView=null,viewHelper=null;
   if(host==='aftereffects'&&message.action==='copyPaste'&&['paste','pasteFiles','undo'].includes(payload.action))try{
    const path=require('path');viewHelper=require(path.join(window.HINGLISH_APP_ROOT,'editor_plugins','shared','project-view.cjs'));
    const viewContext=await evalHost('(function(){return hJSON({project_id:app.project&&app.project.file?app.project.file.fsName:null});})()');
    projectView=await viewHelper.capture(window.HINGLISH_APP_ROOT,viewContext.project_id);
   }catch(_){}
   let result;const nativeStarted=Date.now();let nativeElapsed=0,viewRestored=null;
   try{result=await evalHost(nativeCode);}
   finally{
    nativeElapsed=Date.now()-nativeStarted;
    if(projectView?.ok)try{viewRestored=await viewHelper.restore(window.HINGLISH_APP_ROOT,projectView);}catch(_){}
    if(viewHelper?.recordTiming)try{viewHelper.recordTiming(window.HINGLISH_APP_ROOT,{action:payload.action,native_ms:nativeElapsed,capture_ms:projectView?.elapsed_ms,restore_ms:viewRestored?.elapsed_ms,total_ms:Date.now()-pasteStarted,scroll_ok:viewRestored?.ok===true});}catch(_){}
   }'''
receipts=[]
for index,file in enumerate(files):
    before=file.read_text(encoding='utf-8-sig')
    if 'const pasteStarted=Date.now()' in before:
        continue
    if old_start in before:
        start=before.index(old_start);end=before.index(old_end,start)+len(old_end)
        removed=before[start:end]
    else:
        removed='   let result=await evalHost(nativeCode);'
        if before.count(removed)!=1:raise RuntimeError(f'Ambiguous native dispatch: {file}')
    if before.count(removed)!=1:raise RuntimeError(f'Ambiguous viewport dispatch: {file}')
    after=before.replace(removed,new)
    lifecycle="shortcutWatcher?.stop();if(host==='aftereffects')copyPasteKeys(false);"
    updated="shortcutWatcher?.stop();try{if(host==='aftereffects')require(require('path').join(window.HINGLISH_APP_ROOT,'editor_plugins','shared','project-view.cjs')).stop();}catch(_){}if(host==='aftereffects')copyPasteKeys(false);"
    if after.count(lifecycle)!=1:raise RuntimeError(f'Ambiguous panel lifecycle: {file}')
    after=after.replace(lifecycle,updated)
    if after.replace(new,removed).replace(updated,lifecycle)!=before:raise RuntimeError('Inverse patch verification failed')
    (OUT/f'shell-before-{index}.js').write_text(before,encoding='utf-8')
    file.write_text(after,encoding='utf-8')
    receipts.append({'file':str(file),'before_sha256':hashlib.sha256(before.encode()).hexdigest(),'after_sha256':hashlib.sha256(after.encode()).hexdigest(),'inverse_verified':True})
(OUT/'shell-patch.json').write_text(json.dumps(receipts,indent=2),encoding='utf-8')
print('Updated only Copy Paste viewport timing and helper cleanup.')
