"""Non-publishing diagnostics and existing-path Studio intake contracts."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch,Mock
import json
from hinglish_publish.service import Publisher

class PublisherReadinessTests(TestCase):
 def test_live_check_inspects_only_selected_saved_account(self):
  from hinglish_publish.readiness import check
  bridge=Mock();bridge.snapshot.return_value={'connected':True,'accounts':{'cricket':'fantasy_legends91'}}
  bridge.inspect_account.return_value={'id':'check'};bridge.get.return_value={'id':'check','status':'complete','account':'fantasy_legends91'}
  with patch('hinglish_publish.readiness.report',return_value={'youtube':{'state':'verified'},'instagram':{},'publication_verified':False}):
   result=check(Path('.'),'cricket',bridge,lambda _:None)
  bridge.inspect_account.assert_called_once_with('cricket');bridge.enqueue.assert_not_called()
  self.assertEqual(result['instagram']['state'],'verified');self.assertFalse(result['publication_verified'])
 def setUp(self):
  self.tmp=TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp');self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
 def test_diagnostics_probe_is_read_only_and_keeps_browser_instagram_distinct(self):
  from hinglish_publish.readiness import report
  stored={'channel_id':'cricket-yt','name':'Fantasy Legends','credentials':{'token':'DO-NOT-EXPOSE','refresh_token':'SECRET-REFRESH','expiry':'2020-01-01T00:00:00Z'}}
  browser={'connected':True,'accounts':{'cricket':'fantasy_legends91'},'youtube_scheduling':True,'jobs':[]}
  with patch('hinglish_publish.secrets.load',side_effect=lambda root,key:stored if key=='youtube-cricket' else (_ for _ in ()).throw(FileNotFoundError())),patch('hinglish_publish.readiness.youtube_probe',return_value={'id':'cricket-yt','name':'Fantasy Legends'}) as probe,patch('hinglish_publish.secrets.save') as save:
   result=report(self.root,'cricket',online=True,browser=browser)
  self.assertEqual(result['youtube']['state'],'verified');probe.assert_called_once();save.assert_not_called()
  self.assertEqual(result['instagram']['transport'],'browser');self.assertEqual(result['instagram']['account'],'fantasy_legends91')
  self.assertFalse(result['publication_verified']);self.assertNotIn('DO-NOT-EXPOSE',json.dumps(result));self.assertNotIn('SECRET-REFRESH',json.dumps(result))
 def test_expired_token_is_not_mislabeled_disconnected_without_probe(self):
  from hinglish_publish.readiness import report
  with patch('hinglish_publish.secrets.load',return_value={'channel_id':'cricket-yt','name':'Fantasy Legends','credentials':{'token':'secret','refresh_token':'refresh','expiry':'2020-01-01T00:00:00Z'}}),patch('hinglish_publish.readiness.youtube_probe') as probe:
   r=report(self.root,'cricket')
  self.assertEqual(r['youtube']['state'],'refresh_required');self.assertTrue(r['youtube']['refresh_available']);probe.assert_not_called()
 def test_remote_account_mismatch_is_not_ready(self):
  from hinglish_publish.readiness import report
  with patch('hinglish_publish.secrets.load',return_value={'channel_id':'expected','credentials':{'token':'secret'}}),patch('hinglish_publish.readiness.youtube_probe',return_value={'id':'different','name':'Other'}):r=report(self.root,'cricket',online=True)
  self.assertEqual(r['youtube']['state'],'account_mismatch');self.assertFalse(r['publication_verified'])
 def test_failed_probe_never_echoes_secret_diagnostics_or_claims_reconnect_cause(self):
  from hinglish_publish.readiness import report
  with patch('hinglish_publish.secrets.load',return_value={'channel_id':'expected','credentials':{'token':'secret'}}),patch('hinglish_publish.readiness.youtube_probe',side_effect=RuntimeError('token=secret')):r=report(self.root,'gaming',online=True)
  self.assertEqual(r['youtube']['state'],'verification_failed');self.assertNotIn('secret',json.dumps(r));self.assertNotIn('reconnect',r['youtube']['message'].lower())
 def test_studio_accepts_literal_path_and_youtube_scope_without_folder_copy(self):
  p=self.root/'Shorts 2.mp4';p.write_bytes(b'owner export');pub=Publisher(self.root)
  expected={'job_ids':['draft']}
  with patch.object(pub,'prepare_file',return_value=expected) as prepare:
   r=pub.prepare({'video_path':str(p),'profile':'cricket','kind':'short','platforms':['youtube']})
  self.assertEqual(r,expected);self.assertEqual(prepare.call_args.args[0]['video'],str(p.resolve()));self.assertEqual(prepare.call_args.args[0]['kind'],'short')
 def test_invalid_explicit_path_stops_instead_of_falling_back_to_scanned_file(self):
  pub=Publisher(self.root)
  with patch.object(pub,'selected') as selected,patch.object(pub,'prepare_file') as prepare:
   with self.assertRaisesRegex(ValueError,'video'):pub.prepare({'video_path':str(self.root/'missing.mp4'),'name':'old source','profile':'cricket'})
  selected.assert_not_called();prepare.assert_not_called()
 def test_diagnostic_task_cannot_prepare_or_authorize_posts(self):
  pub=Publisher(self.root)
  with patch('hinglish_publish.readiness.report',return_value={'publication_verified':False}) as report,patch.object(pub,'prepare_file') as prepare:
   r=pub.prepare({'operation':'diagnostics','profile':'cricket'})
  self.assertFalse(r['publication_verified']);prepare.assert_not_called();self.assertEqual(pub.store.list(),[])

 def test_invalid_grant_has_specific_safe_next_action(self):
  from hinglish_publish.readiness import report
  from google.auth.exceptions import RefreshError
  with patch('hinglish_publish.secrets.load',return_value={'channel_id':'expected','credentials':{'token':'secret'}}),patch('hinglish_publish.readiness.youtube_probe',side_effect=RefreshError('sensitive',{'error':'invalid_grant','error_description':'secret'})):
   r=report(self.root,'cricket',online=True)
  self.assertEqual(r['youtube']['technical']['provider_code'],'invalid_grant');self.assertEqual(r['youtube']['state'],'refresh_rejected');self.assertIn('Google',r['youtube']['message']);self.assertNotIn('secret',json.dumps(r))
 def test_scoped_studio_preparation_does_not_create_instagram_api_posts(self):
  pub=Publisher(self.root);item={'profile':'cricket','platform':'youtube','kind':'short','video':'finished.mp4','fingerprint':'abc','metadata':{},'visibility':'private'}
  with patch.object(pub,'accounts',return_value={'youtube':{'connected':True,'id':'cricket-yt'}}),patch.object(pub,'item',return_value=[item,{**item,'platform':'instagram'}]):r=pub.prepare_file({'video':'finished.mp4','kind':'short','thumbnail':''},{'profile':'cricket','platforms':['youtube']})
  self.assertEqual(len(r['job_ids']),1);self.assertEqual(pub.store.list()[0]['platform'],'youtube')
 def test_prepared_account_binding_is_rechecked_before_any_authorization(self):
  pub=Publisher(self.root);item={'profile':'cricket','platform':'youtube','kind':'short','video':'finished.mp4','fingerprint':'abc','metadata':{'title':'Cricket','description':'A match.','instagram_caption':'Match','tags':['Cricket']},'visibility':'private','destination':{'profile_id':'cricket','platform':'youtube','account_id':'original','connection_ref':'youtube-cricket','verified':True},'account_id':'original','connection_ref':'youtube-cricket'}
  j=pub.store.add_batch([item])[0]
  with patch.object(pub,'accounts',return_value={'youtube':{'connected':True,'id':'changed'}}):
   with self.assertRaisesRegex(ValueError,'account|channel'):pub.authorize({'ids':[j],'authorize':True,'made_for_kids':False,'synthetic_media':False})
  self.assertEqual(pub.store.get(j)['status'],'draft')
