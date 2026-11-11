"""Check the real UI export of linked, individually timed typography."""
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    import av
    import numpy as np
    from hinglish_captions.project import cues_from_data
    from hinglish_captions.renderer import draw_editor_caption
    from hinglish_eval.specs import caption_checks,Evaluation
    folder=ROOT/'output/captions/linked-timed-typography/Rog Music'
    data=json.loads((folder/'caption-project.json').read_text(encoding='utf-8'))
    assert data['style']=='typography_5' and data['word_visibility']=='styled_spoken'
    assert all(row['size']==data['size'] for row in data['cue_layouts'])
    assert data['video_encoder']=='h264_nvenc'
    cues=cues_from_data(data['cues'])
    words=[word for cue in cues for word in cue.words]
    assert [word.text for word in words]=='Haan tujhe dekhta raha Kissi khwab ki tarah Jo ab samne hai tu Ho kaise yakeen bhala'.split()
    selected={round((word.start+word.end)/2*30) for word in words}|{15,453}
    samples=[]
    with av.open(str(folder/'media/premium-captions.mov')) as movie:
        for frame_index,frame in enumerate(movie.decode(video=0)):
            if frame_index not in selected:continue
            timestamp=frame_index/30
            cue_index=next((i for i,cue in enumerate(cues) if cue.start<=timestamp<cue.end),None)
            rgba=frame.to_ndarray(format='rgba')
            if cue_index is None:assert rgba[:,:,3].max()==0
            else:
                expected=np.asarray(draw_editor_caption(1080,1920,cues[cue_index],timestamp,data['style'],data['font'],data['cue_layouts'][cue_index],data['word_visibility'],data['word_colors'][cue_index]))
                assert np.array_equal(rgba,expected),frame_index
                assert rgba[:,:,3].max()>0
            samples.append(frame_index)
    def audio_digest(path):
        digest=hashlib.sha256()
        with av.open(str(path)) as movie:
            for packet in movie.demux(audio=0):
                if packet.size:digest.update(bytes(packet))
        return digest.hexdigest()
    assert audio_digest(folder/'media/source.mp4')==audio_digest(folder/'captioned-preview.mp4')
    quality=Evaluation('captions',str(folder),caption_checks(folder,data))
    assert quality.passed,[check.title for check in quality.hard_failed]
    proof=ROOT/'output/validation/linked-timed-typography'
    result={'passed':True,'style':data['style'],'word_visibility':data['word_visibility'],
            'all_caption_sizes':[row['size'] for row in data['cue_layouts']],
            'word_events':len(words),'real_export_frames_checked':samples,'encoder':data['video_encoder'],
            'original_audio_preserved':True,'quality_score':quality.score}
    (proof/'real-export-check.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
