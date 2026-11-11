import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from hinglish_visuals.evaluator import decide, Verdict
from hinglish_visuals.references import collect
from hinglish_visuals.web import Entity, Media


class ReferenceTests(unittest.TestCase):
    def test_evidence_capture_uses_document_rules_instead_of_the_photo_screenshot_ban(self):
        from hinglish_visuals.evaluator import Evaluator
        class Model:
            name='local test vision'
            def look(self,images,system,schema=None):
                self.system=system
                return {'category_ok':True,'identity':'yes','fits_moment':True,'quality_ok':True,
                    'seen':'A real scorecard table naming the teams and scores'}
        model=Model();evaluator=Evaluator(model,None,lambda _:None)
        info={'name':'IPL','kind':'event','show':'photo','visual':'KKR championship records',
            'category':'standings table','strict_context':True,'document_evidence':True}
        self.assertTrue(evaluator._check([Image.new('RGB',(400,300))],info,'a picture','photo').passed)
        self.assertIn('ARE allowed',model.system)
        self.assertNotIn('Fail it for',model.system)

    def test_team_context_accepts_short_aliases_and_authoritative_franchise_description(self):
        from hinglish_visuals.references import context_info
        p={'summary':{},'slots':[],'entities':{'rohit':Entity('rohit','Rohit Sharma','person').to_dict(),
            'mi':Entity('mi','Mumbai Indians','place',label='Mumbai Indians',aliases=['MI'],
                description='Mumbai based franchise of the Indian Premier League').to_dict()}}
        entry={'entity':'rohit','label':'Rohit Sharma','show':'photo','visual':'Rohit Sharma in MI jersey',
            'text':'Rohit MI','meaning':'Rohit playing for MI','reference_type':'identity'}
        self.assertEqual(context_info(entry,p)['required_team'],'Mumbai Indians')

    def test_uniform_check_requires_the_actual_team_not_merely_the_person(self):
        from hinglish_visuals.evaluator import team_matches, Evaluator
        self.assertFalse(team_matches({'team':'India','confidence':'clear'},['Kolkata Knight Riders','KKR']))
        self.assertFalse(team_matches({'team':'KKR','confidence':'uncertain'},['Kolkata Knight Riders','KKR']))
        self.assertTrue(team_matches({'team':'KKR','confidence':'clear'},['Kolkata Knight Riders','KKR']))
        class Model:
            name='local test vision'
            def look(self,images,system,schema=None):
                if schema:
                    return {'team':'India','crest':'BCCI','visible_text':'INDIA','confidence':'clear'}
                return {'category_ok':True,'identity':'yes','fits_moment':True,'quality_ok':True,'seen':'Gambhir'}
        evaluator=Evaluator(Model(),None,lambda _:None)
        info={'name':'Gautam Gambhir','kind':'person','show':'photo','category':'person',
            'visual':'Gambhir in KKR kit','strict_context':True,'required_team':'Kolkata Knight Riders',
            'team_aliases':['Kolkata Knight Riders','KKR']}
        verdict=evaluator._check([Image.new('RGB',(300,400))],info,'a picture','photo')
        self.assertFalse(verdict.passed)
        self.assertIn('TEAM:',verdict.reasons[-1])

    def test_hindi_names_and_team_acronyms_keep_subject_identity(self):
        from hinglish_eval.model_rules import sounds_like
        for said,name in [('मुंबई','Mumbai Indians'),('सीएसके','Chennai Super Kings'),
                          ('CSK','Chennai Super Kings'),('MI','Mumbai Indians'),
                          ('विराट कोहली','Virat Kohli'),('रोहित','Rohit Sharma')]:
            self.assertTrue(sounds_like(said,name),(said,name))
        self.assertFalse(sounds_like('रात','Virat Kohli'))

    def test_cricket_hint_rejects_same_named_person_from_another_profession(self):
        from hinglish_visuals.planner import resolve_entity
        class Web:
            def search_entities(self,*args):
                return [{'id':'Q1','label':'Karen Pollard','description':'New Zealand astronomer'}]
        self.assertIsNone(resolve_entity(None,Web(),{'key':'pollard','name':'Karen Pollard',
            'kind':'person','about':'IPL cricket player'}, {'topic':'2013 IPL final'}))

    def test_correct_player_in_wrong_kit_is_rejected_and_unsure_is_not_approved(self):
        info = {'name':'Virat Kohli','kind':'person','show':'photo','category':'cricket player',
            'visual':'Virat Kohli playing for RCB in IPL','strict_context':True}
        answer = {'category_ok':True,'category_seen':'cricket player','identity':'yes',
            'fits_moment':False,'quality_ok':True,'seen':'Kohli in India blue jersey'}
        self.assertFalse(decide(answer, info).passed)
        answer.update(fits_moment=True,identity='unsure')
        self.assertFalse(decide(answer, info).passed)
        answer['identity']='yes'
        self.assertTrue(decide(answer, info).passed)

    def test_choices_are_downloaded_unique_checked_capped_and_not_auto_selected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);folder=root/'output';folder.mkdir()
            candidates=[]
            for i in range(8):
                path=root/f'{i}.png';Image.new('RGB',(320,400),(i*25,80,150)).save(path)
                candidates.append(Media('image','web',str(i),'Kohli RCB photo',
                    'https://example.com/'+str(i),page_url='https://example.com/source',path=str(path)))
            # One actual duplicate and one correct player in the wrong uniform.
            candidates[1].path=candidates[0].path
            entity=Entity('kohli','Virat Kohli','person')
            entry={'index':0,'start':0.,'end':2.,'text':'Kohli plays for RCB','quote':'Kohli',
                'meaning':'Kohli in RCB kit','visual':'Virat Kohli RCB','queries':['Virat Kohli RCB'],
                'priority':3,'entity':'kohli','label':'Virat Kohli','show':'photo','display':'popup',
                'category':'cricket player','reference_type':'identity','evidence_terms':[],
                'chosen':None,'clip':None,'evaluation':None,'rejected':[],'options':[],'alternatives':[]}
            project={'slots':[entry],'summary':{'topic':'IPL'},'entities':{'kohli':entity.to_dict()}}
            class Evaluator:
                vlm=True
                def image(self,path,info):
                    self_info=info['strict_context'] and 'RCB' in info['context']
                    passed=Path(path).name!='2.png' and self_info
                    return Verdict(passed,1. if passed else 0., seen='RCB player' if passed else 'India jersey')
            with patch('hinglish_visuals.references.gather',return_value=candidates), \
                 patch('hinglish_visuals.references.judge',side_effect=lambda b,m,e,c,**kw:c), \
                 patch('hinglish_visuals.pipeline.write_outputs'),patch('hinglish_visuals.report.write_report'):
                collect(root,[(SimpleNamespace(orientation='portrait',width=720,height=1280),folder,project)],
                    None,SimpleNamespace(session=None),None,SimpleNamespace(vision_check_model='local'),
                    lambda _:None,Evaluator())
            self.assertEqual(len(entry['options']),5)
            self.assertEqual(len({o['sha256'] for o in entry['options']}),5)
            self.assertIsNone(entry['chosen']);self.assertIsNone(entry['clip'])
            self.assertTrue(all((folder/o['asset']).is_file() for o in entry['options']))
            self.assertNotIn('2',[o['id'] for o in entry['options']])
            self.assertTrue((folder/'visuals-project.json').is_file())
            entry['options'] = []
            entry['alternatives'] = []
            with patch('hinglish_visuals.references.gather') as search, \
                 patch('hinglish_visuals.pipeline.write_outputs'), patch('hinglish_visuals.report.write_report'):
                collect(root,[(SimpleNamespace(orientation='portrait',width=720,height=1280),folder,project)],
                    None,SimpleNamespace(session=None),None,SimpleNamespace(vision_check_model='local'),
                    lambda _:None,Evaluator())
            search.assert_not_called()
            self.assertEqual(len(entry['options']), 5)

    def test_abrupt_search_interruption_keeps_a_resumable_review_plan(self):
        from hinglish_visuals import pipeline  # initialize its report binding before the isolated mock
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); folder = root/'review'; folder.mkdir()
            entry = {'index':0,'start':0.,'end':2.,'text':'Kohli plays for RCB','quote':'Kohli',
                'meaning':'Kohli in RCB kit','visual':'Virat Kohli RCB','queries':['Virat Kohli RCB'],
                'priority':3,'entity':'kohli','label':'Virat Kohli','show':'photo','display':'popup',
                'category':'cricket player','reference_type':'identity','evidence_terms':[],
                'chosen':None,'clip':None,'evaluation':None,'rejected':[],'options':[],'alternatives':[]}
            project = {'slots':[entry],'summary':{'topic':'IPL'},
                       'entities':{'kohli':Entity('kohli','Virat Kohli','person').to_dict()}}
            with patch('hinglish_visuals.references.gather',side_effect=KeyboardInterrupt), \
                 patch('hinglish_visuals.report.write_report'):
                with self.assertRaises(KeyboardInterrupt):
                    collect(root,[(SimpleNamespace(orientation='portrait',width=720,height=1280),folder,project)],
                        None,SimpleNamespace(session=None),None,SimpleNamespace(vision_check_model='local'))
            saved = json.loads((folder/'visuals-project.json').read_text('utf-8'))
            self.assertTrue(saved['collecting'])
            self.assertEqual(saved['slots'][0]['entity'], 'kohli')
            self.assertEqual(saved['slots'][0]['options'], [])


if __name__=='__main__':unittest.main()
