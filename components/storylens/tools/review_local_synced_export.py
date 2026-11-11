"""Inspect encoded named-player cue frames and show the local provenance."""
import json,math,html,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import local_documentary_synced as d
from hinglish_motion.speech_clock import frame_at

def main():
    import av
    from PIL import Image,ImageDraw
    plan=d.load('local-plan.json');words={w['id']:w for w in d.load('timed-words.json')}
    audit=d.load('cue-audit.json');receipt=d.load('receipt.json')
    targets=[]
    for mention in plan['mentions']:
        word=words[mention['word']];frame=frame_at(word['start'])
        record=next((r for r in audit['gate_records'] if r['frame']==frame),None)
        if not record:raise ValueError('Missing encoded cue trace: '+mention['word'])
        state=record['state'];visible=state.get('visible',[])
        if mention['person']=='Dale Steyn':
            match=any(p.endswith(('steyn-cutout.png','portrait.jpg','bowler.jpg')) for p in visible)
        else:
            match=state.get('source_identity')==mention['person'] and bool(visible)
        if not match:raise ValueError('Expected player asset absent at cue: '+mention['person'])
        targets.append({**mention,'acoustic_onset':word['start'],'frame':frame,'at':frame/30,
                        'schedule_error_ms':round((frame/30-word['start'])*1000,3),'asset_trace_pass':match,'state':state})
    points={min(1799,max(0,t['frame']+offset)) for t in targets for offset in [-1,0,3,15]}
    images={}
    with av.open(str(d.OUT/'LOCAL_SYNCED_60S.mp4')) as container:
        for i,f in enumerate(container.decode(video=0)):
            if i in points:images[i]=f.to_image().resize((320,180))
    board=Image.new('RGB',(1280,len(targets)*226),'#0d1219');draw=ImageDraw.Draw(board)
    for row,t in enumerate(targets):
        y=row*226;draw.text((8,y+3),f"{t['person']} | acoustic onset {t['acoustic_onset']:.3f}s",fill='white')
        for col,offset in enumerate([-1,0,3,15]):
            point=min(1799,max(0,t['frame']+offset));board.paste(images[point],(col*320,y+24))
            draw.text((col*320+8,y+206),f'{point/30:.3f}s'+(' | cue frame' if offset==0 else ''),fill='white')
    board.save(d.OUT/'named-player-cues.jpg',quality=94)
    d.save('named-player-audit.json',{'players':targets,'encoded_frames_reviewed':len(points),
        'method':'Encoded frames around locally annotated names plus renderer asset traces. Source identities checked against original baked name captions.',
        'limit':'Local acoustic onset estimates; no independently certified frame-by-frame face recognition.'})
    path=d.OUT/'report.html';text=path.read_text(encoding='utf8')
    text=text.replace('Original contemporaneous footage is used inside existing TV/film designs when a separate verified player photo is unavailable.',
        'At Sachin and Rohit name cues, an original reference frame bearing that player name is held inside the existing film design. This avoids inheriting the reference edit\'s later name-caption switch. The other source moments play at the current audio time.')
    text=text.replace('Local runtime:', 'Export pass runtime:')
    rows=''.join(f"<tr><td>{html.escape(t['person'])}</td><td>{t['acoustic_onset']:.3f}s</td><td>{t['at']:.3f}s</td><td>{t['schedule_error_ms']:.1f}ms</td><td><button onclick=\"document.querySelector('video').currentTime={max(0,t['at']-.8):.3f};document.querySelector('video').play()\">Watch cue</button></td></tr>" for t in targets)
    failed_seconds=sum(json.loads(p.read_text(encoding='utf8')).get('server_reported_total_seconds',0) for p in d.OUT.glob('failed-inference-*.json'))
    section=f'''<section id="player-cues"><h2>Player names on the narration clock</h2><p>Existing player imagery may stay visible on repeated mentions. New named-player source frames switch at the local acoustic cue. Labels and note highlights have separate speech clocks from photo reveals.</p><table><tr><th>Player</th><th>Speech estimate</th><th>Scheduled frame</th><th>Frame rounding</th><th>Preview</th></tr>{rows}</table><img src="named-player-cues.jpg" alt="Encoded frames before, at and after each player cue"><p><a href="named-player-audit.json">Named-player check</a> · <a href="source-identity-proof.json">Source caption proof</a> · <a href="export-verification.json">Export/audio checks</a></p><p>The final display text was generated locally by Qwen with reasoning disabled. Extra proposed labels were limited to the template slot count in their returned order; no replacement wording was written by Codex. Earlier invalid drafts were rejected before this export. Completed local inference across all recorded drafts/corrections: {sum(c.get('elapsed_seconds',0) for c in receipt['model_calls'])/60:.1f} minutes; this includes failed drafts. The code and timing adapter were written with Codex; the local model chose the edit, display text and note cues. This is saved local memory and reusable rendering software, not model-weight fine-tuning or newly generated animation rigs.</p></section>'''
    section+=f'<p>A separate rejected reasoning-only attempt consumed {failed_seconds/60:.1f} minutes; it supplied no final creative answer and is excluded from the completed-call total above. Numeric note cues are resolved against literal spoken numeral tokens, retaining local wording. Book labels are measured and fitted into the original page inset.</p>'
    text=text.replace('<main>',section+'<main>');path.write_text(text,encoding='utf8')
    print(json.dumps({'players':[{k:t[k] for k in ['person','acoustic_onset','at','schedule_error_ms','asset_trace_pass']} for t in targets]},indent=2))

if __name__=='__main__':main()

