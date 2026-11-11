import {createHash} from 'node:crypto';
import {discoverCard,discoverAsset} from './discovery.mjs';
import {fetchInstrument} from './providers.mjs';
import {snapshot} from './domain.mjs';

const runs=new WeakMap();
const fingerprint=r=>createHash('sha256').update(JSON.stringify([r.kind,r.name,r.issuer,r.benefitsUrl,r.url,r.provider,r.symbol])).digest('hex');
export function researchState(store){return Object.fromEntries(store.db.prepare('SELECT id,data FROM enrichment').all().filter(r=>r.id==='benchmark'||store.get(r.id)).map(r=>[r.id,JSON.parse(r.data)]));}
export function ensureEnrichment(store,{forceId,now=Date.now(),quote=fetchInstrument,card=discoverCard,asset=discoverAsset}={}){
 if(forceId){const prior=store.db.prepare('SELECT data FROM enrichment WHERE id=?').get(forceId);if(prior)store.db.prepare('UPDATE enrichment SET data=? WHERE id=?').run(JSON.stringify({...JSON.parse(prior.data),nextRefreshAt:'1970-01-01'}),forceId);}
 if(runs.has(store))return runs.get(store);
 const save=(id,data)=>store.db.prepare('INSERT INTO enrichment VALUES(?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data').run(id,JSON.stringify(data));
 const work=(async()=>{
  // Rescan after each wave: a newly saved or renamed record is never lost behind an in-flight job.
  for(let wave=0;wave<20;wave++){
   const records=['position','watch','card','asset'].flatMap(kind=>store.list(kind).map(r=>({...r,kind})));
   if(records.some(r=>r.kind==='position'||r.kind==='watch'))records.push({id:'benchmark',kind:'watch',name:'Benchmark',provider:'yahoo',symbol:store.setting('benchmark','^NSEI')});
   const old=researchState(store),targets=records.filter(r=>!(r.provider==='manual')&&(!old[r.id]||old[r.id].fingerprint!==fingerprint(r)||Date.parse(old[r.id].nextRefreshAt||0)<=now)).slice(0,3);
   if(!targets.length)break;
   for(const r of targets)save(r.id,{...(old[r.id]?.fingerprint===fingerprint(r)?old[r.id]:{}),kind:r.kind,name:r.name,state:'running',fingerprint:fingerprint(r),attemptedAt:new Date().toISOString(),nextRefreshAt:new Date(now+180000).toISOString()});
   let index=0;await Promise.all(Array.from({length:Math.min(3,targets.length)},async()=>{while(index<targets.length){const r=targets[index++],fp=fingerprint(r),prior=old[r.id]?.fingerprint===fp?old[r.id]:{};let result;
    try{result=r.kind==='card'?await card(r):r.kind==='asset'?await asset(r):{state:'ready',kind:'quote',result:await quote(store,r)};}
    catch(e){result={...prior,state:'failed',error:e.message};}
    const current=r.id==='benchmark'?{...r,symbol:store.setting('benchmark','^NSEI')}:store.get(r.id);
    if(!current||fingerprint(current)!==fp){store.db.prepare('DELETE FROM enrichment WHERE id=?').run(r.id);continue;}
    save(r.id,{...result,lastSuccessAt:result.state==='ready'?new Date().toISOString():prior.lastSuccessAt,fingerprint:fp,attemptedAt:new Date().toISOString(),nextRefreshAt:new Date(now+(result.state==='ready'?86400000:300000)).toISOString()});
   }}));snapshot(store);
  }
 })().finally(()=>runs.delete(store));runs.set(store,work);return work;
}
