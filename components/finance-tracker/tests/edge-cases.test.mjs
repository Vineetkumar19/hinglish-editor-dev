import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,writeFileSync,existsSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {DatabaseSync} from 'node:sqlite';
import {openStore} from '../server/store.mjs';
import {validateRecord,validateLedger,portfolio,holding,latestPrice,keyOf,today} from '../server/domain.mjs';
import {analytics} from '../server/analytics.mjs';
import {savePrice,fetchInstrument,refresh,summarize} from '../server/providers.mjs';
import {ensureNews,newsFeed} from '../server/news.mjs';
import {checkReminders} from '../server/scheduler.mjs';
import {createApp} from '../server/index.mjs';

const bank={name:'Edge bank',platform:'Bank',balance:'10000',asOf:'2026-01-01',balanceKind:'confirmed'};
const position={name:'Edge equity',category:'stock',provider:'manual',symbol:'EDGE',units:'10',cost:'1000',openingDate:'2026-01-01',manualPrice:'100',priceDate:'2026-01-01'};
const card={name:'Edge card',issuer:'Issuer',last4:'0000',limit:'5000',outstanding:'2000',statementAmount:'2000',minimumDue:'100',dueDate:today(),billingDay:31,asOf:'2026-01-01'};
const deposit={name:'Deposit',principal:'1000',rate:0,startDate:'2026-01-01',maturityDate:'2027-01-01',compounding:'quarterly',payout:'cumulative'};
const asset={name:'Asset',purchasePrice:'2000',currentResale:'1000',retailPrice:'2000',purchaseDate:'2026-01-01',retailDate:today(),futureResale:'100',futureDate:'2030-01-01',url:''};
function fixture(t){const s=openStore(':memory:');t.after(()=>s.db.close());return s;}
const add=(s,k,d)=>s.put(k,validateRecord(s,k,d));
async function apiFixture(t){const s=fixture(t),server=createApp(s,{automaticNews:false}).listen(0,'127.0.0.1');await new Promise(r=>server.once('listening',r));t.after(()=>new Promise(r=>server.close(r)));const base=`http://127.0.0.1:${server.address().port}`;const call=async(path,method='GET',body,headers={})=>{const r=await fetch(base+'/api'+path,{method,headers:{...(body?{'Content-Type':'application/json'}:{}),...headers},body:body?JSON.stringify(body):undefined});return {status:r.status,data:await r.json()};};return {s,call};}

for(const [label,kind,input] of [
 ['impossible calendar date','account',{...bank,asOf:'2026-02-30'}],
 ['future bank balance','account',{...bank,asOf:'2099-01-01'}],
 ['negative bank balance','account',{...bank,balance:'-1'}],
 ['non-finite money','account',{...bank,balance:'Infinity'}],
 ['zero holding units','position',{...position,units:'0'}],
 ['future holding','position',{...position,openingDate:'2099-01-01'}],
 ['future quote','position',{...position,priceDate:'2099-01-01'}],
 ['invalid fund code','position',{...position,provider:'mfapi',symbol:'wrong-plan'}],
 ['future deposit','deposit',{...deposit,startDate:'2099-01-01',maturityDate:'2100-01-01'}],
 ['reversed maturity','deposit',{...deposit,maturityDate:'2025-01-01'}],
 ['future acquired asset','asset',{...asset,purchaseDate:'2099-01-01'}],
 ['future retail observation','asset',{...asset,retailDate:'2099-01-01'}],
 ['invalid listing link','asset',{...asset,url:'https://'}],
 ['credential-bearing listing link','asset',{...asset,url:'https://secret:password@example.com'}],
 ['future resale before acquisition','asset',{...asset,futureDate:'2025-01-01'}],
 ['minimum exceeds statement','card',{...card,minimumDue:'3000'}],
 ['statement exceeds outstanding','card',{...card,statementAmount:'3000'}],
 ['invalid card last four','card',{...card,last4:'123456789'}]
])test(`rejects ${label}`,t=>assert.throws(()=>validateRecord(fixture(t),kind,input)));

