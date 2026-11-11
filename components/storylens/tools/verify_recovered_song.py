"""Verify the recovered real song export, its RTX receipts and audio."""
import hashlib
import json
from pathlib import Path

import av

ROOT=Path(__file__).resolve().parents[1]


def audio_digest(path):
    digest=hashlib.sha256()
    with av.open(str(path)) as container:
        for packet in container.demux(audio=0):
            if packet.size:
                digest.update(bytes(packet))
    return digest.hexdigest()


def main():
    proof=ROOT/'output/validation/song-captions'
    job=json.loads((proof/'retry-job.json').read_text(encoding='utf-8'))
    assert job['status']=='complete', 'The export is not complete yet'
    path=next(Path(job['result']['folder']).rglob('caption-project.json'))
    data=json.loads(path.read_text(encoding='utf-8'))
    folder=path.parent
    words=[word for cue in data['cues'] for word in cue['words']]
    assert [word['text'] for word in words]=='Haan tujhe dekhta raha Kissi khwab ki tarah Jo ab samne hai tu Ho kaise yakeen bhala'.split()
    assert data['transcription']['backend_device']=='cuda'
    assert data['transcription']['fallback_reason']=='invalid_recognition'
    assert Path(data['transcription']['model_path']).is_relative_to(Path(r'C:\Ai Models'))
    assert data['video_encoder']=='h264_nvenc'
    assert data['word_visibility']=='spoken'
    assert 1.5<words[0]['start']<words[0]['end']
    video=folder/'captioned-preview.mp4'
    assert audio_digest(video)==audio_digest(folder/'media/source.mp4')
    frames=0
    with av.open(str(video)) as container:
        assert (container.streams.video[0].width,container.streams.video[0].height)==(1080,1920)
        for index,frame in enumerate(container.decode(video=0)):
            frames+=1
            if index==78:
                frame.to_image().save(proof/'recovered-caption-frame.jpg')
    assert frames==462
    samples={}
    with av.open(str(folder/'media/premium-captions.mov')) as container:
        for index,frame in enumerate(container.decode(video=0)):
            if index not in (15,51,78,453):
                continue
            alpha=frame.to_ndarray(format='rgba')[:,:,3]
            samples[index]=int((alpha>0).sum())
            assert (alpha.max()==0) if index in (15,453) else (alpha.max()>0)
    assert len((folder/'captions.srt').read_text(encoding='utf-8-sig').strip().split('\n\n'))==17
    assert job['result']['quality_summary']['passed']
    result={'passed':True,'folder':str(folder),'video':str(video),'frames':frames,
            'recognition_device':'cuda','encoder':data['video_encoder'],
            'supplied_lyrics_preserved':True,'word_events':17,'first_word_start':words[0]['start'],
            'original_audio_preserved':True,'overlay_visible_pixels':samples,
            'automated_checks':job['result']['quality_summary']}
    (proof/'recovered-export-check.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
