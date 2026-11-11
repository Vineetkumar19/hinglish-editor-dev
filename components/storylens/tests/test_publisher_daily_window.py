from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from hinglish_publish.store import Store,IST

class DailyWindowTests(TestCase):
    def test_paired_slots_vary_within_ist_window_append_and_survive_retry(self):
        with TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as tmp:
            store=Store(tmp);now=datetime(2026,10,26,12,tzinfo=IST).timestamp()
            def batch(start,n):return [dict(fingerprint='clip-'+str(i),kind='short',platform=p,profile='cricket') for i in range(start,start+n) for p in ('youtube','instagram')]
            first=batch(0,7);ids=store.add_batch(first,now=now,daily_window=True)
            dates={};times=set()
            for row in store.list():
                local=datetime.fromtimestamp(row['due'],IST);self.assertTrue(17<=local.hour<21 or local.hour==21 and local.minute==0)
                dates.setdefault(row['fingerprint'],[]).append(local);times.add((local.hour,local.minute))
            self.assertTrue(all(len(set(pair))==1 for pair in dates.values()));self.assertEqual(len({pair[0].date() for pair in dates.values()}),7)
            self.assertGreater(len(times),1)
            snapshot={r['id']:r['due'] for r in store.list()}
            self.assertEqual(Store(tmp).add_batch(first,now=now,daily_window=True),ids)
            Store(tmp).add_batch(batch(7,2),now=now,daily_window=True)
            rows=store.list();self.assertEqual(len(rows),18);self.assertEqual({r['id']:r['due'] for r in rows if r['id'] in ids},snapshot)
            self.assertGreater(min(r['due'] for r in rows if r['id'] not in ids),max(snapshot.values()))
