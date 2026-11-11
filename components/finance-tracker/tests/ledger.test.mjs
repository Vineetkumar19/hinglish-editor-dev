import test from 'node:test';
import assert from 'node:assert/strict';
import {openStore} from '../server/store.mjs';
import {holding,portfolio,depositValue,validateRecord,keyOf,latestPrice,incomeReport,today} from '../server/domain.mjs';
import {savePrice,refresh} from '../server/providers.mjs';
import {analytics} from '../server/analytics.mjs';
import {checkReminders} from '../server/scheduler.mjs';
import {createApp} from '../server/index.mjs';

const position={name:'Synthetic equity',category:'stock',accountId:'',provider:'manual',symbol:'TEST',isin:'',units:'10',cost:'1000',openingDate:'2026-01-01',manualPrice:'100',priceDate:'2026-01-01',priceBasis:'market',tags:['Sector: Test'],notes:''};
const account={name:'Test bank',platform:'Bank',balance:'10000',asOf:'2026-01-01',balanceKind:'confirmed'};
const card={name:'Test card',issuer:'Test',last4:'0000',limit:'20000',outstanding:'2000',statementAmount:'2000',minimumDue:'100',dueDate:today(),billingDay:1,benefits:'Test benefit',benefitsUrl:'',asOf:'2026-01-01'};
function fixture(t){const s=openStore(':memory:');t.after(()=>s.db.close());return s;}
function add(s,k,d){return s.put(k,validateRecord(s,k,d));}

