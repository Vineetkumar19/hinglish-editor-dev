import express from 'express';
import { resolve, join } from 'node:path';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { createHash, timingSafeEqual } from 'node:crypto';
import { z } from 'zod';
import { openStore } from './store.mjs';
import { validateRecord,validateLedger,kinds,portfolio,snapshot,incomeReport,today,keyOf } from './domain.mjs';
import { analytics } from './analytics.mjs';
import { refresh,refreshNews,savePrice,ollamaModels,summarize } from './providers.mjs';
import { checkReminders,tick } from './scheduler.mjs';
import {ensureNews,newsFeed} from './news.mjs';
import {settingsSchema} from './settings.mjs';
import {ensureEnrichment,researchState} from './enrichment.mjs';
import {searchInstruments} from './discovery.mjs';

export function createApp(store,{automaticNews=true}={}){
 const app=express();app.disable('x-powered-by');
 const lan=process.env.DAYBOOK_LAN==='1',token=process.env.DAYBOOK_TOKEN;
 if(lan&&(!token||token.length<24))throw new Error('LAN mode requires DAYBOOK_TOKEN with at least 24 characters');
 const digest=s=>createHash('sha256').update(s).digest();
 const cookie=token?digest(token).toString('hex'):'';
 app.use((req,res,next)=>{
  const host=req.headers.host||'';
  if(!lan&&!/^(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$/.test(host))return res.status(403).json({error:'Local host only'});
  res.setHeader('X-Content-Type-Options','nosniff');res.setHeader('Referrer-Policy','no-referrer');res.setHeader('X-Frame-Options','DENY');
  if(req.path.startsWith('/api'))res.setHeader('Cache-Control','no-store');
  if(['POST','PUT','PATCH','DELETE'].includes(req.method)){
   if(req.headers.origin&&req.headers.origin!==`http://${host}`&&req.headers.origin!==`https://${host}`)return res.status(403).json({error:'Same-origin requests only'});
   if(!req.is('application/json'))return res.status(415).json({error:'JSON content type required'});
  }
  next();
 });
 app.use(express.json({limit:'2mb'}));
 app.get('/api/health',(req,res)=>res.json({ok:true,name:'Finance Tracker',service:'finance-tracker',revision:'2026-11-04-audit',date:today(),lan}));
 app.post('/api/login',(req,res)=>{
  if(!lan)return res.json({ok:true});
  if(typeof req.body.token!=='string'||!timingSafeEqual(digest(req.body.token),digest(token)))return res.status(401).json({error:'Incorrect access token'});
  res.setHeader('Set-Cookie',`daybook=${cookie}; HttpOnly; SameSite=Strict; Path=/; Max-Age=86400`);res.json({ok:true});
 });
 app.use('/api',(req,res,next)=>{if(lan&&!req.headers.cookie?.split(';').some(c=>c.trim()===`daybook=${cookie}`))return res.status(401).json({error:'Enter your LAN access token'});next();});
 const jsonRows=table=>store.db.prepare(`SELECT data FROM ${table}`).all().map(r=>JSON.parse(r.data));
 const backgroundNews=()=>{if(automaticNews){void ensureNews(store).catch(e=>console.error('News refresh:',e.message));void ensureEnrichment(store).catch(e=>console.error('Source lookup:',e.message));}};
 const conflict=(req,old)=>{if(req.body.updatedAt&&req.body.updatedAt!==old.updatedAt){const e=new Error('This record changed in another tab. Close this form, reload, then edit the latest version.');e.status=409;throw e;}};
 const protectReconciled=old=>{
  const cashId=old.kind==='payment'?old.accountId:old.kind==='income'&&old.creditCash?old.accountId:old.kind==='transaction'?old.cashAccountId:null;
  if(cashId&&old.date<store.get(cashId)?.asOf)throw new Error('This cash entry is before a reconciled bank balance. Correct the reconciliation before changing it.');
  if(old.kind==='payment'&&old.date<store.get(old.cardId)?.asOf)throw new Error('This payment belongs to a previous statement. It cannot be changed after reconciliation.');
 };
 app.get('/api/finance-summary',(req,res)=>{
  if(lan||process.env.DAYBOOK_DEMO==='1')return res.status(403).json({error:'Finance summary is available in the personal local ledger only'});
  const {date,totals,coverage}=portfolio(store);
  const {netWorth,investment,cashAndDeposits,assets,debt}=totals;
  res.json({date,totals:{netWorth,investment,cashAndDeposits,assets,debt},coverage});
 });
 app.get('/api/state',(req,res)=>{
  checkReminders(store);
  backgroundNews();
  res.json({enrichment:researchState(store),portfolio:portfolio(store),income:incomeReport(store),analytics:analytics(store,store.setting('benchmark','^NSEI')),
   settings:{widgets:store.setting('widgets',['history','news','allocation','income','due','holdings']),classifications:store.setting('classifications',['Sector','Strategy','Goal']),benchmark:store.setting('benchmark','^NSEI'),model:store.setting('model','qwen3.5:9b-q4_K_M'),autoRefresh:store.setting('autoRefresh',true)},
   snapshots:jsonRows('snapshots').sort((a,b)=>a.date.localeCompare(b.date)),news:newsFeed(store),newsStatus:store.setting('newsStatus',{state:'empty',count:0,topicCount:0,errors:[]}),
   trash:store.db.prepare('SELECT * FROM trash ORDER BY deleted_at DESC LIMIT 50').all().map(r=>({id:r.id,kind:r.kind,name:JSON.parse(r.data).name||r.kind,deletedAt:r.deleted_at})),
   notifications:jsonRows('notifications').sort((a,b)=>b.createdAt.localeCompare(a.createdAt)),jobs:store.db.prepare('SELECT * FROM jobs ORDER BY started_at DESC LIMIT 12').all().map(r=>({...JSON.parse(r.data),startedAt:r.started_at,finishedAt:r.finished_at})),demo:process.env.DAYBOOK_DEMO==='1'});
 });
 app.post('/api/records/:kind',(req,res)=>{
  const requestKey=req.get('Idempotency-Key');
  if(requestKey&&!/^[\w-]{16,100}$/.test(requestKey))return res.status(400).json({error:'Invalid submission key'});
  const fingerprint=digest(req.params.kind+JSON.stringify(req.body)).toString('hex');
  if(requestKey){const prior=store.db.prepare('SELECT * FROM requests WHERE key=?').get(requestKey);if(prior){const response=JSON.parse(prior.response);if(prior.fingerprint!==fingerprint||!store.get(response.id))return res.status(409).json({error:'This submission was already handled. Reload before creating a different entry.'});return res.json(response);}}
  const data=validateRecord(store,req.params.kind,req.body);
  const result=store.transaction(()=>{const r=store.put(req.params.kind,data);validateLedger(store);snapshot(store);if(requestKey)store.db.prepare('INSERT INTO requests VALUES(?,?,?,?)').run(requestKey,fingerprint,JSON.stringify(r),new Date().toISOString());return r;});backgroundNews();res.status(201).json(result);
 });
 app.put('/api/records/:kind/:id',(req,res)=>{
  const old=store.get(req.params.id);if(!old||old.kind!==req.params.kind)return res.status(404).json({error:'Record not found'});
  conflict(req,old);protectReconciled(old);
  if(old.kind==='position'&&store.list('transaction').some(t=>t.positionId===old.id)){
   for(const k of ['units','cost','openingDate'])if(String(req.body[k])!==String(old[k]))throw new Error('Opening balances with transactions cannot be rewritten. Record an investment transaction.');
  }
  if(old.kind==='account'&&(req.body.balance!==old.balance||req.body.asOf!==old.asOf)){
   const movements=[...store.list('income').filter(i=>i.creditCash),...store.list('payment'),...store.list('transaction').filter(t=>t.type!=='split')].filter(r=>r.accountId===old.id||r.cashAccountId===old.id);
   if(movements.some(r=>r.date>=req.body.asOf))throw new Error('To reconcile a balance, use an as-of date after all recorded cash movements.');
  }
  if(old.kind==='card'&&(req.body.asOf!==old.asOf||req.body.outstanding!==old.outstanding)){
   const payments=store.list('payment').filter(p=>p.cardId===old.id);
   if(payments.length&&(req.body.asOf<=old.asOf||payments.some(p=>p.date>=req.body.asOf)))throw new Error('For a new statement, set the as-of date after the last recorded payment.');
  }
  const data=validateRecord(store,req.params.kind,req.body,old.id);
  store.transaction(()=>{store.put(old.kind,data,old.id);validateLedger(store);snapshot(store);});backgroundNews();res.json({ok:true});
 });
 app.delete('/api/records/:kind/:id',(req,res)=>{
  const r=store.get(req.params.id);if(!r||r.kind!==req.params.kind)return res.status(404).json({error:'Record not found'});
  conflict(req,r);protectReconciled(r);
  for(const k of kinds)for(const entry of store.list(k))if(['accountId','cashAccountId','positionId','cardId','parentId'].some(f=>entry[f]===r.id))throw new Error('Remove linked entries before deleting this record');
  store.transaction(()=>{store.remove(r.id);validateLedger(store);snapshot(store);});backgroundNews();res.json({ok:true});
 });
 app.post('/api/trash/:id/restore',(req,res)=>{
  const r=store.db.prepare('SELECT * FROM trash WHERE id=?').get(req.params.id);if(!r)return res.status(404).json({error:'Deleted entry not found'});
  const raw=JSON.parse(r.data),data=validateRecord(store,r.kind,raw,r.id);
  store.transaction(()=>{store.put(r.kind,{...data,createdAt:raw.createdAt},r.id);validateLedger(store);store.db.prepare('DELETE FROM trash WHERE id=?').run(r.id);snapshot(store);});backgroundNews();res.json({ok:true});
 });
 app.post('/api/prices',(req,res)=>{
  const data=z.object({key:z.string(),rows:z.array(z.object({date:z.string(),price:z.coerce.string()})).min(1).max(1000)}).parse(req.body);
  const allowed=new Set([...store.list('position'),...store.list('watch')].map(keyOf));allowed.add('yahoo:'+store.setting('benchmark','^NSEI'));
  if(!allowed.has(data.key))throw new Error('Choose an existing holding, watchlist item or benchmark');
  store.transaction(()=>{for(const p of data.rows)savePrice(store,data.key,p.date,p.price,'manual');snapshot(store);});res.json({ok:true,count:data.rows.length});
 });
 app.put('/api/settings',(req,res)=>{
  const data=settingsSchema.parse(req.body);
  for(const [k,v] of Object.entries(data))store.setSetting(k,Array.isArray(v)?[...new Set(v)]:v);res.json({ok:true});
 });
 app.post('/api/refresh',async(req,res)=>res.json(await refresh(store)));
 app.post('/api/news/refresh',async(req,res)=>res.json(await refreshNews(store)));
 app.get('/api/model',async(req,res)=>res.json(await ollamaModels()));
 app.get('/api/instruments/search',async(req,res)=>{const q=z.string().trim().min(2).max(100).parse(req.query.q),provider=z.enum(['yahoo','mfapi']).parse(req.query.provider||'yahoo');res.json({results:await searchInstruments(q,provider)});});
 app.post('/api/enrichment/:id/refresh',(req,res)=>{if(!store.get(req.params.id))return res.status(404).json({error:'Record not found'});void ensureEnrichment(store,{forceId:req.params.id}).catch(console.error);res.json({ok:true});});
 app.post('/api/assistant',async(req,res)=>{const {question}=z.object({question:z.string().min(1).max(1500)}).parse(req.body);res.json(await summarize(store,question));});
 app.post('/api/notifications/read',(req,res)=>{for(const n of jsonRows('notifications')){n.read=true;store.db.prepare('UPDATE notifications SET data=? WHERE id=?').run(JSON.stringify(n),n.id);}res.json({ok:true});});
 app.get('/api/export',(req,res)=>{res.setHeader('Content-Disposition',`attachment; filename="finance-tracker-backup-${today()}.json"`);res.json({version:1,exportedAt:new Date().toISOString(),records:Object.fromEntries(kinds.map(k=>[k,store.list(k)])),prices:store.db.prepare('SELECT * FROM prices').all(),settings:store.db.prepare('SELECT * FROM settings').all(),snapshots:jsonRows('snapshots'),news:jsonRows('news'),trash:store.db.prepare('SELECT * FROM trash').all()});});
 app.use('/api',(req,res)=>res.status(404).json({error:'API route not found'}));
 const root=resolve(fileURLToPath(new URL('..',import.meta.url)));
 app.use(express.static(join(root,'dist')));
 app.get('/{*path}',(req,res)=>existsSync(join(root,'dist/index.html'))?res.sendFile(join(root,'dist/index.html')):res.status(503).send('Run npm run build, then refresh.'));
 app.use((error,req,res,next)=>{console.error(error.message);res.status(error.status|| (error instanceof z.ZodError?400:422)).json({error:error instanceof z.ZodError?error.issues.map(i=>`${i.path.join('.')}: ${i.message}`).join('; '):error.message});});
 return app;
}
export function startServer(){
 const store=openStore(),port=Number(process.env.PORT||4310),host=process.env.DAYBOOK_LAN==='1'?'0.0.0.0':'127.0.0.1';
 const server=createApp(store).listen(port,host,()=>{console.log(`Finance Tracker ready: http://127.0.0.1:${port}`);if(process.env.DAYBOOK_NO_SCHEDULER!=='1')tick(store);});
 const timer=process.env.DAYBOOK_NO_SCHEDULER==='1'?null:setInterval(()=>tick(store),60000);
 process.on('SIGINT',()=>{if(timer)clearInterval(timer);server.close(()=>{store.db.close();process.exit(0);});});
 return server;
}
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url))startServer();
