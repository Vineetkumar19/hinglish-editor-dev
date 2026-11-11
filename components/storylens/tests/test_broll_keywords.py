import unittest
from unittest.mock import Mock
from hinglish_cut.model import Word
from hinglish_broll.phrases import Phrase
from hinglish_broll.keywords import discover,anchor_words,physical_keyword


class KeywordOptionsTests(unittest.TestCase):
    def test_years_and_generic_actions_are_not_named_identities(self):
        from hinglish_broll.subjects import specific_subject
        for generic in ('2009','2016','final','first wicket','batting collapse','batting line up','scoreboard display'):
            self.assertEqual(specific_subject(generic),'')
        self.assertEqual(specific_subject('RCB'),'RCB')
        self.assertEqual(specific_subject('Meenakshi temple'),'Meenakshi temple')

    def test_named_search_keeps_sport_year_and_action_context(self):
        from types import SimpleNamespace
        from hinglish_broll.pipeline import gather_candidates
        client=Mock();client.name='web';client.search.return_value=[]
        slot=SimpleNamespace(duration=1,moment=SimpleNamespace(queries=['2009 IPL final'],subject='RCB'))
        timeline=SimpleNamespace(width=720,height=1280)
        gather_candidates(slot,None,None,[client],'portrait',timeline,6,None,lambda _:None,'india')
        queries=[call.args[0] for call in client.search.call_args_list]
        self.assertEqual(len(queries),2)
        self.assertTrue(all(all(word in query for word in ('RCB','2009','IPL','final')) for query in queries),queries)

    def test_named_video_leads_survive_weak_thumbnail_scores_without_wrong_years(self):
        from hinglish_broll.ranker import keyword_backups
        from hinglish_broll.stock import Candidate
        def candidate(title,score):
            return Candidate('web',title,title,60,1280,720,score=score,extraction=True)
        right=candidate('RCB vs RR IPL 2009 highlights',-.12)
        wrong=candidate('RCB IPL 2016 highlights',.5)
        missing=candidate('IPL 2009 highlights',-1)
        self.assertEqual(keyword_backups('2009 IPL season',[wrong,missing,right]),[right])

    def test_stock_cricket_actions_have_a_broad_sport_search_backup(self):
        from hinglish_broll.internet import stock_keyword
        for query in ('first wicket','cricket batting line up','RCB 2016','IPL final'):
            self.assertEqual(stock_keyword(query),'cricket')
        self.assertNotEqual(stock_keyword('nightclub interior'),'cricket')

    def test_generic_cricket_phrases_search_visible_actions_without_relabeling_a_team(self):
        for word,physical in [('batting line-up','cricket batting'),('batting collapse','cricket batting'),
                              ('final match','cricket match'),('first wicket','cricket wicket'),('crowd reaction','cricket crowd')]:
            term,queries=physical_keyword({'keyword':word,'queries':['cricket '+word]})
            self.assertEqual(term,physical)
            self.assertEqual(queries[0],physical)
        self.assertEqual(physical_keyword({'keyword':'RCB team','queries':['RCB cricket team']})[0],'RCB team')

    def test_same_phrase_can_have_sleep_bar_and_club_at_their_own_words(self):
        words=[Word(w,13+i*.25,13+i*.25+.2) for i,w in enumerate(
            'Log soch chuke hote hain koi launch nahin koi club nahin'.split())]
        phrase=Phrase(0,words[0].start,words[-1].end,' '.join(w.text for w in words))
        llm=Mock();llm.json.return_value={'keywords':[
            {'word_index':1,'keyword':'person sleeping','queries':['person asleep','sleeping person','bedroom sleep'],'identity':''},
            {'word_index':6,'keyword':'bar lounge','queries':['bar interior','bar counter','lounge interior'],'identity':''},
            {'word_index':9,'keyword':'nightclub','queries':['nightclub interior','people dancing','disco party'],'identity':''}]}
        slots=discover(llm,[phrase],words,{},10,'Collect related options',lambda _:None)
        self.assertEqual([s.start for s in slots],[13.25,14.5,15.25])
        self.assertEqual(slots[0].end,14.5)
        self.assertEqual(slots[1].end,15.25)
        self.assertNotIn('Log soch',slots[1].text)
        self.assertEqual([s.moment.visual for s in slots],['person sleeping','bar interior','nightclub interior'])

    def test_abstract_rhetoric_does_not_replace_physical_searches(self):
        self.assertEqual(physical_keyword({'keyword':'people asking','queries':['people questioning']}),('',[]))
        self.assertEqual(physical_keyword({'keyword':'lack of nightlife','queries':['nightlife absence']})[0],'nightclub interior')
        self.assertEqual(physical_keyword({'keyword':'enjoyment definition','queries':['definition of fun']})[0],'people having fun')

    def test_missing_appliances_search_the_actual_objects_not_abstract_absence(self):
        term,queries=physical_keyword({'keyword':'washing machine','queries':['no washing machine','missing laundry','lack of appliance']})
        self.assertEqual(term,'washing machine')
        self.assertEqual(queries[0],'washing machine')
        self.assertNotIn('no washing machine',queries)
        self.assertEqual(physical_keyword({'keyword':'AC','queries':['no AC']})[0],'air conditioner')
        self.assertEqual(physical_keyword({'keyword':'Wi Fi','queries':['Wi Fi missing']})[0],'wireless router')
        self.assertEqual(physical_keyword({'keyword':'closed shops','queries':['closed shops']})[0],'closed shops')

    def test_valid_concepts_added_on_repair_are_kept(self):
        words=[Word('club',1.,1.2),Word('enjoy',5.,5.2)]
        phrases=[Phrase(i,w.start,w.end,w.text) for i,w in enumerate(words)]
        bad={'word_index':0,'keyword':'no club','queries':['no club'],'identity':''}
        extra={'word_index':1,'keyword':'people enjoying','queries':['people having fun'],'identity':''}
        llm=Mock();llm.json.side_effect=[{'keywords':[bad]},{'keywords':[bad,extra]},{'keywords':[bad,extra]}]
        slots=discover(llm,phrases,words,{},10,'',lambda _:None)
        self.assertEqual([s.moment.visual for s in slots],['nightclub interior','people having fun'])

    def test_joined_stock_keyword_matches_actual_split_speech_without_inventing_time(self):
        words=[Word('night',2.,2.3),Word('life,',2.3,2.6)]
        p=Phrase(0,2.,2.6,'night life,')
        self.assertEqual(anchor_words('nightlife',p,words),(0,1))
        self.assertIsNone(anchor_words('bar',p,words))
