import copy,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from hinglish_sound.brain import Brain
from hinglish_sound.director import analyse


class WebsiteSoundContextTests(unittest.TestCase):
    def make_brain(self,root):
        b=Brain.__new__(Brain);b.root=root;b.cache=root/'cache';b.cache.mkdir()
        b.model='local14b';b.url='http://local';b.progress=lambda _:None
        return b

    def injectors(self,optional):
        return (patch('hinglish_niche.profiles.inject',side_effect=lambda s,d,**kw:(s,d)),
                patch('hinglish_sound.reference_memory.inject',side_effect=lambda s,*a,**kw:s+optional),
                patch('hinglish_cut.model_preferences.configure_request',side_effect=lambda r,b:b['options'].update(num_ctx=4096)))

    def test_large_optional_memory_is_fitted_before_first_http_request(self):
        optional='\n[Storylens sound reference study]\nReviewed data.\n'+json.dumps({'prose':'optional background '*4000})
        profile={'brief':'Exact full creator instructions','references':[{'text':'Saved full guide'}]}
        data={'creator_profile':profile,'script':'Exact source script','events':[{'id':'cut-1','time':1.25}]}
        original=copy.deepcopy(data);calls=[]
        with tempfile.TemporaryDirectory() as t:
            b=self.make_brain(Path(t))
            def post(url,json,timeout):
                calls.append(json)
                if len(json['messages'][0]['content'])>12000:
                    return SimpleNamespace(status_code=400,json=lambda:{'error':'request exceeds context size'})
                return SimpleNamespace(status_code=200,json=lambda:{'message':{'content':'{"ok":true}'}})
            b.session=SimpleNamespace(post=post)
            a,c,d=self.injectors(optional)
            with a,c,d:b.ask('Sound director',data,{'type':'object'},max_tokens=800)
        self.assertEqual(len(calls),1,'Avoid an overflowing HTTP call before every sound stage')
        sent=json.loads(calls[0]['messages'][1]['content'])
        self.assertEqual(sent['creator_profile'],profile);self.assertEqual(sent['events'],data['events'])
        self.assertEqual(sent['script'],data['script']);self.assertEqual(data,original)

    def test_small_optional_memory_is_kept(self):
        calls=[];optional='\n[Storylens sound reference study]\n'+json.dumps({'rule':'Use relevant sounds'})
        with tempfile.TemporaryDirectory() as t:
            b=self.make_brain(Path(t));b.session=SimpleNamespace(post=lambda u,json,timeout:(calls.append(json) or SimpleNamespace(status_code=200,json=lambda:{'message':{'content':'{"ok":true}'}})))
            a,c,d=self.injectors(optional)
            with a,c,d:b.ask('Sound director',{'script':'Small exact request'},{'type':'object'},max_tokens=800)
        self.assertIn('Use relevant sounds',calls[0]['messages'][0]['content'])

    def test_feature_budget_compacts_optional_prose_before_ram_expansion(self):
        optional='\n[Storylens sound reference study]\n'+json.dumps({'prose':'optional context '*4000})
        data={'creator_profile':{'brief':'Keep my complete direction'},'events':[{'id':'actual','time':2.5}]}
        calls=[]
        with tempfile.TemporaryDirectory() as t:
            b=self.make_brain(Path(t))
            b.session=SimpleNamespace(post=lambda u,json,timeout:(calls.append(copy.deepcopy(json)) or SimpleNamespace(status_code=200,json=lambda:{'message':{'content':'{"ok":true}'}})))
            a,c,d=self.injectors(optional)
            with a,c,d,patch('hinglish_cut.feature_context.limits',return_value=(4096,8192,'local14b')),patch('hinglish_cut.feature_context.configure',return_value={'feature':'sound'}),patch('hinglish_cut.feature_context.record'):
                b.ask('Sound director',data,{'type':'object'},max_tokens=800)
        self.assertEqual(len(calls),1)
        self.assertNotIn('optional context',calls[0]['messages'][0]['content'])
        sent=json.loads(calls[0]['messages'][1]['content'])
        self.assertEqual(sent,data)

    def test_fitting_input_does_not_truncate_the_structured_answer_budget(self):
        from hinglish_sound.brain import fit_sound_request
        body={'messages':[{'role':'system','content':'required fact '*1700}],
              'format':{'type':'object'},'options':{'num_ctx':12288,'num_predict':7000}}
        fitted,_=fit_sound_request(body)
        self.assertEqual(fitted['options']['num_predict'],7000)
        self.assertEqual(fitted['messages'],body['messages'])

    def test_required_context_failure_has_shared_actionable_message(self):
        from hinglish_app.user_messages import problem
        result=problem(ValueError('Sound planning contains too much required information for the local model.'))
        self.assertEqual(result['code'],'sound_context_full')
        self.assertIn('kept',result['message'])

    def test_required_profile_overflow_stops_before_http_without_trimming_profile(self):
        data={'creator_profile':{'brief':'required owner guidance '*10000},'script':'Exact request'}
        original=copy.deepcopy(data)
        with tempfile.TemporaryDirectory() as t:
            b=self.make_brain(Path(t));calls=[]
            b.session=SimpleNamespace(post=lambda *a,**kw:calls.append(kw))
            a,c,d=self.injectors('')
            with a,c,d:
                with self.assertRaisesRegex(ValueError,'required'):
                    b.ask('Sound director',data,{'type':'object'},max_tokens=800)
        self.assertEqual(calls,[]);self.assertEqual(data,original)

    def test_shared_music_endpoint_is_normalized_without_three_model_retries(self):
        lines=[SimpleNamespace(id=i,start=float(i),end=float(i+1),text='source line') for i in range(3)]
        answer={'story':'A source story','palette':'serious','moments':[],
                'lines':[{'id':i,'emotion':'calm','intensity':1,'role':'setup'} for i in range(3)],
                'music':[{'from_id':a,'to_id':b,'mode':'music','mood':'neutral','energy':1,'why':'same selected bed'} for a,b in [(0,1),(1,2),(2,2)]]}
        raw=copy.deepcopy(answer);calls=[]
        brain=SimpleNamespace(ask=lambda *a,**kw:(calls.append(1) or copy.deepcopy(answer)))
        with patch('hinglish_eval.tune.feedback',return_value=[]):
            result=analyse(brain,'short video',lines,[],[],['neutral'],['foley'],progress=lambda _:None,composition={'seconds':3})
        self.assertEqual(len(calls),1,'A shared-endpoint representation should not cause repeated inference')
        self.assertEqual([(s['from_id'],s['to_id']) for s in result['music']],[(0,0),(1,1),(2,2)])
        self.assertEqual([s['mood'] for s in result['music']],['neutral']*3)
        self.assertEqual(answer,raw)


if __name__=='__main__':unittest.main()
