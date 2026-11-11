import { DatabaseSync } from 'node:sqlite';
import { mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { randomUUID } from 'node:crypto';

export function openStore(path = process.env.DAYBOOK_DB || 'data/daybook.sqlite') {
  if (path !== ':memory:') mkdirSync(dirname(resolve(path)), { recursive: true });
  const db = new DatabaseSync(path);
  db.exec(`PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON; PRAGMA busy_timeout=5000;
    CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY, kind TEXT NOT NULL, data TEXT NOT NULL, updated_at TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS records_kind ON records(kind);
    CREATE TABLE IF NOT EXISTS prices(key TEXT NOT NULL, date TEXT NOT NULL, price TEXT NOT NULL, source TEXT NOT NULL, url TEXT NOT NULL, fetched_at TEXT NOT NULL, PRIMARY KEY(key,date,source));
    CREATE TABLE IF NOT EXISTS snapshots(date TEXT PRIMARY KEY, data TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, data TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT, data TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS news(id TEXT PRIMARY KEY, data TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS notifications(id TEXT PRIMARY KEY, data TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS audit(id TEXT PRIMARY KEY, at TEXT NOT NULL, action TEXT NOT NULL, kind TEXT NOT NULL, record_id TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS trash(id TEXT PRIMARY KEY,kind TEXT NOT NULL,data TEXT NOT NULL,deleted_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS requests(key TEXT PRIMARY KEY,fingerprint TEXT NOT NULL,response TEXT NOT NULL,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS enrichment(id TEXT PRIMARY KEY,data TEXT NOT NULL);
    `);
  // Manual observations belong to a specific holding/provider, not every record
  // using a generic label such as GOLD. Preserve legacy observations once.
  if(db.prepare('PRAGMA user_version').get().user_version<2){
    db.exec('BEGIN IMMEDIATE');
    try{for(const r of db.prepare("SELECT id,data FROM records WHERE kind IN ('position','watch')").all()){
      const p=JSON.parse(r.data);if(p.provider==='manual'&&p.symbol)db.prepare('INSERT OR IGNORE INTO prices SELECT ?,date,price,source,url,fetched_at FROM prices WHERE key=?').run('manual:'+r.id,'manual:'+p.symbol);
    }db.exec('PRAGMA user_version=2; COMMIT');}catch(e){db.exec('ROLLBACK');throw e;}
  }
  const list = kind => db.prepare('SELECT id,data,updated_at FROM records WHERE kind=? ORDER BY updated_at DESC').all(kind).map(r => ({ ...JSON.parse(r.data), id:r.id, updatedAt:r.updated_at }));
  const get = id => {const r=db.prepare('SELECT * FROM records WHERE id=?').get(id);return r ? {...JSON.parse(r.data),id:r.id,kind:r.kind,updatedAt:r.updated_at}:null;};
  const audit = (action,kind,id) => db.prepare('INSERT INTO audit VALUES(?,?,?,?,?)').run(randomUUID(),new Date().toISOString(),action,kind,id);
  const put = (kind,data,id=randomUUID()) => {const old=get(id);const now=new Date(Math.max(Date.now(),Date.parse(db.prepare('SELECT MAX(updated_at) stamp FROM records').get().stamp||'1970-01-01')+1)).toISOString();const row={...data,createdAt:old?.createdAt||data.createdAt||now};db.prepare('INSERT INTO records VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data,updated_at=excluded.updated_at').run(id,kind,JSON.stringify(row),now);audit('save',kind,id);return {...row,id,updatedAt:now};};
  const remove = id => {const r=db.prepare('SELECT * FROM records WHERE id=?').get(id);if(r){db.prepare('INSERT OR REPLACE INTO trash VALUES(?,?,?,?)').run(r.id,r.kind,r.data,new Date().toISOString());db.prepare('DELETE FROM records WHERE id=?').run(id);audit('delete',r.kind,id);}};
  const setting = (key,fallback) => {const r=db.prepare('SELECT data FROM settings WHERE key=?').get(key);return r ? JSON.parse(r.data):fallback;};
  const setSetting = (key,data) => db.prepare('INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET data=excluded.data').run(key,JSON.stringify(data));
  const transaction = fn => {db.exec('BEGIN IMMEDIATE');try{const result=fn();db.exec('COMMIT');return result;}catch(e){db.exec('ROLLBACK');throw e;}};
  return {db,list,get,put,remove,setting,setSetting,transaction,path};
}
