"""Optional local evidence tools for Qwen sound planning; neither tool chooses the final cue."""
import json
import os
from pathlib import Path
import subprocess
import sys


def _ffmpeg_env(root):
    env=os.environ.copy()
    ffmpeg=Path(root)/'tools/reelmimic/bin'
    env['PATH']=str(ffmpeg)+os.pathsep+env.get('PATH','')
    return env


def clipwing_motion(root, video, folder, seconds, existing, progress=print):
    """Add measured picture changes as optional anchors, not automatic effects."""
    video=Path(video)
    script=Path(root)/'tools/reference-repositories/clipwing-skills/skills/real-sfx/scripts/find_moments.py'
    if not script.is_file() or not video.is_file() or video.suffix.lower() not in ('.mp4','.mov','.mkv') or seconds>180:
        return [],'Clipwing motion analysis unavailable for this input'
    out=Path(folder)/'clipwing-motion'
    try:
        result=subprocess.run([sys.executable,str(script),str(video),'--out',str(out),'--max','16','--fps','10'],
            cwd=str(root),env=_ffmpeg_env(root),capture_output=True,text=True,timeout=90,check=False)
        if result.returncode:return [],'Clipwing motion analysis unavailable; Qwen kept the existing editor and Vision evidence'
        data=json.loads((out/'moments.json').read_text(encoding='utf-8'))
        anchors=[]
        for row in data.get('moments',[]):
            kind=row.get('kind');t=row.get('t');strength=row.get('strength',0)
            if kind not in ('cut','burst','onset','settle') or type(t) not in (int,float) or not 0<=t<seconds:
                continue
            if kind!='cut' and strength<.5:continue
            if any(abs(t-e.get('time',-10))<.18 for e in existing):continue
            anchors.append(dict(time=t,end=min(seconds,t+.12),kind='transition' if kind=='cut' else 'motion',
                label='Measured picture '+{'cut':'cut','burst':'motion burst','onset':'motion start','settle':'motion settle'}[kind]
                    +'; physical source unknown',precision='sampled_motion',phase=kind,
                confidence=min(1.,max(0.,float(strength)))))
        progress(f'  Clipwing measured {len(anchors)} additional picture moments; Qwen decides which deserve sound')
        return anchors,'Clipwing Real SFX picture analysis (10 fps); candidate timing only'
    except (OSError,ValueError,subprocess.TimeoutExpired,KeyError):
        return [],'Clipwing motion analysis unavailable; Qwen kept the existing editor and Vision evidence'


def earshot_evidence(root, folder, moments, candidate_lists, progress=print):
    """Give Qwen bounded acoustic descriptions before its own file choice; never reorder/veto."""
    repo=Path(root)/'tools/reference-repositories/earshot'
    python=repo/'.venv/Scripts/python.exe'
    script=Path(root)/'tools/sound_tools/earshot_rank_batch.py'
    if not python.is_file() or not script.is_file():return {'status':'unavailable','count':0}
    slates=[];seen=set()
    for i,(moment,cands) in enumerate(zip(moments,candidate_lists)):
        if len(slates)>=8:break
        paths=[c['asset'].path for c in cands[:6]]
        query=str(moment.get('intent','')).strip()[:160]
        key=(query.lower(),tuple(paths))
        if not query or not paths or key in seen:continue
        seen.add(key);slates.append(dict(moment=i,query=query,paths=paths))
    if not slates:return {'status':'no_candidates','count':0}
    inp=Path(folder)/'earshot-input.json';out=Path(folder)/'earshot-evidence.json'
    inp.write_text(json.dumps({'slates':slates},ensure_ascii=False),encoding='utf-8')
    env=_ffmpeg_env(root);env['EARSHOT_OFFLINE']='1';env['EARSHOT_THREADS']='4'
    try:
        result=subprocess.run([str(python),str(script),str(inp),str(out)],cwd=str(repo),env=env,
            capture_output=True,text=True,timeout=180,check=False)
        if result.returncode or not out.is_file():
            return {'status':'unavailable','count':0,'reason':'Local Earshot analysis could not finish'}
        data=json.loads(out.read_text(encoding='utf-8'))
        count=0
        for row in data.get('slates',[]):
            i=row.get('moment')
            if type(i) is not int or not 0<=i<len(candidate_lists):continue
            by_path={r.get('path'):r for r in row.get('results',[]) if isinstance(r,dict)}
            for cand in candidate_lists[i]:
                fact=by_path.get(cand['asset'].path)
                if not fact:continue
                sound=str(fact.get('sounds_most_like',''))[:70]
                verdict=str(fact.get('verdict',''))[:25]
                cand['doc']+=' | Earshot acoustic estimate: '+verdict+(('; '+sound) if sound else '')
                count+=1
        progress(f'  Earshot described {count} shortlisted recordings for Qwen; it did not veto or replace choices')
        return {'status':'used','count':count,'slates':len(data.get('slates',[])),'receipt':str(out)}
    except (OSError,ValueError,subprocess.TimeoutExpired):
        return {'status':'unavailable','count':0,'reason':'Local Earshot analysis could not finish'}
