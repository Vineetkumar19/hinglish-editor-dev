"""CPU-only synthetic fixtures for the manual raw-source handoff contract."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image


class SourceBankTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        refs = self.folder / 'references'
        refs.mkdir()
        # Tiny synthetic fixture; no media pipeline, model, network or host.
        self.asset = refs / 'fixture.png'
        Image.new('RGBA', (2, 2), (20, 40, 60, 255)).save(self.asset)
        with Image.open(self.asset) as im:
            self.fingerprint = hashlib.sha256(im.convert('RGBA').resize((96, 96)).tobytes()).hexdigest()
        self.option = {'id': 'web:fixture', 'kind': 'image', 'asset': 'references/fixture.png',
            'path': str(self.asset.resolve()), 'sha256': self.fingerprint,
            'title': 'Synthetic player fixture', 'source': 'web',
            'url': 'https://example.test/player.png', 'page_url': 'https://example.test/player',
            'author': 'Fixture publisher', 'license': 'Fixture only', 'license_url': '',
            'evaluation': {'passed': True, 'judge': 'synthetic fixture', 'checks': {},
                           'warnings': ['Not a real identity judgment']}}
        self.slot = {'index': 0, 'entity': 'player', 'label': 'Player', 'start': .5, 'end': 1.5,
            'text': 'Player in team kit', 'meaning': 'Player', 'visual': 'Player team photo',
            'queries': ['Player team photo'], 'reference_type': 'identity',
            'show': 'photo', 'display': 'popup', 'options': [self.option],
            'chosen': None, 'clip': None}
        self.project = {'review_options': True, 'options_per_moment': 2,
            'brain': 'synthetic local fixture', 'research_state': {'stage': 'partial'},
            'entities': {'player': {'key': 'player', 'name': 'Raw spoken name',
                'label': 'Player', 'kind': 'person', 'qid': 'Q1'}},
            'timeline': {'name': 'Fixture', 'fps': '30/1', 'width': 1280, 'height': 720,
                'duration': 3., 'xml_path': str(self.folder / 'source.xml')},
            'slots': [self.slot]}
        self.file = self.folder / 'visuals-project.json'
        self.save()

    def save(self):
        self.file.write_text(json.dumps(self.project), encoding='utf-8')

    def build(self, selections=None):
        from hinglish_visuals.source_bank import build_source_bank
        return build_source_bank(self.file, selections)

    def test_two_option_picker_is_ready_without_erasing_saved_choices(self):
        from hinglish_visuals.review_ui import render
        self.slot['options'].append({**self.option, 'id': 'web:second'})
        self.slot['chosen'] = self.option
        before = copy.deepcopy(self.project)
        render(self.folder / 'review.html', self.project, '', 'http://localhost:1')
        page = (self.folder / 'review.html').read_text('utf-8')
        self.assertIn('Visuals · 2/2', page)
        self.assertIn('id="status">Ready', page)
        self.assertIn('aria-pressed="true"', page)
        self.assertEqual(self.project, before)
        self.project['options_per_moment'] = 5
        render(self.folder / 'review.html', self.project, '', 'http://localhost:1')
        page = (self.folder / 'review.html').read_text('utf-8')
        self.assertIn('Visuals · 2/5', page)
        self.assertIn('Some options unavailable', page)

    def test_empty_bank_and_no_match_are_retained_with_correct_target(self):
        self.slot['options'] = []
        self.save()
        bank = self.build({'0': ''})['banks'][0]
        self.assertEqual(bank['selection'], {'state': 'no_visual', 'asset_id': None})
        self.assertEqual(bank['availability'], 'no_match')
        self.assertEqual(bank['target'], 2)
        self.assertEqual(bank['shortfall'], 2)

    def test_source_bytes_provenance_identity_and_anchor_are_preserved(self):
        original = self.file.read_bytes(), self.asset.read_bytes()
        manifest = self.build()
        self.assertEqual(manifest['schema'], 'storylens.smart_visuals.source_bank')
        self.assertEqual(manifest['version'], 1)
        self.assertFalse(manifest['auto_insert'])
        self.assertEqual(manifest['lineage']['saved_planning_model'], 'synthetic local fixture')
        self.assertFalse(manifest['lineage']['new_model_inference'])
        bank = manifest['banks'][0]
        self.assertEqual(bank['entity']['qid'], 'Q1')
        self.assertEqual(bank['entity']['name'], 'Raw spoken name')
        self.assertEqual(bank['anchor']['start_frame'], 15)
        self.assertEqual(bank['anchor']['end_frame'], 45)
        choice = bank['choices'][0]
        self.assertEqual(choice['media_id'], 'web:fixture')
        self.assertEqual(choice['source']['page_url'], self.option['page_url'])
        self.assertEqual(choice['source']['license'], 'Fixture only')
        self.assertEqual(choice['file']['sha256'], hashlib.sha256(original[1]).hexdigest())
        self.assertEqual(choice['image_fingerprint']['value'], self.fingerprint)
        self.assertNotEqual(choice['file']['sha256'], choice['image_fingerprint']['value'])
        self.assertEqual(bank['selection']['state'], 'unreviewed')
        self.assertEqual((self.file.read_bytes(), self.asset.read_bytes()), original)
        self.assertEqual(manifest, self.build())

    def test_explicit_selection_is_bound_and_plain_handoff_never_renders(self):
        from hinglish_visuals.source_bank import selected_source_assets
        manifest = self.build({'0': 'web:fixture'})
        with patch('hinglish_visuals.pipeline.render_slot', side_effect=AssertionError('Must not render')):
            selected = selected_source_assets(manifest, self.file)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]['path'], str(self.asset.resolve()))
        self.assertEqual(selected[0]['presentation'], 'plain_source')
        self.assertFalse(selected[0]['add_text'])
        self.assertFalse(selected[0]['add_card'])
        self.assertFalse(selected[0]['auto_insert'])
        self.assertEqual(selected_source_assets(self.build(), self.file), [])
        self.assertEqual(selected_source_assets(self.build({'0': ''}), self.file), [])
        self.slot['chosen'] = self.option
        self.save()
        self.assertEqual(self.build()['banks'][0]['selection']['state'], 'selected')

    def test_invalid_selection_and_bank_index_never_select_first(self):
        for selections in ({'0': 'not-offered'}, {'9': 'web:fixture'}, {'0': True}):
            with self.subTest(selections=selections), self.assertRaises(ValueError):
                self.build(selections)

    def test_missing_unapproved_video_and_bad_binding_stay_unavailable(self):
        variants = [dict(self.option, asset='references/missing.png'),
            dict(self.option, evaluation={'passed': False}), dict(self.option, kind='video'),
            dict(self.option, path=str(self.folder / 'other.png')),
            dict(self.option, sha256='0' * 64),
            dict(self.option, evaluation={'passed': True, 'checks': {
                'profile_source': 'https://www.cricinfo.com/story/a-high-profile-story'}})]
        for option in variants:
            with self.subTest(option=option):
                self.slot['options'] = [option]
                self.save()
                bank = self.build()['banks'][0]
                self.assertEqual(bank['choices'], [])
                self.assertEqual(len(bank['unavailable_choices']), 1)
                with self.assertRaises(ValueError):
                    self.build({'0': self.option['id']})

    def test_path_escape_duplicate_ids_and_entity_mismatch_fail_safely(self):
        outside = self.folder / 'outside.png'
        outside.write_bytes(self.asset.read_bytes())
        for option in (dict(self.option, asset='../outside.png'),
                       dict(self.option, asset=str(outside.resolve())),
                       dict(self.option, entity='another-player')):
            self.slot['options'] = [option]
            self.save()
            self.assertEqual(self.build()['banks'][0]['choices'], [])
        self.slot['options'] = [self.option, dict(self.option)]
        self.save()
        with self.assertRaises(ValueError):
            self.build()
        self.project['entities']['player']['key'] = 'someone-else'
        self.slot['options'] = [self.option]
        self.save()
        with self.assertRaises(ValueError):
            self.build()

    def test_manifest_tampering_changed_source_and_changed_project_are_rejected(self):
        from hinglish_visuals.source_bank import selected_source_assets
        manifest = self.build({'0': 'web:fixture'})
        for change in ('file', 'qid', 'anchor', 'version', 'auto_insert'):
            altered = copy.deepcopy(manifest)
            if change == 'file': altered['banks'][0]['choices'][0]['file']['path'] = str(self.file)
            if change == 'qid': altered['banks'][0]['entity']['qid'] = 'Q2'
            if change == 'anchor': altered['banks'][0]['anchor']['start_frame'] = 0
            if change == 'version': altered['version'] = 99
            if change == 'auto_insert': altered['auto_insert'] = True
            with self.subTest(change=change), self.assertRaises(ValueError):
                selected_source_assets(altered, self.file)
        self.asset.write_bytes(b'changed bytes')
        with self.assertRaises(ValueError):
            selected_source_assets(manifest, self.file)
        self.project['timeline']['name'] = 'Changed project'
        self.save()
        with self.assertRaises(ValueError):
            selected_source_assets(manifest, self.file)

    def test_export_is_additive_and_does_not_rewrite_existing_outputs(self):
        from hinglish_visuals.source_bank import export_source_bank
        target = self.folder / 'SOURCE_BANK.v1.json'
        original = self.file.read_bytes(), self.asset.read_bytes()
        manifest = export_source_bank(self.file, target)
        self.assertEqual(json.loads(target.read_text('utf-8')), manifest)
        with self.assertRaises(FileExistsError): export_source_bank(self.file, target)
        with self.assertRaises(FileExistsError): export_source_bank(self.file, self.file)
        self.assertEqual((self.file.read_bytes(), self.asset.read_bytes()), original)
        self.assertEqual(manifest['banks'][0]['selection']['state'], 'unreviewed')

    def test_stable_identity_and_strict_version_survive_selection_changes(self):
        from hinglish_visuals.source_bank import selected_source_assets
        unreviewed = self.build()
        selected = self.build({'0': 'web:fixture'})
        self.assertEqual(unreviewed['banks'][0]['bank_id'], selected['banks'][0]['bank_id'])
        self.assertEqual(unreviewed['banks'][0]['choices'][0]['asset_id'],
                         selected['banks'][0]['choices'][0]['asset_id'])
        selected['version'] = True  # bool == 1 in Python, but not a version integer.
        with self.assertRaises(ValueError):
            selected_source_assets(selected, self.file)


if __name__ == '__main__':
    unittest.main()
