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
            from .setup_meaning import load_manifest
            manifest=load_manifest(self.root)
            self.turbo = WhisperModel(manifest['speech_path'], device=self.settings.device,
                                      compute_type='int8' if self.settings.device == 'cpu' else 'float16',
                                      cpu_threads=self.settings.cpu_threads, local_files_only=True)
        segments, _ = self.turbo.transcribe(audio, language='hi', task='transcribe', beam_size=5,
                                            condition_on_previous_text=False, vad_filter=False,
                                            temperature=0, word_timestamps=False)
        from hinglish_cut.recognition_quality import checked_transcript
        return checked_transcript(' '.join(s.text.strip() for s in segments if s.text.strip()))

    def close(self):
        self.turbo = None
        super().close()


def speech_engine(settings, root):
    if settings.speech_backend == 'turbo': return TurboSpeech(settings, root)
    return LocalSpeech(settings.speech_settings(), Path(root) / 'models')