test('canonical symbols, duplicate holdings and watchlist duplicates',t=>{
 const s=fixture(t),p=add(s,'position',{...position,provider:'yahoo',symbol:'infy.ns'});assert.equal(p.symbol,'INFY.NS');
 assert.throws(()=>add(s,'position',{...position,provider:'yahoo',symbol:'INFY.NS'}),/already exists/);
 const account=add(s,'account',bank);assert.doesNotThrow(()=>add(s,'position',{...position,provider:'yahoo',symbol:'infy.ns',accountId:account.id}));
 add(s,'watch',{name:'INFY',provider:'yahoo',symbol:'infy.ns'});assert.throws(()=>add(s,'watch',{name:'Infosys',provider:'yahoo',symbol:'INFY.NS'}),/already/);
});
test('manual gold quotes are isolated across providers/accounts',t=>{
 const s=fixture(t),a=add(s,'account',bank),b=add(s,'account',{...bank,name:'Other provider'});
 const p=add(s,'position',{...position,category:'gold',accountId:a.id}),q=add(s,'position',{...position,category:'gold',accountId:b.id});
 savePrice(s,keyOf(p),today(),'7000','manual');savePrice(s,keyOf(q),today(),'6900','manual');
 assert.notEqual(keyOf(p),keyOf(q));assert.equal(latestPrice(s,p).price,'7000');assert.equal(latestPrice(s,q).price,'6900');
});
test('legacy manual price migration preserves values and remains idempotent',()=>{
 const path=join(mkdtempSync(join(tmpdir(),'daybook-migrate-')),'legacy.sqlite');let s=openStore(path);const p=add(s,'position',position);savePrice(s,'manual:EDGE',today(),'123','manual');s.db.exec('PRAGMA user_version=1');s.db.close();
 s=openStore(path);assert.equal(latestPrice(s,s.get(p.id)).price,'123');s.db.close();s=openStore(path);assert.equal(s.db.prepare('SELECT count(*) n FROM prices WHERE key=?').get('manual:'+p.id).n,1);s.db.close();
});
test('manual override wins on the same date even after a later provider refresh',t=>{
 const s=fixture(t),p=add(s,'position',position);savePrice(s,keyOf(p),today(),'150','manual');savePrice(s,keyOf(p),today(),'145','Yahoo (unofficial)');assert.equal(latestPrice(s,p).price,'150');
});
test('stale manual values are flagged; sold-out holdings need no quote',t=>{
 const s=fixture(t),p=add(s,'position',position);assert.equal(portfolio(s).positions[0].status,'stale');
 add(s,'transaction',{positionId:p.id,type:'sell',date:'2026-01-02',quantity:'10',amount:'1100',fee:'0'});
 s.db.prepare('DELETE FROM prices').run();s.put('position',{...position,manualPrice:'0'},p.id);
 const state=portfolio(s);assert.equal(state.positions[0].value,'0.00');assert.equal(state.positions[0].status,'closed');assert.equal(state.coverage.missing,0);
});
test('report-only historic income is valid before the current bank baseline',t=>{
 const s=fixture(t),a=add(s,'account',{...bank,asOf:'2026-06-01'});
 assert.doesNotThrow(()=>add(s,'income',{name:'Already in balance',type:'interest',accountId:a.id,gross:'100',tax:'0',date:'2026-01-01',creditCash:false}));
 assert.throws(()=>add(s,'income',{name:'Duplicate cash',type:'interest',accountId:a.id,gross:'100',date:'2026-01-01',creditCash:true}),/predates/);
 assert.equal(portfolio(s).totals.cash,'10000.00');
});
test('future account and asset balances do not leak into earlier valuations',t=>{
 const s=fixture(t);add(s,'account',bank);add(s,'asset',asset);assert.equal(portfolio(s,'2025-12-31').totals.netWorth,'0.00');
});
test('full liquidation is included even without a fresh price on the sale date',t=>{
 const s=fixture(t),p=add(s,'position',position);add(s,'transaction',{positionId:p.id,type:'sell',date:'2026-01-02',quantity:'10',amount:'1100',fee:'0'});
 const a=analytics(s);assert.equal(a.end,'2026-01-02');assert.equal(a.dailyPnl,'100.00');assert.ok(Math.abs(a.totalReturn-10)<1e-9);
});
test('a complete investment write-off reports minus 100 percent',t=>{
 const s=fixture(t),p=add(s,'position',position);add(s,'transaction',{positionId:p.id,type:'sell',date:'2026-01-02',quantity:'10',amount:'0',fee:'0'});
 const a=analytics(s);assert.equal(a.totalReturn,-100);assert.equal(a.maxDrawdown,-100);assert.equal(a.dailyPnl,'-1000.00');
});
test('reinvestment after zero capital starts a disclosed new period',t=>{
 const s=fixture(t),p=add(s,'position',position);
 add(s,'transaction',{positionId:p.id,type:'sell',date:'2026-01-02',quantity:'10',amount:'1100',fee:'0'});
 add(s,'transaction',{positionId:p.id,type:'buy',date:'2026-01-03',quantity:'10',amount:'1000',fee:'0'});
 savePrice(s,keyOf(p),'2026-01-03','100','manual');savePrice(s,keyOf(p),'2026-01-04','110','manual');
 const a=analytics(s);assert.equal(a.start,'2026-01-03');assert.match(a.note,/zero invested capital/);assert.ok(Math.abs(a.totalReturn-10)<1e-9);
});
test('carried prices suppress misleading annualized volatility',t=>{
 const s=fixture(t),p=add(s,'position',position),q=add(s,'position',{...position,name:'Other',symbol:'OTHER'});
 for(let day=1;day<=25;day++){const date=`2026-01-${String(day).padStart(2,'0')}`;savePrice(s,keyOf(p),date,'100','manual');if(day%2)savePrice(s,keyOf(q),date,'100','manual');}
 assert.equal(analytics(s).volatility,null);assert.match(analytics(s).note,/fresh prices/);
});
test('overspending and removal of funding income roll back atomically',async t=>{
 const {s,call}=await apiFixture(t),a=(await call('/records/account','POST',{...bank,balance:'100'})).data,c=(await call('/records/card','POST',card)).data;
 const before=portfolio(s).totals.netWorth;
 assert.equal((await call('/records/payment','POST',{cardId:c.id,accountId:a.id,date:'2026-01-02',amount:'200'})).status,422);
 assert.equal(s.list('payment').length,0);assert.equal(portfolio(s).totals.netWorth,before);
 const income=(await call('/records/income','POST',{name:'Funding',type:'interest',accountId:a.id,gross:'500',tax:'0',date:'2026-01-02',creditCash:true})).data;
 assert.equal((await call('/records/payment','POST',{cardId:c.id,accountId:a.id,date:'2026-01-03',amount:'600'})).status,201);
 assert.equal((await call('/records/income/'+income.id,'DELETE',{})).status,422);assert.ok(s.get(income.id));assert.equal(s.db.prepare('SELECT count(*) n FROM trash').get().n,0);
});
test('repeated POST has exactly one effect and mismatched reuse is rejected',async t=>{
 const {s,call}=await apiFixture(t),headers={'Idempotency-Key':'retry-safe-key-0001'};
 const one=await call('/records/account','POST',bank,headers),two=await call('/records/account','POST',bank,headers);
 assert.equal(one.data.id,two.data.id);assert.equal(s.list('account').length,1);
 assert.equal((await call('/records/account','POST',{...bank,balance:'999'},headers)).status,409);
});
test('two-tab stale edits receive a conflict without overwriting',async t=>{
 const {s,call}=await apiFixture(t),a=(await call('/records/account','POST',bank)).data;
 assert.equal((await call('/records/account/'+a.id,'PUT',{...a,name:'Latest name'})).status,200);
 assert.equal((await call('/records/account/'+a.id,'PUT',{...a,name:'Stale name'})).status,409);assert.equal(s.get(a.id).name,'Latest name');
});
test('deleted entries restore with links/identity; a second restore returns not found',async t=>{
 const {s,call}=await apiFixture(t),a=(await call('/records/account','POST',bank)).data;
 assert.equal((await call('/records/account/'+a.id,'DELETE',{})).status,200);assert.equal(s.get(a.id),null);
 assert.equal((await call('/trash/'+a.id+'/restore','POST',{})).status,200);assert.equal(s.get(a.id).balance,'10000');assert.equal(s.db.prepare('SELECT count(*) n FROM trash').get().n,0);
 assert.equal((await call('/trash/'+a.id+'/restore','POST',{})).status,404);
});

