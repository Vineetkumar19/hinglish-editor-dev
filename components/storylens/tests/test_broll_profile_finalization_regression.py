"""Producer packaging/resume regressions: synthetic media metadata, no rendering."""
import copy
import json
import unittest
from unittest.mock import Mock, patch
import sys
from types import SimpleNamespace

from hinglish_broll import pipeline
from hinglish_broll.producer_contract import finalize_candidate_bank
from tests import test_broll_candidate_manifest as fixtures


class ProfileFinalizationRegressionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.CandidateManifestTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.reader = lambda p: self.fixture.metadata[str(p)]

    def finalize(self):
        return finalize_candidate_bank(self.fixture.project_file, media_reader=self.reader)

    def test_normal_producer_string_profiles_keep_their_own_caps(self):
        for profile, cap in [('short', 5), ('long', 2)]:
            with self.subTest(profile=profile):
                # pipeline.run serializes profile.name as this string, not a dict.
                self.fixture.project['profile'] = profile
                self.fixture.write()
                before = self.fixture.project_file.read_bytes()
                manifest = self.finalize()
                self.assertEqual(manifest['content_format'], profile)
                self.assertEqual(manifest['per_keyword_cap'], cap)
                self.assertEqual(len(manifest['slots'][0]['candidates']), cap)
                self.assertEqual(manifest['slots'][0]['choice']['state'], 'unselected')
                self.assertEqual(self.fixture.project_file.read_bytes(), before)

    def test_legacy_profile_object_remains_supported(self):
        self.fixture.project['profile'] = {'name': 'long'}
        self.fixture.write()
        self.assertEqual(self.finalize()['per_keyword_cap'], 2)

    def test_absent_profile_uses_timeline_and_explicit_format_has_precedence(self):
        self.fixture.project.pop('profile', None)
        self.fixture.write()
        self.assertEqual(self.finalize()['content_format'], 'short')
        self.fixture.project.update(profile='short', content_format='long')
        self.fixture.write()
        self.assertEqual(self.finalize()['content_format'], 'long')

    def test_real_write_outputs_boundary_with_string_profile_can_finish_and_repeat(self):
        project = copy.deepcopy(self.fixture.project)
        project.update(profile='short', review_options=True, options_per_moment=5)
        project['timeline']['xml_path'] = str(self.fixture.root / 'source-timeline.xml')
        project['slots'][0]['chosen']['title'] = 'Synthetic component video'
        project['slots'][0]['clip'] = project['slots'][0]['chosen']['clip']
        timeline = SimpleNamespace(name='synthetic')
        xml = self.fixture.root / 'BROLL_SEQUENCE.xml'
        # Only host/render boundaries are replaced. The producer saves the real
        # project JSON, invokes the real finalizer, and builds the real typed bank.
        with patch('hinglish_broll.pipeline.parse_xmeml', return_value=timeline), \
             patch('hinglish_broll.pipeline.export_broll_xml', return_value=xml), \
             patch('hinglish_broll.options.export_xml'), \
             patch('hinglish_broll.pipeline.write_report'), \
             patch('hinglish_broll.candidate_manifest.local_video_metadata', self.reader), \
             patch.dict(sys.modules, {
                 'hinglish_zoom.xml_apply': SimpleNamespace(Sequence=Mock(return_value=SimpleNamespace(frames=0))),
                 'hinglish_zoom.preview': SimpleNamespace(render_preview=Mock())}):
            pipeline.write_outputs(self.fixture.root, self.fixture.root, project)
            first = (self.fixture.root / 'BROLL_CANDIDATES.v1.json').read_bytes()
            pipeline.write_outputs(self.fixture.root, self.fixture.root, project)
        self.assertEqual((self.fixture.root / 'BROLL_CANDIDATES.v1.json').read_bytes(), first)
        self.assertEqual(json.loads(first)['content_format'], 'short')
        self.assertFalse((self.fixture.root / 'BROLL_OWNER_SELECTIONS.v1.json').exists())


if __name__ == '__main__':
    unittest.main()
