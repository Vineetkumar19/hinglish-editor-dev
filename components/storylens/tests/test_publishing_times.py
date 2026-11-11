from datetime import datetime,timedelta
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from hinglish_app.publishing_times import choose,window
from hinglish_app.distribution_schedule import contract
from hinglish_app.assistant_publishing_context import IST


class PublishingTimesTests(TestCase):
    policy={'start':'17:00','end':'21:00'}
    workflow={'daily_time':'19:00','short_release_window':{'enabled':True,'start':'17:00','end':'21:00'}}

    def test_upload_now_means_entire_requested_batch_even_without_repeating_a_count(self):
        for text in ('upload now','upload them now','post these reels now','upload 2 reel on cricket channel now','publish the Shorts immediately'):
            spec=contract(text,self.workflow)
            self.assertTrue(spec['immediate_first'],text)
            self.assertTrue(spec['immediate_all'],text)
            self.assertNotIn('random_window',spec)
        for text in ('schedule these Reels','schedule them now','schedule two Shorts tomorrow'):
            self.assertFalse(contract(text,self.workflow)['immediate_first'],text)
        self.assertNotIn('immediate_all',contract('first Reel now and second tomorrow',self.workflow))

    def test_immediate_upload_status_does_not_claim_to_wait_for_a_release_time(self):
        from hinglish_app.assistant_publish import instagram_waiting_message
        immediate={'instagram_rows':[{'status':'queued','immediate':True,'publish_at':''}]*2}
        scheduled={'instagram_rows':[{'status':'queued','immediate':False,'publish_at':'2032-01-02T19:00:00+05:30'}]}
        self.assertIn('ready now',instagram_waiting_message(immediate))
        self.assertNotIn('release times',instagram_waiting_message(immediate))
        self.assertIn('release times',instagram_waiting_message(scheduled))

    def test_seven_posts_on_each_platform_get_saved_distinct_minutes_and_survive_restart(self):
        now=datetime(2032,1,1,10,tzinfo=IST)
        with TemporaryDirectory(dir=Path.cwd()/'tmp') as tmp:
            values=[]
            for i in range(7):
                day=(now+timedelta(days=i)).date().isoformat()
                for platform in ('youtube','instagram'):
                    key=f'clip-{i}:cricket:{platform}'
                    instant=choose(tmp,key,day,self.policy,now)
                    self.assertTrue('17:00'<=instant.strftime('%H:%M')<='21:00')
                    self.assertEqual(choose(tmp,key,day,self.policy,now+timedelta(days=30)),instant)
                    values.append(instant.strftime('%H:%M'))
            self.assertEqual(len(set(values)),14)
            self.assertEqual(len(json.loads((Path(tmp)/'release-times.json').read_text())['slots']),14)

    def test_current_day_uses_only_remaining_window_and_late_day_rolls_to_tomorrow(self):
        now=datetime(2032,1,1,20,45,tzinfo=IST)
        spec=contract('schedule 2 reels daily',self.workflow,now)
        self.assertEqual(spec['first_date'],'2032-01-01')
        self.assertGreater(spec['clock'],'20:45')
        with TemporaryDirectory(dir=Path.cwd()/'tmp') as tmp:
            instant=choose(tmp,'clip:instagram','2032-01-01',self.policy,now)
            self.assertGreater(instant,now+timedelta(minutes=1))
            self.assertLessEqual(instant.hour,21)
            with self.assertRaisesRegex(ValueError,'has passed'):
                choose(tmp,'another:instagram','2032-01-01',self.policy,now+timedelta(hours=1))
        late=contract('schedule 2 reels daily',self.workflow,now.replace(hour=22))
        self.assertEqual(late['first_date'],'2032-01-02')

    def test_explicit_times_intervals_and_saved_matching_override_random_default(self):
        for text in ('schedule 2 reels tomorrow at 7 pm','post first now and second tomorrow 7 pm',
                     'post 2 reels now with a 1 minute gap','post them in 2 minutes',
                     'match the YouTube dates'):
            with self.subTest(text=text):self.assertIsNone(window(text,self.workflow))
        immediate=contract('post 2 reels on Instagram now',self.workflow)
        self.assertTrue(immediate['immediate_all'])
        self.assertEqual(window('schedule 2 reels on 27 October',self.workflow),self.policy)
        self.assertEqual(window('Use the default random evening times.',self.workflow),self.policy)
        self.assertEqual(window('random times between 5 pm and 9 pm',self.workflow),self.policy)
