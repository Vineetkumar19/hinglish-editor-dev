"""Check the AE caption path does not render the CPU-only overlay video."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import shutil
import sys

workspace = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(workspace))
from hinglish_captions.core import CaptionCue, CaptionWord
from hinglish_captions.pipeline import run

fixture = workspace / 'output' / 'reel-recreate-gpu-validation' / 'conformed'
source = next(fixture.glob('*-nvenc-30fps.mp4'))
words = (CaptionWord('Hello', 0.1, 0.45), CaptionWord('world', 0.45, 0.9))
cue = CaptionCue(words, 0.1, 0.9)
with TemporaryDirectory(dir=workspace / 'output') as temporary:
    root = Path(temporary)
    shutil.copyfile(workspace / 'config.phase2.json', root / 'config.phase2.json')
    with patch('hinglish_captions.lyrics.transcribe_song', return_value=([cue], {'mode':'lyrics','device':'cuda'})), \
         patch('hinglish_captions.pipeline.render_overlay', side_effect=AssertionError('CPU overlay render was called')), \
         patch('hinglish_captions.pipeline.export_caption_xml', side_effect=AssertionError('Premiere XML was called')):
        output = run(root, source, style='caption_2', device='cuda',
                     caption_content='lyrics', editable_only=True, progress=lambda _: None)
    projects = list(output.rglob('caption-project.json'))
    assert len(projects) == 1
    assert not list(output.rglob('premium-captions.mov'))
    assert not list(output.rglob('CAPTIONED_SEQUENCE.xml'))
print('Editable Reel captions saved without a CPU overlay render or Premiere XML.')
