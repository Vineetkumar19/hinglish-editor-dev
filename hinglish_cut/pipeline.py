from dataclasses import asdict
from datetime import datetime
from pathlib import Path
import hashlib
import json
import os
import shutil
from . import __version__
from .model import Media, Word, Transcript, Settings
from .text import split_script
from .matching import arrange
from .cutting import make_cuts, selection_limits, constrain_cuts
from .evaluate import compare_text
from .media import EXTENSIONS, fingerprint, prepare_media, extract_audio, assemble_audio
from .xml_export import export_xml
from .report import write_report


INPUT_FORMATS=(
    ('instagram_vertical','instagram-vertical'),
    ('youtube_horizontal','youtube-horizontal'),
)


def load_settings(path=None,device=None,offline=None):
    data=json.loads(Path(path).read_text(encoding='utf-8-sig')) if path else {}
    if device: data['device']=device
    if offline is not None: data['offline']=offline
    return Settings(**data)


def atomic_json(path,data):
    path=Path(path)
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    temp.replace(path)


def select_video_input(root):
    """Find the one chosen delivery format, while retaining the old videos folder."""
    root=Path(root)
    selected=[]
    for output_format,folder_name in INPUT_FORMATS:
        folder=root/'input'/folder_name
        paths=sorted(p for p in folder.rglob('*') if p.is_file() and p.suffix.lower() in EXTENSIONS) if folder.exists() else []
        if paths:
            selected.append((paths,output_format))
    if len(selected)>1:
        raise ValueError('Use one input folder per run: instagram-vertical or youtube-horizontal, not both')
    if selected:
        return selected[0]
    legacy=root/'input'/'videos'
    paths=sorted(p for p in legacy.rglob('*') if p.is_file() and p.suffix.lower() in EXTENSIONS) if legacy.exists() else []
    if paths:
        return paths,None
    raise ValueError('Add raw videos to input\\instagram-vertical or input\\youtube-horizontal')


def finish_project(lines,transcripts,audio_paths,output,settings,recognize,judge=None,progress=print,errors=None,demo=False,output_format=None):
    output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    if any((output/name).exists() for name in ('report.json','draft.xml','timeline.xml')):
        raise ValueError('Choose a fresh output folder; previous results are never overwritten')
    (output/'review-audio').mkdir(exist_ok=True)
    by_id={t.media.id:t for t in transcripts}
    media={t.media.id:t.media for t in transcripts}
    selections=arrange(lines,transcripts,settings)
    limits=selection_limits(selections,by_id)
    report={'version':__version__,'status':'REVIEW_REQUIRED','demo':demo,'settings':asdict(settings),'output_format':output_format,'lines':[],
            'errors':list(errors or []),'source_issues':{t.media.path:t.issues for t in transcripts if t.issues}}
    cuts=[]
    for selection in selections:
        index=selection.line_index
        row=asdict(selection); row['issues']=[]
        if selection.media_id is None:
            row['issues'].append('missing_script_line'); report['lines'].append(row); continue
        progress(f'Evaluating line {index+1}/{len(lines)}')
        t=by_id[selection.media_id]
        row['source']=t.media.path
        selected=t.words[selection.first_word:selection.last_word]
        row['source_transcript']=' '.join(w.text for w in selected)
        if selection.ambiguous: row['issues'].append('ambiguous_take')
        if any(not w.aligned for w in selected): row['issues'].append('uncertain_word_alignment')
        line_cuts=constrain_cuts(make_cuts(t,selection.first_word,selection.last_word,settings,index),limits[index])
        audio=output/'review-audio'/f'line-{index+1:04d}.wav'
        assemble_audio(line_cuts,media,audio_paths,audio)
        actual=recognize(audio)
        check=compare_text(selection.script,actual,settings)
        row['attempts']=[{'kind':'silence_trimmed','actual':actual,**check}]
        if check['issues']:
            safe_cuts=constrain_cuts(make_cuts(t,selection.first_word,selection.last_word,settings,index,conservative=True),limits[index])
            safe_audio=output/'review-audio'/f'line-{index+1:04d}-conservative.wav'
            assemble_audio(safe_cuts,media,audio_paths,safe_audio)
            safe_actual=recognize(safe_audio)
            safe_check=compare_text(selection.script,safe_actual,settings)
            row['attempts'].append({'kind':'conservative_retry','actual':safe_actual,**safe_check})
            if (len(safe_check['issues']),-safe_check['coverage'])<(len(check['issues']),-check['coverage']):
                line_cuts,actual,check=safe_cuts,safe_actual,safe_check
                shutil.copyfile(safe_audio,audio)
                row['restored_pauses']=True
        if not line_cuts: row['issues'].append('no_valid_cut')
        row['issues'].extend(check['issues'])
        row['actual']=actual; row['coverage']=check['coverage']
        row['audio']=audio.relative_to(output).as_posix()
        row['cuts']=[asdict(c) for c in line_cuts]
        cuts.extend(line_cuts)
        report['lines'].append(row)
    # Quantized handles can overlap even when selected source words do not.
    for i,a in enumerate(cuts):
        for b in cuts[i+1:]:
            if a.media_id==b.media_id and max(a.start_frame,b.start_frame)<min(a.end_frame,b.end_frame):
                for line_index in {a.line_index,b.line_index}:
                    report['lines'][line_index]['issues'].append('source_frames_reused')
    if judge:
        for row in report['lines']:
            if row['media_id'] is None: continue
            try:
                result=judge(row['script'],row['actual'])
                row['judgment']=result
                if not result['intent_preserved'] or result['entity_preservation']<.9:
                    row['issues'].append('semantic_check_failed')
            except Exception as error:
                row['issues'].append('semantic_check_unavailable')
                row['judge_error']=str(error)
    else:
        for row in report['lines']:
            if row['media_id'] is not None: row['issues'].append('semantic_not_checked')
    report['cut_count']=len(cuts)
    report['duration_seconds']=sum(c.duration/float(media[c.media_id].rate) for c in cuts)
    if not any(row['issues'] for row in report['lines']) and not report['errors'] and not demo:
        report['status']='CHECKS_PASSED_REVIEW_RECOMMENDED'
    atomic_json(output/'edit-decisions.json',{'media':{k:asdict(v) for k,v in media.items()},'cuts':[asdict(c) for c in cuts],
                                               'output_format':output_format})
    if cuts:
        export_xml(output/'draft.xml',cuts,media,output_format)
        if report['status']=='CHECKS_PASSED_REVIEW_RECOMMENDED':
            shutil.copyfile(output/'draft.xml',output/'timeline.xml')
        assemble_audio(cuts,media,audio_paths,output/'review-audio'/'full-timeline.wav')
    write_report(output,report)
    return report


