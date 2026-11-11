"""Keep the AE panel's tool controls aligned with the Premiere CEP panel."""
from pathlib import Path
import shutil
import re


def prepare(root):
    root=Path(root);source=root/'editor_plugins/premiere-cep';dest=root/'editor_plugins/after-effects-cep'
    (dest/'js').mkdir(parents=True,exist_ok=True)
    for file in ('panel.css','js/config.js'):
        shutil.copy2(source/file,dest/file)
    html=(source/'index.html').read_text(encoding='utf-8').replace('the open sequence','the open composition work area').replace('open sequence','composition work area').replace('timeline or Project panel','composition layers or Project panel')
    # Beat Studio currently targets Premiere and Resolve, not After Effects.
    html=re.sub(r'<!-- STORYLENS_BEATS_BEGIN -->.*?<!-- STORYLENS_BEATS_END -->','',html,flags=re.S)
    html=html.replace('<script src="js/beats.js"></script>','')
    html=html.replace('<main>','<main><p class="hint">After Effects: edits import into a new composition. Timeline effects are rendered footage; original layers remain untouched.</p>')
    (dest/'index.html').write_text(html,encoding='utf-8')
    js=(source/'js/main.js').read_text(encoding='utf-8')
    js=js.replace("host:'premiere'","host:'aftereffects'").replace("preview:false","preview:true")
    js=js.replace("timeline_xml:timeline","input_path:timeline")
    js=js.replace("const files=(j.result.xml_files||[]).length?j.result.xml_files:(j.result.previews||[]).length?j.result.previews:j.result.media||[];if(!files.length)throw Error('No importable output. Review and render the edit first.');const result=await evalHost('hinglishImportXML('+JSON.stringify(files)+')');", "const manifest=await api('/api/jobs/'+jobId+'/aftereffects');const result=await evalHost('hinglishImportResult('+JSON.stringify(manifest)+')');")
    (dest/'js/main.js').write_text(js,encoding='utf-8')


if __name__=='__main__':prepare(Path(__file__).resolve().parents[1])
