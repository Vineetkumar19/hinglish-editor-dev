"""Generate a small, non-destructive AE host smoke-test script (does not launch AE)."""
import json
from pathlib import Path
from hinglish_app.aftereffects_adapter import cut_manifest
from hinglish_cut.model import Cut,Media
from hinglish_cut.xml_export import export_xml

ROOT=Path(__file__).resolve().parents[1]


def main():
    folder=ROOT/'output/saas/host-test';folder.mkdir(parents=True,exist_ok=True)
    video=ROOT/'output/saas/live-test/SAAS_SMART_CLEAN_TEST.mp4'
    if not video.is_file():raise SystemExit('Run the Smart Clean integration fixture first.')
    import av
    with av.open(str(video)) as source:
        stream=source.streams.video[0];width,height=stream.width,stream.height;rate=str(stream.average_rate)
        duration=float(stream.duration*stream.time_base)
    media=Media('test',str(video),duration,rate,width,height,0,48000)
    xml=folder/'ae-test.xml';export_xml(xml,[Cut('test',0,30,0),Cut('test',45,75,1)],{'test':media})
    manifest=cut_manifest(xml);manifest['name']='HINGLISH HOST CHECK — TEMPORARY'
    host=ROOT/'editor_plugins/after-effects-cep/jsx/host.jsx';receipt=folder/'aftereffects-receipt.json'
    script='''(function(){
var receipt={passed:false,version:app.version,tests:[]},folder=null;
try{
    $.evalFile(new File(HOST));
    var before=app.project.numItems;
    var result=hinglishImportResult(MANIFEST);
    if(result!=='ok')throw new Error(result);
    var comp=app.project.activeItem;
    if(!(comp instanceof CompItem))throw new Error('Imported composition not active.');
    folder=comp.parentFolder;
    receipt.duration=comp.duration;receipt.layers=comp.numLayers;receipt.fps=comp.frameRate;
    receipt.tests.push({name:'Two trimmed cuts imported into a new composition',passed:comp.numLayers===2});
    receipt.tests.push({name:'Destination duration is exactly two seconds',passed:Math.abs(comp.duration-2)<0.01});
    receipt.tests.push({name:'First cut timing',passed:Math.abs(comp.layer(1).inPoint-0)<0.01&&Math.abs(comp.layer(1).outPoint-1)<0.01});
    receipt.tests.push({name:'Second cut timing',passed:Math.abs(comp.layer(2).inPoint-1)<0.01&&Math.abs(comp.layer(2).outPoint-2)<0.01});
    receipt.passed=true;for(var i=0;i<receipt.tests.length;i++)if(!receipt.tests[i].passed)receipt.passed=false;
}catch(error){receipt.error=error.toString();}
finally{
    if(folder)try{folder.remove();}catch(_){}
    var file=new File(RECEIPT);file.encoding='UTF-8';file.open('w');file.write(hJSON(receipt));file.close();
}
})();'''
    script=script.replace('HOST',json.dumps(str(host))).replace('MANIFEST',json.dumps(manifest)).replace('RECEIPT',json.dumps(str(receipt)))
    path=folder/'verify-aftereffects.jsx';path.write_text(script,encoding='utf-8')
    print(str(path))


if __name__=='__main__':main()
