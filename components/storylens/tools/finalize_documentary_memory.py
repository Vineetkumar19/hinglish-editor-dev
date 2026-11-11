"""Validate complete two-library coverage, preserve preferences, then export."""
import hashlib,html,json,sqlite3,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.deepen_documentary_memory import OUT,SETS,read
from tools.analyze_documentary_reference import write_json
from hinglish_niche.documentary_memory import export,RELATIVE
from hinglish_niche.documentary import SETS as NAMES

def relative(value):
    try:return Path(value).relative_to(ROOT).as_posix()
    except ValueError:return value

def main():
    while not (OUT/'coverage.json').exists() or not (OUT/'semantic-progress.json').exists():time.sleep(10)
    while read(OUT/'semantic-progress.json')['status']!='complete':time.sleep(10)
    coverage=read(OUT/'coverage.json');semantic=read(OUT/'semantic-progress.json')
    if coverage['status']!='complete' or len(coverage['sources'])!=16 or len(semantic['sources'])!=16:raise ValueError('Incomplete reference library coverage')
    db=sqlite3.connect(ROOT/'library/creator-profiles/editing-dna.sqlite3');stats=[]
    try:
        for item in coverage['sources']:
            style=item['style'];slug=Path(item['record_file']).parent.name;folder=OUT/style/slug
            expected=item['native_frames'];receipt=read(folder/'motion-coverage.json')
            if expected!=receipt['native_frames'] or not receipt['full_source']:raise ValueError('Incomplete native motion '+slug)
            seconds=read(folder/'motion-seconds.json')
            if sum(s['native_frames'] for s in seconds)!=expected:raise ValueError('Native frame aggregation mismatch '+slug)
            semantic_seconds=read(folder/'semantic-seconds.json')['frames']
            if len(semantic_seconds)!=len(seconds):raise ValueError('Visual interpretation seconds missing '+slug)
            rows=db.execute('SELECT id,data FROM records WHERE style=? AND source=? ORDER BY start',(style,'continuous:'+slug)).fetchall()
            if len(rows)!=len(seconds):raise ValueError('Database second records incomplete '+slug)
            lines=[];camera_active=0;measured=0;graphics=0;graphic_camera=0
            for key,raw in rows:
                data=json.loads(raw);motion=data['motion'];m=motion['median']
                data['native_frame_curve']=relative(data['native_frame_curve'])
                if data['visual'].get('semantic_frame'):data['visual']['semantic_frame']=relative(data['visual']['semantic_frame'])
                motion['measurement_size']=[256,144]
                motion['pan_width_fraction_per_second']=m['dx']/256 if m['dx'] is not None else None
                motion['pan_height_fraction_per_second']=m['dy']/144 if m['dy'] is not None else None
                data['narration_scope']='Intersecting local ASR segments; text may include neighbouring words. Exact current-video cues must be aligned on that video.'
                labels=data['audio']['mixed_track_candidates'];events=data['audio']['classified_event_candidates']
                families={name:[e for e in events if any(c['label']==name for c in e.get('candidates',[]))] for name in ['impact','riser','whoosh','glitch','typing']}
                data['audio']['roles']={'voice':{'fraction':data['audio']['voice_fraction'],'method':'Full-track local VAD'},
                    'background_music_candidates':[x for x in labels if 'music' in x],
                    'ambience_candidates':[x for x in labels if x in ['ambience','applause','broadcast']],
                    'sound_effect_candidates':families,'status':'Mixed track; no isolated stem or confirmed effect identity implied.'}
                active=m['dx'] is not None and ((m['dx']**2+m['dy']**2)**.5>.35 or abs(m['zoom'])>.002 or abs(m['rotation'])>.15)
                tracked=motion['tracked_frame_fraction']>=.5
                measured+=int(tracked);camera_active+=int(tracked and active)
                layout=data['visual']['scene_candidate'];is_graphic=layout not in ['presenter','match-footage','unclassified']
                graphics+=int(is_graphic and tracked);graphic_camera+=int(is_graphic and tracked and active)
                db.execute('UPDATE records SET data=? WHERE id=?',(json.dumps(data,ensure_ascii=False),key))
                original=db.execute('SELECT start,end,kind,text FROM records WHERE id=?',(key,)).fetchone()
                lines.append(json.dumps({'start':original[0],'end':original[1],'kind':original[2],'text':original[3],'data':data},ensure_ascii=False))
            (folder/'editing-seconds.jsonl').write_text('\n'.join(lines)+'\n',encoding='utf8')
            stats.append({'style':style,'slug':slug,'name':item['name'],'native_frames':expected,'indexed_seconds':len(seconds),
                'measurable_seconds':measured,'global_camera_motion_seconds':camera_active,'graphic_candidate_seconds':graphics,
                'graphic_global_camera_motion_seconds':graphic_camera,'audio_available':read(ROOT/'output/reference-analysis'/SETS[style]/slug/'audio-analysis.json').get('audio_available',True)})
        db.commit()
        counts=[{'style':r[0],'kind':r[1],'records':r[2]} for r in db.execute('SELECT style,kind,COUNT(*) FROM records GROUP BY style,kind')]
    finally:db.close()
    for style in SETS:
        path=ROOT/'library/creator-profiles'/f'{style}.json';profile=read(path)
        sources=[s for s in stats if s['style']==style]
        profile['continuous_motion_memory']={'status':'complete','native_frames':sum(s['native_frames'] for s in sources),
            'indexed_seconds':sum(s['indexed_seconds'] for s in sources),'source_count':len(sources),
            'brains':['motion-graphics-editor-brain','motion-graphics-animator-brain'],
            'manifest':(RELATIVE/'manifest.json').as_posix(),'model_independent':True,
            'rule':'Meaningful image/camera motion continues after the entrance; grain alone is insufficient.',
            'fine_tuned_language_weights':False}
        write_json(path,profile)
    quality={'status':'complete','native_frames':sum(s['native_frames'] for s in stats),'visual_semantic_seconds':sum(s['indexed_seconds'] for s in stats),
        'video_seconds':coverage['seconds'],'sources':stats,'database_counts':counts,
        'full_brain_snapshot_hashes':read(ROOT/RELATIVE/'manifest.json')['brains'],
        'limits':coverage['limits'],'original_videos_modified':False,'new_demo_generated':False}
    write_json(OUT/'memory-quality-receipt.json',quality)
    rows=''.join(f'<tr><td>{html.escape(NAMES[s["style"]])}</td><td>{html.escape(s["name"])}</td><td>{s["native_frames"]:,}</td><td>{s["indexed_seconds"]:,}</td><td>{s["global_camera_motion_seconds"]}/{s["measurable_seconds"]}</td><td>{"available" if s["audio_available"] else "no source audio"}</td></tr>' for s in stats)
    (OUT/'report.html').write_text(f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>Your continuous documentary memory</title><style>body{{background:#0f1720;color:#e9e3d5;font:17px/1.6 system-ui;max-width:1250px;margin:auto;padding:30px}}h1{{font:40px Georgia}}td,th{{padding:9px;border-bottom:1px solid #354351;text-align:left}}a{{color:#e9bf76}}.card{{padding:22px;background:#1b2732;margin:20px 0;border-radius:10px}}</style><h1>Your documentary memory survives model changes.</h1><div class="card"><strong>16 videos · 3h 36m 45s · {quality['native_frames']:,} native frames · {quality['visual_semantic_seconds']:,} indexed seconds</strong><p>Both complete motion brains are saved, source-linked and searchable. Adjacent native frames have local motion measurements. One actual frame every second has offline CLIP layout, typography and texture candidates. The full mixed audio retains 20ms measurements, voice activity, music/ambience candidates, classified onset candidates and beat timing estimates.</p></div><div class="card"><strong>Your rule: movement continues after the entrance.</strong><p>Camera travel, zoom, depth-separated photographic layers and focus should support the narration throughout each graphic shot. Grain over a frozen picture does not satisfy the rule. Existing cricket motion renders now flag low measured camera movement for review; General and Gaming retain their defaults.</p></div><p>The knowledge is project JSON + SQLite/E5 retrieval, independent of Ollama language-model weights. Changing the connected model preserves the same preferences, both brains and references; it does not make a smaller model reason like a larger one. The model receives core guidance plus relevant retrieved examples rather than all three hours in one prompt.</p><p>Measurements and candidates are distinguished. A flattened export does not reveal a physical AE camera, Z depth, exact font or isolated sound stems. Global camera-motion seconds below are an image-space estimate: subject movement can imitate camera movement; local/parallax motion may occur even without global motion.</p><table><tr><th>Style</th><th>Reference</th><th>Native frames</th><th>Indexed seconds</th><th>Global movement / measurable seconds</th><th>Audio</th></tr>{rows}</table><p><a href="memory-quality-receipt.json">Coverage and database receipt</a> · <a href="coverage.json">Native-frame coverage</a> · <a href="semantic-progress.json">Per-second interpretation coverage</a> · <a href="../../../docs/DOCUMENTARY_MEMORY_AND_MODEL_CHANGES.md">How memory and model changes work</a> · <a href="DOCUMENTARY_MEMORY_PORTABLE.zip">Portable memory archive</a></p></html>''',encoding='utf8')
    package=export(ROOT,OUT/'DOCUMENTARY_MEMORY_PORTABLE.zip')
    print('COMPLETE validated memory and portable archive:',package,flush=True)

if __name__=='__main__':main()
