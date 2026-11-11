"""Persist approved SEO style and check the existing local model; never upload videos."""
import argparse
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FOLDER = ROOT / 'output/validation/publishing-seo-memory'
LESSON = {
    'scope': 'description',
    'want': 'Write long, detailed, unique English YouTube descriptions focused entirely on each video. '
            'Aim for 1500-3500 characters where source detail supports it, including Shorts. Put the main '
            'topic and viewer value in the opening two lines. Use 1-2 primary search phrases and natural '
            'related keywords, readable topic paragraphs and 3-5 relevant hashtags at the end. Include '
            'only verified source facts. Keep Instagram captions separate and appropriately sized.',
    'avoid': 'Generic two-line descriptions, keyword stuffing, unrelated popular/trending terms, fake '
             'search-volume claims, repetition, invented facts or chapters, guaranteed rankings/views. '
             'Never include Storylens/upload tests/account routing. Do not pad sparse footage just to '
             'reach a length. Preserve the earlier content-only rule and leave existing uploads unchanged.',
    'before': 'A look at the team. #Cricket',
    'after': 'Structure only: topic-focused opening; detailed factual story summary; specific covered '
             'topics with natural search phrases; 3-5 relevant hashtags. Use each new video\'s own '
             'content, not example facts. Longer descriptions must remain useful and accurate.'
}


def save_memory():
    from hinglish_publish.memory import CreatorMemory
    ids = {profile: CreatorMemory(ROOT, profile).add(LESSON)
           for profile in ('general', 'cricket', 'gaming')}
    for profile in ids:
        context = CreatorMemory(ROOT, profile).writing_context()
        assert context[0]['want'] == LESSON['want']
        assert any('actual video content only' in item['want'] for item in context)
    receipt = {'profiles': ids, 'lesson': LESSON,
               'method': 'Persistent creator memory and instructions; no weight training.',
               'existing_uploads_modified': False}
    (FOLDER / 'saved-memory.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print('Saved SEO preference in General, Cricket and Gaming; prior content-only preference retained.')


def check_model():
    from hinglish_publish import metadata
    from hinglish_visuals.brain import open_brain
    from hinglish_niche.profiles import Profiles, use
    # Controlled writing fixture, not a transcript claimed to come from an uploaded video.
    transcript = '''This documentary looks at the Mumbai Indians team during the 2020 IPL season.
The opening introduces Rohit Sharma as captain and explains that a team journey involves more than
one individual. The discussion then moves to preparation: players practising, the role of training,
and how the squad works together before a match. A section on batting describes partnerships,
communication between batters and balancing individual responsibility with the needs of the team.
The bowling section discusses planning, adapting to different phases and supporting the fielders.
Another section looks at fielding as a shared responsibility and the importance of communication.
The film describes Rohit Sharma's role in bringing the squad together and making decisions on the
field. It also discusses the support staff and preparation away from the spotlight. The closing
section returns to teamwork, the contributions of different players, and what fans look for when
following an IPL team across a season. The video uses team photographs and training footage alongside
the narration. It is a team-focused retrospective, not a match-by-match scorecard. This source does
not provide match results, trophies, scores, dates, individual statistics or player quotations.'''
    notes = 'Private Storylens upload test for Fantasy Legends. Verify channel routing; not the video topic.'
    actual = open_brain(ROOT, 'ollama')

    class CheckBrain:
        name = actual.name
        def json(self, system, data, schema, **kwargs):
            return actual.json(system, data, schema, max_tokens=kwargs['max_tokens'], think=False)
        def close(self):
            actual.close()

    with use(Profiles(ROOT).context('cricket')), patch('hinglish_visuals.brain.open_brain', return_value=CheckBrain()):
        output, origin = metadata.generate(ROOT, FOLDER / 'controlled-writing-input.mp4',
                                          transcript=transcript, notes=notes)
    description = output['description']
    combined = json.dumps(output, ensure_ascii=False).casefold()
    forbidden = ('storylens', 'fantasy legends', 'upload test', 'uploadtest', 'routing',
                 'guaranteed', 'trending', 'champions', 'won the', 'fifth title')
    checks = {
        'substantial_description': 1500 <= len(description) <= 4500,
        'topic_in_opening': 'mumbai indians' in description[:250].casefold(),
        'relevant_hashtag_count': 3 <= sum(word.startswith('#') for word in description.split()) <= 5,
        'readable_paragraphs': len(description.split('\n\n')) >= 3,
        'separate_instagram_caption': len(output['instagram_caption']) < 2000
                                      and output['instagram_caption'] != description,
        'no_operational_or_unsupported_claims': not any(word in combined for word in forbidden),
        'specific_source_topics': all(word in description.casefold() for word in ('batting', 'bowling', 'fielding')),
    }
    receipt = {'passed': all(checks.values()), 'checks': checks, 'model': origin,
               'description_characters': len(description), 'scope': 'Controlled local-model writing fixture only.',
               'source': transcript, 'production_notes_to_exclude': notes, 'output': output,
               'weight_training_performed': False, 'existing_uploads_modified': False}
    (FOLDER / 'live-model-check.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps({'passed': receipt['passed'], 'checks': checks,
                      'description_characters': len(description), 'model': origin}, indent=2), flush=True)
    assert receipt['passed'], 'See live-model-check.json for concrete failed checks.'


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--save-memory', action='store_true')
    parser.add_argument('--check-model', action='store_true')
    args = parser.parse_args()
    FOLDER.mkdir(parents=True, exist_ok=True)
    if args.save_memory:
        save_memory()
    if args.check_model:
        check_model()
