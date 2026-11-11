"""Safe regression reproduction of the owner's 25 October Cricket upload chat.

Fixtures replace metadata/model transports; these are component acceptance only.
"""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock,patch
from hinglish_app.assistant_publish_intent import preflight
from hinglish_app.assistant_publish import request,prepare
from hinglish_publish.service import Publisher

META={'title':'Cricket finish','description':'The final over. #Cricket #Match #Finish','instagram_caption':'The final over.','tags':['Cricket']}

class PublishingRegressionTests(TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/"tmp");self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.folder=self.root/'All Shorts';self.folder.mkdir()
        self.video=self.folder/'Shorts 2.mp4';self.video.write_bytes(b'finished exact owner export')
        self.a=Mock(root=self.root)
        self.s={'id':'test','messages':[],'attachments':[], 'last_paths':['unrelated-old-highlights.mp4']}
        self.a._update.side_effect=lambda sid,**kw:self.s.update(kw)
        self.a.attach.side_effect=lambda sid,p:{'id':'owner-file','path':str(p),'name':Path(p).name,'kind':'file'}

    def test_platform_only_answer_continues_cricket_request_and_resolves_named_source(self):
        original=str(self.folder)+'\ntake the shorts2 clip and post my cricket channel'
        self.assertIsNone(preflight(self.a,'test',original,self.s,[]))
        selected=[]
        resolved=preflight(self.a,'test','youtube short',self.s,selected)
        self.assertIn('cricket',resolved)
        self.assertIn('youtube short',resolved)
        self.assertEqual([x['path'] for x in selected],[str(self.video.resolve())])
        self.assertIsNone(self.s['publishing_inputs_pending'])

    def test_attached_source_survives_platform_question_without_reattachment(self):
        attachment={'id':'owned','path':str(self.video),'name':self.video.name,'kind':'file'}
        self.s['attachments']=[attachment]
        self.assertIsNone(preflight(self.a,'test','post this clip to my cricket channel',self.s,[attachment]))
        selected=[];resolved=preflight(self.a,'test','YouTube Short',self.s,selected)
        self.assertIn('cricket',resolved)
        self.assertEqual(selected,[attachment])

    def test_simple_upload_uses_full_finished_draft_route_with_explicit_destination(self):
        spec=request('Post this YouTube Short to my cricket channel','general')
        self.assertIsNotNone(spec)
        self.assertTrue(spec['finished_draft'])
        self.assertEqual(spec['profiles'],['cricket']);self.assertEqual(spec['kinds'],['short'])
        self.assertFalse(spec['upload_requested'])
        spec=request('post it on my cricket yt channel','general')
        self.assertEqual(spec['profiles'],['cricket'])
        # No media kind is inferred from an unrelated old highlights output.
        self.assertEqual(spec['kinds'],['auto'])

    def test_invalid_platforms_refuse_before_metadata_or_draft_creation(self):
        pub=Publisher(self.root)
        file={'video':str(self.video),'kind':'short','thumbnail':''}
        for scope in ('youtube', [], ['youtube','youtube'], ['unknown'], [None], [['youtube']]):
            with self.subTest(scope=scope),patch.object(pub,'item',return_value=[]) as item:
                with self.assertRaisesRegex(ValueError,'destinations'):
                    pub.prepare_file(file,{'profile':'cricket','platforms':scope})
                item.assert_not_called()
        self.assertEqual(pub.store.list(),[])

    def test_finished_short_draft_keeps_every_byte_profile_platform_and_no_upload(self):
        pub=Publisher(self.root);self.a.state.publisher=pub
        self.a._stopped.return_value=False
        self.a.state.work_lock=__import__('threading').RLock()
        account={'youtube':{'connected':True,'id':'cricket-channel','name':'Fantasy Legends'}}
        selected=[{'id':'owned','path':str(self.video),'name':self.video.name,'kind':'file'}]
        spec={'profiles':['cricket'],'kinds':['short'],'finished_draft':True,'upload_requested':False,'any':False}
        facts=SimpleNamespace(duration=47.2,width=1080,height=1920)
        with patch.object(pub,'accounts',return_value=account),patch('hinglish_shorts.source.open_video',return_value=facts),patch('hinglish_publish.metadata.generate',return_value=(META,'Local model fixture')),patch('hinglish_cut.gpu_lock.gpu_lock'),patch('hinglish_app.assistant_publish.excerpt') as excerpt:
            prepare(self.a,'test','post this Short to cricket YouTube',selected,spec,lambda x:None)
        jobs=pub.store.list();self.assertEqual(len(jobs),1)
        j=jobs[0];self.assertEqual((j['profile'],j['platform'],j['kind']),('cricket','youtube','short'))
        self.assertEqual(j['video'],str(self.video.resolve()));self.assertEqual(j['duration'],47.2)
        self.assertEqual(j['status'],'draft');self.assertEqual(j['attempts'],0);self.assertEqual(j['remote'],{})
        self.assertEqual(j['destination']['account_id'],'cricket-channel')
        excerpt.assert_not_called();self.assertFalse(pub.settings(profile='cricket')['enabled'])
        self.assertIn('publish_ids',self.a._message.call_args.kwargs)
        self.assertEqual(self.a._message.call_args.kwargs['publisher_profile'],'cricket')
        # Repeating/restarting preparation reuses the draft rather than adding posts.
        with patch.object(pub,'accounts',return_value=account),patch('hinglish_shorts.source.open_video',return_value=facts),patch('hinglish_publish.metadata.generate',return_value=(META,'Local model fixture')),patch('hinglish_cut.gpu_lock.gpu_lock'):
            prepare(self.a,'test','post this Short to cricket YouTube',selected,spec,lambda x:None)
        self.assertEqual(len(Publisher(self.root).store.list()),1)

    def test_new_edit_clears_question_without_reusing_publish_attachment(self):
        self.s['publishing_inputs_pending']={'request':'post this clip to cricket','attachment_ids':['owned'],'missing':['platform']}
        selected=[];self.assertEqual(preflight(self.a,'test','add captions to this video',self.s,selected),'add captions to this video')
        self.assertEqual(selected,[]);self.assertIsNone(self.s['publishing_inputs_pending'])


