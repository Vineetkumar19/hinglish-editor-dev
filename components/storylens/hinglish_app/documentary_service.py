"""Source-bound cricket documentary intake and reviewed promise graph."""
from pathlib import Path
import json,math
from hinglish_cinematic.curation import Store,file_hash,digest
from hinglish_cinematic.story_graph import validate_graph

def database(state):return Store(state.root/'cache/curation/projects.sqlite3')

def inspect_inputs(value):
    paths=[Path(value[k]).resolve() for k in ('body_path','transcript_path','script_path')]
    hashes=[file_hash(p) for p in paths]
    transcript=json.loads(paths[1].read_text('utf-8'))
    if transcript.get('source_sha256')!=hashes[0]:raise ValueError('Transcript identity does not match the selected body.')
    return {'input_hashes':hashes,'words':transcript['words'],'script':paths[2].read_text('utf-8'),'provenance':transcript.get('provenance',{}),'source_hash':hashes[0]}

def import_body(state,value):
    import av
    if value.get('category')!='cricket':raise ValueError('Documentary intros are cricket-only.')
    source=Path(value['body_path']).resolve();transcript_path=Path(value['transcript_path']).resolve();script_path=Path(value['script_path']).resolve()
    source_hash=file_hash(source);transcript_hash=file_hash(transcript_path);script_hash=file_hash(script_path)
    if sorted(value['input_hashes'])!=sorted([source_hash,transcript_hash,script_hash]):raise ValueError('Documentary inputs changed; inspect the current files.')
    transcript=json.loads(transcript_path.read_text('utf-8'))
    if transcript.get('source_sha256')!=source_hash:raise ValueError('Bind and verify the transcript against these exact source bytes first.')
    words=transcript.get('words',[])
    with av.open(str(source)) as media:
        if not media.streams.video:raise ValueError('Choose the real documentary body video.')
        stream=media.streams.video[0];duration=float(stream.duration*stream.time_base) if stream.duration else float(media.duration/av.time_base)
        width,height=stream.width,stream.height
    if duration<40:raise ValueError('The documentary body is shorter than its requested trailer.')
    if not words or any(not isinstance(w.get('text'),str) or any(not isinstance(w.get(k),(int,float)) or not math.isfinite(w[k]) for k in ('start','end')) or not 0<=w['start']<=w['end']<=duration for w in words):raise ValueError('Use finite, source-timed transcript words.')
    timing_issues=[{'index':i,**w} for i,w in enumerate(words) if w['start']==w['end'] or w.get('aligned') is False]
    timeline={'source_id':source_hash,'path':str(source),'source_in':0,'source_out':duration,'timeline_start':0}
    candidate={'id':source_hash[:20],'source_id':source_hash,'source_sha256':source_hash,'source':str(source),'start':0,'duration':duration,'review_state':'unreviewed','phase_tags':[],'output_frames':round(duration*30),'description':'Complete cricket documentary body','semantic_status':'needs_review'}
    body={'ordered_clip_ids':[candidate['id']],'timeline':[timeline],'duration':duration,'timeline_hash':digest(timeline),'approval_state':'source_review','assemblies_valid':False}
    return database(state).mutate(value['id'],'curation',value,lambda old:{'category':'cricket','documentary':True,'candidates':[candidate],'body':body,'feedback':[],
        'source':{'id':source_hash,'hash':source_hash,'path':str(source),'duration':duration,'size':source.stat().st_size},'canvas':[width,height],'timing_issues':timing_issues,
        'transcript_path':str(transcript_path),'transcript_hash':transcript_hash,'script_path':str(script_path),'script_hash':script_hash,'approval_state':'story_graph_review'})

def save_graph(state,value):
    def change(data):
        if not data or not data.get('documentary'):raise ValueError('Import the cricket documentary body first.')
        source=data['source']
        if file_hash(source['path'])!=source['hash'] or file_hash(data['script_path'])!=data['script_hash'] or file_hash(data['transcript_path'])!=data['transcript_hash']:raise ValueError('The documentary source, script or transcript changed.')
        graph=value['graph']
        expected={'script_hash':data['script_hash'],'transcript_hash':data['transcript_hash'],'body_hash':data['body']['timeline_hash']}
        if any(graph.get(k)!=v for k,v in expected.items()):raise ValueError('The graph must bind the current script, transcript and body timeline.')
        transcript=json.loads(Path(data['transcript_path']).read_text('utf-8'))
        for node in graph.get('nodes',[]):
            if node.get('source_id')!=source['id'] or node.get('body_start')!=node.get('source_start') or node.get('body_end')!=node.get('source_end'):
                raise ValueError('This imported body is unchanged; preserve the exact source-to-body timestamps.')
            # Text is compared to the actual words in the reviewed source span;
            # inserted quotations cannot masquerade as source speech.
            words=[w for w in transcript['words'] if w['start']>=node['source_start']-.001 and w['end']<=node['source_end']+.001]
            if any(node['source_start']<=w['start']<=node['source_end'] for w in data.get('timing_issues',[])):raise ValueError('This span contains unaligned transcript words. Recover their timing before using it.')
            if any(w['start']<node['source_start']<w['end'] or w['start']<node['source_end']<w['end'] for w in transcript['words']):raise ValueError('A source boundary cuts inside a spoken word.')
            if ' '.join(w['text'] for w in words).strip()!=node['text'].strip():raise ValueError('A story node does not match its actual timed transcript wording.')
        data['story_graph']=validate_graph(graph,{source['id']:source},source['duration']);data['approval_state']='intro_plan_review'
        data['body']['assemblies_valid']=False
        return data
    return database(state).mutate(value['id'],'curation',value,change)
