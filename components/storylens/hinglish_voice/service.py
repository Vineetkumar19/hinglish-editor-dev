"""Durable voice profiles, duplicate-safe jobs, shared GPU scheduling and local exports."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import threading
import time
import uuid
from hinglish_app.durable_json import write
from hinglish_app.user_messages import failure
from hinglish_cut.gpu_lock import gpu_lock
from .audio import MAX_UPLOAD, reference, mp3, inspect_audio
from .runtime import ready, synthesize

ENGINE = 'VoiceStudio · OmniVoice'


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{32}', value):
        raise ValueError('Voiceover selection: choose a saved voice or generation from this workspace.')
    return value


class VoiceService:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.base = self.root/'output/voiceover'
        self.library = self.root/'library/voices'
        self.uploads = self.root/'cache/voiceover/uploads'
        self.lock = threading.RLock()
        for folder in (self.base, self.library, self.uploads): folder.mkdir(parents=True, exist_ok=True)
        for path in self.base.glob('*/job.json'):
            data = json.loads(path.read_text('utf-8'))
            import psutil
            if data.get('status') in ('queued','running') and not psutil.pid_exists(data.get('owner_pid',-1)):
                data.update(status='interrupted', stage='Storylens restarted. Your script is saved; select it from history to generate again.')
                write(path, data)

    def upload(self, name, content):
        if not isinstance(content, bytes) or not 0 < len(content) <= MAX_UPLOAD:
            raise ValueError('Voice sample: choose one recording up to 50 MB.')
        ext = Path(name).suffix.lower()
        if ext not in ('.wav','.mp3','.m4a','.flac','.ogg','.opus','.aac','.webm','.mp4','.mov'):
            raise ValueError('Voice sample: choose a WAV, MP3, M4A or video recording.')
        key = uuid.uuid4().hex
        folder = self.uploads/key
        folder.mkdir()
        source, target = folder/('original'+ext), folder/'reference.wav'
        source.write_bytes(content)
        try: duration = reference(source, target)
        except Exception:
            source.unlink(missing_ok=True)
            target.unlink(missing_ok=True)
            folder.rmdir()
            raise
        source.unlink()
        write(folder/'upload.json', dict(id=key, duration=duration, name=Path(name).name))
        return dict(id=key, duration=duration)

    def create_voice(self, payload):
        key = identifier(payload.get('upload_id'))
        name = str(payload.get('name','')).strip()
        transcript = str(payload.get('transcript','')).strip()
        if not name or len(name)>80: raise ValueError('Voice sample: enter a name up to 80 characters.')
        if not transcript or len(transcript)>4000: raise ValueError('Voice sample: paste the exact words spoken in the sample, up to 4,000 characters.')
        if payload.get('consent') is not True: raise ValueError('Voice sample: confirm that this is your voice or you have permission to use it.')
        with self.lock:
            folder = self.uploads/key
            if not (folder/'reference.wav').is_file(): raise ValueError('Voice sample: choose and upload the recording again.')
            data = json.loads((folder/'upload.json').read_text('utf-8'))
            # The upload ID is also the voice ID, making a lost-response retry safe.
            dest = self.library/key
            if (dest/'voice.json').is_file(): return self.voice(key)
            dest.mkdir(exist_ok=True)
            import shutil
            shutil.copyfile(folder/'reference.wav', dest/'reference.wav')
            result = dict(id=key, name=name, transcript=transcript, duration=data['duration'], created_at=time.time(), consent=True,
                          reference_sha256=hashlib.sha256((dest/'reference.wav').read_bytes()).hexdigest(), engine=ENGINE)
            write(dest/'voice.json', result)
            return result

    def voices(self):
        return sorted((json.loads(p.read_text('utf-8')) for p in self.library.glob('*/voice.json')), key=lambda r:r['created_at'], reverse=True)

    def voice(self, key):
        path = self.library/identifier(key)/'voice.json'
        if not path.is_file(): raise ValueError('Voiceover selection: choose a saved voice first.')
        return json.loads(path.read_text('utf-8'))

    def start(self, payload):
        voice = self.voice(payload.get('voice_id'))
        script = payload.get('script')
        if not isinstance(script,str) or not script.strip() or len(script)>20000:
            raise ValueError('Voiceover script: paste your script, up to 20,000 characters.')
        language = payload.get('language','auto')
        if language not in ('auto','en','hi'): raise ValueError('Voiceover settings: select Auto, English or Hindi.')
        try: speed = float(payload.get('speed',1))
        except (ValueError,TypeError): raise ValueError('Voiceover settings: set speed between 0.7 and 1.3.') from None
        if not math.isfinite(speed) or not .7<=speed<=1.3: raise ValueError('Voiceover settings: set speed between 0.7 and 1.3.')
        key = identifier(payload.get('request_id') or uuid.uuid4().hex)
        request = dict(voice_id=voice['id'], script=script, language=language, speed=speed)
        signature = hashlib.sha256(json.dumps(request,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
        with self.lock:
            path = self.base/key/'job.json'
            if path.exists():
                old = self.job(key)
                if old['signature']!=signature: raise ValueError('Voiceover request: the script changed. Start a new generation.')
                return old
            path.parent.mkdir()
            result = dict(id=key, **request, voice_name=voice['name'], status='queued', stage='Waiting for the shared GPU queue.',
                          signature=signature, engine=ENGINE, created_at=time.time(), owner_pid=os.getpid())
            write(path, result)
            self._launch(key)
            return result

    def _launch(self, key):
        threading.Thread(target=self.run, args=(key,), daemon=True, name='voiceover-'+key[:8]).start()

    def _update(self, key, **values):
        with self.lock:
            data = self.job(key)
            data.update(values)
            write(self.base/key/'job.json', data)
            return data

    def run(self, key):
        started = time.monotonic()
        try:
            with gpu_lock(self.root):
                from hinglish_cut.model_preferences import release_ollama
                release_ollama(self.root)
                data = self._update(key,status='running',stage='Preparing pronunciation and generating your narration locally. Longer scripts take more time.')
                voice = self.voice(data['voice_id'])
                ref = self.library/voice['id']/'reference.wav'
                if hashlib.sha256(ref.read_bytes()).hexdigest()!=voice['reference_sha256']:
                    raise ValueError('Voice sample: the saved recording changed. Save the original sample again.')
                request = dict(data,root=str(self.root),reference=str(ref),transcript=voice['transcript'])
                folder = self.base/key
                synthesize(request, folder/'narration.wav', folder/'technical.log')
                self._update(key, stage='Checking audio and preparing MP3.')
                duration = inspect_audio(folder/'narration.wav')
                mp3(folder/'narration.wav', folder/'narration.mp3')
                inspect_audio(folder/'narration.mp3')
                self._update(key,status='complete',stage='Your voiceover is ready.',duration=duration,
                             elapsed_seconds=round(time.monotonic()-started,2),completed_at=time.time())
        except Exception as error:
            self._update(key,status='failed',stage='Voiceover could not finish. Your script and voice sample are saved.',
                         elapsed_seconds=round(time.monotonic()-started,2),**failure(error,feature='Voiceover'))

    def job(self, key):
        path = self.base/identifier(key)/'job.json'
        if not path.is_file(): raise ValueError('Voiceover selection: choose a saved generation.')
        return json.loads(path.read_text('utf-8'))

    def history(self):
        return sorted((json.loads(p.read_text('utf-8')) for p in self.base.glob('*/job.json')), key=lambda r:r['created_at'], reverse=True)

    def file(self, key, kind):
        if kind not in ('mp3','wav'): raise ValueError('Voiceover download: select MP3 or WAV.')
        data = self.job(key)
        if data['status']!='complete': raise ValueError('Voiceover download: wait for this generation to finish.')
        return self.base/identifier(key)/('narration.'+kind)

    def status(self):
        return dict(engine=ENGINE, ready=ready(self.root), voices=self.voices(), jobs=self.history())


_services = {}
_lock = threading.Lock()
def service(root):
    with _lock:
        key = str(Path(root).resolve())
        if key not in _services: _services[key] = VoiceService(root)
        return _services[key]
