"""Audit only an isolated live caption composition; never save the owner file."""
import argparse,json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root))
from hinglish_app.broll_ae_direct import AfterEffectsDirect
parser=argparse.ArgumentParser();parser.add_argument('--comp',required=True);parser.add_argument('--activate',action='store_true');parser.add_argument('--time',type=float,default=0);parser.add_argument('--frames',action='store_true');parser.add_argument('--output',default='native-audit.json');args=parser.parse_args()
if not args.comp.isdigit() or Path(args.output).name!=args.output:raise ValueError('Use an isolated composition ID and a report filename.')
base=root/'output/caption-one-general-speech-20261029'
body='''
var target=null;
for(var i=1;i<=app.project.numItems;i++){var c=app.project.item(i);if(c instanceof CompItem&&String(c.id)===%s)target=c;}
if(!target||String(target.comment).indexOf('Isolated Storylens speech validation ')!==0)throw Error('Choose the isolated speech validation composition.');
if(%s){target.time=Math.max(0,Math.min(target.duration-.01,%s));target.openInViewer();}
var pages=[],total=0;
function tr(l,n){return l.property('ADBE Transform Group').property(n);}
for(i=1;i<=target.numLayers;i++){var outer=target.layer(i),comp=outer.source;if(!(comp instanceof CompItem)||String(comp.comment).indexOf('Storylens caption pattern caption_1_ae_v1 ')!==0)continue;var words=[],left=1e20,right=-1e20;
for(var j=1;j<=comp.numLayers;j++){var l=comp.layer(j);if(!(l instanceof TextLayer)||String(l.comment).indexOf('Source word ')!==0)continue;var p=tr(l,'ADBE Position'),s=tr(l,'ADBE Scale').value,a=tr(l,'ADBE Anchor Point').value,r=l.sourceRectAtTime(comp.duration-.001,false),v=p.valueAtTime(comp.duration-.001,false),d=l.property('ADBE Text Properties').property('ADBE Text Document').value;left=Math.min(left,v[0]+(r.left-a[0])*s[0]/100);right=Math.max(right,v[0]+(r.left+r.width-a[0])*s[0]/100);var ease=p.numKeys?p.keyInTemporalEase(p.numKeys)[0]:null;words.push({text:d.text,slot:l.comment,font:d.font,size:d.fontSize,start:p.numKeys?p.keyTime(1)+outer.startTime:outer.startTime,end:outer.outPoint,keys:p.numKeys,ease_speed:ease?ease.speed:null,ease_influence:ease?ease.influence:null,rotation:tr(l,'ADBE Rotate Z').value});}
total+=words.length;pages.push({name:outer.name,comment:outer.comment,start:outer.inPoint,end:outer.outPoint,comp_id:String(comp.id),words:words,left:left/target.width,right:right/target.width});}
if(%s){var folder=new Folder(%s);folder.create();var times=[1.9,target.duration*.5,target.duration-1];for(var ti=0;ti<times.length;ti++)target.saveFrameToPng(times[ti],new File(folder.fsName+'/'+String(target.id)+'-'+ti+'.png'));}
return {ok:true,comp_id:String(target.id),name:target.name,active_comp:app.project.activeItem?String(app.project.activeItem.id):null,groups:pages.length,words:total,pages:pages,project_saved:false};
'''%(json.dumps(args.comp),'true' if args.activate else 'false',json.dumps(args.time),'true' if args.frames else 'false',json.dumps(str(base/'native-frames')))
result=AfterEffectsDirect(root,None)._call(body);(base/args.output).write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps({k:v for k,v in result.items() if k!='pages'}))
