import { today, portfolio } from './domain.mjs';
import { refresh } from './providers.mjs';
import {ensureNews} from './news.mjs';
import {ensureEnrichment} from './enrichment.mjs';
export function checkReminders(store){
 const date=today(),activeIds=new Set();
 for(const c of portfolio(store).cards){
  if(Number(c.statementRemaining)<=0||c.daysUntil>7)continue;
  const stage=c.daysUntil<0?'overdue':c.daysUntil===0?'today':c.daysUntil<=1?'1-day':c.daysUntil<=3?'3-day':'7-day';
  const id=`card:${c.id}:${c.dueDate}:${stage}`;
  activeIds.add(id);
  const data={id,cardId:c.id,title:`${c.name}: ${c.daysUntil<0?'payment overdue':c.daysUntil===0?'payment due today':`due in ${c.daysUntil} days`}`,body:`₹${Number(c.statementRemaining).toLocaleString('en-IN')} statement balance due ${c.dueDate}.`,createdAt:new Date().toISOString(),read:false};
  const previous=store.db.prepare('SELECT data FROM notifications WHERE id=?').get(id);
  if(previous)data.read=JSON.parse(previous.data).read;
  store.db.prepare('INSERT INTO notifications VALUES(?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data').run(id,JSON.stringify(data));
 }
 // A paid statement should no longer appear as an active alert.
 for(const n of store.db.prepare('SELECT * FROM notifications').all()){const d=JSON.parse(n.data);if(!activeIds.has(n.id)&&!d.read){d.read=true;store.db.prepare('UPDATE notifications SET data=? WHERE id=?').run(JSON.stringify(d),n.id);}}
 store.setSetting('lastReminderCheck',date);
}
let busy=false;
export async function tick(store){
 if(busy)return;busy=true;
 try{
  checkReminders(store);void ensureNews(store).catch(e=>console.error(e.message));void ensureEnrichment(store).catch(e=>console.error(e.message));if(!store.setting('autoRefresh',true)||!['position','watch','account','deposit','asset','card'].some(k=>store.list(k).length))return;
  const date=today();const time=new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Kolkata',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(new Date());
  const slots=['16:00','18:00','23:15'].filter(s=>s<=time);const slot=slots.at(-1);
  if(slot&&store.setting('lastSchedule','')!==date+' '+slot){
   if(store.setting('scheduleRetryAt',0)>Date.now())return;
   try{const job=await refresh(store);if(job.status==='completed'){store.setSetting('lastSchedule',date+' '+slot);store.setSetting('scheduleRetryAt',0);store.setSetting('schedulerError','');}else{store.setSetting('scheduleRetryAt',Date.now()+300000);store.setSetting('schedulerError','Some sources failed; automatic retry in five minutes.');}}catch(e){store.setSetting('scheduleRetryAt',Date.now()+300000);store.setSetting('schedulerError',e.message);}
  }
 }finally{busy=false;}
}
