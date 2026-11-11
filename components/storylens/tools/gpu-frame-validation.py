"""Real small CUDA checks; queue behind existing work without touching owner apps."""
from pathlib import Path
import json, os, sys, time, traceback
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
out=root/'output/gpu-routing-20261029/frame-validation';out.mkdir(parents=True,exist_ok=True)


def save(value):
    (out/'status.json').write_text(json.dumps(value,indent=2),encoding='utf8')


def check():
    import msvcrt
    start=time.monotonic()
    lock=root/'cache/app/gpu-work.lock'
    with lock.open('a+b') as stream:
        while True:
            stream.seek(0)
            try:msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1);break
            except OSError:
                save({'status':'waiting_for_existing_gpu_job','owner_apps_changed':False})
                if time.monotonic()-start>=180:return
                time.sleep(2)
        try:
            save({'status':'checking_actual_cuda','owner_apps_changed':False})
            import numpy as np, av, threading, wave
            from fractions import Fraction
            from hinglish_cut.gpu_frames import CudaFrames
            gpu=CudaFrames()
            try:
                raw=np.zeros((48,64,3),np.uint8);raw[:,:32]=[255,0,0];raw[:,32:]=[0,255,0]
                tensor=gpu.upload(raw)
                identity=gpu.download(gpu.crop(tensor,(0,0,64,48),64,48))
                assert np.abs(identity.astype(int)-raw).max()<=1,'identity crop'
                fit=gpu.download(gpu.fit(tensor,80,80))
                assert fit[0].max()==0 and fit[-1].max()==0,'letterbox boundaries'
                rgba=np.zeros((48,64,4),np.uint8);rgba[:,:,:3]=[0,0,255];rgba[:,:,3]=128
                blend=gpu.download(gpu.over(tensor,gpu.upload(rgba)))
                assert np.abs(blend[20,20].astype(int)-[127,0,128]).max()<=1,'alpha blend'
                frame=gpu.video_frame(tensor)
                roundtrip=frame.to_ndarray(format='rgb24')
                assert np.abs(roundtrip[20,20].astype(int)-[255,0,0]).max()<=3,'GPU YUV red'
                assert np.abs(roundtrip[20,50].astype(int)-[0,255,0]).max()<=3,'GPU YUV green'
                peak=np.zeros((48,64,3),np.uint8);peak[24,32]=255
                assert 0<gpu.download(gpu.blur(gpu.upload(peak),2)).max()<255,'CUDA blur'
            finally:gpu.close()
            # Real NVENC file, silence and two separated cuts. No model is loaded.
            from hinglish_shorts.render import _Video,Composer
            gpu=CudaFrames()
            writer=_Video(out/'source.mp4',256,144,Fraction(30),'h264_nvenc',audio=True)
            try:
                raw=np.zeros((144,256,3),np.uint8);raw[:,:128]=[220,20,30];raw[:,128:]=[20,210,30]
                for n in range(12):
                    writer.write_gpu(gpu.upload(raw),gpu);writer.write_audio(np.zeros((2,1600),np.float32))
                writer.finish()
                with av.open(str(out/'source.mp4')) as source:
                    frame=next(source.decode(video=0))
                    for look in ('face','template'):
                        composer=Composer(look,256,144,gpu=gpu)
                        composed,bg=composer.compose(frame)
                        assert composed.is_cuda and composed.shape[-2:]==(1920,1080)
                        if look=='template':assert bg.is_cuda and bg.shape[-2:]==(960,540)
                        # One small actual image of each GPU layout, never owner footage.
                        from PIL import Image
                        Image.fromarray(gpu.download(gpu.resize(composed,270,480))).save(out/f'{look}.png')
                        del composer,composed,bg
            finally:gpu.close()
            from hinglish_cut.media import probe
            from hinglish_cut.model import Cut
            from hinglish_clean.render import render_mp4
            from hinglish_semantic.preview import render_preview
            media=probe(out/'source.mp4');cuts=[Cut(media.id,1,5,0),Cut(media.id,7,11,1)]
            facts=render_mp4(media,cuts,out/'clean.mp4',canvas=(256,256),progress=lambda _:None,device='cuda')
            assert facts['video_frames']==8 and facts['audio_samples']==12800
            with wave.open(str(out/'speech.wav'),'wb') as wav:
                wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(16000);wav.writeframes(b'\0\0'*16000)
            preview=render_preview(cuts,{media.id:media},out/'speech.wav',out/'semantic.mp4',(256,256),progress=lambda _:None,device='cuda')
            assert preview['frames']==8
            from hinglish_cinematic.render import render_cuda_shot
            plan={'fps':'30','beat_frames':[0,4]}
            shot={'source_in':0.,'speed':1.,'path':str(out/'source.mp4'),'start_frame':0,'end_frame':8,'duration_frames':8}
            render_cuda_shot(plan,shot,out/'cinematic.mp4',256,144,'fill',['punch','flash','shake'],8,threading.Event())
            counts={}
            for name in ('clean','semantic','cinematic'):
                with av.open(str(out/f'{name}.mp4')) as movie:
                    frames=list(movie.decode(video=0));counts[name]=len(frames)
                    assert len(frames)==8 and float(frames[0].time)==0
            from hinglish_visuals.render import still_clip,video_clip
            from PIL import Image
            Image.new('RGB',(96,160),(30,100,220)).save(out/'portrait.png')
            still_clip(out/'portrait.png',8/30,256,144,30,out/'visual-still.mp4',device='cuda')
            video_clip(out/'source.mp4',0,8/30,256,144,30,out/'visual-video.mp4',device='cuda')
            # A tiny CPU-coded alpha fixture only; the actual composition is CUDA.
            overlay=np.zeros((144,256,4),np.uint8);overlay[100:130,20:236]=[255,220,0,220]
            alpha=_Video(out/'alpha-fixture.mov',256,144,Fraction(30),'qtrle')
            for i in range(8):alpha.write(overlay,fmt='rgba')
            alpha.finish()
            from hinglish_captions.export_video import render_captioned_video
            assert render_captioned_video(out/'source.mp4',out/'alpha-fixture.mov',out/'caption-composite.mp4',device='cuda')=='h264_nvenc'
            from hinglish_shorts.source import open_video
            from hinglish_shorts.render import render_short,template_overlay
            from hinglish_shorts.xml import export_short_xml
            source=open_video(out/'source.mp4')
            art=template_overlay('GPU frame check','@test','WATCH FULL VIDEO ON',source.width,source.height)
            fact=render_short(source,[(0,8/30)],'template',out/'short.mp4',out/'assets',1,art,device='cuda',progress=lambda _:None)
            assert Path(fact['layers']['overlay']).suffix=='.png'
            export_short_xml(out/'short.xml','GPU check',source,fact['frames'],'template',fact['layers'])
            for name in ('visual-still','visual-video','caption-composite','short'):
                with av.open(str(out/f'{name}.mp4')) as movie:
                    counts[name]=sum(1 for _ in movie.decode(video=0));assert counts[name]==8
            save({'status':'actual_cuda_passed','gpu':gpu.torch.cuda.get_device_name(0),'encoder':'h264_nvenc',
                  'checks':['identity crop','black letterboxing','alpha compositing','YUV colors','blur','Shorts face/template layouts and finished video','Smart Clean exact cuts/audio','Script Edit preview','Cinematic beat effects','Smart Visuals still/video GPU frames','Caption GPU composite with original audio','Static PNG editable XML'],
                  'frames':counts,'elapsed_seconds':round(time.monotonic()-start,2),'owner_apps_changed':False,'models_loaded':False,'cpu_fallback':False})
        finally:
            stream.seek(0);msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)


if __name__=='__main__':
    try:check()
    except BaseException as error:
        save({'status':'failed','error':str(error),'details':traceback.format_exc(),'cpu_fallback':False})
        raise
    print((out/'status.json').read_text())
