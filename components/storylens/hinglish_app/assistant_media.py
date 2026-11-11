"""Render editor outputs for the next conversational step; retain all editable originals."""
import json
from hinglish_cut.compute_policy import heavy_device
from pathlib import Path


def render_xml(xml, target, progress=print, *, device='cpu'):
    import numpy as np
    from hinglish_zoom.xml_apply import Sequence
    from hinglish_zoom.preview import render_preview
    seq = Sequence(xml)
    if any(not Path(c.path).is_file() or c.reason in ('nested sequence', 'already has motion keyframes', 'next to a transition')
           for c in seq.clips):
        raise ValueError('This timeline needs review before the next automatic editing step.')
    if seq.frames <= 0:
        raise ValueError('The tool produced an empty timeline.')
    audio = None
    mix = Path(xml).parent / 'sound' / 'full-mix.wav'
    if mix.is_file():
        from hinglish_sound.library import decode
        audio = decode(mix).mean(axis=0)
    progress('Rendering the edited video for your chat')
    return str(render_preview(seq, np.ones(seq.frames), [None] * seq.frames, target,
                              max_side=max(seq.width, seq.height), progress=progress, audio=audio,device=device).resolve())


def outputs(root, step, result, folder, progress=print):
    """Return whole edited videos, not reference media or a split-screen comparison."""
    tool = step['tool']
    base = Path(result['folder']).resolve()
    if not base.is_relative_to((Path(root) / 'output').resolve()):
        raise ValueError('The editor returned an unexpected output folder.')
    if tool == 'clean':
        paths = sorted(base.rglob('cleaned.mp4'))
    elif tool == 'gaming':
        paths = sorted(base.rglob('GAMING_HIGHLIGHTS.mp4'))
    elif tool == 'thumbnail':
        return []
    elif tool == 'shorts':
        paths = []
        for project in sorted(base.rglob('shorts-project.json')):
            # The producer already reviewed its captions and titles. Reading
            # completed outputs must not render them again (including across
            # software versions). Explicit repair chat commands own upgrades.
            data = json.loads(project.read_text(encoding='utf-8'))
            paths += [project.parent / s['mp4'] for s in data.get('shorts', []) if s.get('mp4')]
    elif tool == 'eyecontact':
        plan = base / 'eyecontact-plan.json'
        data = json.loads(plan.read_text(encoding='utf-8')) if plan.is_file() else {}
        paths = [Path(f['target']) for f in data.get('files', []) if f.get('target')]
        if data.get('simulated'):
            raise ValueError('Eye Contact produced a simulation. It cannot be used as a corrected video.')
    else:
        paths = []
        names = {'script': ['EDITED_SEQUENCE.xml', 'timeline.xml'], 'captions': ['CAPTIONED_SEQUENCE.xml'],
                 'broll': ['BROLL_SEQUENCE.xml'], 'visuals': ['VISUALS_SEQUENCE.xml'],
                 'zoom': ['ZOOMED_SEQUENCE.xml'], 'sound': ['SOUND_SEQUENCE.xml'],
                 'motion': ['MOTION_SEQUENCE.xml'], 'aiimage': ['AI_IMAGES_SEQUENCE.xml'],
                 'aivideo': ['AI_VIDEO_SEQUENCE.xml']}
        candidates = [Path(p) for p in result.get('xml_files', []) if Path(p).name in names.get(tool, [])]
        # Feature exports use *_SEQUENCE names. Select their actual output, never source/draft XML.
        if not candidates and tool not in ('script',):
            candidates = [Path(p) for p in result.get('xml_files', [])
                          if 'SEQUENCE' in Path(p).stem and 'source' not in Path(p).stem.lower()]
        for n, xml in enumerate(sorted(candidates), 1):
            rendered=Path(render_xml(xml, folder / f'{tool}-{n:03d}.mp4', progress,device=heavy_device(root)))
            paths.append(rendered)
            if tool=='zoom' and (xml.parent/'zoom-plan.json').is_file():
                from hinglish_zoom.provenance import save
                save(rendered,xml.parent/'zoom-plan.json')
        if not paths and tool == 'motion':
            paths = sorted(base.rglob('MOTION_GRAPHICS.mp4'))
    paths = [str(p.resolve()) for p in paths if p.is_file()]
    # Script-only generation legitimately returns an asset library instead of a whole edited video.
    if not paths and tool in ('aiimage', 'aivideo', 'motion'):
        return []
    if not paths:
        raise ValueError('The tool has a review result, but no complete video is ready for the next step. Open the review to resolve it.')
    return paths


def join_videos(paths, folder, progress=print, *, device='cpu'):
    """Input order is the attachment order. Normalize mixed rates using the existing conformer."""
    from hinglish_cut.media import conform_video, probe
    from hinglish_cut.model import Cut
    from hinglish_cut.xml_export import export_xml
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    media, cuts = {}, []
    for i, path in enumerate(paths):
        progress(f'Preparing part {i + 1}/{len(paths)} in attachment order')
        target = folder / f'part-{i + 1:03d}.mp4'
        conform_video(path, target)
        m = probe(target)
        media[m.id] = m
        cuts.append(Cut(m.id, 0, int(m.duration * float(m.rate) + 1e-6), i))
    xml = folder / 'JOINED_SEQUENCE.xml'
    export_xml(xml, cuts, media)
    return render_xml(xml, folder / 'joined-video.mp4', progress,device=device)


def transcribe_voice(root, path, progress=print):
    """Installed multilingual speech model using the configured local device."""
    import av
    import numpy as np
    root = Path(root)
    chunks, samples = [], 0
    with av.open(str(path)) as source:
        if not source.streams.audio:
            raise ValueError('The recording has no audio. Please try again.')
        resampler = av.AudioResampler(format='flt', layout='mono', rate=16000)
        for frame in source.decode(source.streams.audio[0]):
            for out in resampler.resample(frame):
                samples += out.samples
                if samples > 120 * 16000:
                    raise ValueError('Please keep voice requests under two minutes.')
                chunks.append(out.to_ndarray().reshape(-1))
        for out in resampler.resample(None):
            chunks.append(out.to_ndarray().reshape(-1))
    if not samples:
        raise ValueError('The recording was empty. Please try again.')
    model = None
    for manifest in ('meaning-upgrade.json', 'meaning-models.json'):
        p = root / 'models' / manifest
        if p.is_file():
            loc = Path(json.loads(p.read_text(encoding='utf-8'))['speech_path'])
            if (loc / 'model.bin').is_file():
                model = loc
                break
    if model is None:
        raise ValueError('Voice input needs the installed multilingual speech model. Run Download Phase 2 Models.bat once, or type your request.')
    from contextlib import nullcontext
    from hinglish_cut.model_preferences import preferred_device, release_ollama
    from hinglish_cut.gpu_lock import gpu_lock
    device = preferred_device(root)
    options = {'device': device, 'compute_type': 'int8_float16' if device == 'cuda' else 'int8'}
    with gpu_lock(root) if device == 'cuda' else nullcontext():
        if device == 'cuda':
            from .caption_compute import prepare_runtime
            release_ollama(root)
            prepare_runtime(root, options)
        from faster_whisper import WhisperModel
        brain = WhisperModel(str(model), **options, cpu_threads=4, local_files_only=True)
        try:
            segments, _ = brain.transcribe(np.concatenate(chunks), beam_size=3, vad_filter=True,
                                           condition_on_previous_text=False)
            text = ' '.join(s.text.strip() for s in segments).strip()
        finally:
            del brain
    if not text:
        raise ValueError('I could not hear speech in that recording. Please try again or type it.')
    return text
