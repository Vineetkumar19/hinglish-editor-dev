import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock,patch
from hinglish_publish.service import Publisher
from hinglish_publish.local_browser import LocalBrowser
from hinglish_publish.providers import PreflightError
from hinglish_publish.browser_provider import BrowserInstagram

class BrowserTransportTests(TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.video=self.root/'finished.mp4';self.video.write_bytes(b'finished selected bytes')
        self.bridge=LocalBrowser(self.root);self.bridge.bind('cricket','fantasy_legends91')
        self.provider=BrowserInstagram(self.bridge)
        self.job={'id':'draft-one','profile':'cricket','platform':'instagram','transport':'browser','kind':'short','video':str(self.video),
                  'account_id':'fantasy_legends91','authorized_at':time.time(),'metadata':{'instagram_caption':'Cricket finish. #Cricket'},'remote':{}}
    def test_enqueue_is_not_a_publication_receipt_and_repeated_call_reuses_job(self):
        with patch.object(self.bridge,'snapshot',return_value={'connected':True,'accounts':{'cricket':'fantasy_legends91'}}):
            remote,status=self.provider.publish(self.job,Mock())
            self.assertEqual(status,'processing');self.assertNotIn('url',remote)
            again,status=self.provider.publish({**self.job,'remote':remote},Mock())
        self.assertEqual(again,remote)
        self.assertEqual(len([j for j in self.bridge.data['jobs'] if j['action']=='reel']),1)
    def test_unapproved_and_wrong_saved_account_do_not_enqueue(self):
        for change in ({'authorized_at':None},{'account_id':'other_account'}):
            with patch.object(self.bridge,'snapshot',return_value={'connected':True,'accounts':{'cricket':'fantasy_legends91'}}):
                with self.assertRaises(PreflightError):self.provider.publish({**self.job,**change},Mock())
        self.assertEqual(self.bridge.data['jobs'],[])
    def test_verification_requires_matching_real_publication_receipt(self):
        with patch.object(self.bridge,'snapshot',return_value={'connected':True,'accounts':{'cricket':'fantasy_legends91'}}):
            remote,_=self.provider.publish(self.job,Mock())
        job={**self.job,'remote':remote};self.assertEqual(self.provider.verify(job),'processing')
        claimed=self.bridge.claim('0.4.35')['job'];self.bridge.phase(claimed['id'],claimed['lease'],'sharing')
        self.bridge.finish(claimed['id'],claimed['lease'],{'status':'published','account':'fantasy_legends91','url':'https://www.instagram.com/fantasy_legends91/reel/receiptOne/'})
        self.assertEqual(self.provider.verify(job),'published');self.assertIn('receiptOne',job['remote']['url'])
    def test_publisher_uses_browser_mapping_and_never_hosts_browser_media(self):
        pub=Publisher(self.root,browser=self.bridge)
        self.assertEqual(pub.accounts('cricket')['instagram']['id'],'fantasy_legends91')
        from hinglish_publish.store import fingerprint
        item={**self.job,'fingerprint':fingerprint(self.video),'visibility':'public','thumbnail':'','thumbnail_fingerprint':''}
        job_id=pub.store.add_batch([item])[0];pub.store.change(job_id,status='ready',due=time.time()-1)
        pub.settings({'enabled':True},'cricket')
        with patch.object(self.bridge,'snapshot',return_value={'connected':True,'accounts':{'cricket':'fantasy_legends91'}}),patch.object(pub,'host_instagram') as host:
            result=pub.tick()
        self.assertEqual(result['status'],'processing');host.assert_not_called()
        self.assertIn('browser_job_id',result['remote'])

    def test_explicit_paired_preparation_binds_browser_and_youtube_without_arming(self):
        pub=Publisher(self.root,browser=self.bridge)
        base={**self.job,'fingerprint':'unique','duration':20,'width':720,'height':1280,'visibility':'public'}
        prepared=[{**base,'platform':p} for p in ('youtube','instagram')]
        accounts={'youtube':{'connected':True,'id':'yt-cricket'},'instagram':{'connected':True,'id':'fantasy_legends91','transport':'browser'}}
        with patch.object(pub,'accounts',return_value=accounts),patch.object(pub,'item',return_value=prepared):
            pub.prepare_file({'video':str(self.video),'kind':'short','thumbnail':''},{'profile':'cricket','platforms':['youtube','instagram']})
        rows=pub.store.list();self.assertEqual(len(rows),2)
        for row in rows:
            self.assertEqual(row['status'],'draft');self.assertEqual(row['destination']['account_id'],accounts[row['platform']]['id'])
        self.assertEqual(next(r for r in rows if r['platform']=='instagram')['transport'],'browser')
        self.assertEqual(self.bridge.data['jobs'],[])
