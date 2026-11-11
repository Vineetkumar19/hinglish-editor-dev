"""Small persistent workflow RAG; never a chat archive or a publishing queue.

SQLite stores normalized float32 vectors and content/model fingerprints. With a
small curated guide, an exact cosine scan avoids another service or resident
index process. The model receives only a bounded selection of procedural text.
"""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import threading
import time

import numpy as np

_LOCKS={}
_LOCKS_LOCK=threading.Lock()
RULES=('Reusable procedure only, not task state or permission. The latest user request and verified '
       'runtime configuration/receipts override these chunks. Never copy example files, dates or '
       'destinations into a task. Do not execute an informational question. Other chats are not included.')


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def relevant(text):
    return bool(re.search(r'\b(?:workflow|pipeline|usual|repeat\w*|publish\w*|upload\w*|schedul\w*|'
                          r'instagram|insta|youtube|reels?|shorts?|buffer|queue|account.?switch\w*|smart\s*zoom|zooms?|hook|whoosh|swoosh|swish|woosh|captions?|premiere|capcut|fonts?|alignment|b[ -]?rolls?|cutaways?|stock\s+footage)\b',text,re.I))


def configuration(root):
    path=Path(root)/'config.workflow_memory.local.json'
    return json.loads(path.read_text('utf-8-sig')) if path.exists() else {'enabled':False}


def load_guide():
    path=Path(__file__).parent/'knowledge/publishing_workflow.json'
    guide=json.loads(path.read_text('utf-8'))
    rows=guide['chunks']
    if not 1<=len(rows)<=64 or len({r['id'] for r in rows})!=len(rows):
        raise ValueError('Workflow knowledge needs unique, bounded section IDs.')
    for row in rows:
        # Preserve the owner's existing editor-integration guide, which has
        # grown beyond the old per-section limit. The retrieval total below
        # remains bounded; never delete saved guidance to fit this validator.
        if not re.fullmatch(r'[a-z0-9-]+',row['id']) or not 1<=len(row['text'])<=3200:
            raise ValueError('Workflow knowledge has an invalid section.')
        row['passage']=row['title']+'\n'+', '.join(row.get('topics',[]))+'\n'+row['text']
        row['content_hash']=digest(row['passage'])
    return guide


