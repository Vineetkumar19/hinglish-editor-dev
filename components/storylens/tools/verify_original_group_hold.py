"""Verify the real song export uses cumulative original-template timing."""
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
    proof=ROOT/'output/validation/original-template-group-hold'
    data=json.loads((folder/'caption-project.json').read_text(encoding='utf-8'))
    before=json.loads((proof/'before/caption-project.json').read_text(encoding='utf-8'))
    assert data['style']=='typography_5' and data['word_visibility']=='phrase'
    for key in ('cues','font','cue_layouts','word_colors','size','position'):
        assert data[key]==before[key],key
    assert data['video_encoder']=='h264_nvenc'
    cues=cues_from_data(data['cues'])
    selected={15,453}
    for cue in cues:
        selected.update({int(cue.start*30),int(cue.start*30)+1,int(cue.end*30)-1,int(cue.end*30)+1})
        selected.update(round((word.start+word.end)/2*30) for word in cue.words)
    samples=[]
    with av.open(str(folder/'media/premium-captions.mov')) as movie:
        for frame_index,frame in enumerate(movie.decode(video=0)):
            if frame_index not in selected:continue
            timestamp=frame_index/30
            cue_index=next((i for i,cue in enumerate(cues) if cue.start<=timestamp<cue.end),None)
            rgba=frame.to_ndarray(format='rgba')
            if cue_index is None:
                assert rgba[:,:,3].max()==0
                visible=[]
            else:
                cue=cues[cue_index]
                expected=np.asarray(draw_editor_caption(1080,1920,cue,timestamp,data['style'],data['font'],data['cue_layouts'][cue_index],'phrase',data['word_colors'][cue_index]))
                assert np.array_equal(rgba,expected),frame_index
                visible=[word.text for word in cue.words if word.start<=timestamp]
            samples.append({'frame':frame_index,'time':timestamp,'group':None if cue_index is None else cue_index+1,'revealed_words':visible})
    assert len(samples)==len(selected)
    def audio_digest(path):
        digest=hashlib.sha256()
        with av.open(str(path)) as movie:
            for packet in movie.demux(audio=0):
                if packet.size:digest.update(bytes(packet))
        return digest.hexdigest()
    assert audio_digest(folder/'media/source.mp4')==audio_digest(folder/'captioned-preview.mp4')
    with av.open(str(folder/'captioned-preview.mp4')) as movie:
        stream=movie.streams.video[0]
        assert (stream.width,stream.height,stream.frames)==(1080,1920,462)
    quality=Evaluation('captions',str(folder),caption_checks(folder,data))
    assert quality.passed,[check.title for check in quality.hard_failed]
    result={'passed':True,'mode':'phrase','behavior':'Reveal each word at its start; hold until group end; reset at next group.',
            'style':data['style'],'encoder':data['video_encoder'],'original_audio_preserved':True,
            'saved_text_timings_font_colors_and_layouts_preserved':True,'video_frames':462,'checked_frames':samples,
            'regression_tests_passed':63,'quality_score':quality.score}
    (proof/'real-export-check.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({key:value for key,value in result.items() if key!='checked_frames'},indent=2))
    print(f'Checked {len(samples)} real overlay frames, including all group boundaries.')


if __name__=='__main__':main()
