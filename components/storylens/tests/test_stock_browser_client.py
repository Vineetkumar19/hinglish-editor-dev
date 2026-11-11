import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch

class StockClientTests(unittest.TestCase):
    def setUp(self):
        base=Path(__file__).resolve().parents[1]/'cache/test-stock-client';base.mkdir(parents=True,exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=base);self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        (self.root/'cache/app').mkdir(parents=True);(self.root/'cache/stock-browser').mkdir()
        (self.root/'cache/app/bridge.json').write_text(json.dumps({'token':'private-test-token'}))
        (self.root/'cache/stock-browser/connection.json').write_text(json.dumps({'url':'http://127.0.0.1:8765'}))
        self.folder=self.root/'output/broll/run/001';self.folder.mkdir(parents=True)
    def test_unconnected_falls_back_and_never_sends_private_token_to_remote_host(self):
        from hinglish_broll.stock_browser_client import BrowserSearch
        client=BrowserSearch(self.folder)
        with patch.object(client,'_api',return_value={'connected':False}):self.assertIsNone(client.search('pexels','bed','vertical'))
        (self.root/'cache/stock-browser/connection.json').write_text(json.dumps({'url':'https://evil.test'}))
        with self.assertRaises(ValueError):BrowserSearch(self.folder)
    def test_ready_browser_results_keep_source_and_query_without_api_or_vision(self):
        from hinglish_broll.stock_browser_client import BrowserSearch
        client=BrowserSearch(self.folder)
        row={'page_url':'https://www.pexels.com/video/bed-123/','media_url':'https://videos.pexels.com/clip.mp4','width':720,'height':1280,'duration':8,'title':'Bed','thumbnail':''}
        with patch.object(client,'_api',side_effect=[{'connected':True,'providers':['pexels']},{'id':'test'},{'status':'complete','results':[row]}]):
            results=client.search('pexels','bed','vertical')
        self.assertEqual(len(results),1);self.assertEqual(results[0].source,'pexels_browser');self.assertEqual(results[0].query,'bed')
    def test_catalogue_prefers_connected_browser_and_does_not_repeat_blocked_http(self):
        from hinglish_broll.website_catalogs import CatalogueSearch
        search=CatalogueSearch(self.folder,'vertical')
        with patch('hinglish_broll.stock_browser_client.BrowserSearch.search',return_value=[]),patch.object(search,'page',side_effect=AssertionError('HTTP should not run')):
            self.assertEqual(list(search.stock_site('pexels','bed')),[])
        self.assertIn('Chrome',search.status['pexels'])

    def test_unknown_browser_dimensions_are_deferred_to_real_media_decoder(self):
        from hinglish_broll.stock_browser_client import BrowserSearch
        client=BrowserSearch(self.folder)
        row={'page_url':'https://pixabay.com/videos/bed-123/','media_url':'https://cdn.pixabay.com/video/123-large.mp4','title':'Bed','width':0,'height':0,'duration':0}
        with patch.object(client,'_api',side_effect=[{'connected':True,'providers':['pixabay']},{'id':'test'},{'status':'complete','results':[row]}]):
            self.assertEqual(len(client.search('pixabay','bed','vertical')),1)

    def test_parallel_capability_requires_new_server_and_extension(self):
        from hinglish_broll.stock_browser_client import BrowserSearch
        client=BrowserSearch(self.folder)
        for status,expected in [({'connected':True,'version':'0.1.2'},False),({'connected':True,'version':'0.1.1','parallel_provider_claims':True},False),({'connected':True,'version':'0.1.2','parallel_provider_claims':True},True)]:
            with patch.object(client,'_api',return_value=status):self.assertEqual(client.parallel_supported(),expected)

if __name__=='__main__':unittest.main()
