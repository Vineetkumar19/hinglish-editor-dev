import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from tools.weekly_startup import active_plans,run


class StartupTests(unittest.TestCase):
    def test_no_enabled_plan_starts_no_apps_and_needs_no_credentials(self):
        with tempfile.TemporaryDirectory() as temp,patch('tools.weekly_startup.hidden_launch',side_effect=AssertionError('Unexpected application launch')):
            self.assertEqual(run(Path(temp)),{'status':'no_enabled_plans','apps_started':[]})

    def test_only_enabled_actionable_plans_need_login_startup(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);path=root/'cache/publisher/weekly-seo.sqlite3';path.parent.mkdir(parents=True)
            with closing(sqlite3.connect(path)) as db,db:
                db.execute('CREATE TABLE plans(data TEXT)')
                for status in ['complete','paused','cancelled','needs_review']:
                    db.execute('INSERT INTO plans VALUES(?)',(json.dumps({'enabled':True,'status':status}),))
                db.execute('INSERT INTO plans VALUES(?)',(json.dumps({'enabled':False,'status':'active'}),))
            self.assertFalse(active_plans(root))
            with closing(sqlite3.connect(path)) as db,db:db.execute('INSERT INTO plans VALUES(?)',(json.dumps({'enabled':True,'status':'awaiting_publication'}),))
            self.assertTrue(active_plans(root))


if __name__=='__main__':unittest.main()
