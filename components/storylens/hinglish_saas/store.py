from contextlib import contextmanager
from pathlib import Path
import sqlite3
import time

SCHEMA = '''
CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,password TEXT NOT NULL,verified INTEGER NOT NULL DEFAULT 0,created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),csrf TEXT NOT NULL,expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS tokens(hash TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),kind TEXT NOT NULL,expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS orders(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),plan TEXT NOT NULL,amount INTEGER NOT NULL,currency TEXT NOT NULL DEFAULT 'INR',state TEXT NOT NULL DEFAULT 'created',payment_id TEXT UNIQUE,starts REAL,ends REAL,created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS webhook_events(id TEXT PRIMARY KEY,created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS revocations(payment_id TEXT PRIMARY KEY,created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS uploads(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),name TEXT NOT NULL,path TEXT NOT NULL,bytes INTEGER NOT NULL,created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),tool TEXT NOT NULL,payload TEXT NOT NULL,state TEXT NOT NULL DEFAULT 'queued',message TEXT NOT NULL DEFAULT 'Waiting for the rendering worker',created REAL NOT NULL,updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS exports(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),job_id TEXT NOT NULL REFERENCES jobs(id),name TEXT NOT NULL,path TEXT NOT NULL,created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS rate_limits(key TEXT NOT NULL,bucket INTEGER NOT NULL,count INTEGER NOT NULL,PRIMARY KEY(key,bucket));
CREATE INDEX IF NOT EXISTS jobs_owner ON jobs(user_id,created);
CREATE INDEX IF NOT EXISTS uploads_owner ON uploads(user_id);
'''


