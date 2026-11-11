"""Snapshot the two user-selected brains and index their sections for any LLM."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from hinglish_niche.documentary_memory import install,sections,chunks,STYLES
from hinglish_niche.reference_dna import StyleDatabase
from hinglish_niche.style_memory import StyleEmbedder

def main():
    base=Path('C:/Users/vinee/.codex/plugins/cache/claude-cowork/anthropic-skills/1.0.0/skills')
    names=['motion-graphics-editor-brain','motion-graphics-animator-brain']
    manifest=install(ROOT,{n:base/n/'SKILL.md' for n in names});records=[]
    for brain in manifest['brains']:
        for title,text in sections((ROOT/brain['file']).read_text(encoding='utf8')):
            for number,part in enumerate(chunks(text)):
                records.append({'kind':'brain-guidance','text':brain['name']+' / '+title+'\n'+part,
                  'data':{'status':'User-selected technique guidance; documentary format and explicit preferences override generic defaults.',
                    'brain':brain['name'],'section':title,'part':number,'file':brain['file'],'sha256':brain['sha256']}})
    encoder=StyleEmbedder(ROOT);vectors=encoder.encode([r['text'] for r in records])
    for r,v in zip(records,vectors):r.update(vector=v,model=encoder.model_name)
    db=StyleDatabase(ROOT/'library/creator-profiles/editing-dna.sqlite3')
    try:
        for style in STYLES:db.replace_source(style,'user-selected-motion-brains',records)
    finally:db.close()
    print('Saved both complete brains and indexed',len(records),'sections for each documentary style.')

if __name__=='__main__':main()
