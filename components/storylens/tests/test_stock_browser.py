import tempfile,unittest
from pathlib import Path


class StockBrowserTests(unittest.TestCase):
    def setUp(self):
        base=Path(__file__).resolve().parents[1]/'cache/test-stock-browser';base.mkdir(parents=True,exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=base);self.addCleanup(self.tmp.cleanup)
        self.now=1000.
        from hinglish_app.stock_browser import StockBrowser
        self.bridge=StockBrowser(Path(self.tmp.name),clock=lambda:self.now)

    def connected(self):self.bridge.hello('client-one','1.0.0',['pexels','pixabay'])

    def test_unconnected_source_fails_fast_and_no_other_domains_are_allowed(self):
        with self.assertRaisesRegex(ValueError,'Connect'):self.bridge.request('pexels','bed','vertical',6)
        self.connected()
        for provider in ['instagram','http://127.0.0.1','other']:
            with self.assertRaises(ValueError):self.bridge.request(provider,'bed','vertical',6)
        with self.assertRaises(ValueError):self.bridge.request('pexels','bed','vertical',7)

    def test_only_paired_worker_claims_typed_search_not_code_or_arbitrary_url(self):
        self.connected();job=self.bridge.request('pexels','wifi router','vertical',6)
        task=self.bridge.claim('client-one')
        self.assertEqual(task['id'],job['id']);self.assertEqual(task['provider'],'pexels')
        self.assertNotIn('code',task);self.assertNotIn('selectors',task);self.assertNotIn('url',task)
        self.assertEqual(task['limit'],6);self.assertIsNone(self.bridge.claim('client-one'))
        with self.assertRaises(ValueError):self.bridge.claim('other-client')

    def test_browser_results_bind_job_lease_and_source_and_cap_at_six(self):
        self.connected();job=self.bridge.request('pexels','bed','vertical',6);task=self.bridge.claim('client-one')
        rows=[{'page_url':f'https://www.pexels.com/video/bed-{n+1}/','media_url':f'https://videos.pexels.com/video-files/{n+1}/clip.mp4','title':'Bed','width':720,'height':1280} for n in range(8)]
        with self.assertRaises(ValueError):self.bridge.finish('client-one',job['id'],'wrong',rows)
        result=self.bridge.finish('client-one',job['id'],task['lease'],rows)
        self.assertEqual(result['status'],'complete');self.assertEqual(len(result['results']),6)
        self.assertTrue(all(r['provider']=='pexels' for r in result['results']))

    def test_reading_never_accepts_photo_pages_private_urls_or_cookie_payloads(self):
        self.connected();job=self.bridge.request('pixabay','bed','vertical',6);task=self.bridge.claim('client-one')
        for row in [
            {'page_url':'https://pixabay.com/photos/family-123/','media_url':'https://cdn.pixabay.com/video/a.mp4'},
            {'page_url':'https://pixabay.com/videos/bed-123/','media_url':'https://127.0.0.1/private.mp4'},
            {'page_url':'https://pixabay.com/videos/bed-123/','media_url':'https://cdn.pixabay.com/video/a.mp4','cookies':'secret'}]:
            with self.assertRaises(ValueError):self.bridge.finish('client-one',job['id'],task['lease'],[row])

    def test_expired_connection_and_worker_deadline_do_not_hang_the_queue(self):
        self.connected();job=self.bridge.request('pexels','bed','vertical',6);self.bridge.claim('client-one')
        self.now+=200
        self.assertEqual(self.bridge.snapshot(job['id'])['status'],'failed')
        self.assertFalse(self.bridge.status()['connected'])

    def test_verification_is_reported_for_human_action_without_solving_or_replaying_cookies(self):
        self.connected();job=self.bridge.request('pexels','bed','vertical',6);task=self.bridge.claim('client-one')
        result=self.bridge.finish('client-one',job['id'],task['lease'],[],state='needs_verification')
        self.assertEqual(result['status'],'needs_verification');self.assertIn('verification',result['message'])
        self.assertNotIn('cookies',result)

    def test_empty_browser_result_can_be_retried_after_reader_repair(self):
        self.connected();job=self.bridge.request('pexels','bed','vertical',6);task=self.bridge.claim('client-one')
        self.bridge.finish('client-one',job['id'],task['lease'],[])
        self.assertNotEqual(self.bridge.request('pexels','bed','vertical',6)['id'],job['id'])

    def test_two_provider_claims_can_run_together_but_same_provider_stays_serial(self):
        self.connected();a=self.bridge.request('pexels','bed','vertical',6)
        self.bridge.request('pexels','wardrobe','vertical',6)
        b=self.bridge.request('pixabay','bed','vertical',6)
        self.assertEqual(self.bridge.claim('client-one',provider='pexels')['id'],a['id'])
        self.assertEqual(self.bridge.claim('client-one',provider='pixabay')['id'],b['id'])
        self.assertIsNone(self.bridge.claim('client-one',provider='pexels'))
        with self.assertRaises(ValueError):self.bridge.claim('client-one',provider='instagram')

if __name__=='__main__':unittest.main()
