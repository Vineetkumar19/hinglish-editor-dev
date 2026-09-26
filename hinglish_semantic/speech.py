"""Independent multilingual transcription; the script is never an ASR prompt."""
import json
from pathlib import Path
from hinglish_cut.backends import LocalSpeech


class TurboSpeech(LocalSpeech):
    def __init__(self, settings, root):
        super().__init__(settings.speech_settings(), Path(root) / 'models')
        self.root = Path(root)
        self.turbo = None

    def recognize(self, audio):
        if len(audio) < 1600: return ''
        if self.turbo is None:
            from faster_whisper import WhisperModel
            file = self.root / 'models/meaning-upgrade.json'
            if not file.exists(): file = self.root / 'models/meaning-models.json'
            manifest = json.loads(file.read_text(encoding='utf-8'))
            self.turbo = WhisperModel(manifest['speech_path'], device=self.settings.device,
                                      compute_type='int8' if self.settings.device == 'cpu' else 'float16',
                                      cpu_threads=self.settings.cpu_threads, local_files_only=True)
        segments, _ = self.turbo.transcribe(audio, language='hi', task='transcribe', beam_size=5,
                                            condition_on_previous_text=False, vad_filter=False,
                                            temperature=0, word_timestamps=False)
        return ' '.join(s.text.strip() for s in segments if s.text.strip())

    def close(self):
        self.turbo = None
        super().close()


def speech_engine(settings, root):
    if settings.speech_backend == 'turbo': return TurboSpeech(settings, root)
    return LocalSpeech(settings.speech_settings(), Path(root) / 'models')
