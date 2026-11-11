import json,tempfile,unittest
from pathlib import Path


class CatalogueTests(unittest.TestCase):
    def test_coverr_reads_advertised_free_raw_video_and_rejects_premium_and_ai(self):
        from hinglish_broll.website_catalogs import coverr_candidates
        def item(slug,**extra):
            return {'slug':slug,'title':'Fridge','isPremium':False,'isAiGenerated':False,
                'duration':12,'maxWidth':720,'maxHeight':1280,
                'urls':{'mp4':'https://cdn.coverr.co/videos/'+slug+'/1080p.mp4'},**extra}
        records=[item('free-fridge'),item('premium',isPremium=True),item('ai',isAiGenerated=True)]
        page='<a href="/videos/free-fridge">Free</a><a href="/videos/premium">Premium</a><a href="/videos/ai">AI</a>'
        page+='<script type="application/json">'+json.dumps({'data':records})+'</script>'
        found=coverr_candidates(page,'fridge','vertical')
        self.assertEqual([c.page_url for c in found],['https://coverr.co/videos/free-fridge'])
        self.assertEqual((found[0].width,found[0].height),(720,1280))

    def test_coverr_does_not_use_unlinked_recommendations_or_unknown_paid_status(self):
        from hinglish_broll.website_catalogs import coverr_candidates
        row={'slug':'other','title':'Other','isPremium':False,'isAiGenerated':False,
             'urls':{'mp4':'https://cdn.coverr.co/videos/other/1080p.mp4'}}
        text='<script type="application/json">'+json.dumps(row)+'</script>'
        self.assertEqual(coverr_candidates(text,'bed',None),[])

    def test_videezy_requires_explicit_free_flag_and_skips_template_pages(self):
        from hinglish_broll.website_catalogs import videezy_candidates,videezy_links
        page='<script>var resource_is_premium = false;</script><meta property="og:title" content="Fridge"><video src="https://static.videezy.com/system/resources/fridge.mp4"></video>'
        self.assertEqual(len(videezy_candidates('https://www.videezy.com/technology/123-fridge',page,'fridge')),1)
        self.assertEqual(videezy_candidates('https://www.videezy.com/technology/123-fridge',page.replace('false','true'),'fridge'),[])
        self.assertEqual(videezy_candidates('https://www.videezy.com/technology/123-fridge',page.replace('resource_is_premium','unknown'),'fridge'),[])
        links=videezy_links('<a href="/technology/123-fridge">a</a><a href="/after-effects-templates/234-fridge">b</a><a href="https://evil.test/technology/345-fridge">c</a>')
        self.assertEqual(links,['https://www.videezy.com/technology/123-fridge'])

    def test_a_failed_source_cannot_stop_other_sources_and_choices_rotate_sources(self):
        from hinglish_broll.website_catalogs import interleave
        from hinglish_broll.stock import Candidate
        def failed():raise RuntimeError('page broken');yield
        def rows(source):
            for n in range(2):yield Candidate(source,source+str(n),source,10,720,1280)
        status={}
        values=list(interleave([('blocked',failed()),('one',rows('one')),('two',rows('two'))],status))
        self.assertEqual([v.source for v in values],['one','two','one','two'])
        self.assertIn('blocked',status)

    def test_media_policy_allows_new_catalogue_cdns_not_arbitrary_urls(self):
        from hinglish_broll.website_catalogs import media_allowed
        self.assertTrue(media_allowed('https://cdn.coverr.co/videos/clip/1080p.mp4'))
        self.assertTrue(media_allowed('https://static.videezy.com/system/resources/clip.mp4'))
        self.assertFalse(media_allowed('https://127.0.0.1/clip.mp4'))
        self.assertFalse(media_allowed('https://cdn.coverr.co.evil.test/clip.mp4'))
        self.assertFalse(media_allowed('https://user@cdn.coverr.co/clip.mp4'))

    def test_one_oversized_search_does_not_disable_the_entire_website(self):
        from hinglish_broll.website_catalogs import CatalogueSearch
        from unittest.mock import patch
        base=Path(__file__).resolve().parents[1]/'cache/test-catalogues';base.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as folder:
            search=CatalogueSearch(folder,'vertical')
            with patch('hinglish_broll.website_review._html',side_effect=[ValueError('Website page is too large; source skipped.'),'<html>OK</html>']):
                with self.assertRaises(ValueError):search.page('coverr','https://coverr.co/s?q=city')
                self.assertNotIn('coverr',search.blocked)
                self.assertEqual(search.page('coverr','https://coverr.co/s?q=bed'),'<html>OK</html>')

    def test_current_broll_ui_does_not_offer_api_or_vision_mode(self):
        root=Path(__file__).resolve().parents[1]
        page=(root/'hinglish_app/static/index.html').read_text('utf-8')
        self.assertNotIn('<option value="strict">',page)

if __name__=='__main__':unittest.main()
