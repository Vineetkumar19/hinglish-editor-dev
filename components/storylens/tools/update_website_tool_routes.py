"""Narrow guarded edits for the native browser surface; no applications started."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def edit(name,old,new):
    path=ROOT/name;text=path.read_text('utf-8')
    if old.startswith(' '):old='\n'+old;new='\n'+new
    if new in text:return
    if text.count(old)!=1:raise RuntimeError('Source changed: '+name+' / '+old[:90])
    path.write_text(text.replace(old,new),encoding='utf-8')

edit('hinglish_app/server.py',"            if parsed.path.startswith('/api/voiceover/'):","            if parsed.path.startswith('/api/native-tools/'):\n                from .native_browser_bridge import get\n                return get(self,state,parsed)\n            if parsed.path.startswith('/api/workbench/'):\n                from .workbench_http import get\n                return get(self,state,parsed)\n            if parsed.path.startswith('/api/voiceover/'):")
edit('hinglish_app/server.py',"                if parsed.path.startswith('/api/voiceover/'):", "                if parsed.path.startswith('/api/native-tools/'):\n                    from .native_browser_bridge import post\n                    return post(self,state,parsed.path,payload)\n                if parsed.path.startswith('/api/workbench/'):\n                    from .workbench_http import post\n                    return post(self,state,parsed.path,payload)\n                if parsed.path.startswith('/api/voiceover/'):")
edit('hinglish_app/static/editor-panel.html','<script src="editor-panel.js?', '<script src="browser-native-bridge.js?v=20261103"></script><script src="editor-panel.js?')
edit('hinglish_app/static/editor-panel.js',"function native(action,payload={}){return new Promise", "function native(action,payload={}){if(q.get('browser')==='1')return window.storylensBrowserNative.request(host,action,payload);return new Promise")
edit('hinglish_app/static/editor-panel.js',"const isEditingBusy=()=>", "let browserNativeListener=null;\nconst isEditingBusy=()=>!!browserNativeListener?.isRunning()||")
# Attach only inside a real installed panel, after its normal initialization.
path=ROOT/'hinglish_app/static/editor-panel.js';text=path.read_text('utf-8')
marker='/* Browser-native workbench initialization */'
if marker not in text:
    addition='''\n/* Browser-native workbench initialization */
if(q.get('browser')!=='1'&&window.parent!==window){
 setTimeout(()=>{browserNativeListener=window.storylensBrowserNative.listen({host,native,isBusy:isEditingBusy,onError:error});},1500);
 window.addEventListener('beforeunload',()=>browserNativeListener?.stop());
}else if(q.get('browser')==='1'){
 document.body.classList.add('browser-native-tool');
 const style=document.createElement('style');style.textContent='.browser-native-tool header,.browser-native-tool #tools{display:none!important}.browser-native-tool main{padding:6px 0}';document.head.append(style);
 const wanted=q.get('tool')||'templateImport';
 const ready=setInterval(()=>{if(!$('tools').children.length)return;clearInterval(ready);if(['presetLibrary','textEffects','effectsLibrary'].includes(wanted)){document.querySelector('header').style.setProperty('display','flex','important');if(wanted==='textEffects')$('effectsHome').click();else if(wanted==='effectsLibrary')$('effectsLibraryHome').click();else document.querySelector('#presetCategoryStrip button:not([hidden])')?.click();}else select(wanted);},200);
 window.addEventListener('beforeunload',()=>clearInterval(ready));
}
'''
    position=text.rfind('})();')
    if position<0:raise RuntimeError('Panel closure not found')
    text=text[:position]+addition+text[position:]
    path.write_text(text,encoding='utf-8')
