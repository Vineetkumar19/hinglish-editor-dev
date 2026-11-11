import json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from hinglish_sound.brain import Brain


class BrainRuntimeTests(unittest.TestCase):
    def test_no_music_request_cannot_generate_music_sections(self):
        from hinglish_sound.director import analysis_schema
        schema=analysis_schema([],['impact','whoosh'])
        self.assertEqual(schema['properties']['music']['maxItems'],0)

    def test_oversized_request_omits_optional_prose_but_keeps_full_creator_and_evidence(self):
        from hinglish_sound.brain import compact_sound_request
        profile={'brief':'Keep every owner preference','references':[{'guide':'full saved creator guidance'}]}
        payload={'creator_profile':profile,'script':'Exact source words','lines':[{'id':7,'time':'1-2s'}],
                 'composition':{'seconds':20,'direction':'Distinct complementary roles','reference_study':{'huge':'optional '*1000}}}
        system='Sound director rules\n[Storylens sound reference study]\nReviewed data.\n'+json.dumps({'prose':'old '*1000})+'\nCreator profile remains authoritative.'
        body={'messages':[{'role':'system','content':system},{'role':'user','content':json.dumps(payload)}],'format':{'type':'object'}}
        result=compact_sound_request(body)
        kept=json.loads(result['messages'][1]['content'])
        self.assertEqual(kept['creator_profile'],profile)
        self.assertEqual(kept['script'],payload['script']);self.assertEqual(kept['lines'],payload['lines'])
        self.assertEqual(kept['composition']['direction'],payload['composition']['direction'])
        self.assertIn('Creator profile remains authoritative.',result['messages'][0]['content'])
        self.assertLess(len(json.dumps(result)),len(json.dumps(body))/2)
        self.assertIn('reference_study',payload['composition'])

    def brain(self,root,response):
        brain=Brain.__new__(Brain);brain.root=root;brain.cache=root/'cache';brain.cache.mkdir()
        brain.model='local14b';brain.url='http://local';brain.progress=lambda _:None
        self.calls=[]
        def post(url,json,timeout):self.calls.append(json);return response
        brain.session=SimpleNamespace(post=post)
        return brain

    def test_sound_requests_honor_disabled_thinking_for_non_thinking_models(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'config.models.local.json').write_text('{"planning_think":false}')
            response=SimpleNamespace(status_code=200,json=lambda:{'message':{'content':'{"answer":"ok"}'}},raise_for_status=lambda:None)
            brain=self.brain(root,response)
            with patch('hinglish_niche.profiles.inject',side_effect=lambda system,data,**kwargs:(system,data)),patch('hinglish_sound.reference_memory.inject',side_effect=lambda system,*args,**kwargs:system),patch('hinglish_cut.model_preferences.configure_request',side_effect=lambda root,body:body):
                brain.ask('Sound director',{},dict(type='object'),think=True)
            self.assertFalse(self.calls[0]['think'])

    def test_model_rejection_keeps_its_real_reason(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            def bare_error():raise ValueError('bare HTTP error')
            response=SimpleNamespace(status_code=400,json=lambda:{'error':'This model does not support thinking'},raise_for_status=bare_error)
            brain=self.brain(root,response)
            with patch('hinglish_niche.profiles.inject',side_effect=lambda system,data,**kwargs:(system,data)),patch('hinglish_sound.reference_memory.inject',side_effect=lambda system,*args,**kwargs:system),patch('hinglish_cut.model_preferences.configure_request',side_effect=lambda root,body:body):
                with self.assertRaisesRegex(RuntimeError,'does not support thinking'):
                    brain.ask('Sound director',{},dict(type='object'))


if __name__=='__main__':unittest.main()
