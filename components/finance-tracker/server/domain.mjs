import Decimal from 'decimal.js';
import { z } from 'zod';

Decimal.set({precision:32,rounding:Decimal.ROUND_HALF_UP});
export const D=v=>new Decimal(v ?? 0);
export const money=v=>D(v).toDecimalPlaces(2).toFixed(2);
export const today=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Kolkata',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
export const days=(a,b)=>Math.floor((Date.parse(b+'T00:00:00Z')-Date.parse(a+'T00:00:00Z'))/86400000);
const text=z.string().trim().min(1).max(200);
const optional=z.string().trim().max(4000).default('');
const date=z.string().regex(/^\d{4}-\d{2}-\d{2}$/).refine(s=>s>='1900-01-01'&&s<='2200-12-31'&&!Number.isNaN(Date.parse(s))&&new Date(s).toISOString().slice(0,10)===s,'Use a real date between 1900 and 2200');
const amount=z.coerce.string().regex(/^\d{1,14}(\.\d{1,8})?$/,'Enter a non-negative decimal number');
const positive=amount.refine(s=>D(s).gt(0),'Must be greater than zero');
const url=z.string().trim().max(2000).default('').refine(s=>{if(!s)return true;try{const u=new URL(s);return ['http:','https:'].includes(u.protocol)&&!!u.hostname&&!u.username&&!u.password;}catch{return false;}},'Use a valid public http(s) link without credentials');
export const kinds=['account','position','transaction','deposit','asset','card','income','payment','watch'];
export const schemas={
 account:z.object({name:text,platform:text,balance:amount,asOf:date,balanceKind:z.enum(['confirmed','assumed']).default('confirmed')}),
 position:z.object({name:text,category:z.enum(['stock','mutual_fund','etf','bond','gold','silver','copper','scheme']),accountId:optional,provider:z.enum(['manual','yahoo','mfapi']),symbol:optional,isin:optional,units:positive,cost:amount,openingDate:date,manualPrice:amount,priceDate:date,priceBasis:z.enum(['market','sell_quote','benchmark','estimate']).default('market'),tags:z.array(text).max(30).default([]),notes:optional}),
 transaction:z.object({positionId:text,type:z.enum(['buy','sell','split']),date,quantity:positive,amount:amount,fee:amount.default('0'),cashAccountId:optional}),
 deposit:z.object({name:text,accountId:optional,principal:positive,rate:z.coerce.number().min(0).max(40),startDate:date,maturityDate:date,compounding:z.enum(['simple','monthly','quarterly','yearly']),payout:z.enum(['cumulative','paid_out']).default('cumulative')}),
 asset:z.object({name:text,purchasePrice:amount,currentResale:amount,retailPrice:amount,retailDate:date,purchaseDate:date,futureResale:amount,futureDate:date,url,parentId:optional,notes:optional}),
 card:z.object({name:text,issuer:text,last4:z.string().regex(/^\d{4}$/),limit:positive,outstanding:amount,statementAmount:amount,minimumDue:amount,dueDate:date,billingDay:z.coerce.number().int().min(1).max(31),benefits:optional,benefitsUrl:url,asOf:date}),
 income:z.object({name:text,type:z.enum(['dividend','interest']),positionId:optional,accountId:optional,gross:positive,tax:amount.default('0'),date,creditCash:z.boolean().default(false)}),
 payment:z.object({cardId:text,accountId:text,amount:positive,date}),
 watch:z.object({name:text,category:z.enum(['stock','mutual_fund','etf','bond','gold','silver','copper','scheme']).default('stock'),provider:z.enum(['manual','yahoo','mfapi']),symbol:text,notes:optional})
};
export const keyOf=p=>`${p.provider}:${p.provider==='manual'?(p.id||p.symbol):p.symbol}`;
export function holding(position,transactions=[],on=today()) {
 let units=D(position.units),cost=D(position.cost),realized=D(0);
 if(position.openingDate>on)return {...position,units:'0',bookCost:'0',realized:'0'};
 for(const t of transactions.filter(t=>t.positionId===position.id&&t.date<=on).sort((a,b)=>a.date.localeCompare(b.date)||(a.createdAt||a.updatedAt||'').localeCompare(b.createdAt||b.updatedAt||'')||a.id.localeCompare(b.id))){
  if(t.type==='buy'){units=units.plus(t.quantity);cost=cost.plus(t.amount).plus(t.fee);}
  if(t.type==='split'){units=units.mul(t.quantity);}
  if(t.type==='sell'){
   if(D(t.quantity).gt(units))throw new Error('Sale exceeds units held on that date');
   const removed=units.gt(0)?cost.mul(t.quantity).div(units):D(0);
   realized=realized.plus(D(t.amount).minus(t.fee).minus(removed));cost=cost.minus(removed);units=units.minus(t.quantity);
  }
 }
 return {...position,openingUnits:position.units,units:units.toString(),bookCost:money(cost),realized:money(realized)};
}
export function depositValue(p,on=today()) {
 const end=on<p.maturityDate?on:p.maturityDate;
 const years=Math.max(0,days(p.startDate,end))/365;
 const r=D(p.rate).div(100),n={monthly:12,quarterly:4,yearly:1}[p.compounding];
 const maturityYears=Math.max(0,days(p.startDate,p.maturityDate))/365;
 const calc=y=>p.compounding==='simple'?D(p.principal).mul(D(1).plus(r.mul(y))):D(p.principal).mul(D(1).plus(r.div(n)).pow(n*y));
 const value=p.payout==='paid_out'?D(p.principal):calc(years);
 return {...p,value:money(value),accrued:money(value.minus(p.principal)),maturityValue:money(p.payout==='paid_out'?p.principal:calc(maturityYears)),status:on>=p.maturityDate?'matured':'estimated'};
}
export function validateRecord(store,kind,input,id){
 if(!schemas[kind])throw new Error('Unknown record type');
 const data=schemas[kind].parse(input);
 if(kind==='position'||kind==='watch'){
  data.symbol=data.provider==='yahoo'?data.symbol.toUpperCase():data.symbol;
  if(kind==='position')data.tags=[...new Set(data.tags.map(t=>t.trim()))];
  const duplicate=store.list(kind).find(r=>r.id!==id&&r.provider===data.provider&&(r.symbol||r.name).toLowerCase()===(data.symbol||data.name).toLowerCase()&&(kind==='watch'||r.accountId===data.accountId));
  if(duplicate)throw new Error(kind==='watch'?'This instrument is already on your watchlist':'This holding already exists in this account. Record a purchase on it instead.');
 }
 const ref=(field,type)=>{if(data[field]&&store.get(data[field])?.kind!==type)throw new Error(`Choose an existing ${type}`);};
 ref('accountId','account');ref('cashAccountId','account');ref('positionId','position');ref('cardId','card');ref('parentId','asset');
 if(data.parentId&&data.parentId===id)throw new Error('An asset cannot contain itself');
 if(kind==='asset'&&data.parentId&&store.get(data.parentId)?.parentId)throw new Error('Use a top-level parent asset');
 if(kind==='asset'&&data.parentId&&store.list('asset').some(a=>a.parentId===id))throw new Error('An asset with included components must remain a top-level asset');
 if(kind==='card'&&D(data.statementAmount).gt(data.outstanding))throw new Error('Statement amount cannot exceed total outstanding');
 if(kind==='card'&&D(data.minimumDue).gt(data.statementAmount))throw new Error('Minimum due cannot exceed the statement amount');
 if(kind==='position'||kind==='watch'){
  if(data.provider==='mfapi'&&!/^\d+$/.test(data.symbol))throw new Error('MFapi needs the exact numeric scheme code');
  if(data.provider==='yahoo'&&!/^[\w.^=\-]{1,40}$/.test(data.symbol))throw new Error('Enter a Yahoo symbol, e.g. INFY.NS');
  if(kind==='position'&&data.openingDate>today())throw new Error('Opening date cannot be in the future');
  if(kind==='position'&&data.priceDate>today())throw new Error('Price date cannot be in the future');
 }
 if(kind==='deposit'&&data.maturityDate<=data.startDate)throw new Error('Maturity must be after the start date');
 if(kind==='deposit'&&data.startDate>today())throw new Error('A recorded deposit cannot start in the future');
 if(kind==='asset'){
  if(data.purchaseDate>today()||data.retailDate>today())throw new Error('Purchase and observed retail dates cannot be in the future');
  if(data.futureDate<data.purchaseDate)throw new Error('Future estimate cannot predate the purchase');
 }
 if(kind==='income'&&D(data.tax).gt(data.gross))throw new Error('Tax cannot exceed gross income');
 if(kind==='income'&&data.creditCash&&!data.accountId)throw new Error('Choose the receiving bank account');
 if(data.date&&data.date>today())throw new Error('Record actual transactions on or before today');
 if(data.asOf&&data.asOf>today())throw new Error('Balance date cannot be in the future');
 if(kind==='transaction'){
  const p=store.get(data.positionId);if(data.date<p.openingDate)throw new Error('Transaction predates opening holding');
  if(data.type==='split'&&(!D(data.amount).eq(0)||!D(data.fee).eq(0)))throw new Error('Splits change units only; amount and fees must be zero');
  if(data.type==='buy'&&D(data.amount).lte(0))throw new Error('Purchase consideration must be positive');
  if(data.type==='sell'&&D(data.fee).gt(data.amount))throw new Error('Sale fees cannot exceed sale proceeds');
  holding(p,[...store.list('transaction').filter(t=>t.id!==id),{...data,id:id||'zz',createdAt:store.get(id||'')?.createdAt||'9999'}]);
 }
 if(kind==='payment'){
  const card=store.get(data.cardId),paid=store.list('payment').filter(p=>p.id!==id&&p.cardId===card.id&&p.date>=card.asOf).reduce((s,p)=>s.plus(p.amount),D(0));
  if(data.date<card.asOf)throw new Error('Payment predates card opening balance');
  if(D(data.amount).gt(D(card.outstanding).minus(paid)))throw new Error('Payment exceeds outstanding balance');
 }
 if(kind==='income'&&data.positionId&&data.date<store.get(data.positionId).openingDate)throw new Error('Linked income predates the holding; record older receipts without linking this holding');
 const cashId=kind==='payment'?data.accountId:kind==='income'&&data.creditCash?data.accountId:kind==='transaction'&&data.type!=='split'?data.cashAccountId:null;
 if(cashId&&data.date<store.get(cashId).asOf)throw new Error('Cash movement predates the bank opening/reconciliation date');
 return data;
}
export function latestPrice(store,p,on=today()) {
 const row=store.db.prepare("SELECT * FROM prices WHERE key=? AND date<=? ORDER BY date DESC,(source='manual') DESC,fetched_at DESC,source ASC LIMIT 1").get(keyOf(p),on);
 const manual=p.manualPrice!==undefined&&D(p.manualPrice).gt(0)&&p.priceDate<=on;
 if(row&&(!manual||row.date>=p.priceDate))return row;
 if(manual)return {price:p.manualPrice,date:p.priceDate,source:'manual',url:'',fetched_at:null};
 return null;
}
export function portfolio(store,on=today()){
 const transactions=store.list('transaction'),incomes=store.list('income'),payments=store.list('payment');
 const accounts=store.list('account').filter(a=>a.asOf<=on).map(a=>{
  let balance=D(a.balance);
  for(const i of incomes.filter(i=>i.creditCash&&i.accountId===a.id&&i.date>=a.asOf&&i.date<=on))balance=balance.plus(D(i.gross).minus(i.tax));
  for(const p of payments.filter(p=>p.accountId===a.id&&p.date>=a.asOf&&p.date<=on))balance=balance.minus(p.amount);
  for(const t of transactions.filter(t=>t.cashAccountId===a.id&&t.date>=a.asOf&&t.date<=on)){
   if(t.type==='buy')balance=balance.minus(t.amount).minus(t.fee);
   if(t.type==='sell')balance=balance.plus(t.amount).minus(t.fee);
  }
  return {...a,value:money(balance)};
 });
 const positions=store.list('position').filter(p=>p.openingDate<=on).map(p=>{
  const h=holding(p,transactions,on),quote=latestPrice(store,p,on);
  const closed=D(h.units).eq(0),value=closed?'0.00':quote?money(D(h.units).mul(quote.price)):null;
  const age=quote?days(quote.date,on):null;
  const status=closed?'closed':!quote?'missing':age>3?'stale':quote.source==='manual'?'manual':'observed';
  return {...h,quote,value,pnl:value===null?null:money(D(value).minus(h.bookCost)),status,age};
 });
 const deposits=store.list('deposit').filter(p=>p.startDate<=on).map(p=>depositValue(p,on));
 const assets=store.list('asset').filter(a=>a.purchaseDate<=on);
 const cards=store.list('card').filter(c=>c.asOf<=on).map(c=>{
  const paid=payments.filter(p=>p.cardId===c.id&&p.date>=c.asOf&&p.date<=on).reduce((s,p)=>s.plus(p.amount),D(0));
  const outstanding=Decimal.max(0,D(c.outstanding).minus(paid));
  return {...c,value:money(outstanding),statementRemaining:money(Decimal.max(0,D(c.statementAmount).minus(paid))),available:money(Decimal.max(0,D(c.limit).minus(outstanding))),overLimit:money(Decimal.max(0,outstanding.minus(c.limit))),daysUntil:days(on,c.dueDate)};
 });
 const sum=(rows,field)=>rows.reduce((s,r)=>s.plus(r[field]??0),D(0));
 const investment=sum(positions,'value'),cash=sum(accounts,'value'),fixed=sum(deposits,'value'),resale=sum(assets.filter(a=>!a.parentId),'currentResale'),debt=sum(cards,'value');
 const gross=incomes.filter(i=>i.date<=on).reduce((s,i)=>s.plus(i.gross),D(0)),tax=incomes.filter(i=>i.date<=on).reduce((s,i)=>s.plus(i.tax),D(0));
 const groups={};for(const p of positions){groups[p.category]=money(D(groups[p.category]||0).plus(p.value||0));}
 const watch=store.list('watch').map(p=>({...p,quote:latestPrice(store,p,on)}));
 return {date:on,accounts,positions,deposits,assets,cards,incomes,transactions,payments,watch,groups,
  totals:{investment:money(investment),cash:money(cash),deposits:money(fixed),cashAndDeposits:money(cash.plus(fixed)),availableCredit:money(sum(cards,'available')),assets:money(resale),debt:money(debt),netWorth:money(investment.plus(cash).plus(fixed).plus(resale).minus(debt)),cost:money(sum(positions,'bookCost')),unrealized:money(sum(positions,'pnl')),realized:money(sum(positions,'realized')),incomeGross:money(gross),incomeTax:money(tax),incomeNet:money(gross.minus(tax)),creditLimit:money(sum(cards,'limit'))},
  coverage:{observed:positions.filter(p=>p.status==='observed').length,manual:positions.filter(p=>p.status==='manual').length,stale:positions.filter(p=>p.status==='stale').length,missing:positions.filter(p=>p.status==='missing').length}
 };
}
// Validate the entire proposed ledger inside the write transaction. Rechecking
// later dates catches a backdated edit or deletion that makes a later sale/payment impossible.
export function validateLedger(store){
 const tx=store.list('transaction'),payments=store.list('payment'),income=store.list('income');
 for(const p of store.list('position'))holding(p,tx);
 for(const a of store.list('account')){
  let balance=D(a.balance);const movements=[];
  for(const i of income)if(i.creditCash&&i.accountId===a.id&&i.date>=a.asOf)movements.push({date:i.date,delta:D(i.gross).minus(i.tax)});
  for(const p of payments)if(p.accountId===a.id&&p.date>=a.asOf)movements.push({date:p.date,delta:D(p.amount).neg()});
  for(const t of tx)if(t.cashAccountId===a.id&&t.date>=a.asOf&&t.type!=='split')movements.push({date:t.date,delta:t.type==='buy'?D(t.amount).plus(t.fee).neg():D(t.amount).minus(t.fee)});
  const daily=new Map();for(const m of movements)daily.set(m.date,D(daily.get(m.date)||0).plus(m.delta));
  for(const [date,delta] of [...daily].sort((a,b)=>a[0].localeCompare(b[0]))){balance=balance.plus(delta);if(balance.lt(0))throw new Error(`${a.name} would have a negative recorded balance on ${date}. Correct its balance or cash movements first.`);}
 }
 for(const c of store.list('card')){const paid=payments.filter(p=>p.cardId===c.id&&p.date>=c.asOf).reduce((s,p)=>s.plus(p.amount),D(0));if(paid.gt(c.outstanding))throw new Error('Recorded card payments exceed the statement opening balance');}
 for(const a of store.list('asset'))if(a.parentId&&(a.parentId===a.id||store.get(a.parentId)?.parentId))throw new Error('Asset components must refer to a top-level parent');
 return true;
}
export function snapshot(store){const p=portfolio(store);store.db.prepare('INSERT INTO snapshots VALUES(?,?) ON CONFLICT(date) DO UPDATE SET data=excluded.data').run(p.date,JSON.stringify({date:p.date,...p.totals,coverage:p.coverage,groups:p.groups,positions:p.positions.map(r=>({id:r.id,units:r.units,value:r.value,priceDate:r.quote?.date,status:r.status}))}));return p;}
export function incomeReport(store){
 const rows=store.list('income'),months={};
 for(const i of rows){const key=i.date.slice(0,7);months[key]??={month:key,dividend:'0.00',interest:'0.00',gross:'0.00',tax:'0.00',net:'0.00'};const m=months[key];m[i.type]=money(D(m[i.type]).plus(D(i.gross).minus(i.tax)));m.gross=money(D(m.gross).plus(i.gross));m.tax=money(D(m.tax).plus(i.tax));m.net=money(D(m.net).plus(D(i.gross).minus(i.tax)));}
 return {rows:rows.map(i=>({...i,net:money(D(i.gross).minus(i.tax))})),months:Object.values(months).sort((a,b)=>a.month.localeCompare(b.month))};
}
