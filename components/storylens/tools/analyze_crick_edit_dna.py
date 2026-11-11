"""Resumable sequential native-frame and full mixed-audio reference analysis."""
import argparse,gc,json,sys,time,wave
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.analyze_documentary_reference import scan,facts,write_json,fast_transcript
from hinglish_niche.reference_dna import VisualScan,audio_features
from hinglish_sound.library import decode

BASE=ROOT/'output/reference-analysis/crick-edit-editing-style'

def main(speech=False, base=None):
    base=Path(base).resolve() if base else BASE
    items=json.loads((base/'inventory.json').read_text(encoding='utf-8'))
    for number,item in enumerate(items,1):
        path=Path(item['path']);folder=base/item['slug'];folder.mkdir(exist_ok=True)
        source=facts(path)
        receipt=folder/'dna-coverage.json'
        old=json.loads(receipt.read_text()) if receipt.exists() else {}
        if old.get('source')!=source or old.get('feature_version')!=2 or not (folder/'scenes.json').exists():
            print(f"FRAME ANALYSIS {number}/{len(items)}: {path.name}",flush=True)
            collector=VisualScan(folder)
            try:result=scan(path,folder,collector)
            except BaseException:collector.file.close();raise
            scenes=collector.close(source['seconds'])
            write_json(receipt,{'source':source,'feature_version':2,'native_frames_measured':result['decoded_frames'],
                'scene_candidates':len(scenes),'visual_semantics':'Scene and frame measurements plus reviewed contact samples; not verified semantic labels for every frame.',
                'motion_estimate_cadence':'phase correlation every native frame; sparse affine optical flow at up to 5 Hz'})
        audio_path=folder/'analysis-audio.wav'
        import av
        with av.open(str(path)) as container:has_audio=bool(container.streams.audio)
        if not has_audio:
            write_json(folder/'audio-analysis.json',{'duration':source['seconds'],'audio_available':False,
                'analysed_seconds':0,'note':'Original file contains no audio stream; no sound, voice or beat measurements can be recovered.'})
            print(f'No source audio stream {number}/{len(items)}',flush=True)
            continue
        if not audio_path.exists():
            import subprocess
            from imageio_ffmpeg import get_ffmpeg_exe
            subprocess.run([get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-nostdin','-threads','2','-i',str(path),
                '-vn','-ac','1','-ar','16000','-c:a','pcm_s16le',str(audio_path)],check=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if not (folder/'audio-analysis.json').exists():
            print(f"AUDIO MEASUREMENTS {number}/{len(items)}: {path.name}",flush=True)
            with wave.open(str(audio_path),'rb') as reader:audio=np.frombuffer(reader.readframes(reader.getnframes()),dtype='<i2').astype(np.float32)/32768
            metrics,audio_receipt=audio_features(audio)
            np.save(folder/'audio-features.npy',metrics.astype(np.float32));write_json(folder/'audio-analysis.json',audio_receipt)
            del metrics,audio;gc.collect()
        if speech and not (folder/'transcript.json').exists():
            print(f"SPEECH {number}/{len(items)}: {path.name}",flush=True)
            fast_transcript(path,folder,ROOT)
        print(f"Finished source measurements {number}/{len(items)}",flush=True)
    print(f'All {len(items)} source measurements complete.',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--speech',action='store_true')
    parser.add_argument('--base',type=Path,default=BASE)
    args=parser.parse_args();main(args.speech,args.base)
