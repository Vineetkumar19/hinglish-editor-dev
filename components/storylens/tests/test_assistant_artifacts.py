import tempfile
from pathlib import Path
from types import SimpleNamespace
import time
import unittest
from unittest.mock import patch

from hinglish_app.assistant import Assistant
from hinglish_app.assistant_artifacts import catalog, evidence, editing_requested, resolve
from hinglish_app.assistant_plan import plan
from hinglish_app.server import AppState


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name).resolve();self.assistant=Assistant(SimpleNamespace(root=self.root))
        self.session=self.assistant.create()['id']
        self.original=self.root/'two-hour-stream.mp4';self.original.write_bytes(b'original')
        self.highlight=self.root/'GAMING_HIGHLIGHTS.mp4';self.highlight.write_bytes(b'highlights')
        self.assistant._update(self.session,profile='gaming',last_paths=[str(self.highlight)],
            highlights_paths=[str(self.highlight)],original_paths=[str(self.original)])

    def test_current_output_has_real_identity_and_origin_not_cricket_campaigns(self):
        cards=catalog(self.assistant,self.assistant.snapshot(self.session))
        self.assertEqual(len(cards),2)
        self.assertEqual(cards[0]['role'],'gaming_highlights')
        self.assertTrue(cards[0]['latest_in_chat'])
        self.assertEqual(cards[0]['origin_names'],[self.original.name])
        self.assertNotIn('paths',evidence(cards)[0])
        self.assertEqual(resolve(cards,cards[0]['id']),[str(self.highlight)])
        with self.assertRaises(ValueError):resolve(cards,str(self.original))

    def test_new_chat_isolated_and_reopening_restores_artifact_references(self):
        second=self.assistant.create()['id'];restored=Assistant(SimpleNamespace(root=self.root))
        cards=catalog(restored,restored.snapshot(second))
        self.assertEqual(cards,[])
        cards=catalog(restored,restored.snapshot(self.session))
        self.assertEqual(cards[0]['role'],'gaming_highlights')
        self.assertTrue(cards[0]['current_chat'])
        self.assertEqual(resolve(cards,cards[0]['id']),[str(self.highlight)])

    def test_moved_output_never_silently_substitutes_original(self):
        cards=catalog(self.assistant,self.assistant.snapshot(self.session))
        self.highlight.unlink()
        with self.assertRaisesRegex(ValueError,'no other video was substituted'):resolve(cards,cards[0]['id'])
        self.assertFalse(catalog(self.assistant,self.assistant.snapshot(self.session))[0]['available'])

    def test_historical_runner_output_retained_after_latest_becomes_shorts(self):
        self.assistant._message(self.session,'assistant','Done',videos=[str(self.highlight)])
        short=self.root/'short.mp4';short.write_bytes(b'short')
        self.assistant._update(self.session,last_paths=[str(short)],highlights_paths=[])
        cards=catalog(self.assistant,self.assistant.snapshot(self.session))
        self.assertTrue(any(c['paths']==[str(self.highlight)] for c in cards))

    def test_only_fresh_edits_bypass_publishing_recall(self):
        for text in ('now make 5 shorts video form this video.',
                     'I want you to extract five short form content from the above video which you have just created from the two hours live stream',
                     'Add captions to this video', 'Make 5 Shorts and schedule them daily',
                     'Run Smart Clean on this video', 'Start Smart Clean'):
            self.assertTrue(editing_requested(text),text)
        for text in ('Schedule the seven Shorts you created', 'Upload my clips',
                     'How do I make Shorts?', 'Do not make Shorts.', 'What video did you create?',
                     'Do not run Smart Clean.', 'How do I run Smart Clean?'):
            self.assertFalse(editing_requested(text),text)

    def test_local_planner_receives_sources_and_validates_id(self):
        cards=catalog(self.assistant,self.assistant.snapshot(self.session));calls=[]
        class Brain:
            name='Local fixture'
            def json(self,system,data,schema,**kwargs):
                calls.append((system,data,schema))
                return {'reply':'Creating Shorts from the finished highlights.','question':'','combine':False,
                    'source_id':cards[0]['id'] if len(calls)>1 else 'invented-path.mp4',
                    'steps':[{'tool':'shorts','options':{'count':5,'max_seconds':50,'shorts_look':'template'}}]}
            def close(self):pass
        with patch('hinglish_visuals.brain.open_brain',return_value=Brain()):
            parsed,_=plan(self.root,'now make 5 shorts video form this video.',[],[],True,
                          memory_context={'editing_sources':evidence(cards)})
        self.assertEqual(len(calls),2)
        self.assertEqual(parsed['source_id'],cards[0]['id'])
        self.assertIn('latest current-chat OUTPUT',calls[0][0])
        self.assertEqual(calls[0][1]['shared_memory']['editing_sources'][0]['names'],[self.highlight.name])

    def test_explicit_count_is_not_lost_when_model_omits_it(self):
        cards=catalog(self.assistant,self.assistant.snapshot(self.session))
        class Brain:
            name='Local fixture'
            def json(self,*args,**kwargs):
                return {'reply':'Starting Shorts.','question':'','source_id':cards[0]['id'],
                        'steps':[{'tool':'shorts','options':{}}]}
            def close(self):pass
        for text in ('now make 5 shorts video form this video.',
                     'Extract five short form content from the highlights'):
            with self.subTest(text=text),patch('hinglish_visuals.brain.open_brain',return_value=Brain()):
                parsed,_=plan(self.root,text,[],[],True,memory_context={'editing_sources':evidence(cards)})
            self.assertEqual(parsed['steps'][0]['options']['count'],5)
            self.assertEqual(parsed['steps'][0]['options']['max_seconds'],50)
            self.assertEqual(parsed['steps'][0]['options']['shorts_look'],'template')


