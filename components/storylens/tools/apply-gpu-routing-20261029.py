from pathlib import Path
root=Path.cwd()
def edit(name,old,new):
 p=root/name;s=p.read_text(encoding='utf-8-sig')
 if old not in s and new in s:return
 assert old in s,(name,old[:90])
 p.write_text(s.replace(old,new,1),encoding='utf-8')
edit('tests/test_compute_policy.py','with tempfile.TemporaryDirectory() as folder:',"with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as folder:")
edit('hinglish_app/assistant_media.py','def render_xml(xml, target, progress=print):',"def render_xml(xml, target, progress=print, *, device='cpu'):")
edit('hinglish_app/assistant_media.py','max_side=max(seq.width, seq.height), progress=progress, audio=audio)', 'max_side=max(seq.width, seq.height), progress=progress, audio=audio,device=device)')
edit('hinglish_app/assistant_media.py',"render_xml(xml, folder / f'{tool}-{n:03d}.mp4', progress)","render_xml(xml, folder / f'{tool}-{n:03d}.mp4', progress,device=__import__('hinglish_cut.model_preferences',fromlist=['preferred_device']).preferred_device(root))")
# Joining has no project-root parameter; the caller controls its explicit compute choice.
edit('hinglish_app/assistant_media.py',"def join_videos(paths, folder, progress=print):", "def join_videos(paths, folder, progress=print, *, device='cpu'):")
edit('hinglish_app/assistant_media.py',"return render_xml(xml, folder / 'joined-video.mp4', progress)", "return render_xml(xml, folder / 'joined-video.mp4', progress,device=device)")
edit('hinglish_app/assistant_media.py','def transcribe_voice(root, path):','def transcribe_voice(root, path, progress=print):')
edit('hinglish_app/assistant.py',"transcribe_voice(self.root, attachments[voice_id]['path'])", "transcribe_voice(self.root, attachments[voice_id]['path'],progress=progress)")
edit('hinglish_semantic/preview.py',"def render_preview(cuts, media, audio_path, destination, canvas, progress=print):", "def render_preview(cuts, media, audio_path, destination, canvas, progress=print, *, device='cpu'):")
edit('hinglish_semantic/preview.py',"video = output.add_stream('libx264', rate=fps)","from hinglish_cut.compute_policy import h264_profile\n        codec, options=h264_profile(device,23)\n        video = output.add_stream(codec, rate=fps)")
edit('hinglish_semantic/preview.py',"video.options = {'crf': '23', 'preset': 'fast'}",'video.options = options')
edit('hinglish_semantic/paragraph_export.py',"output / 'preview.mp4', canvas, progress)","output / 'preview.mp4', canvas, progress,device=settings.device)")
edit('hinglish_sound/pipeline.py',"progress=lambda _: None, audio=mixed['master'])", "progress=lambda _: None, audio=mixed['master'],device=settings.device)")
edit('hinglish_captions/auto_caption.py','def render_preview(folder,cues,settings,colors,progress):',"def render_preview(folder,cues,settings,colors,progress,device='cpu'):")
edit('hinglish_captions/auto_caption.py',"stream=container.add_stream('libx264',rate=30);stream.width=w;stream.height=h;stream.pix_fmt='yuv420p';stream.options={'crf':'24','preset':'fast'};stream.thread_count=2", "from hinglish_cut.compute_policy import h264_profile\n        codec,options=h264_profile(device,24)\n        stream=container.add_stream(codec,rate=30);stream.width=w;stream.height=h;stream.pix_fmt='yuv420p';stream.options=options;stream.thread_count=2")
edit('hinglish_captions/auto_caption.py','output=render_preview(project_folder,cues,settings,colors,progress)',"with gpu_lock(root):\n                from hinglish_cut.model_preferences import preferred_device\n                output=render_preview(project_folder,cues,settings,colors,progress,device=preferred_device(root))")
# CPU image generation/alpha formats remain unchanged; only H.264 encoding changes.
edit('hinglish_captions/script_preview.py','from imageio_ffmpeg import get_ffmpeg_exe\n    result=',"from imageio_ffmpeg import get_ffmpeg_exe\n    from hinglish_cut.compute_policy import ffmpeg_h264\n    from hinglish_cut.model_preferences import preferred_device\n    encoder=ffmpeg_h264(preferred_device(root),28)\n    result=")
edit('hinglish_captions/script_preview.py',"'-t',str(duration),'-c:v','libx264','-threads','2',\n        '-preset','ultrafast','-crf','28',", "'-t',str(duration),*encoder,'-threads','2',")
edit('hinglish_app/downloader.py',"else ['-c:v','libx264','-crf','16','-preset','fast','-pix_fmt','yuv420p','-threads','4']", "else [*__import__('hinglish_cut.compute_policy',fromlist=['ffmpeg_h264']).ffmpeg_h264(__import__('hinglish_cut.model_preferences',fromlist=['preferred_device']).preferred_device(self.root),16),'-pix_fmt','yuv420p','-threads','2']")
edit('hinglish_app/downloader.py','    def _ffmpeg(self, args, cancel):\n', '''    def _ffmpeg(self,args,cancel):
        from contextlib import nullcontext
        from hinglish_cut.gpu_lock import gpu_lock
        with gpu_lock(self.root) if 'h264_nvenc' in args else nullcontext():
            return self._ffmpeg_unlocked(args,cancel)

    def _ffmpeg_unlocked(self, args, cancel):
''')
edit('hinglish_cinematic/service.py','            with self.work_lock:', '            from hinglish_cut.gpu_lock import gpu_lock\n            from hinglish_cut.model_preferences import preferred_device\n            with self.work_lock,gpu_lock(self.root):\n                payload[\'device\']=preferred_device(self.root)')
edit('hinglish_cinematic/render.py',"'-r',plan['fps'],'-c:v','libx264','-threads','2','-preset','fast','-crf','18',", "'-r',plan['fps'],*__import__('hinglish_cut.compute_policy',fromlist=['ffmpeg_h264']).ffmpeg_h264(options.get('device','cpu'),18),'-threads','2',")
print('GPU encoding and queued speech callers updated.')
