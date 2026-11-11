import unittest,tempfile,json,datetime as dt,uuid
from pathlib import Path
import app,research
class Contracts(unittest.TestCase):
 def setUp(self):
  testdir=app.ROOT/'test-data';testdir.mkdir(exist_ok=True);self.old=app.DB;app.DB=testdir/(uuid.uuid4().hex+'.sqlite');app.init();app.put('config',{**research.DEFAULTS,'mode':'manual','event':'game release','gpt_enabled':False,'enabled':False,'interval_minutes':30})
 def tearDown(self):app.DB=self.old
 def test_off_never_invokes_model(self):
  def forbidden(*a):raise AssertionError('Model was invoked whileOFF')
  self.assertEqual(research.run(forbidden,app.get,forbidden,True)['status'],'off')
  c=app.app.test_client();self.assertEqual(c.post('/api/gpt',headers={'X-Inbox-Token':app.TOKEN}).status_code,400)
 def test_csrf(self):self.assertEqual(app.app.test_client().post('/api/review',json={'id':'x','review':'keep'}).status_code,403)
 def test_dedupe_and_review_preservation(self):
  row={'url':'https://x.com/a/status/123?utm_source=x','title':'Meme','published':''}
  self.assertEqual(app.ingest([row]),1);self.assertEqual(app.ingest([row]),0)
  with app.db()as c:c.execute('UPDATE items SET review="keep"')
  row['media_url']='https://pbs.twimg.com/a.jpg';app.ingest([row])
  with app.db()as c:r=c.execute('SELECT * FROM items').fetchone();self.assertEqual(r['review'],'keep');self.assertEqual(r['published'],'')
 def test_window_and_dates(self):
  c={**research.DEFAULTS,'gpt_enabled':True};z=dt.timezone(dt.timedelta(hours=5,minutes=30));n=lambda h,m:dt.datetime(2026,12,1,h,m,tzinfo=z)
  self.assertIsNone(research.slot(c,n(17,59)));self.assertIsNotNone(research.slot(c,n(18,0)));self.assertEqual(research.slot(c,n(18,1)),research.slot(c,n(18,29)));self.assertNotEqual(research.slot(c,n(18,29)),research.slot(c,n(18,30)));self.assertIsNone(research.slot(c,n(0,0)))
  c['active_from']='2026-12-02';self.assertIsNone(research.slot(c,n(18,0)))
 def test_validation_and_ssrf(self):
  with self.assertRaises(ValueError):research.validate({'domains':'https://secret.invalid/a'},research.DEFAULTS)
  self.assertFalse(app.media_allowed('http://127.0.0.1/image'));self.assertFalse(app.media_allowed('https://evil.com/image'));self.assertIsNone(app.platform('javascript:alert(1)'))
 def test_news_feed_excludes_stale_or_future_dates(self):
  from email.utils import format_datetime
  import xml.etree.ElementTree as ET
  n=dt.datetime.now(dt.timezone.utc)
  entries=[('recent',n-dt.timedelta(hours=1)),('stale',n-dt.timedelta(days=20)),('future',n+dt.timedelta(days=2))]
  xml='<rss><channel>'+''.join('<item><title>'+title+'</title><link>https://news.xbox.com/'+title+'</link><pubDate>'+format_datetime(date)+'</pubDate></item>'for title,date in entries)+'</channel></rss>'
  self.assertEqual([r['title']for r in app.rss_rows(ET.fromstring(xml),source='news')],['recent'])
if __name__=='__main__':unittest.main()