class FollowupIntegrationTests(unittest.TestCase):
    def test_run_smart_clean_uses_named_source_instead_of_latest_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();state=AppState(root);assistant=state.assistant
            sid=assistant.create()['id']
            arranged=root/'arranged.mp4';arranged.write_bytes(b'arranged')
            previous=root/'previous-cleaned.mp4';previous.write_bytes(b'previous')
            assistant._update(sid,last_paths=[str(previous)])
            captured=[]
            def create(payload):
                captured.append(payload)
                result=root/'tight-cleaned.mp4';result.write_bytes(b'rendered')
                job={'id':'1','status':'complete','stage':'Done',
                     'result':{'folder':str(root),'previews':[str(result)]}}
                state.jobs['1']=job;return job
            with patch.object(state,'create_job',side_effect=create), \
                 patch('hinglish_app.assistant_media.outputs',side_effect=lambda *args:args[2]['previews']):
                assistant.send(sid,'Run Smart Clean on this video:\n'+arranged.as_posix())
                for _ in range(200):
                    result=assistant.snapshot(sid)
                    if result['status'] not in ('planning','running'):break
                    time.sleep(.01)
            self.assertEqual(result['status'],'complete',result['stage'])
            self.assertEqual(captured[0]['source_paths'],[str(arranged)])
            self.assertEqual(captured[0]['mode'],'clean')

    def test_local_plan_edits_completed_highlight_without_campaign_interception(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();state=AppState(root);assistant=state.assistant
            sid=assistant.create()['id'];original=root/'stream.mp4';original.write_bytes(b'original')
            highlights=root/'GAMING_HIGHLIGHTS.mp4';highlights.write_bytes(b'highlights')
            assistant._update(sid,profile='gaming',last_paths=[str(highlights)],highlights_paths=[str(highlights)],original_paths=[str(original)])
            assistant._message(sid,'assistant','Which cricket filename?',question=True)
            captured=[]
            def planner(*args,**kwargs):
                sources=kwargs['memory_context']['editing_sources']
                chosen=next(c for c in sources if c['role']=='gaming_highlights')
                return {'reply':'Extracting five Shorts.','question':'','combine':False,'source_id':chosen['id'],
                        'steps':[{'tool':'shorts','options':{'count':5,'max_seconds':50,'shorts_look':'template'}}]},'Local model'
            def create(payload):
                captured.append(payload)
                target=root/'output/shorts';target.mkdir(parents=True)
                clip=target/'short.mp4';clip.write_bytes(b'rendered')
                job={'id':'1','status':'complete','stage':'Done','result':{'folder':str(target),'previews':[str(clip)]}}
                state.jobs['1']=job;return job
            with patch('hinglish_app.assistant.plan',side_effect=planner), \
                 patch('hinglish_app.assistant_campaign.followup') as campaign, \
                 patch('hinglish_app.assistant_distribution.followup') as distribution, \
                 patch.object(state,'create_job',side_effect=create), \
                 patch('hinglish_app.assistant_media.outputs',side_effect=lambda *args:args[2]['previews']):
                assistant.send(sid,'now make 5 shorts video form this video.',profile='gaming')
                for _ in range(200):
                    result=assistant.snapshot(sid)
                    if result['status'] not in ('planning','running'):break
                    time.sleep(.01)
            self.assertEqual(result['status'],'complete',result['stage'])
            self.assertEqual(captured[0]['source_paths'],[str(highlights)])
            self.assertEqual(captured[0]['shorts_count'],'5')
            self.assertEqual(result['original_paths'],[str(original)])
            campaign.assert_not_called();distribution.assert_not_called()
            self.assertTrue(highlights.is_file())


if __name__=='__main__':unittest.main()
