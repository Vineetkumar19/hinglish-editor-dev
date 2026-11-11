"""Withdraw the rejected reference-derived demo, retaining labelled study evidence."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools'))
from hinglish_motion.reference_policy import REFERENCE_RULES, withdraw_report
from hinglish_niche.documentary_memory import atomic, read

OUT = ROOT / 'output/reference-analysis/cricAddict-by-video/reference-01'


def main():
    folder = ROOT / 'library/creator-profiles/documentary-memory'
    prefs = read(folder / 'preferences.json')
    prefs['requirements'] = list(dict.fromkeys(prefs['requirements'] + REFERENCE_RULES))
    prefs['reference_media_usage'] = 'analysis-only; no production reuse'
    atomic(folder / 'preferences.json', prefs)
    manifest = read(folder / 'manifest.json')
    manifest['reference_media_usage'] = 'analysis-only; no production reuse'
    manifest['revision'] = hashlib.sha256(json.dumps({'previous':manifest['revision'], 'preferences':prefs}, sort_keys=True).encode()).hexdigest()
    atomic(folder / 'manifest.json', manifest)
    atomic(folder / 'reference-media-policy.json', {
        'scope':'cricAddict and vineet documentry edit reference learning',
        'language_model_independent':True, 'requirements':REFERENCE_RULES,
        'rejected_demo':'reference-01/CRICADDICT_REFERENCE_01_LOCAL_60S.mp4',
        'production_source':'user-owned/permitted narration plus independently sourced permitted visuals',
        'copyright_permission_not_established_by':['search result','download','identity check','cropping','watermark removal'],
    })
    rejected = OUT / 'rejected-sample'
    rejected.mkdir(exist_ok=True)
    candidates = [OUT / 'CRICADDICT_REFERENCE_01_LOCAL_60S.mp4', OUT / 'sample-final-contact-sheet.jpg'] + list(OUT.glob('sample-scene-*.jpg'))
    for path in candidates:
        if path.exists():
            if not path.resolve().is_relative_to(OUT.resolve()):
                raise ValueError('Withdrawal target escaped the declared output folder')
            path.replace(rejected / path.name)
    atomic(rejected / 'DO_NOT_PUBLISH.json', {'status':'withdrawn','purpose':'rejected diagnostic only',
        'reason':'Reused another creator\'s reference frames, footage, branding and mixed audio.',
        'permitted_use':'Inspect the failed implementation only; excluded from production and portable memory package.'})
    atomic(OUT / 'reference-media-withdrawal.json', {'status':'sample-withdrawn','analysis_preserved':True,
        'reason':'Reference supplied for style learning only; sample wrongly used reference media as production assets.',
        'replacement_video_generated':False, 'old_renderer_blocked':True, 'sourcing_agent_bypassed_by_old_adapter':True,
        'future_workflow':'User-owned/permitted audio -> local director retrieves technique lessons -> independent sourcing with provenance -> render with own branding.',
        'memory_policy':str(folder / 'reference-media-policy.json')})
    completion = read(OUT / 'completion.json')
    completion.update(status='study-complete_sample-withdrawn', sample_status='withdrawn', video=None,
        publishable=False, next_reference_started=False)
    atomic(OUT / 'completion.json', completion)
    curriculum = read(folder / 'cricaddict-curriculum.json')
    curriculum['review_status'] = 'Reference study complete; sample rejected for reusing reference media. Await independent production inputs.'
    curriculum['sample_status'] = 'withdrawn'
    atomic(folder / 'cricaddict-curriculum.json', curriculum)
    source = read(OUT / 'source.json')
    source.update(purpose='style-reference-analysis-only', production_reuse_allowed=False)
    atomic(OUT / 'source.json', source)
    withdraw_report(OUT)
    (OUT / 'progress.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><title>Reference study</title><h1>Reference study complete; sample withdrawn</h1><p>The reference video teaches editing techniques only. Its footage, audio and branding cannot be used as our production output.</p><a href="report.html">Open the labelled analysis report</a></html>', encoding='utf-8')
    from finish_one_cricaddict_study import archive
    archive()
    print('Rejected sample withdrawn. Analysis preserved. Shared rules saved. Archive rebuilt without sample media.')


if __name__ == '__main__':
    main()
