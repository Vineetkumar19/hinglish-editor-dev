"""Two bounded search strategies; no live web/model access in these cases."""
import threading
import unittest

from hinglish_photos.search_agents import heading_query, search_candidates


class PhotoSearchAgentTests(unittest.TestCase):
    def test_heading_uses_visible_words_and_publisher_without_completing_ellipsis(self):
        row={'caption':'IPL 2020, Kings XI Punjab season revie…','publisher':'Scroll.in'}
        self.assertEqual(heading_query(row),'"IPL 2020, Kings XI Punjab season revie" Scroll.in')
        self.assertEqual(heading_query({'caption':'…','publisher':'Scroll.in'}),'')

    def test_both_searches_start_concurrently_and_keep_their_identity(self):
        barrier=threading.Barrier(2,timeout=2)
        class Finder:
            def images(self,query,limit=24):
                barrier.wait()
                return [{'url':'https://photos.example/'+('title' if query.startswith('"') else 'visual')+'.jpg'}]
        batches=list(search_candidates(Finder(),{
            'query':'red cricket team celebrating','caption':'Schedule announced for IPL 2020','publisher':'Punjab Kings'}))
        self.assertEqual({batch['agent'] for batch in batches},{'visual','heading'})
        for batch in batches:
            self.assertEqual(batch['candidates'][0]['search_agent'],batch['agent'])

    def test_one_search_failure_does_not_discard_the_other_search(self):
        class Finder:
            def images(self,query,limit=24):
                if query.startswith('"'):raise TimeoutError('title provider unavailable')
                return [{'url':'https://photos.example/visual.jpg'}]
        batches=list(search_candidates(Finder(),{'query':'team photo','caption':'Some visible heading'}))
        self.assertEqual(sum(len(batch['candidates']) for batch in batches),1)
        self.assertTrue(next(batch for batch in batches if batch['agent']=='heading')['error'])

    def test_missing_heading_does_not_invent_a_second_query(self):
        calls=[]
        class Finder:
            def images(self,query,limit=24):calls.append(query);return []
        list(search_candidates(Finder(),{'query':'team photo','caption':'','publisher':'Unknown'}))
        self.assertEqual(calls,['team photo'])

    def test_cancelled_collection_never_dispatches_searches(self):
        cancel=threading.Event();cancel.set()
        class Finder:
            def images(self,*args,**kwargs):raise AssertionError('search started after cancellation')
        with self.assertRaises(InterruptedError):
            list(search_candidates(Finder(),{'query':'team photo','caption':'A heading'},cancel))
