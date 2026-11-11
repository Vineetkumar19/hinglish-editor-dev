"""Local shared chat archive and bounded retrieval for the editor's planning models."""
from contextlib import contextmanager
import json
from pathlib import Path
import re
import sqlite3
import threading

STOP=set('the and you have that this what with please can for all from your my me now it is to do of in i a an we our how does did will be on at as was are has not only'.split())


class ConversationMemory:
    def __init__(self,root):
        self.folder=Path(root)/'cache/assistant';self.folder.mkdir(parents=True,exist_ok=True)
        self.path=self.folder/'shared-memory.sqlite3';self.lock=threading.RLock()
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS threads(id TEXT PRIMARY KEY,created REAL,updated REAL,title TEXT,profile TEXT,status TEXT);
                CREATE TABLE IF NOT EXISTS turns(rowid INTEGER PRIMARY KEY,session_id TEXT,message_id TEXT,created REAL,
                    role TEXT,text TEXT,payload TEXT,UNIQUE(session_id,message_id));
                CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY,mtime INTEGER,size INTEGER);
                CREATE VIRTUAL TABLE IF NOT EXISTS turns_fts USING fts5(text,content='turns',content_rowid='rowid');
                CREATE TRIGGER IF NOT EXISTS turns_ai AFTER INSERT ON turns BEGIN
                    INSERT INTO turns_fts(rowid,text) VALUES(new.rowid,new.text); END;
                CREATE TRIGGER IF NOT EXISTS turns_ad AFTER DELETE ON turns BEGIN
                    INSERT INTO turns_fts(turns_fts,rowid,text) VALUES('delete',old.rowid,old.text); END;
                CREATE TRIGGER IF NOT EXISTS turns_au AFTER UPDATE OF text ON turns BEGIN
                    INSERT INTO turns_fts(turns_fts,rowid,text) VALUES('delete',old.rowid,old.text);
                    INSERT INTO turns_fts(rowid,text) VALUES(new.rowid,new.text); END;
                CREATE INDEX IF NOT EXISTS turns_session ON turns(session_id,rowid);
            ''')
        self.sync()

    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=30);db.row_factory=sqlite3.Row
        try:
            with db:yield db
        finally:db.close()

    def _thread(self,db,session):
        messages=session.get('messages',[])
        first=next((m.get('text','') for m in messages if m.get('role')=='user'),'New chat')
        title=session.get('title') or first.replace('\n',' ')[:90] or 'New chat'
        updated=max([session.get('created',0)]+[m.get('created',0) for m in messages])
        db.execute('INSERT INTO threads VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET updated=excluded.updated,title=excluded.title,profile=excluded.profile,status=excluded.status',
            (session['id'],session.get('created',0),updated,title,session.get('profile','general'),session.get('status','idle')))

    def _turn(self,db,session_id,message):
        db.execute('INSERT INTO turns(session_id,message_id,created,role,text,payload) VALUES(?,?,?,?,?,?) '
                   'ON CONFLICT(session_id,message_id) DO UPDATE SET text=excluded.text,payload=excluded.payload',
                   (session_id,message['id'],message.get('created',0),message['role'],message.get('text',''),json.dumps(message,ensure_ascii=False)))

    def remember(self,session,message):
        with self.lock,self.connect() as db:
            self._thread(db,session);self._turn(db,session['id'],message)

    def sync(self):
        with self.lock,self.connect() as db:
            for path in self.folder.glob('*.json'):
                if not re.fullmatch(r'[a-f0-9]{16}',path.stem):continue
                stat=path.stat();old=db.execute('SELECT mtime,size FROM sources WHERE id=?',(path.stem,)).fetchone()
                if old and (old['mtime'],old['size'])==(stat.st_mtime_ns,stat.st_size):continue
                try:
                    session=json.loads(path.read_text('utf-8'))
                    if session.get('id')!=path.stem:continue
                    self._thread(db,session)
                    for message in session.get('messages',[]):self._turn(db,session['id'],message)
                    db.execute('INSERT OR REPLACE INTO sources VALUES(?,?,?)',(path.stem,stat.st_mtime_ns,stat.st_size))
                except (OSError,ValueError,KeyError,TypeError):continue

    @staticmethod
    def terms(query):
        return list(dict.fromkeys(t.casefold() for t in re.findall(r'\w+',query) if len(t)>1 and t.casefold() not in STOP))[:16]

    def history(self,query=''):
        self.sync();terms=self.terms(query)
        with self.connect() as db:
            where='';args=[]
            if terms:
                where=' AND t.id IN (SELECT session_id FROM turns JOIN turns_fts f ON f.rowid=turns.rowid WHERE turns_fts MATCH ?)'
                args=[' OR '.join('"'+t+'"' for t in terms)]
            rows=db.execute('SELECT t.*,COUNT(m.rowid) AS message_count FROM threads t JOIN turns m ON m.session_id=t.id '
                            'WHERE 1=1'+where+' GROUP BY t.id ORDER BY t.updated DESC,t.id LIMIT 500',args).fetchall()
            return [dict(row) for row in rows]

    def messages(self,session_id,before=None,limit=80):
        self.sync()
        with self.connect() as db:
            if before:
                anchor=db.execute('SELECT rowid FROM turns WHERE session_id=? AND message_id=?',(session_id,before)).fetchone()
                if not anchor:raise ValueError('Message cursor is unavailable for this chat.')
                rows=db.execute('SELECT payload,rowid FROM turns WHERE session_id=? AND rowid<? ORDER BY rowid DESC LIMIT ?',
                                (session_id,anchor['rowid'],limit+1)).fetchall()
            else:rows=db.execute('SELECT payload,rowid FROM turns WHERE session_id=? ORDER BY rowid DESC LIMIT ?',
                                 (session_id,limit+1)).fetchall()
            page=list(reversed(rows[:limit]))
            return {'messages':[json.loads(r['payload']) for r in page],'has_more':len(rows)>limit}

    def retrieve(self,query,session_id=''):
        """Read only the active chat's last five exchanges, never an archive search."""
        from .chat_context import memory
        if not session_id:return memory({'id':'','messages':[]})
        with self.connect() as db:
            anchor=db.execute("SELECT rowid FROM turns WHERE session_id=? AND role='user' ORDER BY rowid DESC LIMIT 1 OFFSET 4",(session_id,)).fetchone()
            rows=db.execute('SELECT payload FROM turns WHERE session_id=? AND rowid>=? ORDER BY rowid',
                            (session_id,anchor['rowid'] if anchor else 0)).fetchall()
        return memory({'id':session_id,'messages':[json.loads(r['payload']) for r in rows]})
