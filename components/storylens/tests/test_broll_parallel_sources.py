import threading,unittest,tempfile
from pathlib import Path
from unittest.mock import patch

class ParallelSourcesTests(unittest.TestCase):
    def test_all_five_sources_start_together_and_each_has_a_bounded_batch(self):
        from hinglish_broll.website_catalogs import parallel_interleave
        started=[];lock=threading.Lock();ready=threading.Event()
        def source(name):
            with lock:
                started.append(name)
                if len(started)==5:ready.set()
            if not ready.wait(2):raise AssertionError('Sources were serialized')
            for i in range(100):yield (name,i)
        status={};names=['mixkit','coverr','videezy','pexels','pixabay']
        result=list(parallel_interleave([(n,lambda n=n:source(n)) for n in names],status,per_source=6))
        self.assertEqual(len(result),30);self.assertEqual([x[0] for x in result[:5]],names)
        self.assertTrue(all(sum(x[0]==n for x in result)==6 for n in names))

    def test_failed_source_does_not_remove_other_results(self):
        from hinglish_broll.website_catalogs import parallel_interleave
        def fail():raise ValueError('source unavailable');yield
        state={};result=list(parallel_interleave([('bad',fail),('good',lambda:iter([1,2]))],state))
        self.assertEqual(result,[1,2]);self.assertIn('bad',state)

    def test_real_fallback_dispatches_each_provider_with_independent_sessions(self):
        from hinglish_broll.website_review import WebsiteFallback
        base=Path(__file__).resolve().parents[1]/'cache/test-broll-parallel';base.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as tmp:
            finder=WebsiteFallback(tmp,'vertical');started=[];lock=threading.Lock();ready=threading.Event()
            def source(name):
                with lock:
                    started.append(name)
                    if len(started)==5:ready.set()
                if not ready.wait(2):raise AssertionError('Provider dispatch stayed serial')
                yield name
            finder.mixkit=lambda _:source('mixkit');finder.catalogues.probe_other_catalogues=lambda:None
            for name,provider in finder.provider_catalogues.items():
                if name in ('pexels','pixabay'):provider.stock_site=lambda n,q:source(n)
                else:setattr(provider,name,lambda q,n=name:source(n))
            with patch('hinglish_broll.stock_browser_client.BrowserSearch.parallel_supported',return_value=True):
                self.assertEqual(list(finder('bed')),['mixkit','coverr','videezy','pexels','pixabay'])
            sessions=[p.session for p in finder.provider_catalogues.values()]
            self.assertEqual(len({id(s) for s in sessions}),4)

    def test_chrome_capability_failure_does_not_disable_public_sources(self):
        from hinglish_broll.website_review import WebsiteFallback
        base=Path(__file__).resolve().parents[1]/'cache/test-broll-parallel';base.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as tmp:
            finder=WebsiteFallback(tmp,'vertical');finder.mixkit=lambda _:iter(['clip'])
            finder.catalogues.probe_other_catalogues=lambda:None
            for name,p in finder.provider_catalogues.items():
                p.stock_site=lambda *_:iter(());p.coverr=lambda *_:iter(());p.videezy=lambda *_:iter(())
            with patch('hinglish_broll.stock_browser_client.BrowserSearch.parallel_supported',side_effect=ValueError('connection unreadable')):
                self.assertEqual(list(finder('bed')),['clip'])

if __name__=='__main__':unittest.main()
