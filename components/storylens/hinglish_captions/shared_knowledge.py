"""Reuse original Auto Captions data without rewriting pasted scripts or weights."""
import hashlib
import json
import re
from pathlib import Path


def for_script(root, text, profile):
    from .proofread import references
    from hinglish_publish.memory import CreatorMemory
    from hinglish_niche.profiles import Profiles
    root = Path(root)
    ref = references()
    selected = Profiles(root).read()['selected']
    spellings = CreatorMemory(root, selected).spellings()
    terms = set(re.findall(r'\w+', text.casefold()))

    def relevant(value):
        return bool(terms.intersection(re.findall(r'\w+', str(value).casefold())))

    data = {
        'purpose': 'Original Auto Captions reference knowledge. Use for understanding, grouping and emphasis only. Preserve every pasted word and number exactly. Do not replace text from spelling examples. Do not apply another style’s visual design.',
        'caption_rules': ref.get('caption_rules', []),
        'roman_spellings': ref.get('roman_spellings', []),
        'entities': [x for x in ref.get('cricket_entities', []) if relevant(x)][:24],
        'terms': [x for x in ref.get('cricket_terms', []) if relevant(x)][:24],
        'recognition_examples': [x for x in ref.get('recognition_examples', []) if relevant(x['heard']) or relevant(x['canonical'])][:12],
        'creator_spellings': {a:b for a,b in spellings.items() if relevant(a) or relevant(b)},
        'layout_rules': ['Measure the complete row before revealing words.', 'Keep revealed words fixed.', 'Use the selected style’s own font, hierarchy and motion.', 'Keep compact ink gaps, black background and at most five words per slide.', 'Emphasize meaningful content words rather than articles or filler.'],
        'selected_style_examples': [r.get('text', '') for r in profile.get('recipes', []) if r.get('text')][:12],
    }
    sources = []
    from hinglish_cut.reelmimic import context as reference_context
    reference = reference_context(root, 'captions')
    if reference:
        data['reelmimic_reference'] = reference
    from hinglish_motion.creative import planning_guidance, CATALOG
    data['creative_design_guidance'] = planning_guidance('captions', text)
    sources.append({'path': str(CATALOG), 'sha256': hashlib.sha256(CATALOG.read_bytes()).hexdigest()})
    for name in ('references.json', 'cricket_vocabulary.json'):
        p = Path(__file__).with_name(name)
        sources.append({'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()})
    return {
        'context': data,
        'receipt': {'mode': 'retrieved reference knowledge; no weight training', 'sources': sources,
                    'creator_profile': selected, 'available_entities': len(ref.get('cricket_entities', [])),
                    'available_terms': len(ref.get('cricket_terms', [])), 'available_spelling_examples': len(ref.get('recognition_examples', [])),
                    'available_creator_spellings': len(spellings), 'context_sha256': hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()},
    }
