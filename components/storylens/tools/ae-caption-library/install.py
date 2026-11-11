from pathlib import Path
import shutil,json,hashlib,sys
from datetime import datetime
root=Path(__file__).resolve().parents[2]
p=Path('C:/Users/Vineet Kumar/AppData/Roaming/Adobe/CEP/extensions/Storylens-after-effects-cep/js/main.js')
assert p.resolve()==Path('C:/Users/Vineet Kumar/AppData/Roaming/Adobe/CEP/extensions/Storylens-after-effects-cep/js/main.js').resolve()
s=p.read_text(encoding='utf-8-sig');backup=root/'output/ae-3d-caption-library/installed-main-before-3d.js';
if not backup.exists():shutil.copyfile(p,backup)
if "calls.caption3d=" not in s:
 needle="if(host==='aftereffects')calls.presetLibrary="
 assert needle in s
 s=s.replace(needle,"if(host==='aftereffects')calls.caption3d='storylens3DInsert';\n "+needle,1)
if "message.action==='caption3d'" not in s:
 needle="if(host==='aftereffects'&&message.action==='presetLibrary'){"
 assert needle in s
 route="""if(host==='aftereffects'&&message.action==='caption3d'){
    const path=require('path'),root=window.HINGLISH_APP_ROOT;if(!root)throw Error('Reopen the installed Storylens panel.');
    const helper=require(path.join(root,'editor_plugins','caption-3d','bridge.cjs'));
    const result=await evalHost(helper.nativeRequest(root,payload));frame.contentWindow.postMessage({type:'storylens-host-response',nonce,id:message.id,result},origin);return;
   }
   """
 s=s.replace(needle,route+needle,1)
s=s.replace("const helper=require(path.join(root,'editor_plugins','caption-3d','bridge.cjs'));","const modulePath=path.join(root,'editor_plugins','caption-3d','bridge.cjs');delete require.cache[require.resolve(modulePath)];delete require.cache[require.resolve(path.join(root,'editor_plugins','caption-3d','model.cjs'))];const helper=require(modulePath);",1)
writes=[(p,s)]
shared=(root/'editor_plugins/shared/aftereffects-panel.jsx').read_text(encoding='utf-8-sig')
def words_function(text):
 a=text.index('function storylensAEWords(');b=text.index('\nfunction ',a+1);return text[a:b]
words=words_function(shared)
for target in [root/'editor_plugins/after-effects-cep/jsx/panel.jsx',p.parent.parent/'jsx/panel.jsx']:
 text=target.read_text(encoding='utf-8-sig');old=words_function(text);writes.append((target,text.replace(old,words,1)))
stamp=datetime.now().strftime('%Y%m%d-%H%M%S-%f');out=root/'output/ae-3d-caption-library/surface-repair';out.mkdir(parents=True,exist_ok=True);records=[]
for target,text in writes:
 previous=target.read_text(encoding='utf-8-sig');changed=previous!=text
 if changed and '--check' not in sys.argv:
  backup=out/(stamp+'-'+target.parent.name+'-'+target.name+'.backup');shutil.copyfile(target,backup)
  target.write_text(text,encoding='utf-8')
 records.append(dict(path=str(target),changed=changed,sha256=hashlib.sha256(text.encode('utf-8')).hexdigest()))
report=dict(dry_run='--check' in sys.argv,files=records,applications_opened=False,project_edited=False)
if '--check' not in sys.argv:(out/'installation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
