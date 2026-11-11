import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET

from hinglish_sound.keyword_folders import organize,folder_name,premiere_project
from hinglish_sound.human_review import apply
from tests.test_sound_human_review import fixture


class KeywordFolderTests(unittest.TestCase):
    def test_merge_preserves_occurrences_and_expands_options_without_touching_selections(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan=fixture(Path(tmp));review=plan['human_review'];first=review['events'][0]
            first['keyword']='Walking in water';second=copy.deepcopy(first)
            second.update(id='event-1',time=2,keyword='walking in water')
            second['candidates'][0]['asset']['path']=str(Path(tmp)/'other.wav')
            review['events'].append(second);review['selections']=[dict(event='event-0',candidate='choice-0',start=0,duration=.5,level_db=-4)]
            before=copy.deepcopy(review['selections']);groups=organize(review)
            self.assertEqual(len(groups),1);self.assertEqual(len(groups[0]['candidates']),2)
            self.assertEqual(len(first['candidates']),2);self.assertEqual(review['selections'],before)
            self.assertEqual(groups,organize(review))

    def test_paths_cannot_escape_package_or_use_device_names(self):
        self.assertEqual(folder_name('../../Water: splash'), 'Water splash')
        self.assertEqual(folder_name('CON'),'_CON')

    def test_real_audio_package_and_project_keep_draft_and_full_sources_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);plan=fixture(folder)
            plan['human_review']['events'][0]['keyword']='Walking in water'
            plan['cues']=[{'time':0,'length':.2}]
            path=folder/'sound-plan.json';path.write_text(json.dumps(plan),encoding='utf-8')
            (folder/'SOUND_SEQUENCE.xml').write_text('<xmeml version="4"><sequence id="draft"><name>Draft</name><duration>120</duration><rate><timebase>30</timebase><ntsc>FALSE</ntsc></rate><media><audio><track/></audio></media></sequence></xmeml>')
            result=ET.parse(premiere_project(path)).getroot()
            self.assertEqual(result.findtext('./project/children/bin/name'),'Sound Design')
            self.assertEqual(result.findtext('.//bin/children/bin/name'),'Walking in water')
            self.assertEqual(result.findtext('.//bin/children/bin/children/clip/duration'),'30')
            self.assertEqual(len(result.findall('.//sequence')),1)
            self.assertEqual(result.findtext('.//sequence/marker/name'),'Walking in water')
            self.assertEqual(json.loads(path.read_text())['cues'],plan['cues'])
            self.assertTrue((folder/'sound-keyword-folders.zip').exists())

    def test_picker_offers_twenty_and_keyword_without_secondary_judge(self):
        from hinglish_sound.director import pick
        class Brain:
            def ask(self,system,data,schema,**kwargs):
                self.schema=schema;self.system=system
                return {'effects':[{'moment':0,'choice':0,'why':'water','alternatives':list(range(1,20)),'keyword':'Walking in water'}],'music':[]}
        brain=Brain();moment=dict(line_text='walk',word='walk',type='foley',intent='wet footsteps')
        with patch('hinglish_sound.director.guard.ask_checked',side_effect=lambda ask,system,data,schema,*a,**kw:ask(system,data,schema)):
            result=pick(brain,'walking','calm',[moment],[[{'doc':'water'}]*20],[],[],human_review=True)
        self.assertEqual(len(result['effects'][0]['alternatives']),19)
        self.assertIn('keyword',brain.schema['properties']['effects']['items']['required'])

