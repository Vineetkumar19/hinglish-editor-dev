"""Incremental, selected-root metadata index with bounded resumable scanning."""
import hashlib
import os
import time
from pathlib import Path
from core import local_store as store
from core.app_config import approved_search_roots
from core.tasks import check_cancelled
from tools.files import within_approved_roots, SKIP_DIRS_CASEFOLD


def _schema(conn):
    conn.execute('CREATE TABLE IF NOT EXISTS file_metadata (path TEXT PRIMARY KEY, root TEXT, name TEXT, size INTEGER, modified REAL, file_id TEXT, generation TEXT)')
    conn.execute('CREATE INDEX IF NOT EXISTS metadata_name ON file_metadata(name)')


def index_files(root, seconds=5):
    root=str(Path(root).resolve(strict=True))
    if not Path(root).is_dir() or not within_approved_roots(root,approved_search_roots()):
        raise ValueError('Select an existing folder within approved roots.')
    key=hashlib.sha256(root.casefold().encode()).hexdigest()[:24]
    try:
        state=store.get('file_scan',key)
    except ValueError:
        state={}
    if not state.get('pending'):
        state={'root':root,'pending':[root],'generation':str(time.time_ns()),'indexed':0}
    start=time.monotonic()
    with store.connection() as conn:
        _schema(conn)
        conn.execute('BEGIN IMMEDIATE')
        examined = 0
        while state['pending'] and time.monotonic()-start<max(1,min(seconds,10)):
            check_cancelled()
            cursor=state['pending'].pop(0)
            if isinstance(cursor,str):
                cursor={'path':cursor,'offset':0}
            folder=cursor['path']
            try:
                current_mtime=Path(folder).stat().st_mtime_ns
                if cursor.get('mtime') != current_mtime:
                    cursor.update(offset=0,mtime=current_mtime)
                with os.scandir(folder) as entries:
                    for offset,entry in enumerate(entries):
                        check_cancelled()
                        if offset < cursor['offset']:
                            continue
                        if examined >= 2000 or time.monotonic()-start >= max(1,min(seconds,10)):
                            state['pending'].insert(0,{**cursor,'offset':offset})
                            break
                        examined += 1
                        if entry.is_symlink() or not within_approved_roots(entry.path,approved_search_roots()):
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            if entry.name.casefold() not in SKIP_DIRS_CASEFOLD and not entry.name.startswith('.'):
                                if entry.path not in state['pending']:
                                    state['pending'].append(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            # Windows DirEntry.stat reports st_ino=0; use the
                            # same filesystem identity API as lookup/restore.
                            stat=Path(entry.path).stat(follow_symlinks=False)
                            conn.execute('INSERT OR REPLACE INTO file_metadata VALUES(?,?,?,?,?,?,?)',
                                (str(Path(entry.path).resolve()),root,entry.name,stat.st_size,stat.st_mtime,
                                 str(stat.st_ino),state['generation']))
                            state['indexed']+=1
            except (PermissionError,OSError):
                state.setdefault('inaccessible',[]).append(folder)
            if examined >= 2000:
                break
        if not state['pending'] and not state.get('inaccessible'):
            conn.execute('DELETE FROM file_metadata WHERE root=? AND generation<>?',(root,state['generation']))
        state['status']='partial' if state['pending'] or state.get('inaccessible') else 'complete'
        result=store.put_in_transaction(conn,'file_scan',state,key)
    return {k:v for k,v in result.items() if k!='pending'} | {'remaining_folders':len(state['pending'])}


def search_index(query):
    if not query.strip():
        raise ValueError('Provide a filename or part of one.')
    with store.connection() as conn:
        _schema(conn)
        escaped=query.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
        rows=conn.execute("SELECT * FROM file_metadata WHERE name LIKE ? ESCAPE '\\' ORDER BY modified DESC LIMIT 100",
                          ('%'+escaped+'%',)).fetchall()
    matches=[]
    for row in rows:
        path=Path(row['path'])
        try:
            if path.is_file() and within_approved_roots(str(path),approved_search_roots()):
                stat=path.stat()
                if str(stat.st_ino)==row['file_id']:
                    matches.append({**dict(row),'match_reason':'filename contains query','access':'available'})
        except OSError:
            continue
    return {'matches':matches[:25],'ambiguous':len(matches)>1,
            'note':'Choose the exact path when multiple files match. Only indexed roots are searched.'}