test('sale cost basis, fees and splits retain exact decimal units',t=>{
 const p={...position,id:'p',units:'0.3',cost:'30'};
 const tx=[{id:'1',positionId:'p',date:'2026-01-02',type:'buy',quantity:'0.2',amount:'20',fee:'1'},{id:'2',positionId:'p',date:'2026-01-03',type:'split',quantity:'2',amount:'0',fee:'0'},{id:'3',positionId:'p',date:'2026-01-04',type:'sell',quantity:'0.4',amount:'30',fee:'1'}];
 const h=holding(p,tx);assert.equal(h.units,'0.6');assert.equal(h.bookCost,'30.60');assert.equal(h.realized,'8.60');assert.equal(h.openingUnits,'0.3');
 assert.throws(()=>holding(p,[{...tx[2],quantity:'1'}]),/exceeds/);
});
test('same-day purchases are ordered by creation, not random ID',()=>{
 const p={...position,id:'p',units:'1',cost:'100'};
 const h=holding(p,[{id:'z',positionId:'p',date:'2026-01-02',createdAt:'2026-01-02T09:00Z',type:'buy',quantity:'2',amount:'200',fee:'0'},{id:'a',positionId:'p',date:'2026-01-02',createdAt:'2026-01-02T10:00Z',type:'sell',quantity:'3',amount:'360',fee:'0'}]);
 assert.equal(h.units,'0');assert.equal(h.realized,'60.00');
});
test('old prices remain visible before newer fallback date; zero is missing',t=>{
 const s=fixture(t),p=add(s,'position',{...position,manualPrice:'120',priceDate:'2026-01-20'});
 savePrice(s,keyOf(p),'2026-01-02','101','test');assert.equal(latestPrice(s,p,'2026-01-05').price,'101');assert.equal(latestPrice(s,p,'2026-01-22').price,'120');
 const missing=add(s,'position',{...position,symbol:'MISSING',manualPrice:'0'});assert.equal(latestPrice(s,missing),null);assert.equal(portfolio(s).coverage.missing,1);
});
test('invalid dates, zero prices and duplicate observations are handled',t=>{
 const s=fixture(t);assert.throws(()=>savePrice(s,'k','2026-02-30','100','test'));assert.throws(()=>savePrice(s,'k','2026-01-01','0','test'));
 savePrice(s,'k','2026-01-01','100','test');savePrice(s,'k','2026-01-01','101','test');assert.equal(s.db.prepare('SELECT COUNT(*) n FROM prices').get().n,1);
});
test('income credits net cash once, while reporting gross and tax',t=>{
 const s=fixture(t),a=add(s,'account',account),p=add(s,'position',position);
 add(s,'income',{name:'Dividend',type:'dividend',positionId:p.id,accountId:a.id,gross:'500',tax:'50',date:'2026-02-01',creditCash:true});
 assert.equal(portfolio(s).totals.cash,'10450.00');assert.equal(portfolio(s).totals.netWorth,'11450.00');assert.equal(incomeReport(s).months[0].net,'450.00');
 assert.throws(()=>add(s,'income',{name:'Bad',type:'interest',gross:'10',tax:'20',date:'2026-02-01'}),/Tax/);
});
test('card payment reduces cash and debt equally; limits are excluded',t=>{
 const s=fixture(t),a=add(s,'account',account),c=add(s,'card',card);const before=portfolio(s).totals.netWorth;
 checkReminders(s);assert.equal(s.db.prepare('SELECT count(*) n FROM notifications').get().n,1);
 add(s,'payment',{cardId:c.id,accountId:a.id,amount:'2000',date:today()});const p=portfolio(s);
 assert.equal(p.totals.netWorth,before);assert.equal(p.totals.cash,'8000.00');assert.equal(p.totals.debt,'0.00');assert.equal(p.cards[0].available,'20000.00');
 checkReminders(s);assert.equal(JSON.parse(s.db.prepare('SELECT data FROM notifications').get().data).read,true);
 assert.throws(()=>add(s,'payment',{cardId:c.id,accountId:a.id,amount:'1',date:today()}),/exceeds/);
});
test('retail, future resale and included components do not inflate net worth',t=>{
 const s=fixture(t),asset={name:'Computer',purchasePrice:'300000',currentResale:'100000',retailPrice:'350000',retailDate:today(),purchaseDate:'2026-01-01',futureResale:'50000',futureDate:'2030-01-01',url:'',parentId:'',notes:''};
 const parent=add(s,'asset',asset);add(s,'asset',{...asset,name:'Included GPU',currentResale:'30000',parentId:parent.id});assert.equal(portfolio(s).totals.assets,'100000.00');
 assert.throws(()=>validateRecord(s,'asset',{...asset,parentId:parent.id},parent.id),/itself/);
});
test('FD accrual stops at maturity; paid-out interest is not capitalized',()=>{
 const fd={principal:'100000',rate:8,startDate:'2025-01-01',maturityDate:'2026-01-01',compounding:'quarterly',payout:'cumulative'};
 assert.equal(depositValue(fd,'2027-01-01').value,'108243.22');assert.equal(depositValue({...fd,payout:'paid_out'},'2027-01-01').value,'100000.00');
 assert.equal(depositValue({...fd,compounding:'simple'},'2027-01-01').value,'108000.00');
});
test('watchlist never changes wealth',t=>{
 const s=fixture(t);const w=add(s,'watch',{name:'Watch only',provider:'manual',symbol:'WATCH'});savePrice(s,keyOf(w),'2026-01-01','100000','manual');assert.equal(portfolio(s).totals.netWorth,'0.00');assert.equal(portfolio(s).watch[0].quote.price,'100000');
});
test('contributions and withdrawals do not masquerade as investment returns',t=>{
 const s=fixture(t),p=add(s,'position',position);
 add(s,'transaction',{positionId:p.id,type:'buy',date:'2026-01-02',quantity:'5',amount:'500',fee:'0'});
 add(s,'transaction',{positionId:p.id,type:'sell',date:'2026-01-03',quantity:'5',amount:'500',fee:'0'});
 for(const d of ['2026-01-01','2026-01-02','2026-01-03'])savePrice(s,keyOf(p),d,'100','test');
 const a=analytics(s);assert.equal(a.totalReturn,0);assert.equal(a.dailyPnl,'0.00');assert.equal(a.volatility,null);assert.equal(a.maxDrawdown,0);
});
test('dividend return, drawdown and benchmark use aligned dates',t=>{
 const s=fixture(t),p=add(s,'position',position);
 savePrice(s,keyOf(p),'2026-01-02','90','test');savePrice(s,keyOf(p),'2026-01-03','95','test');
 add(s,'income',{name:'Distribution',type:'dividend',positionId:p.id,gross:'100',tax:'0',date:'2026-01-02'});
 savePrice(s,'yahoo:^NSEI','2026-01-02','20000','test');savePrice(s,'yahoo:^NSEI','2026-01-03','21000','test');
 const a=analytics(s);assert.ok(Math.abs(a.totalReturn-5.55555556)<.00001);assert.equal(a.maxDrawdown,0);assert.equal(a.comparison[0].portfolio,100);assert.equal(a.comparison[0].benchmark,100);assert.equal(a.comparison[1].benchmark,105);
});
test('risk is measured only with enough daily history',t=>{
 const s=fixture(t),p=add(s,'position',position);
 for(let i=1;i<=24;i++)savePrice(s,keyOf(p),`2026-01-${String(i).padStart(2,'0')}`,String(i===12?80:100),'test');
 const a=analytics(s);assert.ok(a.volatility>0);assert.ok(Math.abs(a.maxDrawdown+20)<1e-8);assert.equal(a.observations,23);
});
test('failed public sources retain the last good valuation and report partial',async t=>{
 const s=fixture(t),p=add(s,'position',{...position,provider:'yahoo',symbol:'TEST.NS'});savePrice(s,keyOf(p),'2026-01-01','123','test');
 const original=globalThis.fetch;globalThis.fetch=async()=>{throw new Error('Simulated offline source');};t.after(()=>{globalThis.fetch=original;});
 const result=await refresh(s,{news:false});assert.equal(result.status,'partial');assert.equal(portfolio(s).positions[0].value,'1230.00');assert.equal(result.results[0].status,'failed');
});
test('API protects references, rolls back invalid deletion and reconciles next card cycle',async t=>{
 const s=fixture(t),server=createApp(s,{automaticNews:false}).listen(0,'127.0.0.1');await new Promise(r=>server.once('listening',r));t.after(()=>new Promise(r=>server.close(r)));
 const base=`http://127.0.0.1:${server.address().port}`;const call=async(path,method='GET',body)=>{const r=await fetch(base+'/api'+path,{method,headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});return {status:r.status,data:await r.json()};};
 const a=(await call('/records/account','POST',account)).data,p=(await call('/records/position','POST',position)).data,c=(await call('/records/card','POST',card)).data;
 assert.equal((await call('/records/income','POST',{name:'Dividend',type:'dividend',accountId:a.id,gross:'10',tax:'0',date:'2026-01-02',creditCash:true})).status,201);
 assert.equal((await call('/records/account/'+a.id,'DELETE',{})).status,422);
 const buy=(await call('/records/transaction','POST',{positionId:p.id,type:'buy',date:'2026-01-02',quantity:'10',amount:'1000',fee:'0'})).data;
 await call('/records/transaction','POST',{positionId:p.id,type:'sell',date:'2026-01-03',quantity:'15',amount:'1500',fee:'0'});
 assert.equal((await call('/records/transaction/'+buy.id,'DELETE',{})).status,422);assert.ok(s.get(buy.id));
 await call('/records/payment','POST',{cardId:c.id,accountId:a.id,amount:'1000',date:'2026-01-02'});
 assert.equal((await call('/records/card/'+c.id,'PUT',{...card,outstanding:'500',statementAmount:'500',asOf:'2026-02-01'})).status,200);
 const state=(await call('/state')).data;assert.equal(state.portfolio.cards[0].value,'500.00');assert.equal(state.portfolio.totals.cash,'9010.00');
 const backup=(await call('/export')).data;assert.equal(backup.version,1);assert.equal(backup.records.account.length,1);
 const badOrigin=await fetch(base+'/api/settings',{method:'PUT',headers:{'Content-Type':'application/json',Origin:'https://unrelated.example'},body:'{}'});assert.equal(badOrigin.status,403);
});
