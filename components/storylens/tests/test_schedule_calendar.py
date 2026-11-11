"""Calendar inputs and changed release dates, independent of any source or channel."""
import calendar
from datetime import datetime,timedelta
import unittest

from hinglish_app.assistant_publishing_context import IST,daily_dates,schedule_literals


class CalendarTests(unittest.TestCase):
    NOW=datetime(2030,6,15,12,tzinfo=IST)

    def test_undated_instagram_upload_is_now_but_scheduled_and_other_platforms_are_not(self):
        from hinglish_app.distribution_schedule import contract
        for text in ('take mi final and extract 1 short clip n upload on my cricket insta page',
                     'upload it on my cricket insta page','Extract two clips and post on Instagram when ready'):
            self.assertTrue(contract(text,{'daily_time':'19:00'},self.NOW)['immediate_first'],text)
        for text in ('Schedule this on Instagram daily','Upload it on Instagram tomorrow at 19:00',
                     'Upload the clip to YouTube','How do I upload on Instagram?',
                     'Do not upload it on Instagram','Upload on Instagram on Friday'):
            self.assertFalse(contract(text,{'daily_time':'19:00'},self.NOW)['immediate_first'],text)

    def test_post_now_accepts_selected_clip_but_not_negation_or_future_release(self):
        from hinglish_app.distribution_schedule import contract
        for text in ('Post only the second Short now on Instagram',
                     'Upload clip 7 right now', 'Publish it now'):
            self.assertTrue(contract(text,{'daily_time':'19:00'},self.NOW)['immediate_first'],text)
        for text in ("Don't post it now", 'Post it tomorrow, prepare it now',
                     'Schedule this video for next Friday; check now'):
            self.assertFalse(contract(text,{'daily_time':'19:00'},self.NOW)['immediate_first'],text)

    def test_shared_month_and_ordinals_in_every_month(self):
        for month in range(1,13):
            for name in (calendar.month_name[month],calendar.month_abbr[month]):
                for pair in ('3 and 4','3rd and 4th','3 to 4'):
                    with self.subTest(month=name,pair=pair):
                        spec=schedule_literals(f'reschedule it for {pair} {name} 2032 at 7:30 p.m.',self.NOW)
                        self.assertEqual(spec,{'first_date':f'2032-{month:02}-03',
                            'end_date':f'2032-{month:02}-04','clock':'19:30'})

    def test_trial_gap_wording_overrides_daily_cadence(self):
        from hinglish_app.distribution_schedule import contract
        for wording in ('for trail version i want u to upload both video at once after 2 min gap between the video',
                        'Post both Reels now with a gap of two minutes',
                        'Upload both videos immediately, 120 sec apart'):
            result=contract(wording,{'daily_time':'19:00'},self.NOW)
            self.assertTrue(result['immediate_first'],wording)
            self.assertEqual(result['interval_seconds'],120,wording)
            self.assertFalse(result.get('immediate_all'),wording)

    def test_both_now_is_distinct_from_one_now_and_the_second_tomorrow(self):
        from hinglish_app.distribution_schedule import contract
        self.assertTrue(contract('Post both videos now on Instagram',{'daily_time':'19:00'},self.NOW)['immediate_all'])
        self.assertFalse(contract('Post one video now and the second tomorrow at 7 pm on Instagram',{'daily_time':'19:00'},self.NOW).get('immediate_all'))
        self.assertFalse(contract('Do not upload both videos at once',{'daily_time':'19:00'},self.NOW)['immediate_first'])

    def test_month_first_and_day_first_are_equivalent(self):
        for text in ('March 3rd and 4th, 2032','3 March 2032 and 4 March 2032',
                     '2032-03-03 to 2032-03-04','3rd and 4th Mar. 2032'):
            with self.subTest(text=text):
                self.assertEqual(schedule_literals(text,self.NOW),
                    {'first_date':'2032-03-03','end_date':'2032-03-04'})

    def test_cross_month_and_year_with_leap_day(self):
        for text,start,end in (
            ('28 February 2032 to 1 March 2032','2032-02-28','2032-03-01'),
            ('31 December 2030 to 1 January','2030-12-31','2031-01-01'),
            ('31 December to 1 January','2030-12-31','2031-01-01')):
            with self.subTest(text=text):
                spec=schedule_literals(text,self.NOW)
                self.assertEqual((spec['first_date'],spec['end_date']),(start,end))

    def test_invalid_calendar_dates_and_reversed_ranges_are_rejected(self):
        for text in ('29 February 2031','31 April 2032','2032-02-30',
                     '24 to 23 October 2032','31 December 2032 to 1 January 2032'):
            with self.subTest(text=text),self.assertRaises(ValueError):
                schedule_literals(text,self.NOW)

    def test_relative_days_use_india_clock_and_24_hour_time(self):
        now=datetime(2030,12,31,23,59,tzinfo=IST)
        self.assertEqual(schedule_literals('tomorrow at 00:05',now),
                         {'first_date':'2031-01-01','clock':'00:05'})
        self.assertEqual(schedule_literals('today at 23:40',now),
                         {'first_date':'2030-12-31','clock':'23:40'})

    def test_changing_dates_keeps_daily_clock_across_every_calendar_boundary(self):
        clips=[{'publish_at':'2031-10-21T19:00:00+05:30'} for _ in range(3)]
        for year in (2032,2033):
            for month in range(1,13):
                first=datetime(year,month,calendar.monthrange(year,month)[1],19,tzinfo=IST)
                dates=daily_dates(clips,{'first_date':first.date().isoformat()})
                self.assertEqual([datetime.fromisoformat(d) for d in dates],
                                 [first+timedelta(days=i) for i in range(3)])
        self.assertEqual(clips[0]['publish_at'],'2031-10-21T19:00:00+05:30')


if __name__=='__main__':unittest.main()
