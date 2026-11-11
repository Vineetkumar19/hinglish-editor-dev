"""Rebuild the verified exact-lyric project in readable ordered karaoke style."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    import av
    from hinglish_captions.project import rebuild_project
    from hinglish_eval.specs import caption_checks,Evaluation
    proof_path=ROOT/'output/validation/song-captions/corrected-localhost-result.json'
    proof=json.loads(proof_path.read_text(encoding='utf-8'))
    project=Path(proof['caption_project'])
    rebuild_project(project,{'style':'karaoke'},print)
    data=json.loads(project.read_text(encoding='utf-8'))
    assert [' '.join(word['text'] for word in cue['words']) for cue in data['cues']]==proof['lyrics'].splitlines()
    evaluation=Evaluation('captions',str(project.parent),caption_checks(project.parent,data))
    assert evaluation.passed
    with av.open(proof['video']) as video:
        assert video.streams.audio
        frames=0
        for i,frame in enumerate(video.decode(video=0)):
            frames+=1
            if i in (60,180,285,408):frame.to_image().save(ROOT/f'output/validation/song-captions/final-frame-{i}.jpg')
    assert frames==proof['frames']
    proof.update(style='karaoke',readable_style_rebuild_verified=True)
    proof_path.write_text(json.dumps(proof,indent=2,ensure_ascii=False),encoding='utf-8')
    print('READABLE_LYRIC_VIDEO_PASSED',flush=True)


if __name__=='__main__':
    from hinglish_cut.gpu_lock import gpu_lock
    with gpu_lock(ROOT):main()