class NormalAssistantRegressionTests(TestCase):
 def test_generic_gaming_draft_plan_uses_finished_highlight_not_original_recording(self):
  import time
  from hinglish_app.server import AppState
  with TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as tmp:
   root=Path(tmp);a=AppState(root).assistant;sid=a.create()['id']
   raw=root/'stream.mp4';raw.write_bytes(b'raw');highlight=root/'highlight.mp4';highlight.write_bytes(b'edited')
   a._update(sid,profile='gaming',original_paths=[str(raw)],last_paths=[str(highlight)])
   plan={'reply':'Prepare editable drafts','question':'','combine':False,'steps':[{'tool':'publish','options':{'make_shorts':True}}]}
   with patch('hinglish_app.assistant.plan',return_value=(plan,'fixture')),patch('hinglish_app.assistant_publish.request',return_value=None),patch.object(a.state.publisher,'prepare_file',return_value={'job_ids':['draft']}) as prepare:
    a.send(sid,'Prepare metadata for the finished edit',profile='gaming')
    for _ in range(200):
     result=a.snapshot(sid)
     if result['status'] not in ('planning','running','transcribing'):break
     time.sleep(.01)
   self.assertEqual(result['status'],'complete',result.get('stage'))
   self.assertEqual(prepare.call_args.args[1]['shorts_source'],str(highlight))
   self.assertEqual(result['messages'][-1]['publisher_profile'],'gaming')

 def test_reported_two_turn_request_uses_publishing_without_general_edit_planner(self):
  import threading,time
  from hinglish_app.server import AppState
  with TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as tmp:
   root=Path(tmp);state=AppState(root);a=state.assistant;sid=a.create()['id'];folder=root/'All Shorts';folder.mkdir();video=folder/'Shorts 2.mp4';video.write_bytes(b'exact finished short')
   (root/'config.workflow_memory.local.json').write_text(json.dumps({'enabled':False}),'utf-8')
   old=root/'old-gaming-highlights.mp4';old.write_bytes(b'unrelated old output')
   a._update(sid,last_paths=[str(old)],profile='general')
   def wait():
    for _ in range(400):
     s=a.snapshot(sid)
     if s['status'] not in ('planning','running','transcribing'):return s
     time.sleep(.01)
    raise AssertionError('Request did not finish')
   facts=SimpleNamespace(duration=47.2,width=1080,height=1920)
   accounts={'youtube':{'connected':True,'id':'cricket-yt','name':'Fantasy Legends'}}
   with patch.object(state.publisher,'accounts',return_value=accounts),patch('hinglish_shorts.source.open_video',return_value=facts),patch('hinglish_publish.metadata.generate',return_value=(META,'Local model fixture')),patch('hinglish_cut.gpu_lock.gpu_lock'),patch('hinglish_app.assistant.plan') as general,patch('hinglish_app.assistant_finished_upload.prepare',wraps=__import__('hinglish_app.assistant_finished_upload',fromlist=['prepare']).prepare) as draft:
    a.send(sid,str(folder)+'\ntake the shorts2 clip and post my cricket channel');first=wait()
    self.assertIsNotNone(first['publishing_inputs_pending'])
    a.send(sid,'youtube short');last=wait()
   self.assertEqual(last['status'],'complete',last.get('stage'));general.assert_not_called();draft.assert_called_once()
   jobs=state.publisher.store.list();self.assertEqual(len(jobs),1);self.assertEqual(jobs[0]['profile'],'cricket');self.assertEqual(jobs[0]['kind'],'short');self.assertNotEqual(jobs[0]['video'],str(old));self.assertEqual(Path(jobs[0]['video']).read_bytes(),video.read_bytes());self.assertEqual(jobs[0]['attempts'],0)
