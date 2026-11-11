"""Reference studies supply technique evidence, never production media."""
from pathlib import Path
import hashlib
import json

REFERENCE_RULES = [
    'Reference videos are analysis-only. Learn pacing, composition, motion, camera treatment, typography techniques and sound relationships; never use their frames, clips, narration, music, sound effects, logos, watermarks or channel branding in generated production output.',
    'Production audio must be the user\'s own narration or separately permitted audio. Production visuals must come from the independent asset-sourcing workflow or the user\'s permitted media, with recorded origin and reuse permission. An internet search, download, face check or crop does not establish reuse permission.',
    'Never cover, crop, blur or remove another creator\'s watermark as a way to reuse their reference footage. Recreate the editing technique with different, permitted assets and the user\'s own branding.',
    'When independently sourced media is missing, pause that production shot and report the missing asset. Do not silently substitute reference footage or another creator\'s mixed audio.',
]


class ReferenceMediaError(ValueError):
    pass


def block_reference_sample():
    """Retire the adapter that explicitly binds reference frames and audio."""
    raise ReferenceMediaError(
        'This sample adapter is withdrawn: it extracts another creator\'s reference '
        'frames and mixed audio. Reference media is analysis-only. Use the production '
        'editor with user-owned/permitted narration and independently sourced assets; '
        'do not reuse this adapter or its cached sample.'
    )


def validate_production_asset(path, provenance, reference_paths=()):
    """Check an explicit asset receipt, not an LLM's assertion of permission.

    This checks recorded provenance and file identity. It cannot independently
    prove ownership or that the supplied licence evidence is legally sufficient.
    """
    path = Path(path).resolve()
    if not path.is_file():
        raise ReferenceMediaError('Production asset is missing.')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    for reference in reference_paths:
        ref = Path(reference).resolve()
        if path == ref or (ref.is_file() and digest == hashlib.sha256(ref.read_bytes()).hexdigest()):
            raise ReferenceMediaError('A reference file or an identical copy cannot be a production asset.')
    if provenance.get('purpose') != 'production' or provenance.get('derived_from_reference') is not False:
        raise ReferenceMediaError('Reference-derived or unclassified assets cannot enter production.')
    if provenance.get('sha256') != digest:
        raise ReferenceMediaError('Asset changed or its provenance belongs to a different file.')
    if provenance.get('rights') not in ('owned', 'licensed', 'public-domain'):
        raise ReferenceMediaError('Production asset has no recorded reuse permission.')
    if not provenance.get('permission_evidence'):
        raise ReferenceMediaError('Production asset is missing ownership or permission evidence.')
    if provenance.get('rights') != 'owned' and not all(provenance.get(k) for k in ('source_url', 'license')):
        raise ReferenceMediaError('Sourced media needs its original source URL and licence information.')
    return {'path': str(path), 'sha256': digest, 'purpose': 'production'}


def withdraw_report(folder):
    """Keep analysis evidence visible; remove the rejected sample player."""
    import re
    folder = Path(folder)
    path = folder / 'report.html'
    if not path.exists():
        return
    text = path.read_text(encoding='utf-8')
    notice = ('<section id="reference-only-notice"><h2>Sample withdrawn</h2>'
        '<p>The previous sample reused frames, clips, branding and mixed audio from '
        'the creator\'s reference video. It is withdrawn and is not an original or '
        'publishable production output. These videos teach editing techniques only.</p>'
        '<p>Study frames and panels below are labelled reference evidence. Future output '
        'must use independently sourced, permitted assets, your own or permitted '
        'narration, and your own branding. No replacement video has been generated.</p></section>')
    text = re.sub(r'<video\b[^>]*>.*?</video>\s*<p>.*?</p>', notice, text, count=1, flags=re.S)
    text = re.sub(r'<h2>The local model\'s sample</h2>.*?(?=<h2>Timestamped local vision review</h2>)', '', text, flags=re.S)
    text = re.sub(r'<section id="final-review">.*?</section>', '', text, flags=re.S)
    text = text.replace('>Portable video-1 memory</a>', '>Analysis-only memory package</a>')
    if 'id="reference-only-notice"' not in text:
        text = text.replace('<h1>', notice + '<h1>', 1)
    path.write_text(text, encoding='utf-8')
