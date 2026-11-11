"""Describe appearance that a media/edit XML handoff cannot certify.

Premiere's XML can omit effects entirely. Inspect the native capture as well as
the XML; never infer full appearance preservation from clip-count equality.
"""
from pathlib import Path
import xml.etree.ElementTree as ET

TICKS_PER_SECOND = 254016000000
INTRINSIC = {'ADBE Motion', 'ADBE Opacity', 'ADBE Time Remapping',
             'AE.ADBE Motion', 'AE.ADBE Opacity', 'AE.ADBE Time Remapping'}
XML_BASIC = {'basic', 'opacity', 'audiolevels', 'timeremap'}


def audit(xml: Path, context: dict) -> dict:
    root = ET.parse(xml).getroot()
    issues = []
    native = context.get('native_video_inventory')
    if native is None:
        issues.append({'kind': 'native_inventory_missing',
                       'detail': 'Recapture with the updated Premiere panel before claiming effect preservation.'})
    for clip in native or []:
        for component in clip.get('components', []):
            name = component.get('match_name', '')
            if name not in INTRINSIC:
                issues.append({'kind': 'native_effect_requires_appearance_conversion',
                               'clip': clip['name'], 'track': clip['track'],
                               'start_seconds': int(clip['start_ticks']) / TICKS_PER_SECOND,
                               'end_seconds': int(clip['end_ticks']) / TICKS_PER_SECOND,
                               'effect': component})
        if not clip.get('source'):
            issues.append({'kind': 'generated_or_nested_picture', 'clip': clip['name'],
                           'detail': 'No direct media path. XML does not certify the generated/nested appearance.'})
    xml_effects = []
    for effect in root.findall('.//filter/effect'):
        effect_id = effect.findtext('effectid') or ''
        item = {'id': effect_id, 'name': effect.findtext('name') or ''}
        xml_effects.append(item)
        if effect_id.lower() not in XML_BASIC:
            issues.append({'kind': 'xml_effect_requires_verification', **item})
    transitions = [{'name': t.findtext('effect/name'), 'start': t.findtext('start'),
                    'end': t.findtext('end')} for t in root.findall('.//transitionitem')]
    # Even basic properties need an actual native conform review. This status
    # establishes only that no known unsupported appearance was silently dropped.
    return {'status': 'needs_appearance_conversion' if issues else 'basic_media_edit_candidate',
            'issues': issues, 'native_video_clips': len(native) if native is not None else None,
            'xml_effects': xml_effects, 'xml_transitions': transitions,
            'rendered': False, 'full_appearance_verified': False,
            'notice': 'Compound grouping does not render or translate missing effects. '
                      'Unsupported ranges need native reconstruction or a rendered appearance fallback.'}
