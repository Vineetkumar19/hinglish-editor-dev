"""Prepare editable supported XML layers for AE, without launching Adobe."""
from pathlib import Path
import json


def prepare_scripts(result,destination,identity):
    from .editor_panel import layer_manifest
    xmls=result['xml_files']
    if not xmls:raise ValueError('This result has no supported editable XML. Import its saved media or use the native Auto Captions panel.')
    manifests=[layer_manifest(xml) for xml in xmls]
    root=Path(__file__).resolve().parents[1]
    files=[root/'editor_plugins/after-effects-cep/jsx/host.jsx',root/'editor_plugins/shared/aftereffects-panel.jsx']
    q=lambda value:json.dumps(str(value),ensure_ascii=True)
    script='''(function(){
if(!app.project)throw Error("Open an After Effects project first.");
'''+''.join('$.evalFile(new File('+q(file)+'));\n' for file in files)+'''
var manifests='''+json.dumps(manifests,ensure_ascii=True)+''';
for(var n=0;n<manifests.length;n++){
 var identity='''+q('StorylensHandoff:'+identity+':')+'''+n,existing=null;
 for(var i=1;i<=app.project.numItems;i++){var item=app.project.item(i);if(item instanceof CompItem&&item.comment===identity){existing=item;break;}}
 if(existing){existing.openInViewer();continue;}
 // hJSON from the trusted native dispatcher is a JSON object literal. Older
 // ExtendScript hosts do not expose JSON.parse.
 var result=eval('('+storylensPanelImport(manifests[n])+')');
 if(result.error)throw Error(result.error);
 if(!result.ok)throw Error("After Effects did not confirm this composition.");
 var comp=app.project.activeItem;if(comp instanceof CompItem)comp.comment=identity;
}
})();
'''
    file=Path(destination)/'STORYLENS_TIMELINES.jsx';file.write_text(script,encoding='utf-8')
    return [str(file)]
