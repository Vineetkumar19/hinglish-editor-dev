"""Prepare a separate, small native validation project; never execute it here."""
from pathlib import Path
import json
import shutil
from tests.test_cinematic import make_music,make_shot

def prepare(root):
    root=Path(root).resolve();folder=root/'output/plugin-validation';folder.mkdir(parents=True,exist_ok=True)
    clip=folder/'native-panel-check-10sec.mp4'
    if not clip.is_file():raise ValueError('Run the isolated real-engine fixture preparation first.')
    music=folder/'native-beats-10sec.wav';shot=folder/'native-second-shot.mp4'
    if not music.exists():make_music(music,seconds=10)
    if not shot.exists():make_shot(shot,seconds=6,seed=2)
    def literal(path):return json.dumps(str(path).replace('\\','/'))
    script='''/* Test data only. Run through AE File > Scripts after the owner saves. */
(function(){
 if(app.project&&app.project.dirty===true){alert('Save your current project first. No test project was created.');return;}
 var source=new File(CLIP),music=new File(MUSIC),shot=new File(SHOT);
 if(!source.exists||!music.exists||!shot.exists){alert('The validation media is missing.');return;}
 var project=app.newProject();if(!project)return;
 var folder=project.items.addFolder('Storylens validation sources');
 function add(file){var item=project.importFile(new ImportOptions(file));item.parentFolder=folder;return item;}
 var footage=add(source),song=add(music),second=add(shot);
 var comp=project.items.addComp('Storylens panel check - 10 seconds',640,360,1,10,30);
 var layer=comp.layers.add(footage);layer.inPoint=0;layer.outPoint=10;
 comp.openInViewer();project.save(new File(PROJECT));
})();
'''
    for name,path in [('CLIP',clip),('MUSIC',music),('SHOT',shot),('PROJECT',folder/'native-panel-check.aep')]:script=script.replace(name,literal(path))
    file=folder/'Prepare AE plugin check.jsx';file.write_text(script,encoding='utf-8')
    # Reuse the existing native sequence writer with no caption/overlay slots.
    # The tiny project is opened explicitly later; preparing it does not run PP.
    premiere=folder/'premiere-fixture';premiere.mkdir(exist_ok=True)
    context=json.loads((folder/'native-fixture-context.json').read_text(encoding='utf-8'))
    from hinglish_app.editor_panel import snapshot_xml
    timeline=premiere/'source-timeline.xml';shutil.copy2(snapshot_xml(root,context),timeline)
    project_file=premiere/'broll-project.json'
    project_file.write_text(json.dumps({'timeline':{'xml_path':str(timeline)},'slots':[]}),encoding='utf-8')
    from hinglish_broll.premiere import export
    destination=premiere/'Storylens Plugin Check.prproj'
    if not destination.exists():export(project_file,destination,include_options=False)
    return file

if __name__=='__main__':print(prepare(Path(__file__).resolve().parents[1]))
