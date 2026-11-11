"""Short NVENC VFR fixture for Reel Recreate; writes only under output/."""
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from hinglish_cut.media import prepare_media, probe

folder = root / 'output' / 'reel-recreate-gpu-validation'
folder.mkdir(parents=True, exist_ok=True)
ffmpeg = root / 'tools' / 'broll-ffmpeg' / 'ffmpeg.exe'
source = folder / 'vfr-fixture.mp4'
if not source.is_file():
    command = [str(ffmpeg), '-hide_banner', '-loglevel', 'error', '-y',
               '-f', 'lavfi', '-i', 'testsrc2=size=320x180:rate=30:duration=1.2',
               '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=1.2',
               '-vf', "select='not(eq(mod(n,5),0))'", '-fps_mode', 'vfr',
               '-c:v', 'h264_nvenc', '-preset', 'p5', '-cq', '25', '-b:v', '0',
               '-c:a', 'aac', '-shortest', str(source)]
    subprocess.run(command, check=True, capture_output=True, text=True, timeout=60)
try:
    probe(source)
except ValueError as error:
    assert 'variable frame rate or missing frames' in str(error) or 'unsupported frame rate' in str(error), str(error)
else:
    raise AssertionError('The test fixture was not variable-frame-rate footage.')
converted, note = prepare_media(source, folder / 'conformed', encoder='cuda')
assert note and 'auto_conformed' in note
assert float(converted.rate) == 30 and Path(converted.path).is_file()
assert converted.width == 320 and converted.height == 180
assert 'nvenc' in Path(converted.path).name
print(f'NVENC conformed VFR footage: {converted.width}x{converted.height}, {converted.rate} fps, {converted.duration:.2f}s')

source_24 = folder / '24fps-fixture.mp4'
if not source_24.is_file():
    command = [str(ffmpeg), '-hide_banner', '-loglevel', 'error', '-y',
               '-f', 'lavfi', '-i', 'testsrc2=size=320x180:rate=24:duration=1.2',
               '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=1.2',
               '-c:v', 'h264_nvenc', '-preset', 'p5', '-cq', '25', '-b:v', '0',
               '-c:a', 'aac', '-shortest', str(source_24)]
    subprocess.run(command, check=True, capture_output=True, text=True, timeout=60)
assert float(probe(source_24).rate) == 24
converted_24, note_24 = prepare_media(source_24, folder / 'conformed', encoder='cuda', require_30fps=True)
assert note_24 and float(converted_24.rate) == 30 and 'nvenc' in Path(converted_24.path).name
print('NVENC conformed a supported 24 fps source before caption analysis.')
