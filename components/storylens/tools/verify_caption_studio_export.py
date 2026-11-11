"""Check the real UI export, downloaded file, word gaps and original source."""
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
FOLDER=ROOT/'output/captions/connected-caption-studio/Rog Music'


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    import av
    import numpy as np
    project=json.loads((FOLDER/'caption-project.json').read_text(encoding='utf-8'))
    out=ROOT/'output/validation/caption-studio-editing';out.mkdir(parents=True,exist_ok=True)
    original=ROOT/'output/captions/20261018-091908-b22ac7/001-0000-e11e1551-Rog Music'
    assert (original/'caption-project.json').read_bytes()==(out/'original-project/caption-project.json').read_bytes()
    assert project['font']=='bahnschrift' and project['word_visibility']=='spoken'
    assert project['video_encoder']=='h264_nvenc' and len(project['cues'])==4
    assert project['cues'][0]['words'][0]['start']==1.68
    assert project['cue_layouts']==[{'x':.5,'y':.4,'size':.55}]*4
    downloaded=Path(r'C:\Users\Vineet Kumar\Downloads\captioned-preview.mp4')
    assert downloaded.is_file() and digest(downloaded)==digest(FOLDER/'captioned-preview.mp4')
    def audio_digest(path):
        h=hashlib.sha256()
        with av.open(str(path)) as video:
            for packet in video.demux(audio=0):
                if packet.size:h.update(bytes(packet))
        return h.hexdigest()
    assert audio_digest(FOLDER/'media/source.mp4')==audio_digest(FOLDER/'captioned-preview.mp4')
    earlier=ROOT/'cache/app/jobs/c5bb5a966d94/media/0000-6c06e15c-Rog Music.mp4'
    assert audio_digest(earlier)==audio_digest(FOLDER/'media/source.mp4'),'Earlier alignment was for different audio'
    frames=0
    with av.open(str(FOLDER/'captioned-preview.mp4')) as video:
        assert (video.streams.video[0].width,video.streams.video[0].height)==(1080,1920)
        for i,frame in enumerate(video.decode(video=0)):
            frames+=1
            if i in (15,51,78,150,453):frame.to_image().save(out/f'export-frame-{i}.jpg')
    assert frames==462
    samples={}
    from hinglish_captions.core import CaptionWord,CaptionCue
    from hinglish_captions.renderer import draw_editor_caption
    from hinglish_captions.project import cues_from_data
    cues=cues_from_data(project['cues'])
    with av.open(str(FOLDER/'media/premium-captions.mov')) as video:
        for i,frame in enumerate(video.decode(video=0)):
            if i not in (15,51,78,150,453):continue
            pixels=frame.to_ndarray(format='rgba');alpha=pixels[:,:,3]
            samples[str(i)]={'visible_pixels':int((alpha>0).sum())}
            if i in (15,453):assert alpha.max()==0,'A word is visible outside its spoken range'
            else:
                assert alpha.max()>0
                qindex=next(k for k,q in enumerate(cues) if q.start<=i/30<q.end)
                expected=np.asarray(draw_editor_caption(1080,1920,cues[qindex],i/30,project['style'],project['font'],project['cue_layouts'][qindex],'spoken',project['word_colors'][qindex]))
                assert np.array_equal(pixels,expected),'Export pixels differ from the selected word/layout'
    srt=(FOLDER/'captions.srt').read_text(encoding='utf-8-sig')
    assert len(srt.strip().split('\n\n'))==17 and '00:00:01,680 --> 00:00:01,800' in srt
    result={'passed':True,'original_saved_project_unchanged':True,'original_audio_bitstream_preserved':True,
        'browser_download_matches_export':True,'download':str(downloaded),'video':str(FOLDER/'captioned-preview.mp4'),
        'frames':frames,'encoder':project['video_encoder'],'word_visibility':'spoken','word_subtitle_events':17,
        'blank_during_music_intro_and_after_lyrics':True,'sampled_overlay_pixels_match_selected_word_and_layout':True,'samples':samples}
    (out/'real-export-check.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':main()
