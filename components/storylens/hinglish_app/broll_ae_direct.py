"""Windows Adobe-supported -r transport for explicit browser B-roll choices.

Uses an already-running trusted Adobe host, fixed repository scripts, checked
private media and receipt-bound operations. Never opens/saves/closes a project.
No browser-supplied script or arbitrary source path is executed.
"""
from pathlib import Path
import json,os,subprocess,threading,time,uuid
from .timed_choice_delivery import TimedChoiceDelivery,file_digest

_LOCK=threading.RLock()


def execute_script(script,out,nonce):
    import psutil
    adobe=(Path(os.environ.get('ProgramFiles',r'C:\Program Files'))/'Adobe').resolve()
    hosts=[]
    for process in psutil.process_iter(['name','exe']):
        if str(process.info.get('name') or '').lower()!='afterfx.exe':continue
        exe=Path(process.info.get('exe') or '').resolve()
        if exe.is_relative_to(adobe) and exe.parent.name.lower()=='support files':hosts.append(exe)
    if len(hosts)!=1:
        raise ValueError('Open one After Effects instance and the intended composition before connecting B-roll.')
    # Adobe documents the unquoted-script-path form for Windows hosts that
    # otherwise return immediately without running -r. shell=False throughout.
    subprocess.run('"'+str(hosts[0])+'" -r '+str(script),shell=False,
        creationflags=subprocess.CREATE_NO_WINDOW,timeout=20,check=True)
    end=time.monotonic()+25
    while time.monotonic()<end:
        if out.is_file():
            try:return json.loads(out.read_text('utf-8-sig'))
            except (OSError,ValueError):pass
        time.sleep(.15)
    raise TimeoutError('After Effects has not confirmed this choice. Retry the same choice to reconcile it; it may still be processing.')


class AfterEffectsDirect:
    def __init__(self,root,contexts,*,execute=execute_script):
        self.root=Path(root).resolve();self.contexts=contexts;self.execute=execute
        self.folder=self.root/'cache/editor-panel/ae-direct'

    def _call(self,body):
        self.folder.mkdir(parents=True,exist_ok=True);nonce=uuid.uuid4().hex
        script=self.folder/(nonce+'.jsx');out=self.folder/(nonce+'.json')
        q=lambda value:json.dumps(str(value),ensure_ascii=True)
        host=self.root/'editor_plugins/after-effects-cep/jsx/host.jsx'
        panel=self.root/'editor_plugins/shared/aftereffects-panel.jsx'
        source='''(function(){
if(typeof hJSON!=="function")$.evalFile(new File('''+q(host)+'''));
if(typeof storylensProjectId!=="function"||typeof storylensFootage!=="function")$.evalFile(new File('''+q(panel)+'''));
var answer;
try{answer=(function(){'''+body+'''})();}catch(e){answer={error:String(e)};}
var target=new File('''+q(out)+'''),temp=new File('''+q(str(out)+'.tmp')+''');
temp.encoding="UTF-8";
if(temp.open("w")){temp.write(hJSON({invocation_id:'''+q(nonce)+''',result:answer}));temp.close();temp.rename(target.name);}
})();'''
        script.write_text(source,encoding='utf-8')
        response=self.execute(script,out,nonce)
        if not isinstance(response,dict) or response.get('invocation_id')!=nonce or not isinstance(response.get('result'),dict):
            raise ValueError('The editor returned a stale or unreadable receipt. Retry the same choice.')
        result=response['result']
        if result.get('error'):raise ValueError('After Effects could not confirm this choice. '+str(result['error'])[:1600])
        return result

    def capture(self):
        with _LOCK:
            result=self._call('''
if(!app.project)throw Error("Open an After Effects project first.");
var comp=app.project.activeItem;
if(!(comp instanceof CompItem))throw Error("Open the intended composition first.");
return {host:"aftereffects",project_id:storylensProjectId(),sequence_id:String(comp.id),
 name:comp.name,width:comp.width,height:comp.height,fps:comp.frameRate,duration:comp.duration};''')
            if result.get('host')!='aftereffects' or result.get('sequence_id')=='_project_':
                raise ValueError('Connect the actual After Effects composition before inserting B-roll.')
            return self.contexts.save({**result,'content_format':'short','transport':'aftereffects_script'})

    def invoke_choice(self,manifest):
        # Accept only a controller-owned saved operation, never a caller's code.
        stored=TimedChoiceDelivery(self.root)._operation(manifest.get('operation_id'))['manifest']
        requested={k:v for k,v in manifest.items() if k!='already_confirmed'}
        if stored!=requested or manifest.get('expected',{}).get('host')!='aftereffects':
            raise ValueError('Choose the saved After Effects timeline operation.')
        file=Path(manifest['path']).resolve()
        base=(self.root/'output/editor-handoffs/timed-choices/media'/manifest['binding_id']).resolve()
        if not file.is_relative_to(base) or not file.is_file() or file_digest(file)!=manifest['asset_sha256']:
            raise ValueError('This checked private media changed. Check it again before inserting it.')
        native=self.root/'editor_plugins/shared/timed-choice.jsx'
        return self._call('$.evalFile(new File('+json.dumps(str(native))+'));var receipt=SLTimedChoice.ae('
            +json.dumps(manifest,ensure_ascii=True)+');if(receipt.ok)app.activate();return receipt;')

    def deliver(self,folder,value,context_id):
        from .panel_broll_choices import select_timed
        with _LOCK:
            context=self.contexts.load(context_id)
            if context.get('host')!='aftereffects' or context.get('transport')!='aftereffects_script':
                raise ValueError('Reconnect this After Effects composition before inserting B-roll.')
            response=select_timed(self.root,folder,value,context);manifest=response['manifest']
            receipt=self.invoke_choice(manifest)
            accepted=TimedChoiceDelivery(self.root).accept(manifest['operation_id'],receipt,context=context)
            return {'id':manifest['operation_id'],'status':'confirmed','receipt':accepted,
                    'message':accepted.get('message','After Effects confirmed this choice.')}
