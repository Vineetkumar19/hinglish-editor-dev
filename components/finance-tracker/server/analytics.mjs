import { D, money, holding, latestPrice, keyOf, today, days } from './domain.mjs';

// Return series covers the investment sleeve only. Cash at banks, FDs, debt and
// personal resale estimates must not dilute market volatility or benchmark returns.
export function analytics(store,benchmark='^NSEI') {
 const positions=store.list('position'),tx=store.list('transaction'),income=store.list('income');
 const allDates=new Set();
 for(const t of tx)allDates.add(t.date);
 for(const i of income)if(i.positionId)allDates.add(i.date);
 for(const p of positions){
  for(const q of store.db.prepare('SELECT date FROM prices WHERE key=? AND date>=? AND date<=?').all(keyOf(p),p.openingDate,today()))allDates.add(q.date);
  if(p.priceDate>=p.openingDate)allDates.add(p.priceDate);
 }
 const dates=[...allDates].filter(d=>d<=today()).sort().slice(-730);
 const points=[];let prior=null,index=100;let incomplete=0,restarts=0;
 for(const date of dates){
  const active=positions.filter(p=>p.openingDate<=date);if(!active.length)continue;
  let value=D(0),complete=true,carried=false;
  for(const p of active){const h=holding(p,tx,date);if(D(h.units).eq(0))continue;const q=latestPrice(store,p,date);if(!q||days(q.date,date)>7){complete=false;break;}carried ||= q.date!==date;value=value.plus(D(h.units).mul(q.price));}
  if(!complete){incomplete++;prior=null;continue;}
  if(prior&&prior.value.eq(0)&&value.gt(0)){prior=null;restarts++;}
  if(prior){
   let contributions=D(0),withdrawals=D(0);
   for(const p of active.filter(p=>p.openingDate>prior.date)){const q=latestPrice(store,p,p.openingDate);if(!q){complete=false;break;}contributions=contributions.plus(D(p.units).mul(q.price));}
   if(!complete){incomplete++;prior=null;continue;}
   for(const t of tx.filter(t=>t.date>prior.date&&t.date<=date)){
    if(t.type==='buy')contributions=contributions.plus(t.amount).plus(t.fee);
    if(t.type==='sell')withdrawals=withdrawals.plus(D(t.amount).minus(t.fee));
   }
   for(const i of income.filter(i=>i.positionId&&i.date>prior.date&&i.date<=date))withdrawals=withdrawals.plus(D(i.gross).minus(i.tax));
   if(prior.value.gt(0)){
    const r=value.minus(contributions).plus(withdrawals).div(prior.value).minus(1).toNumber();
    if(!Number.isFinite(r)||r< -1){incomplete++;prior=null;continue;}
    index*=1+r;
    points.push({date,value:money(value),index,return:r,days:days(prior.date,date),carried:carried||prior.carried,pnl:money(value.minus(prior.value).minus(contributions).plus(withdrawals))});
   }
  }else{index=100;points.length=0;points.push({date,value:money(value),index,return:null,days:0,pnl:null});}
  prior={date,value,carried};
 }
 const returns=points.filter(p=>p.return!==null);
 // Weekend gaps are normal. Longer gaps cannot be annualized as daily samples.
 const riskReturns=returns.filter(p=>p.days<=4&&!p.carried);
 const dailyEnough=riskReturns.length>=20;
 let peak=100,drawdown=0,currentDrawdown=0,peakDate=points[0]?.date,maxDuration=0;
 for(const p of points){if(p.index>=peak){peak=p.index;peakDate=p.date;}currentDrawdown=(p.index/peak-1)*100;drawdown=Math.min(drawdown,currentDrawdown);maxDuration=Math.max(maxDuration,days(peakDate,p.date));}
 const mean=riskReturns.length?riskReturns.reduce((s,p)=>s+p.return,0)/riskReturns.length:0;
 const variance=riskReturns.length>1?riskReturns.reduce((s,p)=>s+(p.return-mean)**2,0)/(riskReturns.length-1):0;
 const benchmarkPrices=store.db.prepare("SELECT date,price FROM prices WHERE key=? ORDER BY date,(source='manual') ASC,fetched_at ASC,source DESC").all('yahoo:'+benchmark);
 const bm=new Map(benchmarkPrices.map(p=>[p.date,Number(p.price)]));
 const comparison=points.filter(p=>bm.has(p.date));
 const first=comparison[0];
 const aligned=first?.index>0?comparison.map(p=>({date:p.date,portfolio:p.index/first.index*100,benchmark:bm.get(p.date)/bm.get(first.date)*100})):[];
 const start=points[0]?.date,end=points.at(-1)?.date;
 return {points,comparison:aligned,benchmark,benchmarkBasis:'Price return; portfolio includes recorded investment income',start,end,observations:returns.length,riskObservations:riskReturns.length,incomplete,
  totalReturn:returns.length?(index/100-1)*100:null,volatility:dailyEnough?Math.sqrt(variance*252)*100:null,
  maxDrawdown:returns.length>=1?drawdown:null,currentDrawdown:returns.length>=1?currentDrawdown:null,maxDrawdownDuration:returns.length>=1?maxDuration:null,
  dailyPnl:returns.at(-1)?.pnl??null,
  note:(!returns.length?'Add dated prices or refresh a supported investment to begin your history.':!dailyEnough?'Volatility needs 20 daily returns with fresh prices for all active holdings; carried prices are excluded.':`Volatility uses ${riskReturns.length} fresh daily returns out of ${returns.length} observed intervals; carried-price and long-gap intervals are excluded. Annualized using 252 sessions, not a forecast.`)+((incomplete||restarts)?' Only the latest continuous priced period is shown; missing history or zero invested capital interrupted the earlier series.':'')};
}
