"""Synthetic candidate/controller XML checks; no model or native host success."""
import json
import tempfile
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET
from unittest.mock import patch

from tests.test_broll_candidate_manifest import CandidateManifestTests


class PanelBrollChoiceTests(unittest.TestCase):
    def setUp(self):
        self.fixture=CandidateManifestTests();self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root=self.fixture.root
        codec=patch('hinglish_app.panel_broll_choices.video_codec',return_value='h264')
        codec.start();self.addCleanup(codec.stop)
        self.manifest=self.fixture.build()
        self.timeline=self.root/'source-timeline.xml'
        self.timeline.write_text('''<xmeml version="5"><sequence id="source"><name>Original</name>
          <duration>360</duration><rate><timebase>30</timebase><ntsc>FALSE</ntsc></rate>
          <media><video><format><samplecharacteristics><width>1080</width><height>1920</height></samplecharacteristics></format>
          <track><clipitem id="keep-camera"><start>0</start><end>360</end><in>0</in><out>360</out>
          <file id="camera"><pathurl>file:///camera.mp4</pathurl></file></clipitem></track></video>
          <audio><track><clipitem id="keep-audio"><start>0</start><end>360</end></clipitem></track></audio></media></sequence></xmeml>''')
        project=json.loads(self.fixture.project_file.read_text())
        project['timeline']['xml_path']=str(self.timeline)
        self.fixture.project_file.write_text(json.dumps(project))
        from hinglish_broll.candidate_manifest import build_manifest
        self.manifest=build_manifest(self.fixture.project_file,content_format='short',bank_id='fixture-bank',media_reader=lambda p:self.fixture.metadata[str(p)])

    def test_no_machine_suggestion_is_inserted_without_explicit_choice(self):
        from hinglish_app.panel_broll_choices import handoff
        with self.assertRaisesRegex(ValueError,'Choose'):
            handoff(self.root,self.manifest,'premiere',{})

    def test_report_click_resolves_only_an_offered_source_to_its_typed_identity(self):
        from hinglish_app.panel_broll_choices import report_request
        slot=self.manifest['slots'][0];candidate=slot['candidates'][0]
        value={'folder':str(self.fixture.project_file.parent),'project':str(self.fixture.project_file),
               'slot_index':slot['slot_index'],'source_id':candidate['candidate_id']}
        with patch('hinglish_app.panel_broll_choices.load_bank',return_value=self.manifest):
            result=report_request(self.root,value,'short')
            self.assertEqual(result['slot_id'],slot['id']);self.assertEqual(result['candidate_id'],candidate['id'])
            cleared=report_request(self.root,{**value,'state':'no_broll','source_id':''},'short')
            self.assertEqual(cleared['state'],'no_broll');self.assertIsNone(cleared['candidate_id'])
            with self.assertRaises(ValueError):report_request(self.root,{**value,'source_id':'unoffered'},'short')
            with self.assertRaises(ValueError):report_request(self.root,{**value,'slot_index':'0'},'short')

    def test_selected_prepared_trim_anchor_and_original_handles_are_preserved(self):
        from hinglish_app.panel_broll_choices import handoff
        from hinglish_broll.candidate_selection import choose
        slot=self.manifest['slots'][0]
        selected=choose(self.manifest,slot['id'],'selected',slot['candidates'][0]['id'])
        before=self.timeline.read_bytes()
        result=handoff(self.root,selected,'premiere',{'project_id':'owner','sequence_id':'source'})
        tree=ET.parse(result['paths'][0]);track=tree.findall('.//sequence/media/video/track')[1]
        item=track.find('clipitem')
        self.assertEqual([int(item.findtext(k))for k in ('start','end','in','out')],[64,93,90,119])
        self.assertIn('preview-0.mp4',item.findtext('file/pathurl'))
        self.assertEqual(int(item.findtext('file/duration')),240)
        self.assertIsNotNone(tree.find(".//clipitem[@id='keep-camera']"))
        self.assertIsNotNone(tree.find(".//clipitem[@id='keep-audio']"))
        self.assertEqual(result['expected'],{'project_id':'owner','sequence_id':'source'})
        self.assertIn(str(self.root/'raw-0.mp4'),result['paths'])
        self.assertEqual(self.timeline.read_bytes(),before)
        self.assertEqual(handoff(self.root,selected,'premiere',{})['paths'],result['paths'])

    def test_changed_selected_media_blocks_native_handoff(self):
        from hinglish_app.panel_broll_choices import handoff
        from hinglish_broll.candidate_selection import choose
        slot=self.manifest['slots'][0]
        selected=choose(self.manifest,slot['id'],'selected',slot['candidates'][0]['id'])
        (self.root/'raw-0.mp4').write_bytes(b'CHANGED SYNTHETIC SOURCE')
        with self.assertRaises(ValueError):handoff(self.root,selected,'premiere',{})

    def test_unsupported_optional_original_stays_external_with_a_new_handoff_version(self):
        from hinglish_app.panel_broll_choices import handoff
        from hinglish_broll.candidate_selection import choose
        slot=self.manifest['slots'][0];selected=choose(self.manifest,slot['id'],'selected',slot['candidates'][0]['id'])
        original=self.root/'raw-0.mp4';before=original.read_bytes()
        prior=handoff(self.root,selected,'premiere',{});old_receipt=Path(prior['paths'][0]).with_suffix('.json');old_bytes=old_receipt.read_bytes()
        with patch('hinglish_app.panel_broll_choices.video_codec',side_effect=lambda p:'libdav1d' if str(p)==str(original) else 'h264'):
            result=handoff(self.root,selected,'premiere',{})
        self.assertNotEqual(result['selection_id'],prior['selection_id'])
        self.assertNotIn(str(original),result['paths']);self.assertEqual(result['external_references'][0]['original']['path'],str(original))
        self.assertEqual(result['external_references'][0]['codec'],'libdav1d');self.assertIn('full-original',result['notice'])
        tree=ET.parse(result['paths'][0]);item=tree.findall('.//sequence/media/video/track')[1].find('clipitem')
        self.assertEqual([int(item.findtext(k)) for k in ('start','end','in','out')],[64,93,90,119])
        self.assertEqual(original.read_bytes(),before);self.assertEqual(old_receipt.read_bytes(),old_bytes)

    def test_unsupported_original_never_waives_prepared_media_compatibility(self):
        from hinglish_app.panel_broll_choices import handoff
        from hinglish_broll.candidate_selection import choose
        slot=self.manifest['slots'][0];selected=choose(self.manifest,slot['id'],'selected',slot['candidates'][0]['id'])
        with patch('hinglish_app.panel_broll_choices.video_codec',return_value='libdav1d'):
            with self.assertRaisesRegex(ValueError,'H264'):handoff(self.root,selected,'premiere',{})

    def test_path_boundary_does_not_accept_arbitrary_or_sibling_projects(self):
        from hinglish_app.panel_broll_choices import project_path
        with self.assertRaises(ValueError):project_path(self.root,self.root/'other',self.fixture.project_file)
        folder=self.root/'output/broll/result';folder.mkdir(parents=True)
        with self.assertRaises(ValueError):project_path(self.root,folder,self.fixture.project_file)

    def test_cards_use_the_checked_anchor_and_keep_unbound_choices_disabled(self):
        from hinglish_app.panel_broll_choices import cards
        folder=self.root/'output/broll/result';folder.mkdir(parents=True)
        (folder/'broll-project.json').write_text('{}')
        self.manifest['slots'][0]['candidates'][0]['selectable']=False
        with patch('hinglish_app.panel_broll_choices.load_bank',return_value=self.manifest):
            rows=cards(self.root,folder,'short')
        self.assertEqual(rows[0]['start'],64/30)
        self.assertEqual(rows[0]['end'],93/30)
        self.assertFalse(rows[0]['selectable'])
        self.assertEqual(rows[1]['candidate_id'],self.manifest['slots'][0]['candidates'][1]['id'])

    def test_rejected_options_keep_the_actionable_failure_in_the_panel(self):
        from hinglish_app.panel_broll_choices import cards
        folder=self.root/'output/broll/result';folder.mkdir(parents=True)
        (folder/'broll-project.json').write_text('{}')
        slot=self.manifest['slots'][0];slot['candidates']=[]
        slot['rejected_candidates']=[{'issue':{'message':'The saved duration exceeds this file.','details':'Measured source bounds differ'}}]
        with patch('hinglish_app.panel_broll_choices.load_bank',return_value=self.manifest):
            rows=cards(self.root,folder,'short')
        self.assertIn('duration',rows[0]['issue']['message'])
        self.assertIn('bounds',rows[0]['issue']['details'])

    def test_panel_reuses_the_producer_owner_sidecar_and_bank_identity(self):
        from hinglish_app.panel_broll_choices import load_bank
        folder=self.root/'output/broll/result';folder.mkdir(parents=True)
        (folder/'broll-project.json').write_text('{}')
        canonical=folder/'BROLL_OWNER_SELECTIONS.v1.json';canonical.write_text('{}')
        with patch('hinglish_broll.candidate_selection.load_selections',return_value={'saved':'decision'}) as previous, \
             patch('hinglish_broll.candidate_manifest.build_manifest',return_value=self.manifest) as build:
            load_bank(self.root,folder,'broll-project.json','short')
        previous.assert_called_once_with(canonical)
        self.assertNotIn('bank_id',build.call_args.kwargs)
        self.assertEqual(build.call_args.kwargs['previous'],{'saved':'decision'})

