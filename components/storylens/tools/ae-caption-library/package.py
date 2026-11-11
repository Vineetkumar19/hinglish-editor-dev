from pathlib import Path
import json,shutil
root=Path(__file__).resolve().parents[2]
base=root/'editor_plugins/caption-3d';static=root/'hinglish_app/static'
audio=(base/'sound-data.jsx').read_text(encoding='utf-8')+'\n'+(base/'sound.jsx').read_text(encoding='utf-8')+'\n'+(base/'solid.jsx').read_text(encoding='utf-8')+'\n'
src=(base/'camera-engine.jsx').read_text(encoding='utf-8')
audio=(base/'folders.jsx').read_text(encoding='utf-8')+'\n$.global.StorylensSurfaceCatalog='+json.dumps(json.loads((base/'catalog.json').read_text(encoding='utf-8-sig')))+';\n'+audio
for filename in ['engine.jsx','camera-engine.jsx','catalog.json']:
 
 if filename.endswith('.jsx'):(static/('caption-3d-'+filename)).write_text(audio+(base/filename).read_text(encoding='utf-8'),encoding='utf-8')
 else:shutil.copyfile(base/filename,static/('caption-3d-'+filename))
catalog=json.loads((base/'catalog.json').read_text(encoding='utf-8-sig'))
colours=catalog['colours']
# Prepare fixed trusted sample plans with the same rules as the bridge.
def plan(f,v):
 words=v['text'].split(); cursor=0; rows=[]
 for r in v.get('rows',[]):
  rr=dict(r);rr['text']=' '.join(words[cursor:cursor+r['count']]);cursor+=r['count'];rows.append(rr)
 return dict(family=f['id'],variant=v['id'],format='vertical',layout=v['layout'],font='Anton-Regular',colour=v['colour'],colourValue=colours[v['colour']],words=v.get('words'),rows=rows,orientation=v.get('orientation'),duration=8,motion='none',delay=.35,perspective={},surface='both' if v['layout']=='corner' else 'ground' if v['layout']=='ground' else 'left' if v.get('orientation',[0,0])[1]>0 else 'right')
for f in catalog['families'][1:]:
 out=root/'output'/('ae-'+f['id']+'-surface');out.mkdir(parents=True,exist_ok=True)
 for i,v in enumerate(f['variants']):
  content=audio+(base/'engine.jsx').read_text(encoding='utf-8-sig')+'\ntry{$.global.StorylensSurfaceTitles.create('+json.dumps(plan(f,v))+');}catch(e){alert("Open a composition and try again.\\n"+String(e));}\n'
  label=v['label'].replace(chr(183),'-')
  (out/f"{i+1:02d} {label}.jsx").write_text(content,encoding='utf-8')
  if f['id']=='3d2' and i==0:
   (root/'tools/ae-surface-text/build.jsx').write_text(content,encoding='utf-8')
   (out/'Create 3D2 Surface Text.jsx').write_text(content,encoding='utf-8')
attach=(root/'tools/ae-surface-text/attach.jsx').read_text(encoding='utf-8-sig')
attach=attach.replace("String(l.comment||'')==='3D2 Surface Placement'", "/^3D[23] Surface Placement$/.test(String(l.comment||''))").replace("String(l.parent.comment||'')==='3D2 Surface Placement'", "/^3D[23] Surface Placement$/.test(String(l.parent.comment||''))")
for family in ['3d2','3d3']:(root/'output'/('ae-'+family+'-surface')/'Attach to Track Null.jsx').write_text(attach,encoding='utf-8')
print('Native library and eight standalone surface presets packaged.')

model=(base/"model.cjs").read_text(encoding="utf-8-sig").replace("const catalog=require('./catalog.json');", "").replace("module.exports={catalog,prepare,prepareUpdate};", "return {catalog,prepare,prepareUpdate};")
(static/"caption-3d-model.js").write_text("window.storylens3DModel=(function(catalog){"+model+"})("+json.dumps(catalog)+");",encoding="utf-8")

(root/'output/ae-3d1/Create 3D1 Titles.jsx').write_text(audio+src+'\n$.global.StorylensCameraTitles({sound_fx:true});\n',encoding='utf-8')