test('restoring a duplicate holding fails and preserves the recoverable copy',async t=>{
 const {s,call}=await apiFixture(t),p=(await call('/records/position','POST',position)).data;
 await call('/records/position/'+p.id,'DELETE',{});await call('/records/position','POST',position);
 assert.equal((await call('/trash/'+p.id+'/restore','POST',{})).status,422);
 assert.equal(s.list('position').length,1);assert.ok(s.db.prepare('SELECT id FROM trash WHERE id=?').get(p.id));
});

test('backup round-trip retains prices and recoverable deletions but resets operational caches',async t=>{
 const {s,call}=await apiFixture(t),p=(await call('/records/position','POST',position)).data,a=(await call('/records/account','POST',bank)).data;
 savePrice(s,keyOf(p),'2026-01-02','120','manual');await call('/records/account/'+a.id,'DELETE',{});s.setSetting('newsStatus',{state:'running'});
 const backup=(await call('/export')).data,dir=mkdtempSync(join(tmpdir(),'daybook-backup-')),source=join(dir,'backup.json'),target=join(dir,'restored.sqlite');writeFileSync(source,JSON.stringify(backup));
 const result=spawnSync(process.execPath,['server/restore.mjs',source,target],{encoding:'utf8',windowsHide:true});assert.equal(result.status,0,result.stderr);
 const restored=openStore(target);t.after(()=>restored.db.close());assert.equal(latestPrice(restored,p).price,'120');assert.equal(restored.db.prepare('SELECT count(*) n FROM trash').get().n,1);assert.equal(restored.setting('newsStatus',null),null);assert.equal(portfolio(restored).totals.netWorth,portfolio(s).totals.netWorth);
 const again=spawnSync(process.execPath,['server/restore.mjs',source,target],{encoding:'utf8',windowsHide:true});assert.notEqual(again.status,0);assert.match(again.stderr,/already exists/);
});