class WorkflowMemory:
    def __init__(self,root,encoder=None):
        self.root=Path(root);self.config=configuration(root);self.encoder=encoder
        self.path=self.root/'cache/assistant/workflow-vectors.sqlite3'
        with _LOCKS_LOCK:self.lock=_LOCKS.setdefault(str(self.path.resolve()),threading.RLock())

    @contextmanager
    def connect(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        db=sqlite3.connect(self.path,timeout=30);db.row_factory=sqlite3.Row
        try:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS workflow_chunks(
                    id TEXT PRIMARY KEY,title TEXT NOT NULL,text TEXT NOT NULL,content_hash TEXT NOT NULL,
                    model_signature TEXT NOT NULL,dimensions INTEGER NOT NULL,vector BLOB NOT NULL);
                CREATE TABLE IF NOT EXISTS workflow_queries(
                    key TEXT PRIMARY KEY,model_signature TEXT NOT NULL,dimensions INTEGER NOT NULL,
                    vector BLOB NOT NULL,used REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS workflow_index(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            ''')
            with db:yield db
        finally:db.close()

    def model(self):
        from hinglish_cut.model_preferences import preferences
        from hinglish_cut.model_storage import role
        selected=role(self.root,'embedding') or {}
        name=self.encoder.model if self.encoder is not None else preferences(self.root).get('embedding_model','')
        dimensions=self.encoder.dimensions if self.encoder is not None else selected.get('dimensions',4096)
        if not name or name.endswith(':cloud') or type(dimensions) is not int or not 8<=dimensions<=16384:
            raise ValueError('Select an installed local embedding model for workflow memory.')
        signature=digest(json.dumps([name,dimensions,selected.get('revision',''),selected.get('verified',[])],sort_keys=True))
        return name,dimensions,signature

    @staticmethod
    def vector(blob,dimensions):
        try:vector=np.frombuffer(blob,np.float32)
        except (ValueError,TypeError):return None
        if vector.shape!=(dimensions,) or not np.isfinite(vector).all() or not .99<float(np.linalg.norm(vector))<1.01:
            return None
        return vector

    @staticmethod
    def terms(text):
        from .conversation_memory import STOP
        return {v.casefold() for v in re.findall(r'\w+',text) if len(v)>2 and v.casefold() not in STOP}

    def retrieve(self,query,progress=lambda _:None):
        if not self.config.get('enabled') or not relevant(query):
            return {'status':'disabled' if not self.config.get('enabled') else 'not_needed','chunks':[]}
        guide=load_guide();rows=guide['chunks']
        # Only the retrieval query is compacted. The planner keeps the full request.
        search=query[:1800];query_hash=digest(query)
        revision=digest(json.dumps(guide,sort_keys=True,ensure_ascii=False))
        used_cache=False;reason='';model=''
        try:
            model,dimensions,signature=self.model()
            key=digest(signature+'\0query\0'+search)
            with self.lock,self.connect() as db:
                saved={r['id']:r for r in db.execute('SELECT * FROM workflow_chunks')}
                vectors={}
                for row in rows:
                    old=saved.get(row['id'])
                    if old and old['model_signature']==signature and old['content_hash']==row['content_hash']:
                        vector=self.vector(old['vector'],dimensions)
                        if vector is not None:vectors[row['id']]=vector
                cached=db.execute('SELECT * FROM workflow_queries WHERE key=?',(key,)).fetchone()
                query_vector=self.vector(cached['vector'],dimensions) if cached else None
                used_cache=query_vector is not None and len(vectors)==len(rows)
                missing=[row for row in rows if row['id'] not in vectors]
                if missing or query_vector is None:
                    progress('Recalling the saved publishing workflow locally')
                    from hinglish_cut.ollama_embeddings import OllamaEmbeddings
                    from hinglish_cut.model_preferences import release_ollama
                    encoder=self.encoder or OllamaEmbeddings(self.root,model,dimensions,
                        timeout=max(10,min(120,self.config.get('embedding_timeout_seconds',90))))
                    release_ollama(self.root)
                    try:
                        if missing:
                            encoded=encoder.encode([r['passage'] for r in missing],manage_residency=False)
                            if encoded.shape!=(len(missing),dimensions):raise ValueError('Invalid workflow embedding batch.')
                            for row,vector in zip(missing,encoded):
                                vector=self.vector(np.asarray(vector,np.float32).tobytes(),dimensions)
                                if vector is None:raise ValueError('Invalid workflow embedding vector.')
                                vectors[row['id']]=vector
                        if query_vector is None:
                            encoded=encoder.encode([search],query=True,manage_residency=False)
                            if encoded.shape!=(1,dimensions):raise ValueError('Invalid workflow query embedding.')
                            query_vector=self.vector(np.asarray(encoded[0],np.float32).tobytes(),dimensions)
                            if query_vector is None:raise ValueError('Invalid workflow query vector.')
                    finally:encoder.close()
                for row in rows:
                    db.execute('INSERT OR REPLACE INTO workflow_chunks VALUES(?,?,?,?,?,?,?)',
                        (row['id'],row['title'],row['text'],row['content_hash'],signature,dimensions,vectors[row['id']].tobytes()))
                active={r['id'] for r in rows}
                for old in set(saved)-active:db.execute('DELETE FROM workflow_chunks WHERE id=?',(old,))
                db.execute('INSERT OR REPLACE INTO workflow_queries VALUES(?,?,?,?,?)',
                    (key,signature,dimensions,query_vector.tobytes(),time.time()))
                limit=max(1,min(256,self.config.get('query_cache_limit',128)))
                db.execute('DELETE FROM workflow_queries WHERE key NOT IN (SELECT key FROM workflow_queries ORDER BY used DESC LIMIT ?)',(limit,))
                db.execute('INSERT OR REPLACE INTO workflow_index VALUES(?,?)',('revision',revision))
                scores={row['id']:float(np.dot(query_vector,vectors[row['id']])) for row in rows}
            method='vector'
        except (ValueError,OSError,RuntimeError,sqlite3.Error) as error:
            method='keyword_fallback';reason=type(error).__name__;scores={r['id']:0. for r in rows}
        except Exception as error:
            # Model/network unavailability must not discard exports or break an
            # otherwise executable request. Record the degraded method honestly.
            import requests
            if not isinstance(error,requests.RequestException):raise
            method='keyword_fallback';reason=type(error).__name__;scores={r['id']:0. for r in rows}
        terms=self.terms(search)
        def score(row):
            overlap=len(terms&self.terms(row['passage']))/max(1,len(terms))
            return .85*scores[row['id']]+.15*overlap if method=='vector' else overlap
        ranked=sorted(rows,key=score,reverse=True)
        relevant_rows=[r for r in ranked if (scores[r['id']]>=.3 if method=='vector' else score(r)>0)]
        top=max(1,min(6,self.config.get('top_k',4)));budget=max(1000,min(5000,self.config.get('max_context_chars',3600)))
        chosen=[];size=0
        # Broad workflow questions need the connected overview as well as details.
        if relevant_rows and re.search(r'\b(?:workflow|pipeline|usual|repeated)\b',search,re.I):
            overview=next(r for r in rows if r['id']=='overview')
            relevant_rows=[overview]+[r for r in relevant_rows if r['id']!='overview']
        while relevant_rows and len(chosen)<top:
            if chosen and method=='vector':
                # Diversity prevents several nearly identical account sections
                # from crowding out the Instagram buffer in a whole-flow query.
                row=max(relevant_rows,key=lambda r:score(r)-.2*max(
                    float(np.dot(vectors[r['id']],vectors[c['id']])) for c in chosen))
            else:row=relevant_rows[0]
            relevant_rows.remove(row)
            if size+len(row['text'])>budget:continue
            chosen.append({'id':row['id'],'title':row['title'],'text':row['text'],'score':round(score(row),4)})
            size+=len(row['text'])
        return {'status':'ready' if method=='vector' else 'degraded','method':method,'model':model,
                'source':guide['id'],'version':guide['version'],'revision':revision,'query_hash':query_hash,
                'cache_hit':used_cache,'rules':RULES,'chunks':chosen,**({'reason':reason} if reason else {})}
