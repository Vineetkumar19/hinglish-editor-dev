import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from hinglish_broll.internet import stock_keyword
from hinglish_broll.stock import PixabayClient

class ObjectSearchTests(unittest.TestCase):
    def test_wardrobe_aliases_retrieve_the_provider_closet_inventory(self):
        for term in ('wardrobe','closet interior','clothes cupboard'):
            self.assertEqual(stock_keyword(term),'closet')
        base=Path(__file__).resolve().parents[1]/'cache/test-object-search';base.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as temporary:
            client=PixabayClient('unit-fixture-key',temporary);queries=[]
            def response(url,params,headers=None):
                queries.append(params['q'])
                return {'hits':([{'id':163116,'type':'film','duration':8,'tags':'closet, clothes, hanger',
                    'videos':{'large':{'width':1920,'height':1080,'url':'https://example.org/unit-video.mp4'}}}]
                    if params['q']=='closet' else [])}
            with patch.object(client,'_get',side_effect=response):
                candidates=client.search('wardrobe','portrait',1080,1920,per_page=12)
            self.assertEqual(queries,['wardrobe','closet'])
            self.assertEqual([c.id for c in candidates],['pixabay:163116'])
            self.assertEqual(candidates[0].kind,'video')
            self.assertFalse(candidates[0].verified_description)

if __name__=='__main__':unittest.main()
