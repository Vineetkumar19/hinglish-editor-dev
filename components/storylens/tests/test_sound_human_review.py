import json
from pathlib import Path
from unittest.mock import patch

import unittest
import tempfile

from hinglish_sound.human_review import build, bind_timeline, apply
from hinglish_sound.library import Asset
from hinglish_sound.pipeline import selection_order


def fixture(tmp_path):
    import soundfile as sf
    import numpy as np
    p=tmp_path/'water.wav'
    sf.write(p,np.sin(np.arange(48000)*.02)*.1,48000)
    a=Asset(str(p),'sfx','foley','Water','water',1.,-20.,.1)
    m={'type':'foley','intent':'Water splash','target':0.,'duration':1.}
    review=build([m],[[{'asset':a,'doc':'water recording'}]],{'effects':[{'moment':0,'choice':0,'alternatives':[]}]})
    return {'seconds':4.,'human_review':review,'settings':{}}


def test_human_choice_never_falls_back():
    assert selection_order(2,6,True)==[2]
    assert selection_order(-1,6,True)==[]
    assert selection_order(2,6,False)==[2,0,1,3,4,5]


def test_human_review_keeps_all_candidates_and_marks_provenance(tmp_path):
    plan=fixture(tmp_path);review=plan['human_review']
    cue={'path':review['events'][0]['candidates'][0]['asset']['path'],'target':0.,'time':0.,'length':.8,'offset_db':-4.}
    bind_timeline(review,[cue])
    assert review['selections'][0]['duration']==.8
    assert review['events'][0]['candidates'][0]['recommendation']=='Qwen first choice'


def test_literal_human_timing_level_and_no_inference(tmp_path):
    plan=fixture(tmp_path)
    with patch('hinglish_sound.brain.Brain.ask',side_effect=AssertionError('No model allowed')):
        out=apply(plan,[dict(event='event-0',candidate='choice-0',start=2.,duration=.8,level_db=-3.)])
    c=out['cues'][0]
    assert (c['time'],c['length'],c['offset_db'])==(2.,.8,-3.)
    assert c['source']=='human_review'


def test_invalid_review_is_rejected_without_modifying_plan(tmp_path,change):
    p=fixture(tmp_path);before=json.dumps(p)
    s=dict(event='event-0',candidate='choice-0',start=0.,duration=.8,level_db=-3.);s.update(change)
    with unittest.TestCase().assertRaises(ValueError):apply(p,[s])
    assert json.dumps(p)==before


def test_empty_selection_keeps_no_effects(tmp_path):
    assert apply(fixture(tmp_path),[])['cues']==[]


class ReviewTests(unittest.TestCase):
    def test_human_policy(self): test_human_choice_never_falls_back()
    def test_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            test_human_review_keeps_all_candidates_and_marks_provenance(p)
            test_literal_human_timing_level_and_no_inference(p)
            test_empty_selection_keeps_no_effects(p)
            for change in [{'start':float('nan')},{'duration':4.},{'candidate':'../../secret'},{'level_db':100}]:
                test_invalid_review_is_rejected_without_modifying_plan(p,change)

    def test_aftereffects_has_independent_stems_and_option_bin(self):
        from hinglish_sound.editors import aftereffects_script
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);plan=folder/'sound-plan.json'
            plan.write_text(json.dumps({'human_review':{'events':[{'candidates':[{'asset':{'path':'option.wav'}}]}]}}))
            spec={'width':1280,'height':720,'duration':3000000,'fps':30,'clips':[],
                  'audio_layers':[{'path':'stem.wav','start':500000,'duration':1000000,'source_in':0}],
                  'mute_source_audio':True}
            with patch('hinglish_sound.editors.capcut_spec',return_value=spec), patch('hinglish_sound.keyword_folders.package',return_value=None):
                result=aftereffects_script(plan,folder/'sound.jsx')
            script=Path(result).read_text()
            self.assertIn('Sound options - not on timeline',script)
            self.assertIn('"audio_layers": [{"path": "stem.wav"',script)
            self.assertIn('setValue([0,0])',script)