test('backup restore rejects negative cash and malformed dashboard settings',t=>{
 const dir=mkdtempSync(join(tmpdir(),'daybook-bad-backup-'));
 for(const [label,records,settings] of [['cash',{account:[{...bank,id:'a',balance:'100'}],card:[{...card,id:'c'}],payment:[{id:'p',cardId:'c',accountId:'a',amount:'200',date:'2026-01-02'}]},[]],['settings',{},[{key:'widgets',data:'["unknown"]'}]]]){
  const source=join(dir,label+'.json'),target=join(dir,label+'.sqlite');writeFileSync(source,JSON.stringify({version:1,records,settings}));const r=spawnSync(process.execPath,['server/restore.mjs',source,target],{encoding:'utf8',windowsHide:true});assert.notEqual(r.status,0);assert.equal(existsSync(target),false);
 }
});
test('negative cash on an intermediate date is caught, even if later income covers it',t=>{
 const s=fixture(t),a=add(s,'account',{...bank,balance:'100'}),c=add(s,'card',card);
 add(s,'payment',{cardId:c.id,accountId:a.id,date:'2026-01-02',amount:'200'});add(s,'income',{name:'Later receipt',type:'interest',accountId:a.id,date:'2026-01-03',gross:'500',creditCash:true});assert.throws(()=>validateLedger(s),/2026-01-02/);
});
test('over-limit cards show zero available credit and the excess separately',t=>{
 const s=fixture(t);add(s,'card',{...card,limit:'1000'});const c=portfolio(s).cards[0];assert.equal(c.available,'0.00');assert.equal(c.overLimit,'1000.00');
});
test('a changed due date leaves only the current reminder active',t=>{
 const s=fixture(t),c=add(s,'card',card);checkReminders(s);s.put('card',{...c,dueDate:'2099-01-01'},c.id);checkReminders(s);assert.equal(s.db.prepare('SELECT data FROM notifications').all().map(r=>JSON.parse(r.data)).filter(r=>!r.read).length,0);
});
test('an included component cannot become its parent ancestor',t=>{
 const s=fixture(t),a=add(s,'asset',asset),b=add(s,'asset',{...asset,name:'Part',parentId:a.id});assert.throws(()=>validateRecord(s,'asset',{...a,parentId:b.id},a.id));
});
const rss=(link='https://example.com/news',title='Public headline')=>`<rss version="2.0"><channel><title>Feed</title><link>https://example.com</link><description>Feed</description><item><title>${title}</title><link>${link}</link><pubDate>${new Date().toUTCString()}</pubDate></item></channel></rss>`;
test('automatic news covers more than ten instruments and merges duplicates',async t=>{
 const s=fixture(t);for(let i=0;i<12;i++)add(s,'watch',{name:'Public company '+i,provider:'yahoo',symbol:`C${i}.NS`});let calls=0;
 const result=await ensureNews(s,{fetchFeed:async()=>{calls++;return rss();}});assert.equal(calls,12);assert.equal(result.state,'ready');assert.equal(newsFeed(s).length,1);assert.equal(newsFeed(s)[0].relatedNames.length,12);
 await ensureNews(s,{fetchFeed:async()=>{calls++;return rss();}});assert.equal(calls,12);
});
test('concurrent news requests coalesce and one failed topic does not stop others',async t=>{
 const s=fixture(t);add(s,'watch',{name:'Good company',provider:'yahoo',symbol:'GOOD.NS'});add(s,'watch',{name:'Bad company',provider:'yahoo',symbol:'BAD.NS'});let calls=0;
 const fetchFeed=async url=>{calls++;if(url.includes('Bad'))throw new Error('Offline test');return rss();};
 const [a,b]=await Promise.all([ensureNews(s,{fetchFeed}),ensureNews(s,{fetchFeed})]);assert.equal(calls,2);assert.equal(a.state,'partial');assert.deepEqual(a,b);assert.equal(newsFeed(s).length,1);
 const offline=await ensureNews(s,{force:true,fetchFeed:async()=>{throw new Error('Offline');}});assert.equal(offline.state,'failed');assert.equal(newsFeed(s).length,1);
});
test('adding a holding invalidates news cache; removed instruments disappear',async t=>{
 const s=fixture(t),w=add(s,'watch',{name:'First company',provider:'yahoo',symbol:'FIRST.NS'});await ensureNews(s,{fetchFeed:async()=>rss()});add(s,'watch',{name:'Second company',provider:'yahoo',symbol:'SECOND.NS'});let calls=0;
 await ensureNews(s,{fetchFeed:async()=>{calls++;return rss();}});assert.equal(calls,2);s.remove(w.id);assert.deepEqual(newsFeed(s)[0].relatedNames,['Second company']);
});
test('no instruments means no network; zero headlines differs from failure',async t=>{
 const s=fixture(t);const empty=await ensureNews(s,{fetchFeed:async()=>{throw new Error('Must not call');}});assert.equal(empty.state,'empty');
 add(s,'watch',{name:'Quiet company',provider:'yahoo',symbol:'QUIET.NS'});const none=await ensureNews(s,{fetchFeed:async()=>'<rss version="2.0"><channel><title>Feed</title></channel></rss>'});assert.equal(none.state,'ready');assert.equal(none.count,0);
});
test('malformed NAV rows do not erase valid observations',async t=>{
 const s=fixture(t),p=add(s,'position',{...position,provider:'mfapi',symbol:'123456'}),original=globalThis.fetch;t.after(()=>{globalThis.fetch=original;});
 globalThis.fetch=async()=>new Response(JSON.stringify({meta:{scheme_name:'Test'},data:[{date:'01-01-2026',nav:'105'},{date:'30-02-2026',nav:'120'},{date:'02-01-2026',nav:'NaN'}]}));
 const result=await fetchInstrument(s,p);assert.equal(result.count,1);assert.equal(result.skipped,2);assert.equal(latestPrice(s,p).price,'105');
});
test('unknown currency and empty stock closes are rejected',async t=>{
 const s=fixture(t),p=add(s,'position',{...position,provider:'yahoo',symbol:'BAD.NS'}),original=globalThis.fetch;t.after(()=>{globalThis.fetch=original;});
 globalThis.fetch=async()=>new Response(JSON.stringify({chart:{result:[{timestamp:[1767225600],meta:{},indicators:{quote:[{close:[100]}]}}]}}));await assert.rejects(fetchInstrument(s,p),/Currency/);
 globalThis.fetch=async()=>new Response(JSON.stringify({chart:{result:[{timestamp:[1767225600],meta:{currency:'INR'},indicators:{quote:[{close:[null]}]}}]}}));await assert.rejects(fetchInstrument(s,p),/No valid/);
});
test('overlapping price refreshes share one job',async t=>{
 const s=fixture(t);const [a,b]=await Promise.all([refresh(s,{news:false}),refresh(s,{news:false})]);assert.equal(a.id,b.id);assert.equal(s.db.prepare('SELECT count(*) n FROM jobs').get().n,1);
});

test('local model receives explicit INR amounts and only the loopback request',async t=>{
 const s=fixture(t);add(s,'account',bank);const original=globalThis.fetch;t.after(()=>{globalThis.fetch=original;});
 globalThis.fetch=async(url,options)=>{assert.equal(url,'http://127.0.0.1:11434/api/chat');const request=JSON.parse(options.body),context=JSON.parse(request.messages[1].content.split('\nQuestion:')[0]);assert.equal(context.currency,'INR');assert.equal(context.totals.netWorth,'INR 10000.00');assert.match(request.messages[0].content,/never \$ or dollars/);return new Response(JSON.stringify({message:{content:'INR 10,000.00'}}));};
 assert.equal((await summarize(s,'What is my net worth?')).text,'INR 10,000.00');
});
