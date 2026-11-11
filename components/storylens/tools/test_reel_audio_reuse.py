"""The Reel speech path must reuse its existing analysis WAV."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
import json
import sys

workspace = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(workspace))
from hinglish_cut.media import probe
from hinglish_cut.model import Settings
from hinglish_semantic.analysis import transcribe_media

saved = workspace / 'output' / 'reel-recreate' / 'dfb55ed4995b4f80bc58766a2b9bf6db'
plan = json.loads((saved / 'reel-plan.json').read_text('utf-8'))
media = probe(plan['audio'])
audio = saved / 'analysis-audio.wav'
settings = SimpleNamespace(speech_settings=lambda: Settings(device='cuda', cpu_threads=1),
                           device='cuda', cpu_threads=1, speech_backend='swift')
with TemporaryDirectory(dir=workspace / 'output') as temporary:
    with patch('hinglish_cut.model_storage.signature', return_value='test-model'), \
         patch('hinglish_semantic.analysis.detect_blocks', return_value=[]), \
         patch('hinglish_semantic.analysis.extract_audio', side_effect=AssertionError('MP4 audio was decoded twice')):
        _, reused = transcribe_media(media, 'reel-audio-reuse-fixture', temporary, settings,
                                     progress=lambda _: None, predecoded_audio=audio)
    assert reused.is_file() and reused.stat().st_size == audio.stat().st_size
print('Speech analysis reused the prepared Reel WAV without another MP4 audio decode.')
