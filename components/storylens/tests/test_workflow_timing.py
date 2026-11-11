import copy
import unittest
from types import SimpleNamespace
from datetime import datetime
from hinglish_publish.store import IST
from hinglish_publish.workflow_timing import parse_request,validate,apply

class Engine:
    def __init__(self,jobs=()):self.publisher=SimpleNamespace(store=SimpleNamespace(list=lambda:list(jobs)))
    def _save(self,draft):self.saved=copy.deepcopy(draft)

class TimingTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,30,21,tzinfo=IST).timestamp()
        self.timing={'long_at':'2026-10-31T19:00:00+05:30','shorts_start':'2026-10-30','instagram_interval':60}
    def test_explicit_request_parses_scopes(self):
        # A fixed future date isolates parsing from the test machine clock.
        x=parse_request('Schedule long on 2099-10-31 at 19:00 IST. Shorts daily from 2099-10-30. Instagram every 1 minute.')
        self.assertEqual(x,{'long_at':'2099-10-31T19:00:00+05:30','shorts_start':'2099-10-30','instagram_interval':60})
    def test_long_exact_and_short_consecutive_from_today(self):
        e=Engine();d={'count':1,'jobs_by_platform':{}}
        apply(e,d,'long','youtube',self.timing,self.now)
        self.assertEqual(d['requested_release_slots']['youtube'],[datetime(2026,10,31,19,tzinfo=IST).timestamp()])
        d={'count':5,'jobs_by_platform':{}}
        apply(e,d,'shorts','youtube',self.timing,self.now)
        slots=d['requested_release_slots']['youtube']
        self.assertEqual([datetime.fromtimestamp(t,IST).strftime('%Y-%m-%d') for t in slots],['2026-10-30','2026-10-31','2026-11-01','2026-11-02','2026-11-03'])
        self.assertEqual(slots[0],self.now+120)
        apply(e,d,'shorts','instagram',self.timing,self.now)
        self.assertEqual(d['requested_release_slots']['instagram'],[self.now+60*n for n in range(1,6)])
        self.assertEqual(d['requested_release_slots']['youtube'],slots)
    def test_natural_long_date_and_reel_gap(self):
        x=parse_request('Schedule the long video on cricket YouTube for 1 November 2099 at 7 PM IST. Make 5 Shorts and post the same 5 Instagram Reels one minute apart for testing.')
        self.assertEqual(x,{'long_at':'2099-11-01T19:00:00+05:30','instagram_interval':60})
        x=parse_request('Schedule long on cricket YouTube for 2 November 2099, 12:15 AM IST. Instagram Reels 2 minutes apart.')
        self.assertEqual(x,{'long_at':'2099-11-02T00:15:00+05:30','instagram_interval':120})
    def test_queued_jobs_are_not_moved_and_past_dates_refused(self):
        d={'count':5,'jobs_by_platform':{'instagram':['existing']}}
        apply(Engine(),d,'shorts','instagram',self.timing,self.now)
        self.assertNotIn('requested_release_slots',d)
        with self.assertRaises(ValueError):validate({'shorts_start':'2026-10-29'},self.now)
    def test_new_batch_appends_after_existing_days_in_same_channel(self):
        last=datetime(2026,11,3,19,tzinfo=IST).timestamp()
        jobs=[dict(profile='cricket',platform='youtube',kind='short',prepare_post_id='old',status='scheduled',authorized_at=1,account_id='channel',due=last),
              dict(profile='gaming',platform='youtube',kind='short',status='scheduled',authorized_at=1,due=last+864000)]
        d={'id':'new','profile':'cricket','bindings':{'youtube':{'id':'channel'}},'count':5,'jobs_by_platform':{}}
        apply(Engine(jobs),d,'shorts','youtube',self.timing,self.now)
        days=[datetime.fromtimestamp(t,IST).strftime('%Y-%m-%d') for t in d['requested_release_slots']['youtube']]
        self.assertEqual(days,['2026-11-04','2026-11-05','2026-11-06','2026-11-07','2026-11-08'])
        apply(Engine(jobs),d,'shorts','instagram',{'shorts_start':'2026-10-30'},self.now)
        self.assertEqual(d['requested_release_slots']['instagram'],d['requested_release_slots']['youtube'])
    def test_invalid_intervals_and_missing_timezone_refused(self):
        for x in [{'instagram_interval':0},{'instagram_interval':True},{'long_at':'2026-10-31T19:00:00'}]:
            with self.assertRaises(ValueError):validate(x,self.now)

if __name__=='__main__':unittest.main()