class Store:
    def __init__(self, folder, database_url=''):
        self.folder = Path(folder); self.folder.mkdir(parents=True, exist_ok=True)
        self.path = self.folder/'subscriptions.sqlite3'
        self.mysql=None;self.backend='mysql' if database_url else 'sqlite'
        if database_url:
            from .mysql import Database
            self.mysql=Database(database_url);self._bundle_migration();return
        with self.connect(immediate=True) as db:
            db.executescript(SCHEMA)
            if 'expires' not in {row['name'] for row in db.execute('PRAGMA table_info(rate_limits)')}:
                db.execute('ALTER TABLE rate_limits ADD COLUMN expires REAL NOT NULL DEFAULT 0')
                # Retain existing attempts conservatively for the longest
                # current throttle window while migrating older databases.
                db.execute('UPDATE rate_limits SET expires=?',(time.time()+3600,))
            if 'edition' not in {row['name'] for row in db.execute('PRAGMA table_info(orders)')}:
                db.execute("ALTER TABLE orders ADD COLUMN edition TEXT NOT NULL DEFAULT 'desktop'")
            db.executescript('''
CREATE TABLE IF NOT EXISTS device_codes(code TEXT PRIMARY KEY,user_code TEXT UNIQUE NOT NULL,edition TEXT NOT NULL,public_key TEXT NOT NULL,name TEXT NOT NULL,expires REAL NOT NULL,user_id TEXT,consumed INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS devices(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),edition TEXT NOT NULL,public_key TEXT NOT NULL,name TEXT NOT NULL,credential TEXT NOT NULL,revoked INTEGER NOT NULL DEFAULT 0,created REAL NOT NULL,UNIQUE(user_id,edition,public_key));
CREATE TABLE IF NOT EXISTS license_nonces(device_id TEXT NOT NULL,nonce TEXT NOT NULL,expires REAL NOT NULL,PRIMARY KEY(device_id,nonce));
CREATE TABLE IF NOT EXISTS device_bindings(user_id TEXT NOT NULL REFERENCES users(id),edition TEXT NOT NULL,device_id TEXT,release_after REAL NOT NULL DEFAULT 0,PRIMARY KEY(user_id,edition));
CREATE TABLE IF NOT EXISTS security_events(id TEXT PRIMARY KEY,actor TEXT NOT NULL,action TEXT NOT NULL,target TEXT NOT NULL,created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS support_tickets(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),subject TEXT NOT NULL,category TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'open',created REAL NOT NULL,updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS support_messages(id TEXT PRIMARY KEY,ticket_id TEXT NOT NULL REFERENCES support_tickets(id),author TEXT NOT NULL REFERENCES users(id),staff INTEGER NOT NULL DEFAULT 0,body TEXT NOT NULL,created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS support_outbox(id TEXT PRIMARY KEY,recipient TEXT NOT NULL,subject TEXT NOT NULL,body TEXT NOT NULL,state TEXT NOT NULL DEFAULT 'pending',attempts INTEGER NOT NULL DEFAULT 0,available REAL NOT NULL,lease_until REAL NOT NULL DEFAULT 0,claim TEXT,created REAL NOT NULL);
CREATE INDEX IF NOT EXISTS tickets_owner ON support_tickets(user_id,updated);
CREATE TABLE IF NOT EXISTS computer_bindings(user_id TEXT PRIMARY KEY REFERENCES users(id),public_key TEXT,hardware_hash TEXT,release_after REAL NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS reviews(id TEXT PRIMARY KEY,user_id TEXT UNIQUE NOT NULL REFERENCES users(id),display_name TEXT NOT NULL,rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),title TEXT NOT NULL,body TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',created REAL NOT NULL,updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS usage_events(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),device_id TEXT NOT NULL REFERENCES devices(id),tool TEXT NOT NULL,outcome TEXT NOT NULL,duration REAL NOT NULL,app_version TEXT NOT NULL,created REAL NOT NULL);
CREATE INDEX IF NOT EXISTS reviews_public ON reviews(status,updated);
CREATE INDEX IF NOT EXISTS usage_owner ON usage_events(user_id,created);
''')
            for table,columns in {'devices':{'hardware_hash':"TEXT NOT NULL DEFAULT ''",'last_lease':"REAL NOT NULL DEFAULT 0"},
                                  'device_codes':{'hardware_hash':"TEXT NOT NULL DEFAULT ''"}}.items():
                current={row['name'] for row in db.execute('PRAGMA table_info('+table+')')}
                for name,definition in columns.items():
                    if name not in current:db.execute('ALTER TABLE '+table+' ADD COLUMN '+name+' '+definition)
            rows=db.execute('SELECT id,user_id,edition,hardware_hash FROM devices ORDER BY created').fetchall()
            for row in rows:
                db.execute('INSERT OR IGNORE INTO device_bindings(user_id,edition,device_id) VALUES(?,?,?)',(row['user_id'],row['edition'],row['id']))
                binding=db.execute('SELECT device_id FROM device_bindings WHERE user_id=? AND edition=?',(row['user_id'],row['edition'])).fetchone()
                if not row['hardware_hash'] or binding['device_id']!=row['id']:
                    db.execute('UPDATE devices SET revoked=1 WHERE id=?',(row['id'],))
        self._bundle_migration()

    def _bundle_migration(self):
        with self.connect(immediate=True) as db:
            for row in db.execute('SELECT * FROM devices ORDER BY created').fetchall():
                db.execute('INSERT OR IGNORE INTO computer_bindings(user_id,public_key,hardware_hash) VALUES(?,?,?)',(row['user_id'],row['public_key'],row['hardware_hash']))
                binding=db.execute('SELECT * FROM computer_bindings WHERE user_id=?',(row['user_id'],)).fetchone()
                if not row['hardware_hash'] or (binding['public_key'],binding['hardware_hash'])!=(row['public_key'],row['hardware_hash']):
                    db.execute('UPDATE devices SET revoked=1 WHERE id=?',(row['id'],))

    @contextmanager
    def connect(self, immediate=False):
        if self.mysql:
            with self.mysql.connect(immediate) as db:yield db
            return
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON');db.execute('PRAGMA busy_timeout=30000')
        try:
            if immediate: db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except BaseException:
            db.rollback();raise
        finally: db.close()

    def one(self, sql, args=()):
        with self.connect() as db:
            row=db.execute(sql,args).fetchone()
            return dict(row) if row else None

    def all(self, sql, args=()):
        with self.connect() as db: return [dict(r) for r in db.execute(sql,args).fetchall()]

    def execute(self, sql, args=()):
        with self.connect() as db: db.execute(sql,args)

    def entitlement(self, user_id, now=None, edition=None):
        now=time.time() if now is None else now
        sql="SELECT id,plan,ends,edition FROM orders WHERE user_id=? AND state='paid' AND starts<=? AND ends>?"
        args=(user_id,now,now)
        order=self.one(sql+' ORDER BY ends DESC LIMIT 1',args)
        return {'active': bool(order), 'plan': order['plan'] if order else None,
                'expires': order['ends'] if order else None, 'edition':'bundle','included':['desktop','plugins'],
                'grant':order['id'] if order else None}

    def close(self):
        if self.mysql:self.mysql.close()

    def rate(self, key, limit, seconds=60):
        bucket=int(time.time()//seconds)
        with self.connect(immediate=True) as db:
            # Buckets for minute/hour/day windows are incomparable. Comparing
            # raw bucket numbers erased hourly login limits on minute requests.
            db.execute('DELETE FROM rate_limits WHERE expires<=?',(time.time(),))
            row=db.execute('SELECT count FROM rate_limits WHERE key=? AND bucket=?',(key,bucket)).fetchone()
            if row and row['count']>=limit:return False
            db.execute('INSERT INTO rate_limits(key,bucket,count,expires) VALUES(?,?,1,?) ON CONFLICT(key,bucket) DO UPDATE SET count=count+1',(key,bucket,(bucket+1)*seconds))
        return True
