"""Local analytics store, daily collector and authenticated dashboard routes."""
import csv
import io
import json
import re
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs

from . import analytics_sources as source


class Analytics:
    def __init__(self, root, browser=None):
        self.root = Path(root)
        self.browser = browser
        self.path = self.root / 'cache/app/creator-analytics.sqlite3'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.guard = threading.Lock()
        self.busy = set()
        with self.db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS analytics_rows (
                  account TEXT, kind TEXT, day TEXT, item TEXT, metrics TEXT,
                  PRIMARY KEY(account,kind,day,item)
                );
                CREATE TABLE IF NOT EXISTS analytics_status (
                  account TEXT PRIMARY KEY, attempted REAL, verified REAL, state TEXT, notes TEXT
                );
                CREATE TABLE IF NOT EXISTS analytics_disabled (account TEXT PRIMARY KEY);
            ''')

    @contextmanager
    def db(self):
        with closing(sqlite3.connect(self.path, timeout=15)) as connection, connection:
            connection.row_factory = sqlite3.Row
            yield connection

    @staticmethod
    def now():
        return datetime.now(source.IST)

    def schedule(self):
        stop = threading.Event()

        def tick():
            while not stop.is_set():
                try:
                    self.refresh(only_due=True)
                except OSError:
                    pass
                stop.wait(900)

        threading.Thread(target=tick, name='storylens-daily-analytics', daemon=True).start()
        return stop

    def refresh(self, account=None, month=None, *, only_due=False):
        now = self.now()
        today = now.date()
        due = now.replace(hour=8, minute=0, second=0, microsecond=0)
        if now < due:
            due -= timedelta(days=1)
        targets_instagram = account is None or account.startswith('instagram')
        browser = self.browser() if self.browser and targets_instagram else None
        chrome_ready = browser and browser.instagram_analytics_ready()
        with self.guard, self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            targets = []
            for key in ([account] if account else source.ACCOUNTS):
                if key in self.busy or db.execute('SELECT 1 FROM analytics_disabled WHERE account=?', (key,)).fetchone():
                    continue
                previous = db.execute('SELECT attempted,state FROM analytics_status WHERE account=?', (key,)).fetchone()
                if previous and previous['state'] == 'refreshing' and time.time() - previous['attempted'] < 900:
                    continue
                if only_due and previous and previous['attempted'] >= due.timestamp():
                    continue
                if only_due and key.startswith('instagram') and not chrome_ready:
                    continue
                db.execute('''INSERT INTO analytics_status VALUES (?,?,0,'refreshing','[]')
                    ON CONFLICT(account) DO UPDATE SET attempted=excluded.attempted,state=excluded.state''',
                           (key, time.time()))
                targets.append(key)
            self.busy.update(targets)
        if targets:
            def run():
                with ThreadPoolExecutor(max_workers=4) as pool:
                    list(pool.map(lambda key: self.collect(key, today, month), targets))
            threading.Thread(target=run, name='storylens-analytics-refresh', daemon=True).start()
        return {'refreshing': targets}

    def collect(self, account, today, month=None):
        rows = []

        def emit(kind, day, item, metrics):
            rows.append((account, kind, str(day), item, json.dumps(metrics, ensure_ascii=False)))

        this_month = str(today)[:7]
        previous_month = str(today.replace(day=1) - timedelta(days=1))[:7]
        with self.db() as db:
            backfill = not db.execute("SELECT 1 FROM analytics_rows WHERE account=? AND kind='activity' LIMIT 1", (account,)).fetchone()
        start = today - timedelta(days=400 if backfill else 40)
        platform = source.ACCOUNTS[account][0]
        try:
            if platform == 'youtube':
                state, notes = source.collect_youtube(self.root, account, today,
                    list(dict.fromkeys([this_month, previous_month, month or this_month])), start, emit)
            elif self.browser:
                from .chrome_source import collect
                state, notes = collect(self.browser(), account, today, emit)
            else:
                state, notes = 'needs_connection', ['Connect the existing StoryLens Chrome bridge.']
        except source.SourceError as error:
            state, notes = 'unavailable', [str(error)]
        except Exception:
            state, notes = 'unavailable', ['This account could not refresh. Check its saved connection and try again.']
        try:
            with self.db() as db:
                db.execute('BEGIN IMMEDIATE')
                if db.execute('SELECT 1 FROM analytics_disabled WHERE account=?', (account,)).fetchone():
                    return
                if platform == 'instagram':
                    self.instagram_daily(db, account, today, rows)
                db.executemany('''INSERT INTO analytics_rows VALUES (?,?,?,?,?)
                    ON CONFLICT(account,kind,day,item) DO UPDATE SET metrics=excluded.metrics''', rows)
                db.execute('''UPDATE analytics_status SET state=?,notes=?,
                    verified=CASE WHEN ? THEN ? ELSE verified END WHERE account=?''',
                           (state, json.dumps(notes), any(row[1] == 'snapshot' for row in rows), time.time(), account))
                db.execute("DELETE FROM analytics_rows WHERE account=? AND kind='content' AND day<?",
                           (account, str(today - timedelta(days=29))))
        finally:
            with self.guard:
                self.busy.discard(account)

    @staticmethod
    def instagram_daily(db, account, today, rows):
        current = {row[3]: json.loads(row[4]).get('grid_views') for row in rows if row[1] == 'content'}
        prior = db.execute("SELECT item,metrics FROM analytics_rows WHERE account=? AND kind='content' AND day=?",
                           (account, str(today - timedelta(days=1))))
        deltas = []
        for row in prior:
            earlier = json.loads(row['metrics']).get('grid_views')
            latest = current.get(row['item'])
            if type(earlier) is int and type(latest) is int:
                deltas.append(latest - earlier)
        if deltas:
            rows.append((account, 'activity', str(today), '', json.dumps({'views': sum(deltas), 'tracked_reels': len(deltas)})))

    def connect_youtube(self, account, monetary):
        with self.guard:
            if account in self.busy:
                raise ValueError('Wait for this account’s current request to finish.')
            self.busy.add(account)
            with self.db() as db:
                db.execute('''INSERT INTO analytics_status VALUES (?,?,0,'connecting','[]')
                    ON CONFLICT(account) DO UPDATE SET state='connecting',attempted=excluded.attempted,notes='[]' ''',
                           (account, time.time()))

        def authorize():
            try:
                source.yt_connect(self.root, account, monetary)
                with self.db() as db:
                    db.execute('DELETE FROM analytics_disabled WHERE account=?', (account,))
                self.collect(account, self.now().date())
            except Exception as error:
                detail = str(error) if isinstance(error, source.SourceError) else 'Google sign-in did not finish. Try again and select the matching channel.'
                with self.db() as db:
                    db.execute("UPDATE analytics_status SET state='unavailable',notes=? WHERE account=?", (json.dumps([detail]), account))
            finally:
                with self.guard:
                    self.busy.discard(account)

        threading.Thread(target=authorize, name='storylens-youtube-analytics-consent', daemon=True).start()

    def connect_instagram(self, account):
        with self.guard:
            if account in self.busy:
                raise ValueError('Wait for this account’s current request to finish.')
            with self.db() as db:
                db.execute('DELETE FROM analytics_disabled WHERE account=?', (account,))
        self.refresh(account)

    def disconnect(self, account):
        with self.guard, self.db() as db:
            if account in self.busy:
                raise ValueError('Wait for this account’s current request to finish.')
            db.execute('INSERT OR IGNORE INTO analytics_disabled VALUES (?)', (account,))
            db.execute('DELETE FROM analytics_rows WHERE account=?', (account,))
            db.execute('DELETE FROM analytics_status WHERE account=?', (account,))
            (self.root / 'cache/publisher' / ('analytics-' + account + '.dpapi')).unlink(missing_ok=True)

    def read(self, year, month):
        today = self.now().date()
        begin, end = f'{year}-01-01', f'{year}-12-31'
        with self.db() as db:
            status = {row['account']: dict(row) for row in db.execute('SELECT * FROM analytics_status')}
            disabled = {row[0] for row in db.execute('SELECT * FROM analytics_disabled')}
            rows = db.execute('''SELECT * FROM analytics_rows WHERE
                (kind IN ('activity','revenue') AND (day BETWEEN ? AND ? OR day>=?)) OR
                (kind='snapshot' AND (day BETWEEN ? AND ? OR day>=?)) OR
                (kind='browser_30d' AND (day BETWEEN ? AND ? OR day>=?)) OR
                (kind='content' AND day>=?) OR
                (kind IN ('video_activity','video_revenue') AND day=?) ORDER BY day''',
                (begin, end, str(today - timedelta(days=15)), begin, end, str(today - timedelta(days=15)),
                 begin, end, str(today - timedelta(days=15)), str(today - timedelta(days=2)), month)).fetchall()
        accounts = {}
        for key, (platform, profile, name, identity) in source.ACCOUNTS.items():
            state = status.get(key, {})
            valid = state.get('verified', 0) >= time.time() - 30 * 86400
            accounts[key] = {'id': key, 'platform': platform, 'profile': profile, 'name': name, 'identity': identity,
                             'state': 'paused' if key in disabled else state.get('state', 'needs_connection' if platform == 'instagram' else 'waiting'),
                             'verified': state.get('verified') or None, 'notes': json.loads(state.get('notes', '[]')),
                             'stale': bool(state.get('verified') and not valid), 'snapshot': {}, 'activity': {}, 'revenue': {},
                             'content': {}, 'browser_30d': {}, 'video_activity': {}, 'video_revenue': {}}
        for row in rows:
            account = accounts[row['account']]
            if account['stale']:
                continue
            values = json.loads(row['metrics'])
            kind, day, item = row['kind'], row['day'], row['item']
            if item and kind == 'content':
                account[kind].setdefault(item, {})[day] = values
            else:
                account[kind][item or day] = values
        return {'today': str(today), 'year': year, 'month': month, 'accounts': list(accounts.values())}

    def export(self, year):
        report = self.read(year, f'{year}-01')
        fields = ['audience', 'following', 'posts', 'views', 'likes', 'comments', 'shares', 'saves', 'interactions',
                  'profile_views', 'reach', 'accounts_engaged', 'link_taps', 'tracked_reels', 'gained', 'lost', 'watch_minutes', 'revenue']
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['platform', 'account', 'date', 'basis', *fields])
        for account in report['accounts']:
            for kind, label in [('snapshot', 'daily snapshot (IST, cumulative)'),
                                ('activity', 'reported daily activity (Pacific)' if account['platform'] == 'youtube' else 'observed Reel view change (IST)'),
                                ('browser_30d', 'Instagram browser Insights (rolling 30 days)'),
                                ('revenue', 'daily estimated revenue (INR, Pacific)')]:
                for day, values in account[kind].items():
                    if day.startswith(f'{year}-'):
                        writer.writerow([account['platform'], account['identity'], day, label, *[values.get(key, '') for key in fields]])
        return output.getvalue().encode('utf-8-sig')

    def video(self, account, item):
        if account not in source.ACCOUNTS or not account.startswith('youtube') or not re.fullmatch(r'[A-Za-z0-9_-]{11}', item):
            raise ValueError('Choose a video from one of your YouTube accounts.')
        with self.db() as db:
            row = db.execute("SELECT day,metrics FROM analytics_rows WHERE account=? AND kind='content' AND item=? ORDER BY day DESC LIMIT 1",
                             (account, item)).fetchone()
            verified = db.execute('SELECT verified FROM analytics_status WHERE account=?', (account,)).fetchone()
        if row is None or verified is None or verified[0] < time.time() - 30 * 86400:
            raise ValueError('Refresh this channel to verify the selected video and load its details.')
        counter = json.loads(row['metrics'])
        try:
            result = source.yt_video_detail(self.root, account, item, counter.get('published', ''))
        except source.SourceError as error:
            result = {'lifetime': {}, 'daily': {}, 'notes': [str(error)]}
        return {**result, 'counter': counter, 'captured': row['day']}


def service(state):
    with state.lock:
        if not hasattr(state, '_creator_analytics'):
            state._creator_analytics = Analytics(state.root, browser=lambda: state.local_browser)
        return state._creator_analytics


def selection(year, month):
    if not re.fullmatch(r'20\d{2}', str(year)) or not 2005 <= int(year) <= Analytics.now().year:
        raise ValueError('Choose a year from 2005 through the current year.')
    if not isinstance(month, str) or not re.fullmatch(rf'{year}-(?:0[1-9]|1[0-2])', month):
        raise ValueError('Choose a month in the selected year.')
    return int(year), month


def get(handler, state, parsed):
    if not handler._authorized():
        return handler._json(403, {'error': 'Not connected'})
    query = parse_qs(parsed.query)
    if parsed.path == '/api/analytics/video':
        account = query.get('account', [''])[0]
        item = query.get('id', [''])[0]
        return handler._json(200, service(state).video(account, item))
    current = Analytics.now()
    year = query.get('year', [str(current.year)])[0]
    month = query.get('month', [f'{year}-01'])[0]
    year, month = selection(year, month)
    dashboard = service(state)
    if parsed.path == '/api/analytics/dashboard':
        return handler._json(200, dashboard.read(year, month))
    if parsed.path == '/api/analytics/export':
        data = dashboard.export(year)
        handler.send_response(200)
        handler.send_header('Content-Type', 'text/csv; charset=utf-8')
        handler.send_header('Content-Disposition', f'attachment; filename="StoryLens-Analytics-{year}.csv"')
        handler.send_header('Cache-Control', 'no-store')
        handler.send_header('Content-Length', str(len(data)))
        handler.end_headers()
        handler.wfile.write(data)
        return
    return handler._json(404, {'error': 'Unknown analytics route'})


def post(handler, state, path, payload):
    account = payload.get('account')
    if account is not None and account not in source.ACCOUNTS:
        raise ValueError('Choose one of the four dashboard accounts.')
    dashboard = service(state)
    try:
        if path == '/api/analytics/refresh':
            month = payload.get('month')
            if month is not None:
                if not isinstance(month, str):
                    raise ValueError('Choose a reporting month.')
                selection(month[:4], month)
            return handler._json(202, dashboard.refresh(account, month))
        if path == '/api/analytics/connect-youtube' and account and account.startswith('youtube'):
            dashboard.connect_youtube(account, payload.get('monetary') is True)
            return handler._json(202, {'state': 'connecting'})
        if path == '/api/analytics/connect-instagram' and account and account.startswith('instagram'):
            dashboard.connect_instagram(account)
            return handler._json(202, {'state': 'refreshing'})
        if path == '/api/analytics/disconnect' and account and payload.get('confirm') is True:
            dashboard.disconnect(account)
            return handler._json(200, {'state': 'paused'})
    except source.SourceError as error:
        return handler._json(400, {'error': str(error)})
    return handler._json(404, {'error': 'Unknown analytics route'})
