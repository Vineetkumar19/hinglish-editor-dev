"""Create one isolated AE composition for the original failing narration.

Uses the already-running Adobe host; never saves/closes the owner's project.
"""
import argparse,json,re,sys,uuid
from pathlib import Path
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root))
from hinglish_app.broll_ae_direct import AfterEffectsDirect
base=root/'output/caption-one-general-speech-20261029'
parser=argparse.ArgumentParser();parser.add_argument('--job',default='24034e757ca82b6a313606ff77a00cdb');parser.add_argument('--name',default='Caption 1 - New recording speech');parser.add_argument('--output',default='native-setup.json');args=parser.parse_args()
if not re.fullmatch('[a-f0-9]{32}',args.job) or Path(args.output).name!=args.output:raise ValueError('Use a saved speech request and a report filename.')
request=json.loads((root/'output/captions/ae-speech'/args.job/'request.json').read_text('utf8'))
voice=request['timing_context']['clips'][0]['path'];nonce=uuid.uuid4().hex
body='''
if(!app.project.file||app.project.file.fsName!==new File(%s).fsName)throw Error('Keep the caption project open for the isolated check.');
var footage=null;
for(var i=1;i<=app.project.numItems;i++){var item=app.project.item(i);if(item instanceof FootageItem&&item.file&&item.file.fsName===new File(%s).fsName){footage=item;break;}}
if(!footage)throw Error('The original narration source is not in this project.');
var comp=null,opened=false;
try{app.beginUndoGroup('Caption 1 isolated new-recording validation');opened=true;
comp=app.project.items.addComp(%s,1080,1920,1,%s,30);comp.comment='Isolated Storylens speech validation %s';comp.resolutionFactor=[4,4];var layer=comp.layers.add(footage);layer.startTime=0;layer.inPoint=0;layer.outPoint=Math.min(footage.duration,comp.duration);comp.time=0;comp.openInViewer();
}finally{if(opened)app.endUndoGroup();}
return {ok:true,comp_id:String(comp.id),project_id:app.project.file.fsName,name:comp.name,duration:comp.duration,source:footage.file.fsName,nonce:%s,project_saved:false};
'''%(json.dumps(request['context']['project_id']),json.dumps(voice),json.dumps(args.name),request['timing_context']['duration'],nonce,json.dumps(nonce))
try:result=AfterEffectsDirect(root,None)._call(body)
except Exception as error:result={'ok':False,'error':str(error),'nonce':nonce}
(base/args.output).write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps(result))
