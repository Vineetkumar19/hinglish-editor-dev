"""Downloader contract tests, written before implementation."""
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import xml.etree.ElementTree as ET

from hinglish_app.downloader import DownloadService, validate_request, format_selector, export_timeline

class DownloaderUnitTests(unittest.TestCase):
    def test_supported_platform_urls(self):
        cases={'https://youtu.be/abc123':'youtube','https://www.youtube.com/shorts/abc':'youtube',
               'https://www.instagram.com/reel/abc/':'instagram','https://www.pinterest.com/pin/123/':'pinterest',
               'https://pin.it/abc':'pinterest'}
        for url,platform in cases.items():
            with self.subTest(url=url):self.assertEqual(validate_request({'url':url})['platform'],platform)
    def test_reject_unsafe_or_nonvideo_urls(self):
        for url in ['file:///etc/passwd','http://127.0.0.1/a','https://youtube.com.evil.org/watch?v=a',
                    'https://user:password@youtube.com/watch?v=a','https://youtube.com:8443/watch?v=a',
                    'https://youtube.com/playlist?list=abc','https://instagram.com/someone/',
                    'https://pinterest.com/username/board/','https://youtube.com/redirect?q=http://localhost',
                    'https://youtube.com/watch?v=a\n--exec=bad']:
            with self.subTest(url=url),self.assertRaises(ValueError):validate_request({'url':url})
    def test_options_and_caps_are_strict(self):
        for quality in ['best','2160','1440','1080','720']:
            self.assertEqual(validate_request({'url':'https://youtu.be/abc','quality':quality})['quality'],quality)
        for args in [{'quality':'9999'},{'mode':'shell'},{'url':['oops']},{'audio_format':'exe'}]:
            with self.subTest(args=args),self.assertRaises(ValueError):validate_request({'url':'https://youtu.be/abc',**args})
        self.assertEqual(validate_request({'url':'https://instagram.com/reel/a','quality':'720'})['quality'],'best')
    def test_video_cap_has_no_uncapped_fallback(self):
        for height in [720,1080,1440,2160]:
            selector=format_selector(str(height),'video')
            self.assertTrue(all('height<='+str(height) in choice for choice in selector.split('/')))
        self.assertIn('bestaudio',format_selector('best','audio'))
    def test_invalid_start_does_not_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            service=DownloadService(tmp)
            try:
                with self.assertRaises(ValueError):service.start({'url':'http://localhost/video'})
                self.assertEqual(service.history(),[])
            finally:service.close()
    def test_paths_are_isolated_and_ids_are_validated(self):
        with tempfile.TemporaryDirectory() as tmp:
            service=DownloadService(tmp)
            try:
                for bad in ['../private','missing','a'*31,'a'*33]:
                    with self.assertRaises(ValueError):service.snapshot(bad)
                with self.assertRaises(ValueError):service.media('a'*32,'../../secret')
            finally:service.close()
    def test_transfer_checks_metadata_before_downloading_single_video(self):
        from threading import Event
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);service=DownloadService(folder);calls=[];metadata={'title':'One clip','duration':1}
            class FakeDL:
                def __init__(self,options):calls.append(('options',options))
                def __enter__(self):return self
                def __exit__(self,*args):pass
                def extract_info(self,url,download):calls.append(('extract',download));return metadata
                def process_ie_result(self,info,download):
                    calls.append(('process',download));(folder/'source.mp4').write_bytes(b'clip');return info
            try:
                with patch('yt_dlp.YoutubeDL',FakeDL):
                    path,meta=service.transfer(validate_request({'url':'https://youtu.be/a'}),folder,lambda *a:None,Event())
                    self.assertNotIn('max_downloads',calls[0][1])
                    self.assertIn(('extract',False),calls);self.assertIn(('process',True),calls)
                    self.assertEqual(path.name,'source.mp4')
                    calls.clear();metadata={'_type':'playlist','entries':[{}]}
                    with self.assertRaises(ValueError):service.transfer(validate_request({'url':'https://youtu.be/a'}),folder,lambda *a:None,Event())
                    self.assertNotIn(('process',True),calls)
            finally:service.close()
    def test_downloader_errors_do_not_relabel_other_features(self):
        from hinglish_app.user_messages import problem
        download=problem(RuntimeError('HTTP Error 403: forbidden'),feature='Downloader')
        other=problem(RuntimeError('HTTP Error 403: forbidden'),feature='Publishing')
        self.assertEqual(download['code'],'download_site_blocked')
        self.assertNotEqual(other['code'],'download_site_blocked')
    def test_xml_audio_has_no_phantom_video_clip(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);audio=p/'source.wav';audio.write_bytes(b'fixture')
            result=export_timeline(audio,{'duration':2,'fps':'30','width':0,'height':0,'channels':2,'sample_rate':48000},'audio')
            tree=ET.parse(result)
            self.assertFalse(tree.findall('.//sequence/media/video/track/clipitem'))
            self.assertEqual(len(tree.findall('.//sequence/media/audio/track/clipitem')),2)
            self.assertIn('source.wav',tree.findtext('.//file/pathurl'))

class DownloaderPipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        from tests.test_cinematic import make_shot,make_music
        self.clip=self.root/'clip.mp4';silent=self.root/'silent.mp4';music=self.root/'music.wav'
        make_shot(silent,seconds=1);make_music(music,seconds=1)
        import subprocess,imageio_ffmpeg
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-i',str(silent),'-i',str(music),'-c:v','copy','-c:a','aac','-shortest',str(self.clip)],check=True,capture_output=True)
        self.service=DownloadService(self.root)
    def tearDown(self):self.service.close();self.tmp.cleanup()
    def wait(self,job):
        deadline=time.monotonic()+20
        while job['status'] in ('queued','running') and time.monotonic()<deadline:
            time.sleep(.03);job=self.service.snapshot(job['id'])
        return job
    def transfer(self,request,folder,progress,cancel):
        import shutil
        dest=folder/'source.mp4';shutil.copy2(self.clip,dest)
        progress('Downloading',50)
        return dest,{'title':'Test <clip>','height':180,'width':320,'duration':1}
    def test_real_media_processing_both_outputs_persistence_and_catalog(self):
        from hinglish_app.editor_handoff import catalog
        with patch.object(self.service,'transfer',side_effect=self.transfer):
            job=self.wait(self.service.start({'url':'https://youtu.be/test','mode':'both','quality':'720'}))
        self.assertEqual(job['status'],'complete',job)
        self.assertEqual(set(job['result']['assets']),{'video','audio'})
        self.assertEqual(job['result']['assets']['video']['height'],180)
        for kind,asset in job['result']['assets'].items():
            self.assertTrue(Path(asset['path']).is_file())
            self.assertTrue(Path(asset['xml_files'][0]).is_file())
            self.assertIn(str(Path(asset['path']).resolve()),catalog(self.root,asset['folder'])['videos'])
        reloaded=DownloadService(self.root)
        try:self.assertEqual(reloaded.snapshot(job['id'])['status'],'complete')
        finally:reloaded.close()
        import av
        with av.open(job['result']['assets']['audio']['path']) as container:
            self.assertFalse(container.streams.video);self.assertEqual(container.streams.audio[0].sample_rate,48000)
    def test_failure_is_plain_language_with_technical_evidence(self):
        with patch.object(self.service,'transfer',side_effect=RuntimeError('HTTP Error 403: forbidden')):
            job=self.wait(self.service.start({'url':'https://youtu.be/test'}))
        self.assertEqual(job['status'],'failed');self.assertTrue(job['error']['message']);self.assertIn('403',job['error']['details'])
    def test_missing_audio_is_reported_and_video_preserved(self):
        from tests.test_cinematic import make_shot
        make_shot(self.clip,seconds=1)
        with patch.object(self.service,'transfer',side_effect=self.transfer):
            job=self.wait(self.service.start({'url':'https://youtu.be/test','mode':'both'}))
        self.assertEqual(job['status'],'failed',job)
        self.assertTrue(list((self.root/'output/downloads'/job['id']).rglob('*.mp4')))
    def test_audio_only_mp3_is_independent_of_video(self):
        import shutil
        def audio_transfer(request,folder,progress,cancel):
            dest=folder/'source.wav';shutil.copy2(self.root/'music.wav',dest);return dest,{'title':'Audio test'}
        with patch.object(self.service,'transfer',side_effect=audio_transfer):
            job=self.wait(self.service.start({'url':'https://youtu.be/audio','mode':'audio','audio_format':'mp3'}))
        self.assertEqual(job['status'],'complete',job)
        self.assertEqual(set(job['result']['assets']),{'audio'})
        self.assertTrue(job['result']['assets']['audio']['path'].endswith('.mp3'))
    def test_cancel_stops_the_job_and_another_link_can_wait(self):
        import threading
        entered=threading.Event()
        def waiting(request,folder,progress,cancel):
            entered.set();cancel.wait(3);raise ValueError('Cancelled')
        with patch.object(self.service,'transfer',side_effect=waiting):
            job=self.service.start({'url':'https://youtu.be/test'})
            self.assertTrue(entered.wait(2))
            queued=self.service.start({'url':'https://youtu.be/other'})
            self.assertEqual(queued['status'],'queued')
            self.service.cancel(queued['id'])
            self.service.cancel(job['id']);job=self.wait(job)
        self.assertEqual(job['status'],'cancelled')
    def test_audio_capcut_project_has_audio_material_and_track(self):
        from hinglish_app.capcut_adapter import create_project
        import shutil
        path=self.root/'output/audio.wav';path.parent.mkdir(exist_ok=True);shutil.copy2(self.root/'music.wav',path)
        (self.root/'config.editors.local.json').write_text(json.dumps({'capcut_home':str(self.root/'CapCut')}),encoding='utf-8')
        project=create_project(self.root,path,'Downloaded audio','test-audio')
        draft=json.loads((Path(project['folder'])/'draft_content.json').read_text(encoding='utf-8'))
        self.assertEqual(draft['tracks'][0]['type'],'audio')
        self.assertEqual(len(draft['materials']['audios']),1)
        self.assertFalse(draft['materials']['videos'])

if __name__=='__main__':unittest.main()
