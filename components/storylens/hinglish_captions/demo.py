"""Prepare editable caption samples without uploads or speech recognition.

Run ``python -m hinglish_captions.demo`` when installing caption templates.
Preparing samples again preserves each template's saved edits and exports.
"""
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess

from hinglish_cut.model import Media
from .core import CaptionWord, build_cues
from .project import write_project, cues_from_data
from .report import write_report
from .styles import SELECTABLE_TEMPLATES, template
from .subtitles import write_ass, write_srt

DURATION = 30.0
SCRIPT = (
    "Imagine a monument that changes with the light. "
    "The Taj Mahal stands beside the Yamuna River in Agra. "
    "Its white marble glows softly at sunrise and shines beneath the moon. "
    "Look closer at the carved flowers, the balanced gardens, and the reflections in the water. "
    "Every detail invites you to slow down. "
    "Some places are more than buildings. They become stories that the world remembers."
)


def sample_cues():
    tokens = SCRIPT.split()
    step = DURATION / len(tokens)
    words = [CaptionWord(text, round(i * step, 4), round((i + 1) * step, 4))
             for i, text in enumerate(tokens)]
    cues = build_cues(words)
    # Editable projects require disjoint cue intervals. build_cues adds a small
    # reading hold, which must stop before the following sample phrase starts.
    return [replace(cue, end=min(cue.end, cues[i + 1].start if i + 1 < len(cues) else DURATION))
            for i, cue in enumerate(cues)]


def caption_one_sample_cues():
    """Taj Mahal words timed from the bundled narration, never evenly spaced."""
    from .core import CaptionCue
    timing=json.loads(Path(__file__).with_name('caption_one_taj_words.json').read_text('utf-8'))
    words=[CaptionWord(w['text'],w['start'],w['end']) for w in timing['words']]
    from .caption_one import profile,paginate_cues
    groups=[];cursor=0
    for recipe in profile()['demo_phrases']:
        count=len(recipe['text'].split());group=tuple(words[cursor:cursor+count]);cursor+=count
        if ' '.join(w.text for w in group)!=recipe['text']:raise ValueError('Taj Mahal narration and caption phrases differ')
        groups.append(group)
    if cursor!=len(words):raise ValueError('Taj Mahal caption phrases must keep every narration word')
    return paginate_cues([CaptionCue(group,group[0].start,groups[i+1][0].start if i+1<len(groups) else DURATION) for i,group in enumerate(groups)])


