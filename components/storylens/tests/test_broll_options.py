import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from tests.test_broll_media import fake_video
from hinglish_cut.model import Media,Cut
from hinglish_cut.xml_export import export_xml
from hinglish_broll.options import export_xml as export_options


class HumanChoiceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.folder=Path(self.temp.name)
        self.base=self.folder/'speech.mp4';fake_video(self.base,seconds=4,fps=25,width=64,height=96)
        for name in ('option-a.mp4','option-b.mp4'):fake_video(self.folder/name,seconds=2,fps=25,width=64,height=96)
        media=Media('speech',str(self.base),4,'25',64,96,2,48000)
        xml=self.folder/'source-timeline.xml';export_xml(xml,[Cut('speech',0,100,0)],{'speech':media})
        opts=[{'id':name,'source':'pixabay','title':name,'clip':name,'path':str(self.folder/name),
               'source_in':.2,'source_duration':2.,'score':.4,'review_note':'Related option','kind':'video'}
              for name in ('option-a.mp4','option-b.mp4')]
        self.project={'review_options':True,'requested_count':1,'timeline':{'xml_path':str(xml),'name':'Speech',
            'duration':4,'fps':'25','width':64,'height':96},'slots':[{'index':0,'start':1.,'end':2.,
            'text':'people sleeping','visual':'person asleep','queries':['person asleep'],'chosen':opts[0],
            'clip':'option-a.mp4','source_in':.2,'source_duration':2.,'options':opts,'alternatives':opts}]}
        self.file=self.folder/'broll-project.json';self.file.write_text(json.dumps(self.project))

    def test_review_and_xml_keep_both_playable_options_with_speech_time_labels(self):
        from hinglish_broll.report import write_report
        export_options(self.project,self.folder)
        items=ET.parse(self.folder/'BROLL_OPTIONS.xml').findall('.//clipitem')
        self.assertEqual(len(items),2)
        self.assertTrue(all('01.00s | people sleeping | option' in n.findtext('name') for n in items))
        write_report(self.folder/'report.html',self.project)
        html=(self.folder/'report.html').read_text('utf-8')
        self.assertIn('2 playable videos',html)
        self.assertIn('option-b.mp4',html)
        self.assertIn('Use option 2',html)

    def test_premiere_project_bin_contains_unselected_option_and_only_one_timed_overlay(self):
        from hinglish_broll.premiere import export
        result=export(self.file,self.folder/'choices.prproj')
        tree=ET.fromstring(gzip.decompress(Path(result).read_bytes()))
        names=[n.findtext('ProjectItem/Name','') for n in tree if n.tag=='ClipProjectItem']
        self.assertTrue(any('option 1' in n for n in names),names)
        self.assertTrue(any('option 2' in n for n in names),names)
        group=next(n for n in tree if n.get('ObjectID')=='164').find('TrackGroup/Tracks')
        self.assertEqual(len(group),2)
        lane=next(n for n in tree if n.get('ObjectUID')==group[1].get('ObjectURef'))
        self.assertEqual(len(lane.findall('ClipTrack/ClipItems/TrackItems/TrackItem')),1)

    def test_capcut_keeps_base_overlay_and_all_options_separate(self):
        from hinglish_broll.capcut import spec
        from hinglish_app.capcut_adapter import create_project
        timeline=spec(self.file)
        self.assertEqual(len(timeline['options']),2)
        self.assertGreater(timeline['options'][0]['start'],4_000_000)
        with patch('hinglish_app.capcut_adapter.settings',return_value=(self.folder,self.folder/'drafts')):
            result=create_project(self.folder,self.base,'Choices','test',timeline=timeline)
        draft=json.loads((Path(result['folder'])/'draft_content.json').read_text('utf-8'))
        self.assertEqual([len(t['segments']) for t in draft['tracks']],[1,1,2])
        self.assertEqual(draft['tracks'][0]['segments'][0]['target_timerange']['duration'],4_000_000)
        self.assertTrue(all(c['volume']==0 for t in draft['tracks'][1:] for c in t['segments']))

    def test_selected_only_capcut_has_exact_timestamps_and_no_choice_deck(self):
        from hinglish_broll.capcut import spec
        from hinglish_app.capcut_adapter import create_project
        timeline=spec(self.file,include_options=False)
        self.assertEqual(timeline['options'],[])
        self.assertEqual(timeline['duration'],4_000_000)
        with patch('hinglish_app.capcut_adapter.settings',return_value=(self.folder,self.folder/'drafts')):
            result=create_project(self.folder,self.base,'Selected','selected-test',timeline=timeline)
        draft=json.loads((Path(result['folder'])/'draft_content.json').read_text('utf8'))
        self.assertEqual([len(t['segments']) for t in draft['tracks']],[1,1])
        clip=draft['tracks'][1]['segments'][0]
        self.assertEqual(clip['target_timerange'],{'start':1_000_000,'duration':1_000_000})
        self.assertEqual(clip['source_timerange'],{'start':200_000,'duration':1_000_000})

    def test_selected_only_premiere_keeps_saved_time_and_trim_without_unused_media(self):
        from hinglish_broll.premiere import export
        from hinglish_app.premiere_captions import TICKS
        result=export(self.file,self.folder/'selected.prproj',include_options=False)
        tree=ET.fromstring(gzip.decompress(Path(result).read_bytes()))
        names=[n.findtext('ProjectItem/Name','') for n in tree if n.tag=='ClipProjectItem']
        self.assertFalse(any('option 2' in n for n in names))
        group=next(n for n in tree if n.get('ObjectID')=='164').find('TrackGroup/Tracks')
        lane=next(n for n in tree if n.get('ObjectUID')==group[1].get('ObjectURef'))
        ref=lane.find('ClipTrack/ClipItems/TrackItems/TrackItem').get('ObjectRef')
        item=next(n for n in tree if n.get('ObjectID')==ref)
        self.assertEqual(item.findtext('ClipTrackItem/TrackItem/Start'),str(TICKS))
        self.assertEqual(item.findtext('ClipTrackItem/TrackItem/End'),str(2*TICKS))
        sub=next(n for n in tree if n.get('ObjectID')==item.find('ClipTrackItem/SubClip').get('ObjectRef'))
        clip=next(n for n in tree if n.get('ObjectID')==sub.find('Clip').get('ObjectRef'))
        self.assertEqual(int(clip.findtext('Clip/InPoint')),round(.2*TICKS))

    def test_chat_planner_passes_five_options_per_keyword(self):
        from hinglish_app.assistant_plan import validate_plan,job_payload
        plan=validate_plan({'reply':'Collect choices','question':'','steps':[{'tool':'broll','options':{
            'broll_review_options':True,'broll_count':10,'broll_options_per_moment':5,'broll_brief':'Find related videos'}}]})
        payload=job_payload(plan['steps'][0],[])
        self.assertEqual(payload['broll_options_per_moment'],5)
        self.assertEqual(payload['broll_count'],10)
        self.assertTrue(payload['broll_review_options'])
        alias=job_payload({'tool':'broll','options':{'visuals_black_background':True}},[])
        self.assertTrue(alias['broll_black_background'])

    def test_more_than_five_is_rejected_before_any_model_or_download(self):
        from hinglish_app.assistant_plan import validate_plan
        from hinglish_broll.pipeline import run
        for amount in (6,20):
            with self.assertRaisesRegex(ValueError,'broll_options_per_moment'):
                validate_plan({'steps':[{'tool':'broll','options':{'broll_options_per_moment':amount}}]})
            with self.assertRaisesRegex(ValueError,'between 1 and 5'):
                run(self.folder,self.base,review_options=True,options_per_moment=amount)
