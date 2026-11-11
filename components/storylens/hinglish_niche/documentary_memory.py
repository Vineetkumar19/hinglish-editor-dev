"""Persistent documentary guidance shared by all local language-model backends.

The database/embedding encoder are project assets, not an Ollama model's weights.
Use bounded context per call; preserve full documents for retrieval and export.
"""
import hashlib,json,re,sqlite3,zipfile
from pathlib import Path

RELATIVE=Path('library/creator-profiles/documentary-memory')
STYLES=('beneath-documentary-edit','crick-edit-editing-style')

def read(path):return json.loads(Path(path).read_text(encoding='utf8'))

def atomic(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8');temp.replace(path)

def install(root,brain_paths):
    root=Path(root);folder=root/RELATIVE;brains=folder/'brains';brains.mkdir(parents=True,exist_ok=True)
    receipts=[]
    for name,path in brain_paths.items():
        raw=Path(path).read_bytes();target=brains/(name+'.md');target.write_bytes(raw)
        receipts.append({'name':name,'file':str(target.relative_to(root)).replace('\\','/'),
            'sha256':hashlib.sha256(raw).hexdigest(),'source':str(path)})
    from hinglish_motion.reference_policy import REFERENCE_RULES
    requirements=REFERENCE_RULES+[
        'Personal cricket documentary mode only; preserve General and Gaming behaviour and existing approved style identities.',
        'Continue meaningful camera or photographic-layer motion throughout every graphic shot, including after entry animations settle. Moving grain or flickering texture alone does not count.',
        'A readable evidence hold can still have restrained camera travel, internal image drift and depth separation. Avoid a photograph frozen until the sentence ends.',
        'Use continuous push-in/pull-out, lateral camera travel, depth-separated foreground/background movement, focus shifts and perspective when motivated by the narration and measured reference. Do not add arbitrary shakes every second.',
        'Keep each motion family structurally distinct; changing a colour or entrance direction does not create a new style. Never repeat the same large-left/two-small-right collage across styles.',
        'Timeline camera advances along the story: old images leave the frame and new milestones arrive ahead; do not stack the newest card over the earlier pair.',
        'Use grounding shadows, lighting, restrained glow, blur during fast movement, depth-of-field and texture without covering faces or making evidence unreadable.',
        'Player images, labels, statistics and motivated sound events follow measured narration onsets. Background duplicates must not reveal a future player early.',
        'For real match footage, preserve the actual action and broadcast context; its subject movement may supply motion. Do not force an unrelated camera effect over every frame.',
        'Inspect the complete shot after the entrance, not just a mid-shot still. A long low-motion tail is a quality failure in image-led documentary scenes unless deliberately justified.',
        'Distinguish measured image-space motion from an inferred 3D camera. A flattened export does not reveal original Z positions, true lens parameters or After Effects keyframes.',
        'Audio measurements concern the mixed track. Voice/music/impact/riser/whoosh/ambience and beat labels are candidates until checked; do not claim isolated stems or verified musical beats.',
        'Use source-linked frame curves and per-second records to choose timing and motion intensity. Retrieve relevant examples rather than filling the model context with three hours of records.',
        'Keep all titles, descriptions, captions and other publishing copy in proper English. Preserve factual uncertainty and verify player, team kit, year and match separately.',
        'The editor and animator brains are technique guidance. User documentary format, preferred backgrounds and readability take precedence over vertical-only, compulsory beat, flat-grey or plugin-specific defaults.',
        'Save future feedback as project data. Changing the language model must not overwrite style records, reference evidence, encoder metadata or user preferences.'
    ]
    existing=read(folder/'preferences.json') if (folder/'preferences.json').exists() else {}
    requirements=list(dict.fromkeys(existing.get('requirements',[])+requirements))
    preference={**existing,'version':1,'scope':'personal cricket documentary','requirements':requirements,
        'priority':'Explicit user preferences before generic skill defaults; source facts retain uncertainty.',
        'not_fine_tuning':True}
    atomic(folder/'preferences.json',preference)
    digest=hashlib.sha256(json.dumps({'brains':receipts,'preferences':preference},sort_keys=True).encode()).hexdigest()
    atomic(folder/'manifest.json',{'version':1,'revision':digest,'styles':list(STYLES),'brains':receipts,
        'preferences':'library/creator-profiles/documentary-memory/preferences.json',
        'database':'library/creator-profiles/editing-dna.sqlite3','embedding_model':'intfloat/multilingual-e5-small',
        'language_model_independent':True,'new_model_action':'Load the same project memory at every request; keep the E5 encoder unchanged unless explicitly reindexing.',
        'coverage_receipt':'output/reference-analysis/continuous-documentary-memory/coverage.json'})
    return read(folder/'manifest.json')

def sections(text):
    for part in re.split(r'(?m)(?=^## )',text):
        if part.startswith('## '):yield part.splitlines()[0][3:],part.strip()

def chunks(text,max_chars=700):
    """Bounded passages keep late sections inside the embedding token window."""
    if max_chars<50:raise ValueError('Guidance chunk is too small')
    words=text.split();parts=[];current=''
    for word in words:
        if current and len(current)+len(word)+1>max_chars:parts.append(current);current=''
        current=(current+' '+word).strip()
    if current:parts.append(current)
    return parts

def context(root,style,purpose=None):
    root=Path(root);folder=root/RELATIVE
    if style not in STYLES or not (folder/'manifest.json').exists():return {}
    manifest=read(folder/'manifest.json');prefs=read(folder/'preferences.json');guidance=[]
    chosen={'motion-graphics-editor-brain':('Universal principles','Key system insight'),
            'motion-graphics-animator-brain':('A. Core workflow','H. Ambient occlusion','M. Layering philosophy','N. Non-negotiables')}
    for item in manifest['brains']:
        text=(root/item['file']).read_text(encoding='utf8')
        excerpt=[part for title,part in sections(text) if any(title.startswith(t) for t in chosen.get(item['name'],()))]
        guidance.append({'name':item['name'],'excerpt':'\n'.join(excerpt)[:1600],'full_document':item['file'],'sha256':item['sha256']})
    return {'revision':manifest['revision'],'style':style,'user_requirements':prefs['requirements'],
        'brains':guidance,'storage':'External project JSON + SQLite/E5 retrieval; independent of language model weights.',
        'reference_status':'Analysis-only technique evidence; never a production asset library. Native-frame and audio measurements retain semantic and physical-camera limits.'}

def export(root,destination):
    """Consistent SQLite backup plus canonical evidence; no original GB videos."""
    root=Path(root);destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    temporary=destination.with_suffix('.sqlite3')
    source=sqlite3.connect(root/'library/creator-profiles/editing-dna.sqlite3');target=sqlite3.connect(temporary)
    try:source.backup(target)
    finally:target.close();source.close()
    files=list((root/RELATIVE).rglob('*'))
    files += [root/'library/creator-profiles'/f'{s}.json' for s in STYLES]
    base=root/'output/reference-analysis/continuous-documentary-memory'
    files += [p for p in base.rglob('*') if (p.name in ('editing-seconds.jsonl','motion-coverage.json','motion-seconds.json','continuous-motion.csv','semantic-seconds.json','coverage.json','semantic-progress.json','report.html','memory-quality-receipt.json','verification.json') or (p.suffix=='.jpg' and p.parent.name=='frames')) and 'benchmark' not in p.parts]
    guide=root/'docs/DOCUMENTARY_MEMORY_AND_MODEL_CHANGES.md'
    if guide.is_file():files.append(guide)
    for name in ('cricket-documentaries','crick-edit-editing-style'):
        ref=root/'output/reference-analysis'/name
        files += [p for p in ref.rglob('*') if p.name in ('inventory.json','dna-coverage.json','scan.json','scenes.json','frame-metrics.csv','visual-features.csv','scene-interpretations.json','audio-features.npy','audio-interpretations.json','audio-analysis.json','sound-event-candidates.json','transcript.json','words.json','review-notes.json') or (p.suffix=='.jpg' and p.parent.name=='scene-keyframes')]
    with zipfile.ZipFile(destination,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        z.write(temporary,'library/creator-profiles/editing-dna.sqlite3')
        for p in sorted(set(files)):
            if p.is_file():z.write(p,str(p.relative_to(root)))
    temporary.unlink()
    atomic(destination.with_suffix('.manifest.json'),{'file':str(destination),'bytes':destination.stat().st_size,
        'sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),'contains_original_videos':False,
        'contains_model_weights':False,'restore':'Extract into project root. Restore/install the same offline multilingual E5 encoder for vector search; keyword retrieval works without that encoder.'})
    return destination
