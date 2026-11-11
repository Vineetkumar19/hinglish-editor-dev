"""Bounded local speech-to-timeline control in a fresh isolated fixture folder."""
import json
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--upgrade',action='store_true')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    os.environ['HF_HUB_OFFLINE'] = '1'
    from imageio_ffmpeg import get_ffmpeg_exe
    from hinglish_cut.model import Settings
    from hinglish_cut.pipeline import run_project
    from hinglish_app.assistant_media import render_xml
    import av

    validation = ROOT / 'output/validation/new-laptop'
    core = json.loads((validation / 'core-inference.json').read_text(encoding='utf-8'))
    speech = core['hinglish_speech_vad_and_alignment']['result']
    fixture = validation / ('edit-control-' + uuid.uuid4().hex[:10])
    inputs = fixture / 'input/instagram-vertical'
    inputs.mkdir(parents=True)
    subprocess.run([get_ffmpeg_exe(), '-nostdin', '-v', 'error', '-y', '-i', speech['source'],
        '-t', '6', '-vf', 'scale=360:-2', '-r', '30', '-c:v', 'libx264', '-preset', 'veryfast',
        '-threads', '2', '-c:a', 'aac', str(inputs / 'six-second-control.mp4')], check=True)
    script=speech['transcript']
    if args.upgrade:
        script='Log mujhe poochhate hain.\nBhai Madurai mein night life kaisi hai?'
    (fixture / 'input/script.txt').write_text(script, encoding='utf-8')
    models = json.loads((ROOT/'downloads/laptop-model-downloads.json').read_text(encoding='utf-8'))['models']
    settings = Settings(device='cuda', offline=True, cpu_threads=8,
        asr_model=models['Oriserve/Whisper-Hindi2Hinglish-Swift']['path'],
        align_model=models['MahmoudAshraf/mms-300m-1130-forced-aligner']['path'])
    if args.upgrade:
        from hinglish_cut.model_storage import role
        from hinglish_cut.model_preferences import release_ollama
        selected=role(ROOT,'asr')
        assert selected,'A staged upgrade selection is required'
        settings.asr_model=selected['path']
        release_ollama(ROOT)
    started = time.monotonic()
    folder, report = run_project(fixture, settings)
    assert report['cut_count'] > 0 and (folder/'draft.xml').is_file()
    preview = render_xml(folder/'draft.xml', folder/'rendered-control.mp4')
    with av.open(str(preview)) as media:
        assert media.streams.video and media.streams.audio
        frames = sum(1 for _ in media.decode(video=0))
        assert frames > 0
    receipt = dict(passed=True, scope='Six-second local speech-to-timeline/render control; script taken from the prior speech control. Semantic approval is not asserted.',
        runtime_passed=True, complete_script_matched=all(r['media_id'] is not None for r in report['lines']),
        seconds=round(time.monotonic()-started, 2), cuts=report['cut_count'],
        review_status=report['status'], issues=[r['issues'] for r in report['lines']],
        frames=frames, timeline=str(folder/'draft.xml'), preview=str(preview))
    if args.upgrade:
        receipt.update(asr_revision=selected['revision'],asr_path=selected['path'],script=script,
            scope='Upgraded ASR, VAD, alignment, script matching, timeline export and audio/video render. Semantic approval is not asserted.')
        receipt['passed']=receipt['complete_script_matched']
    file='edit-pipeline-upgrade-inference.json' if args.upgrade else 'edit-pipeline-inference.json'
    (args.output or validation/file).write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps(receipt, indent=2), flush=True)
    assert receipt['passed'],'The upgraded recognizer did not match both script lines'


if __name__ == '__main__':
    from hinglish_cut.gpu_lock import gpu_lock
    with gpu_lock(ROOT): main()
