"""Synthetic tiny WAV review/transport checks; no local-model/native acceptance."""
import copy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from tests import test_sound_audition as fixtures


class PanelSoundReviewTests(unittest.TestCase):
    def setUp(self):
        self.fx=fixtures.AuditionTests();self.fx.setUp();self.addCleanup(self.fx.doCleanups)
        self.job={'id':'actual-sound','mode':'sound','status':'complete','result':{'folder':str(self.fx.job),
            'sound_recommendations':{'status':'ready','manifest_path':str(self.fx.path),'manifest_sha256':self.fx.sha}}}
        self.state=SimpleNamespace(root=self.fx.root,snapshot=lambda key:copy.deepcopy(self.job) if key==self.job['id'] else None)

    def test_describe_keeps_ranked_time_windows_without_an_automatic_winner(self):
        from hinglish_app.panel_sound_review import describe
        result=describe(self.state,'actual-sound')
        row=result['groups'][0]['candidates'][0]
        self.assertEqual(row['source_in'],1.);self.assertEqual(row['source_out'],3.)
        self.assertFalse(result['auto_insert']);self.assertNotIn('path',row)

    def test_saved_sound_list_uses_only_completed_bound_manifest_jobs(self):
        from hinglish_app.panel_sound_review import saved_results
        rows=saved_results(self.state,[self.job,{**self.job,'status':'running'},{**self.job,'id':'foreign'}])
        self.assertEqual([r['job_id'] for r in rows],['actual-sound'])
        self.fx.path.write_text('{}');self.assertEqual(saved_results(self.state,[self.job]),[])

    def test_explicit_original_import_is_verified_bin_only_and_keeps_window_metadata(self):
        from hinglish_app.panel_sound_review import original
        result=original(self.state,'actual-sound',self.fx.candidate['id'],{'project_id':'owner','sequence_id':'source'})
        self.assertEqual(result['manifest']['paths'],[self.fx.candidate['source']['path']])
        self.assertFalse(result['manifest']['insert']);self.assertTrue(result['manifest']['source_assets'])
        self.assertEqual(result['source_window'],{'in':1.,'out':3.})
        self.assertEqual(result['manifest']['expected']['project_id'],'owner')

    def test_audition_uses_only_the_saved_job_manifest_and_explicit_id(self):
        from hinglish_app.panel_sound_review import audition
        with patch('hinglish_sound.audition.prepare',return_value={'status':'ready','id':'a'*64}) as prepare:
            result=audition(self.state,'actual-sound',self.fx.candidate['id'])
        self.assertEqual(result['id'],'a'*64)
        self.assertEqual(prepare.call_args.args[1:4],(self.fx.path,self.fx.sha,self.fx.candidate['id']))

    def test_changed_manifest_is_rejected_before_audition_or_original_import(self):
        from hinglish_app.panel_sound_review import audition
        self.fx.path.write_text('{}')
        with patch('hinglish_sound.audition.prepare') as prepare:
            with self.assertRaisesRegex(ValueError,'changed'):audition(self.state,'actual-sound',self.fx.candidate['id'])
        prepare.assert_not_called()

    def test_media_reads_only_the_bound_prepared_audition_and_rejects_changed_bytes(self):
        from hinglish_app.panel_sound_review import preview
        result=self.fx.call();self.assertEqual(result['status'],'ready')
        served=preview(self.state,'actual-sound',result['id'])
        self.assertEqual(served['path'],result['preview']['path']);self.assertEqual(served['mime'],'audio/wav')
        from pathlib import Path
        Path(served['path']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'changed'):preview(self.state,'actual-sound',result['id'])

    def test_generic_import_cannot_mislabel_an_audition_as_the_original_sound(self):
        from hinglish_app.editor_panel import prepare_import
        audition=self.fx.call();self.assertEqual(audition['status'],'ready')
        with self.assertRaisesRegex(ValueError,'checked sound'):
            prepare_import(self.fx.root,'premiere',self.fx.job,asset=audition['preview']['path'])
