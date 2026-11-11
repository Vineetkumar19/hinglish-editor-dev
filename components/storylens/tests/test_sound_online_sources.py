import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from hinglish_sound import online_sources as s

class SourcesTests(unittest.TestCase):
    def test_default_has_keyless_commons_but_no_paid_providers(self):
        with TemporaryDirectory() as d,patch.object(s,'credentials',return_value={}):
            status=s.status(d)
        self.assertTrue(status['commons']['ready'])
        self.assertFalse(status['elevenlabs']['ready'])
        self.assertEqual(status['pixabay']['mode'],'manual')
        self.assertEqual(status['mixkit']['mode'],'website')
        self.assertEqual(status['epidemic']['mode'],'excluded')
        self.assertEqual(status['artlist']['mode'],'excluded')

    def test_license_is_explicit_and_editable(self):
        self.assertTrue(s.allowed_license('https://creativecommons.org/licenses/by/4.0/'))
        self.assertTrue(s.allowed_license('http://creativecommons.org/publicdomain/zero/1.0/'))
        self.assertTrue(s.allowed_license('http://creativecommons.org/publicdomain/zero/1.0/deed.en'))
        for url in ['','royalty free','https://creativecommons.org/licenses/by-nc/4.0/',
                    'https://creativecommons.org/licenses/by-nd/4.0/','https://creativecommons.org/licenses/by-sa/4.0/',
                    'https://creativecommons.org.evil.test/licenses/by/4.0/']:
            self.assertFalse(s.allowed_license(url))

    def test_media_urls_cannot_target_arbitrary_hosts(self):
        hosts={'upload.wikimedia.org'}
        self.assertEqual(s.checked_url('https://upload.wikimedia.org/a.ogg',hosts),'https://upload.wikimedia.org/a.ogg')
        for url in ['http://upload.wikimedia.org/a','https://upload.wikimedia.org.evil.test/a',
                    'https://upload.wikimedia.org:444/a','https://user@upload.wikimedia.org/a','file:///a']:
            with self.assertRaises(ValueError):s.checked_url(url,hosts)

    def test_commons_rejects_non_audio_and_missing_license(self):
        row={'pageid':12,'title':'File:River.ogg','imageinfo':[{'url':'https://upload.wikimedia.org/a.ogg',
             'descriptionurl':'https://commons.wikimedia.org/wiki/File:River.ogg','mime':'audio/ogg','size':100,
             'extmetadata':{'LicenseUrl':{'value':'https://creativecommons.org/publicdomain/zero/1.0/'},
                            'Artist':{'value':'<b>Artist</b>'}}}]}
        parsed=s.commons_candidate(row)
        self.assertEqual(parsed['author'],'Artist')
        self.assertEqual(parsed['id'],'12')
        row['imageinfo'][0]['mime']='video/ogg'
        self.assertIsNone(s.commons_candidate(row))
        row['imageinfo'][0]['mime']='audio/ogg';row['imageinfo'][0]['extmetadata']={}
        self.assertIsNone(s.commons_candidate(row))

    def test_openverse_accepts_only_attributed_licensed_audio_on_known_hosts(self):
        row={'id':'abc','title':'Rain on pavement','creator':'Field recordist',
             'url':'https://upload.wikimedia.org/audio/rain.ogg',
             'foreign_landing_url':'https://commons.wikimedia.org/wiki/File:Rain.ogg',
             'license_url':'https://creativecommons.org/licenses/by/4.0/',
             'filesize':1000,'tags':[{'name':'rain'}]}
        candidate=s.openverse_candidate(row)
        self.assertEqual(candidate['provider'],'openverse')
        self.assertEqual(candidate['author'],'Field recordist')
        for bad in [dict(row,license_url='https://creativecommons.org/licenses/by-nc/4.0/'),
                    dict(row,url='https://other.test/rain.ogg'),
                    dict(row,url='https://upload.wikimedia.org/rain.exe'),
                    dict(row,mature=True),dict(row,filesize='invalid'),
                    dict(row,filesize=s.MAX_BYTES+1),dict(row,foreign_landing_url='')]:
            self.assertIsNone(s.openverse_candidate(bad))

    def test_mixkit_uses_observed_modal_and_keeps_titles_with_their_ids(self):
        markup='''<div class="item-grid-card"><div data-audio-player-item-id-value="12"></div>
        <h2 class="item-grid-card__title">Rain on roof</h2><button data-download--button-modal-url-value="/free-sound-effects/download/12/"></button></div>
        <div class="item-grid-card"><div data-audio-player-item-id-value="15"></div><h2 class="item-grid-card__title">River</h2>
        <button data-download--button-modal-url-value="https://evil.test/download"></button></div>'''
        rows=s.mixkit_cards(markup,'https://mixkit.co/free-sound-effects/discover/rain/')
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['name'],'Rain on roof')
        self.assertEqual(rows[0]['id'],'12')

    def test_physical_online_search_rejects_generic_trending_click(self):
        self.assertFalse(s.relevant_candidate({'name':'Hard pop click'},'water slide splash','foley'))
        self.assertTrue(s.relevant_candidate({'name':'Water splashing into pool'},'water slide splash','foley'))

    def test_jamendo_respects_artist_download_switch(self):
        row={'id':'12','name':'Track','artist_name':'A','audiodownload_allowed':False,
             'audiodownload':'https://prod-1.storage.jamendo.com/a.mp3',
             'license_ccurl':'https://creativecommons.org/licenses/by/4.0/'}
        self.assertIsNone(s.jamendo_candidate(row))
        row['audiodownload_allowed']=True
        self.assertEqual(s.jamendo_candidate(row)['id'],'12')

    def test_free_generation_never_uses_paid_or_uncertain_allowance(self):
        ok={'tier':'free','character_count':0,'character_limit':10000,'allowed_to_extend_character_limit':False}
        self.assertTrue(s.free_generation_allowed(ok,400))
        for bad in [dict(ok,tier='starter'),dict(ok,character_count=9900),
                    dict(ok,allowed_to_extend_character_limit=True),{},dict(ok,character_count=True)]:
            self.assertFalse(s.free_generation_allowed(bad,400))

    def test_credentials_status_never_returns_a_secret(self):
        with TemporaryDirectory() as d,patch.object(s,'credentials',return_value={'ELEVENLABS_API_KEY':'private-marker'}):
            self.assertNotIn('private-marker',str(s.status(d)))

    def test_acquire_validates_kind_category_and_limits(self):
        with TemporaryDirectory() as d:
            for kwargs in [{'kind':'video'},{'category':'../../evil'},{'limit':100},{'limit':True}]:
                args={'category':'foley','limit':1,'kind':'sfx'};args.update(kwargs)
                with self.assertRaises(ValueError):s.acquire(d,'river',**args)

    def test_fallback_does_not_search_when_disabled_or_budget_exhausted(self):
        with TemporaryDirectory() as d,patch.object(s,'acquire') as fetch:
            marker=object();f=s.Fallback(d,enabled=False)
            self.assertIs(f.extend(marker,'river','ambience','sfx',None,None,lambda _:None,3),marker)
            f=s.Fallback(d,enabled=True);f.remaining=0
            self.assertIs(f.extend(marker,'river','ambience','sfx',None,None,lambda _:None,3),marker)
            fetch.assert_not_called()

    def test_optional_source_failure_keeps_local_index_and_does_not_repeat_query(self):
        with TemporaryDirectory() as d,patch.object(s,'acquire',side_effect=OSError('private diagnostic')) as fetch:
            marker=object();f=s.Fallback(d)
            for _ in range(2):
                self.assertIs(f.extend(marker,'river','ambience','sfx',None,None,lambda _:None,3),marker)
            fetch.assert_called_once()
            self.assertIn('local sounds',f.notes[0])
            self.assertNotIn('private diagnostic',str(f.notes))

    def test_music_mood_can_have_spaces_without_becoming_a_path(self):
        with TemporaryDirectory() as d,patch.object(s,'credentials',return_value={}),patch.object(s,'status',return_value={n:{'ready':False} for n in ('jamendo','openverse','mixkit','commons','elevenlabs')}):
            result=s.acquire(d,'gentle piano','Hopeful Calm',kind='music')
            self.assertEqual(result['paths'],[])

    def test_free_generation_refuses_paid_account_before_post(self):
        from unittest.mock import Mock
        with TemporaryDirectory() as d,patch.object(s,'_json',return_value={'tier':'starter'}):
            session=Mock()
            with self.assertRaises(ValueError):s._generate(session,d,'river','ambience',{'ELEVENLABS_API_KEY':'secret'},3)
            session.post.assert_not_called()

    def test_recommendation_ranking_retries_with_downloaded_candidates(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from hinglish_sound.recommendation_pipeline import LocalRuntime
        with TemporaryDirectory() as d:
            root=Path(d);before=Mock(assets=[]);before.search.return_value=[]
            asset=SimpleNamespace(path=str(root/'new.mp3'))
            after=Mock(assets=[asset]);after.search.return_value=[(asset,.7,'heard')];after.facts_for.return_value={}
            runtime=LocalRuntime.__new__(LocalRuntime)
            runtime.root=root;runtime.folder=root;runtime.settings=SimpleNamespace(online_sounds=True)
            runtime.indexes={'music':before,'sfx':before};runtime.proxy=Mock();runtime.listener=None
            runtime.progress=lambda _:None;runtime.roots={'music':[root],'sfx':[root]}
            request={'music_sections':[dict(intent='quiet piano',mood='calm',start=0,end=3)],'sfx_events':[]}
            with patch.object(s.Fallback,'extend',return_value=after) as extend,patch('hinglish_sound.recommendation_pipeline.CachedRankingIndex') as cache:
                runtime.rankings(request,Mock(),Mock(),3)
                extend.assert_called_once()
                self.assertEqual(cache.call_args_list[0].args[0],[asset])

if __name__=='__main__':unittest.main()
