from pathlib import Path
import json,os,subprocess,time,sys
root=Path(__file__).resolve().parents[1];out=root/'output/gpu-routing-20261029';out.mkdir(exist_ok=True);sys.path.insert(0,str(root))
def run():
 import msvcrt
 from imageio_ffmpeg import get_ffmpeg_exe
 result={'main_service_restarted':False,'owner_apps_changed':False,'local_models_changed':False,'cpu_fallback':False}
 raw=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.used,memory.total,utilization.gpu','--format=csv,noheader,nounits'],text=True).strip();result['gpu']=raw
 lock=root/'cache/app/gpu-work.lock';lock.parent.mkdir(parents=True,exist_ok=True)
 with lock.open('a+b') as stream:
  stream.seek(0,2)
  if stream.tell()==0:stream.write(b'\0');stream.flush()
  stream.seek(0)
  try:msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
  except OSError:
   result['hardware_check']='waiting_for_existing_gpu_job';return result
  try:
   import av,numpy as np
   from fractions import Fraction
   from hinglish_cut.compute_policy import h264_profile,ffmpeg_h264
   codec,options=h264_profile('cuda',18);target=out/'nvenc-pyav.mp4';started=time.monotonic()
   with av.open(str(target),'w') as c:
    s=c.add_stream(codec,rate=30);s.width=256;s.height=144;s.pix_fmt='yuv420p';s.options=options
    for i in range(6):
     pixels=np.zeros((144,256,3),dtype=np.uint8);pixels[:,:,i%3]=100+i*20;frame=av.VideoFrame.from_ndarray(pixels,format='rgb24');frame.pts=i;frame.time_base=Fraction(1,30)
     for packet in s.encode(frame):c.mux(packet)
    for packet in s.encode():c.mux(packet)
   with av.open(str(target)) as c:result['pyav_frames']=sum(1 for _ in c.decode(video=0))
   args=[get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-y','-f','lavfi','-i','testsrc2=size=256x144:rate=30','-frames:v','6',*ffmpeg_h264('cuda',18),'-pix_fmt','yuv420p',str(out/'nvenc-ffmpeg.mp4')]
   completed=subprocess.run(args,capture_output=True,text=True,timeout=15,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
   if completed.returncode:raise RuntimeError(completed.stderr[-1500:])
   with av.open(str(out/'nvenc-ffmpeg.mp4')) as c:result['ffmpeg_frames']=sum(1 for _ in c.decode(video=0))
   assert result['pyav_frames']==result['ffmpeg_frames']==6
   result.update(hardware_check='actual_NVIDIA_NVENC_passed',elapsed_seconds=time.monotonic()-started,encoder=codec)
  finally:stream.seek(0);msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
 return result
if __name__=='__main__':
 try:result=run()
 except Exception as error:result={'hardware_check':'failed','details':str(error),'cpu_fallback':False}
 (out/'hardware-check.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
