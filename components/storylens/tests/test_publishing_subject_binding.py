"""A destination profile must not relabel an explicitly saved gameplay export."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

from hinglish_publish.metadata import generate_youtube, validate_source_copy


SPEECH = 'Banda pichhe. Mere paas se idhar se goliyaan chali hain. Tu dar mat. What? Amazing.'
SOURCE = "Ajay's Hallucination Gameplay"
BAD = {'title': 'Cricket Fans Chat About the Game', 'description': 'Fans discuss a cricket match. #Cricket #CricketFans #CricketChat', 'tags': ['Cricket', 'CricketFans', 'CricketChat']}
GOOD = {'title': 'Unexpected Shots and Confused Team Chat', 'description': 'Sudden shots spark a confused exchange between teammates. #Gameplay #VoiceChat #GamingMoments', 'tags': ['Gameplay', 'VoiceChat', 'GamingMoments']}


class PublishingSubjectBindingTests(TestCase):
    def workspace(self):
        tmp = TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / 'tmp'); self.addCleanup(tmp.cleanup)
        return Path(tmp.name)

    def test_cricket_destination_revises_a_cricket_label_for_a_gameplay_source(self):
        root = self.workspace(); video = root / 'short.mp4'; video.write_bytes(b'fixture')
        brain = Mock(); brain.name = 'Actual configured local model fixture'; brain.json.side_effect = [BAD, GOOD]
        with patch('hinglish_visuals.brain.open_brain', return_value=brain), patch('hinglish_publish.metadata.review_grounding') as audit:
            value, name = generate_youtube(root, video, profile='cricket', transcript=SPEECH,
                notes='Post to my Cricket YouTube channel.', source_title=SOURCE, progress=lambda _: None)
        self.assertEqual(value['title'], GOOD['title']); self.assertEqual(name, brain.name)
        self.assertEqual(brain.json.call_count, 2); audit.assert_called_once()
        self.assertEqual(brain.json.call_args.args[1]['source_title'], SOURCE)
        self.assertFalse(brain.json.call_args.args[1]['spelling_reference']['names'])

    def test_real_cricket_gameplay_does_not_lose_its_cricket_subject(self):
        with self.assertRaisesRegex(ValueError, 'gameplay'):
            validate_source_copy(BAD, SPEECH, source_title=SOURCE)
        validate_source_copy(BAD, 'The bowler takes a wicket in this cricket match.', source_title='Cricket gameplay')

    def test_common_copy_preparation_passes_the_exact_export_hint_to_writer(self):
        from hinglish_app.assistant_distribution import prepare_copy
        root = self.workspace(); video = root / 'short.mp4'; video.write_bytes(b'fixture')
        with patch('hinglish_publish.metadata.generate_youtube', return_value=({**GOOD, 'instagram_caption': ''}, 'fixture')) as writer:
            prepare_copy(root, video, 'cricket', 'Cricket destination', lambda _: None,
                instagram=False, transcribe=False, source_title=SOURCE)
        self.assertEqual(writer.call_args.kwargs.get('source_title'), SOURCE)
