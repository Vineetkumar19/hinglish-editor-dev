"""Preview policy component tests: synthetic media/checks and mocked render only."""
import copy
import json
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import Mock, patch

from hinglish_broll import pipeline
from hinglish_broll.candidate_selection import choose, save_selections
from tests import test_broll_candidate_manifest as fixtures


class WatchPage(HTMLParser):
    def __init__(self,text):
        super().__init__();self.watch=[];self.save=None;self.feed(text)
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='video' and a.get('class')=='watch':self.watch.append(a)
        if tag=='button' and a.get('id')=='save':self.save=a


class DeferredPreviewTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.CandidateManifestTests();self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.folder=self.fixture.root/'001-source';self.folder.mkdir()
        self.project=copy.deepcopy(self.fixture.project)
        self.project.update(profile='short',review_options=True,audio_only_test=True)
        self.project['timeline']['xml_path']=str(self.fixture.root/'source.xml')
        for option in self.project['slots'][0]['options']:
            before=self.fixture.root/option['clip'];after=self.folder/option['clip']
            after.write_bytes(before.read_bytes())
            self.fixture.metadata[str(after)]=copy.deepcopy(self.fixture.metadata[str(before)])
        self.project['slots'][0]['chosen']['title']='Synthetic preview fixture'
        self.project['slots'][0]['clip']=self.project['slots'][0]['chosen']['clip']
        self.project['slots'][0].update(alternatives=[],queries=['room interior'])
        self.source=self.fixture.root/'audio-only-source.mp4';self.source.write_bytes(b'SYNTHETIC ORIGINAL AUDIO OVER BLACK')
        self.messages=[]
        def render(seq,scales,faces,target,**kwargs):Path(target).write_bytes(b'SYNTHETIC AGGREGATE PREVIEW')
        self.render=Mock(side_effect=render)
        self.reader=lambda p:self.fixture.metadata[str(p)]

    def outputs(self,defer=True):
        timeline=SimpleNamespace(name='synthetic')
        with patch('hinglish_broll.pipeline.parse_xmeml',return_value=timeline), \
             patch('hinglish_broll.pipeline.export_broll_xml',return_value=self.folder/'BROLL_SEQUENCE.xml'), \
             patch('hinglish_broll.options.export_xml'), \
             patch('hinglish_broll.candidate_manifest.local_video_metadata',self.reader), \
             patch('hinglish_broll.report.app_token',return_value='synthetic-token'), \
             patch('hinglish_broll.report.embed_token',side_effect=lambda page:page), \
             patch.dict(sys.modules,{'hinglish_zoom.xml_apply':SimpleNamespace(Sequence=Mock(return_value=SimpleNamespace(frames=4))),
                                     'hinglish_zoom.preview':SimpleNamespace(render_preview=self.render)}):
            pipeline.write_outputs(self.fixture.root,self.folder,self.project,
                                   defer_review_preview=defer,progress=self.messages.append)
        self.saved=json.loads((self.folder/'broll-project.json').read_text(encoding='utf-8'))
        self.html=(self.folder/'report.html').read_text(encoding='utf-8');self.page=WatchPage(self.html)

    def test_new_unselected_bank_has_real_source_audio_and_checked_options_without_aggregate(self):
        checks=copy.deepcopy(self.project['slots'][0]['checks']);source=self.source.read_bytes()
        self.outputs()
        self.render.assert_not_called()
        self.assertEqual(self.saved['preview_state'],'deferred')
        self.assertFalse(self.saved['preview_requested'])
        self.assertEqual(self.page.watch[0]['src'],'../audio-only-source.mp4')
        self.assertEqual(self.page.watch[0]['data-preview-kind'],'source-audio')
        self.assertNotIn('disabled',self.page.save)
        self.assertEqual(self.source.read_bytes(),source)
        self.assertEqual(self.saved['slots'][0]['checks'],checks)
        self.assertEqual(len(self.saved['slots'][0]['options']),6)
        self.assertIn('preview-0.mp4',self.html)
        manifest=json.loads((self.folder/'BROLL_CANDIDATES.v1.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['slots'][0]['choice']['state'],'unselected')

    def test_explicit_preview_after_deferral_renders_once_and_reports_real_boundaries(self):
        self.outputs();self.outputs(defer=False)
        self.assertEqual(self.render.call_count,1)
        self.assertEqual(self.saved['preview_state'],'ready')
        self.assertTrue(self.saved['preview_requested'])
        self.assertEqual(self.page.watch[0]['src'],'preview.mp4')
        self.assertIn('Rendering the combined B-roll preview',self.messages)
        self.assertIn('Combined B-roll preview ready',self.messages)

    def test_nonreview_output_keeps_aggregate_even_when_defer_is_requested(self):
        self.project['review_options']=False;self.outputs()
        self.assertEqual(self.render.call_count,1)
        self.assertEqual(self.saved['preview_state'],'ready')

    def test_stale_aggregate_file_is_preserved_but_not_shown_as_current(self):
        stale=self.folder/'preview.mp4';stale.write_bytes(b'OLDER PREVIEW')
        self.project['preview_details']='Old failure must not masquerade as current'
        self.outputs()
        self.assertEqual(stale.read_bytes(),b'OLDER PREVIEW')
        self.assertEqual([v['src'] for v in self.page.watch],['../audio-only-source.mp4'])
        self.assertNotIn('preview_details',self.saved)

    def test_saved_explicit_owner_selection_does_not_get_deferred(self):
        self.outputs()
        manifest=json.loads((self.folder/'BROLL_CANDIDATES.v1.json').read_text(encoding='utf-8'))
        slot=manifest['slots'][0];chosen=choose(manifest,slot['id'],'selected',slot['candidates'][0]['id'])
        save_selections(self.folder/'BROLL_OWNER_SELECTIONS.v1.json',chosen)
        self.outputs()
        self.assertEqual(self.render.call_count,1)
        self.assertEqual(self.saved['preview_state'],'ready')
        again=json.loads((self.folder/'BROLL_CANDIDATES.v1.json').read_text(encoding='utf-8'))
        self.assertEqual(again['slots'][0]['choice'],chosen['slots'][0]['choice'])

    def test_no_accessible_source_audio_retains_the_existing_preview_path(self):
        self.source.unlink();self.outputs()
        self.assertEqual(self.render.call_count,1)
        self.assertEqual(self.page.watch[0]['src'],'preview.mp4')

    def test_failed_explicit_render_never_claims_ready_or_plays_stale_aggregate(self):
        self.render.side_effect=RuntimeError('Synthetic preview failure')
        self.outputs(defer=False)
        self.assertEqual(self.saved['preview_state'],'failed')
        self.assertEqual(self.page.watch,[])
        self.assertIn('could not be rendered',self.html)

    def test_run_requests_deferral_through_ordinary_output_boundary_without_models(self):
        from dataclasses import asdict
        from fractions import Fraction
        from hinglish_broll.settings import BrollSettings,profile_for
        source=self.fixture.root/'input.mp4';source.write_bytes(b'SYNTHETIC INPUT NOT DECODED')
        timeline=SimpleNamespace(name='Synthetic',fps=Fraction(30),width=1080,height=1920,duration=12,
            xml_path=self.fixture.root/'source.xml',warnings=[],orientation='portrait',sources=lambda:[str(source)])
        store=SimpleNamespace(output=self.fixture.root,data={'plans':[{'folder':self.folder.name,
            'summary':{},'profile':asdict(profile_for(12)),'slots':[],'phrases':[]}],'jobs':[]},save=Mock())
        (self.folder/'ranked-candidates.json').write_text('{"cached":[]}',encoding='utf-8')
        settings=BrollSettings(use_library=False,use_pexels=False,use_pixabay=True,pixabay_key='synthetic',
                               use_web=False,use_commons=False)
        def outputs(*args,**kwargs):
            (self.folder/'report.html').write_text('Synthetic boundary only',encoding='utf-8')
            return self.folder/'BROLL_SEQUENCE.xml'
        with patch('hinglish_broll.pipeline.load_settings',return_value=settings), \
             patch('hinglish_broll.pipeline.RunStore',return_value=store), \
             patch('hinglish_broll.pipeline.timelines_for',return_value=[(timeline,self.folder)]), \
             patch('hinglish_broll.pipeline.PixabayClient'), \
             patch('hinglish_broll.pipeline.verified_internet_sources',return_value=[]), \
             patch('hinglish_visuals.brain.open_brain') as brain, \
             patch('hinglish_broll.vision.Vision') as vision, \
             patch('hinglish_broll.verify.Checker') as checker, \
             patch('hinglish_broll.pipeline.write_outputs',side_effect=outputs) as writer:
            pipeline.run(self.fixture.root,source,review_options=True,progress=self.messages.append)
        self.assertTrue(writer.call_args.kwargs['defer_review_preview'])
        self.assertTrue(callable(writer.call_args.kwargs['progress']))
        brain.assert_not_called();vision.assert_not_called();checker.assert_not_called()

    def test_explicit_rebuild_preserves_render_default_at_output_boundary(self):
        self.outputs()
        with patch('hinglish_broll.pipeline.parse_xmeml',return_value=SimpleNamespace()), \
             patch('hinglish_broll.pipeline.write_outputs',return_value=self.folder/'BROLL_SEQUENCE.xml') as writer:
            pipeline.rebuild_project(self.folder/'broll-project.json',{},progress=self.messages.append)
        self.assertNotIn('defer_review_preview',writer.call_args.kwargs)
        self.assertTrue(callable(writer.call_args.kwargs['progress']))


if __name__=='__main__':unittest.main()