def run_project(root,settings,progress=print):
    root=Path(root).resolve()
    script=root/'input'/'script.txt'
    if not script.exists(): raise ValueError(f'Add your UTF-8 Hinglish script: {script}')
    lines=split_script(script.read_text(encoding='utf-8-sig'))
    if not lines: raise ValueError('The master script is empty')
    paths,output_format=select_video_input(root)
    cache=root/'cache'; cache.mkdir(exist_ok=True)
    models=root/'models'; models.mkdir(exist_ok=True)
    if settings.offline:
        os.environ['HF_HUB_OFFLINE']='1'; os.environ['TRANSFORMERS_OFFLINE']='1'
    from .backends import LocalSpeech, LocalJudge
    speech=LocalSpeech(settings,models)
    transcripts=[]; audio_paths={}; errors=[]
    try:
        for i,path in enumerate(paths,1):
            progress(f'Analyzing video {i}/{len(paths)}: {path.name}')
            # Hash includes all settings for safe reuse, even though some only affect editing.
            key=hashlib.sha256((str(path)+fingerprint(path)+json.dumps(asdict(settings),sort_keys=True)+__version__).encode()).hexdigest()
            cached=cache/f'{key}.json'; wav=cache/f'{key}.wav'
            if cached.exists() and wav.exists():
                try:
                    data=json.loads(cached.read_text(encoding='utf-8'))
                    t=Transcript(Media(**data['media']),[Word(**w) for w in data['words']],data['speech'],data['issues'])
                    progress('  Reusing completed analysis')
                except (ValueError,KeyError,TypeError):
                    raise ValueError(f'Invalid cache entry: {cached}. Remove only this cache entry and rerun.')
            else:
                try:
                    m,conform_note=prepare_media(path,cache/'conformed',progress)
                except ValueError as error:
                    errors.append(str(error)); progress(str(error)); continue
                extract_audio(m,wav)
                t=speech.analyze(m,wav,progress)
                if conform_note:
                    t.issues.append(conform_note)
                atomic_json(cached,asdict(t))
            transcripts.append(t); audio_paths[t.media.id]=wav
        if len({t.media.rate for t in transcripts})>1:
            raise ValueError('Input videos have mixed frame rates. Conform them to one constant frame rate before running.')
        output=root/'output'/datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        judge_instance=None
        def judge(expected,actual):
            nonlocal judge_instance
            if judge_instance is None:
                speech.close()
                progress('Loading the local semantic evaluator')
                judge_instance=LocalJudge(settings,models)
            return judge_instance.judge(expected,actual)
        report=finish_project(lines,transcripts,audio_paths,output,settings,speech.transcribe_cut,
                              judge if settings.judge_model else None,progress,errors,output_format=output_format)
        progress(f'{report["status"]}: {output / "report.html"}')
        return output,report
    finally:
        speech.close()