def ensure_caption_one_background(path):
    """Create Caption 1's own 60 fps black media with the timed demo voice."""
    path=Path(path)
    if path.is_file():return path
    from imageio_ffmpeg import get_ffmpeg_exe
    narration=Path(__file__).parent/'demo_media/caption1-taj.wav'
    path.parent.mkdir(parents=True,exist_ok=True)
    partial=path.with_name(path.stem+'.partial.mp4')
    result=subprocess.run([get_ffmpeg_exe(),'-nostdin','-hide_banner','-v','error','-y',
        '-f','lavfi','-i','color=c=black:s=720x1280:r=60','-i',str(narration),
        '-t',str(DURATION),'-c:v','libx264','-preset','ultrafast','-crf','28',
        '-pix_fmt','yuv420p','-c:a','aac','-ar','48000','-ac','2','-movflags','+faststart',str(partial)],
        capture_output=True,text=True,encoding='utf-8',errors='replace',
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode:raise RuntimeError('Could not prepare the narrated Caption 1 demo: '+result.stderr[-1500:])
    partial.replace(path)
    return path


def ensure_solid_demo_background(folder, source, color):
    """Replace only a sample's video pixels; keep narration and word timing."""
    if color not in ('black', 'white'):
        raise ValueError('Choose a black or white demo background.')
    folder, source = Path(folder), Path(source)
    target = folder / 'media' / ('solid-' + color + '.mp4')
    if target.is_file():
        return target
    from imageio_ffmpeg import get_ffmpeg_exe
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.stem + '.partial.mp4')
    level = '0' if color == 'black' else '255'
    result = subprocess.run([get_ffmpeg_exe(), '-nostdin', '-hide_banner', '-v', 'error', '-y',
        '-i', str(source), '-vf', f'lutrgb=r={level}:g={level}:b={level}',
        '-map', '0:v:0', '-map', '0:a:0?', '-c:v', 'libx264', '-preset', 'ultrafast',
        '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'copy', '-movflags', '+faststart', str(partial)],
        capture_output=True, text=True, encoding='utf-8', errors='replace',
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        raise RuntimeError('The demo background could not be prepared. Try again. Technical details: ' + result.stderr[-1500:])
    partial.replace(target)
    return target


def ensure_caption_three_background(path):
    """Reference 3's dark lettering needs its light paper demonstration media."""
    path=Path(path)
    if path.is_file():return path
    from imageio_ffmpeg import get_ffmpeg_exe
    from .caption_three import background_image
    path.parent.mkdir(parents=True,exist_ok=True)
    still=path.parent/'caption3-paper.png';background_image(720,1280).save(still)
    audio_source=path.parents[2]/'caption_1/media/taj-mahal-background.mp4'
    ensure_caption_one_background(audio_source)
    partial=path.with_name(path.stem+'.partial.mp4')
    result=subprocess.run([get_ffmpeg_exe(),'-nostdin','-hide_banner','-v','error','-y',
        '-loop','1','-framerate','60','-i',str(still),'-i',str(audio_source),
        '-map','0:v:0','-map','1:a:0','-t',str(DURATION),'-c:v','libx264','-preset','ultrafast','-crf','24',
        '-pix_fmt','yuv420p','-c:a','copy','-movflags','+faststart',str(partial)],
        capture_output=True,text=True,encoding='utf8',errors='replace',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode:raise RuntimeError('Could not prepare the light Caption 3 sample: '+result.stderr[-1000:])
    partial.replace(path);return path


def ensure_caption_four_background(path):
    """Neutral grey paper with the existing, unchanged sample narration."""
    path=Path(path)
    if path.is_file():return path
    from imageio_ffmpeg import get_ffmpeg_exe
    from .caption_four import background_image
    path.parent.mkdir(parents=True,exist_ok=True)
    still=path.parent/'caption4-paper.png';background_image(720,1280).save(still)
    audio_source=path.parents[2]/'caption_1/media/taj-mahal-background.mp4'
    ensure_caption_one_background(audio_source)
    partial=path.with_name(path.stem+'.partial.mp4')
    result=subprocess.run([get_ffmpeg_exe(),'-nostdin','-hide_banner','-v','error','-y',
        '-loop','1','-framerate','60','-i',str(still),'-i',str(audio_source),
        '-map','0:v:0','-map','1:a:0','-t',str(DURATION),'-c:v','libx264','-preset','ultrafast','-crf','24',
        '-pix_fmt','yuv420p','-c:a','copy','-movflags','+faststart',str(partial)],
        capture_output=True,text=True,encoding='utf8',errors='replace',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode:raise RuntimeError('Could not prepare the Caption 4 sample: '+result.stderr[-1000:])
    partial.replace(path);return path


def ensure_caption_five_background(path):
    """Reference 5's white canvas with the unchanged sample narration."""
    path=Path(path)
    if path.is_file():return path
    from imageio_ffmpeg import get_ffmpeg_exe
    path.parent.mkdir(parents=True,exist_ok=True)
    audio_source=path.parents[2]/'caption_1/media/taj-mahal-background.mp4';ensure_caption_one_background(audio_source)
    partial=path.with_name(path.stem+'.partial.mp4')
    result=subprocess.run([get_ffmpeg_exe(),'-nostdin','-hide_banner','-v','error','-y',
        '-f','lavfi','-i','color=c=white:s=720x1280:r=60','-i',str(audio_source),
        '-map','0:v:0','-map','1:a:0','-t',str(DURATION),'-c:v','libx264','-preset','ultrafast','-crf','24',
        '-pix_fmt','yuv420p','-c:a','copy','-movflags','+faststart',str(partial)],
        capture_output=True,text=True,encoding='utf8',errors='replace',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode:raise RuntimeError('Could not prepare the Caption 5 sample: '+result.stderr[-1000:])
    partial.replace(path);return path


def ensure_demo_projects(root):
    root = Path(root).resolve()
    base = root / 'output' / 'captions' / 'template-demos'
    base.mkdir(parents=True, exist_ok=True)
    background = base / 'black-background.mp4'
    if not background.is_file():
        from imageio_ffmpeg import get_ffmpeg_exe
        partial = base / 'black-background.partial.mp4'
        result = subprocess.run([
            get_ffmpeg_exe(), '-nostdin', '-hide_banner', '-v', 'error', '-y',
            '-f', 'lavfi', '-i', 'color=c=black:s=720x1280:r=30',
            '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo',
            '-t', str(DURATION), '-c:v', 'libx264', '-preset', 'ultrafast',
            '-crf', '28', '-pix_fmt', 'yuv420p', '-c:a', 'aac',
            '-movflags', '+faststart', str(partial),
        ], capture_output=True, text=True, encoding='utf-8', errors='replace',
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode:
            raise RuntimeError('Could not prepare the black caption demo background: ' + result.stderr[-1500:])
        partial.replace(background)
    entries = {}
    for style, info in SELECTABLE_TEMPLATES.items():
        # Keep the owner's edited experimental demo; the reference revision has
        # its own saved project and starts at the measured default size/anchor.
        folder = base / (style + '_reference16' if style == 'kinetic_documentary' else style)
        if style == 'caption_2' and (base / 'caption_2_medium' / 'caption-project.json').is_file():
            folder = base / 'caption_2_medium'
        elif style == 'caption_2' and (base / 'caption_2_approved' / 'caption-project.json').is_file():
            folder = base / 'caption_2_approved'
        if style == 'caption_3' and (base / 'caption_3_compact' / 'caption-project.json').is_file():
            folder = base / 'caption_3_compact'
        # The approved Typography 5 revision has its own narrated, saved demo.
        # Keep its timing/layout and leave the earlier sample available too.
        if style == 'typography_5' and (base / 'typography_5_interlock' / 'caption-project.json').is_file():
            folder = base / 'typography_5_interlock'
        media_folder = folder / 'media'
        media_folder.mkdir(parents=True, exist_ok=True)
        source = media_folder / ('white-background.mp4' if style=='caption_5' else 'light-background.mp4' if style in ('caption_3','caption_4') else 'taj-mahal-background.mp4' if style in ('caption_1','caption_2') else 'black-background.mp4')
        if style in ('caption_1','caption_2'):
            ensure_caption_one_background(source)
        elif style=='caption_3':
            ensure_caption_three_background(source)
        elif style=='caption_4':
            ensure_caption_four_background(source)
        elif style=='caption_5':
            ensure_caption_five_background(source)
        elif not source.is_file():
            try:
                os.link(background, source)
            except OSError:
                import shutil
                shutil.copyfile(background, source)
        project_path = folder / 'caption-project.json'
        if project_path.is_file():
            data = json.loads(project_path.read_text(encoding='utf-8'))
            cues = cues_from_data(data['cues'])
        else:
            from .caption_two import sample_cues as caption_two_sample_cues
            from .caption_three import sample_cues as caption_three_sample_cues
            from .caption_four import sample_cues as caption_four_sample_cues
            from .caption_five import sample_cues as caption_five_sample_cues
            cues = caption_one_sample_cues() if style=='caption_1' else caption_two_sample_cues() if style=='caption_2' else caption_three_sample_cues() if style=='caption_3' else caption_four_sample_cues() if style=='caption_4' else caption_five_sample_cues() if style=='caption_5' else sample_cues()
            media = Media('caption-demo-' + style, str(source), DURATION,
                          '60' if style in ('caption_1','caption_2','caption_3','caption_4','caption_5') else '30', 720, 1280, 2, 48000)
            data = write_project(project_path, media, cues, style,
                                 'instagram_vertical' if info.get('layout') == 'kinetic_documentary' else 'source',
                                 'media/'+source.name,
                                 reference_script=' '.join(cue.text for cue in cues),
                                 position=template(style).get('default_position', .7))
            data.update(demo=True, caption_content='speech', word_visibility='phrase')
            if style in ('caption_1','caption_2','caption_3','caption_4','caption_5'):
                data['demo_narration']={'voice':'Microsoft Zira Desktop','sample':'Taj Mahal',
                                        'timing':'Speech engine word audio positions','fps':60}
            project_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            write_srt(folder / 'captions.srt', cues)
            write_ass(folder / 'captions.ass', cues, style, 720, 1280)
            (folder / 'transcript.txt').write_text(' '.join(cue.text for cue in cues), encoding='utf-8')
        files = [('Editable SRT', 'captions.srt'), ('Styled ASS', 'captions.ass'),
                 ('Sample script', 'transcript.txt')]
        if (folder / 'CAPTIONED_SEQUENCE.xml').is_file():
            files.append(('Premiere / Resolve XML', 'CAPTIONED_SEQUENCE.xml'))
        if (folder / 'captioned-preview.mp4').is_file():
            files.append(('Captioned MP4', 'captioned-preview.mp4'))
        write_report(folder / 'report.html', '30-second caption demo',
                     data['source_relative'], cues, data['style'], files, data)
        entries[style] = {'name': info['name'],
                          'url': f'/caption-output/template-demos/{folder.name}/report.html'}
    manifest = {'duration': DURATION, 'templates': entries}
    (root / 'hinglish_app' / 'static' / 'caption-demos.json').write_text(
        json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    args = parser.parse_args()
    result = ensure_demo_projects(args.root)
    print(f"Ready: {len(result['templates'])} editable 30-second caption demos")
