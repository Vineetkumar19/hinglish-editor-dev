import {readFileSync,existsSync,unlinkSync} from 'node:fs';
import {resolve} from 'node:path';
import {openStore} from './store.mjs';
import {schemas,kinds,validateLedger} from './domain.mjs';
import {savePrice} from './providers.mjs';
import {settingsSchema} from './settings.mjs';

// Restore to a NEW file only. Never overwrite the active ledger.
const [source,destination]=process.argv.slice(2);
if(!source||!destination)throw new Error('Usage: node server/restore.mjs backup.json NEW-database.sqlite');
const target=resolve(destination);if(existsSync(target))throw new Error('Destination already exists. Restore to a new file.');
const input=JSON.parse(readFileSync(resolve(source),'utf8'));
if(input.version!==1||!input.records)throw new Error('Unsupported backup format');
const records=[];const ids=new Set();
for(const kind of kinds)for(const r of input.records[kind]||[]){
 if(typeof r.id!=='string'||!r.id||ids.has(r.id))throw new Error('Missing or duplicate record ID');ids.add(r.id);
 records.push({id:r.id,kind,data:{...schemas[kind].parse(r),createdAt:r.createdAt}});
}
const byId=new Map(records.map(r=>[r.id,r]));
for(const {data,id} of records)for(const [field,kind] of Object.entries({accountId:'account',cashAccountId:'account',positionId:'position',cardId:'card',parentId:'asset'}))if(data[field]&&(data[field]===id||byId.get(data[field])?.kind!==kind))throw new Error('Invalid linked record in backup');
const s=openStore(target);
try{
 s.transaction(()=>{
  for(const r of records)s.put(r.kind,r.data,r.id);
  for(const p of input.prices||[])savePrice(s,p.key,p.date,p.price,p.source,p.url||'');
  // Operational caches and schedules must restart rather than inheriting an
  // in-flight status from another process or an old backup.
  for(const r of input.settings||[])if(Object.hasOwn(settingsSchema.shape,r.key)){
   const value=settingsSchema.parse({[r.key]:JSON.parse(r.data)})[r.key];s.setSetting(r.key,Array.isArray(value)?[...new Set(value)]:value);
  }
  for(const r of input.snapshots||[])s.db.prepare('INSERT INTO snapshots VALUES(?,?)').run(r.date,JSON.stringify(r));
  for(const r of input.news||[])s.db.prepare('INSERT INTO news VALUES(?,?)').run(r.id,JSON.stringify(r));
  for(const r of input.trash||[]){
   if(!kinds.includes(r.kind)||!r.id||ids.has(r.id)||!Number.isFinite(Date.parse(r.deleted_at)))throw new Error('Invalid deleted entry in backup');
   const raw=JSON.parse(r.data),data=schemas[r.kind].parse(raw);ids.add(r.id);
   s.db.prepare('INSERT INTO trash VALUES(?,?,?,?)').run(r.id,r.kind,JSON.stringify({...data,createdAt:raw.createdAt}),r.deleted_at);
  }
  // Legacy exports predate per-provider manual quote identities.
  for(const r of records)if(['position','watch'].includes(r.kind)&&r.data.provider==='manual')s.db.prepare('INSERT OR IGNORE INTO prices SELECT ?,date,price,source,url,fetched_at FROM prices WHERE key=?').run('manual:'+r.id,'manual:'+r.data.symbol);
  validateLedger(s);
 });
 s.db.close();console.log(`Restored ${records.length} records to ${target}. Start with DAYBOOK_DB pointing to this file; the original ledger was not changed.`);
}catch(e){s.db.close();unlinkSync(target);throw e;}
