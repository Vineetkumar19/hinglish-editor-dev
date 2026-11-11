import Parser from 'rss-parser';
import {createHash} from 'node:crypto';
import {holding,D,keyOf} from './domain.mjs';
import {matchesName} from './discovery.mjs';
export const relevantNews=(topic,title,summary='')=>topic.category!=='asset'||matchesName(topic.name.replace(/\b\d+\s*(?:tb|gb)\b/gi,''),title+' '+summary);

const runs=new WeakMap();
const hash=s=>createHash('sha256').update(s).digest('hex');
export function newsTopics(store){
 const tx=store.list('transaction'),map=new Map();
 const positions=store.list('position').filter(p=>D(holding(p,tx).units).gt(0));
 for(const p of [...positions,...store.list('watch')]){
  const key=p.provider==='manual'?'topic:'+p.name.toLowerCase():keyOf(p);
  if(!map.has(key))map.set(key,{key,name:p.name,category:p.category});
 }
 for(const a of store.list('asset'))map.set('asset:'+a.name.toLowerCase(),{key:'asset:'+a.name.toLowerCase(),name:a.name,category:'asset'});
 return [...map.values()].sort((a,b)=>a.key.localeCompare(b.key));
}
export function newsFeed(store){
 const topics=new Map(newsTopics(store).map(t=>[t.key,t]));
 const names=new Set([...topics.values()].map(t=>t.name));
 const cutoff=Date.now()-30*86400000;
 const rows=store.db.prepare('SELECT data FROM news').all().map(r=>JSON.parse(r.data)).map(r=>{
  const relatedNames=r.topicKeys?.filter(k=>topics.has(k)&&relevantNews(topics.get(k),r.title,r.summary)).map(k=>topics.get(k).name)||[r.related].filter(n=>names.has(n));
  return {...r,relatedNames:[...new Set(relatedNames)],related:[...new Set(relatedNames)].join(' · ')};
 }).filter(r=>r.relatedNames.length&&(!r.publishedAt||Date.parse(r.publishedAt)>=cutoff))
 .sort((a,b)=>(b.publishedAt||'').localeCompare(a.publishedAt||''));
 const unique=new Map();for(const row of rows){const key=row.title.toLowerCase().replace(/\s+/g,' ').trim()+'|'+(row.publishedAt||'').slice(0,10);const old=unique.get(key);if(old){old.relatedNames=[...new Set([...old.relatedNames,...row.relatedNames])];old.related=old.relatedNames.join(' · ');}else unique.set(key,row);}return [...unique.values()].slice(0,300);
}
async function publicFeed(url){
 const r=await fetch(url,{signal:AbortSignal.timeout(15000),headers:{'User-Agent':'Finance Tracker/0.2 personal news reader'}});
 if(!r.ok)throw new Error(`Source returned HTTP ${r.status}`);return r.text();
}
// Cached headlines are returned immediately. Refreshes run separately from model
// questions, coalesce concurrent callers, and isolate failures per instrument.
export function ensureNews(store,{force=false,fetchFeed=publicFeed,now=Date.now()}={}){
 if(runs.has(store))return runs.get(store);
 const topics=newsTopics(store),fingerprint=hash(JSON.stringify(topics)),previous=store.setting('newsStatus',{});
 if(!topics.length){const empty={state:'empty',count:0,topicCount:0,errors:[],fingerprint};store.setSetting('newsStatus',empty);return Promise.resolve(empty);}
 if(!force&&previous.fingerprint===fingerprint&&Date.parse(previous.nextRefreshAt||0)>now)return Promise.resolve(previous);
 if(previous.state==='running'&&Date.parse(previous.attemptedAt||0)>now-120000)return Promise.resolve(previous);
 const status={state:'running',attemptedAt:new Date(now).toISOString(),lastSuccessAt:previous.lastSuccessAt||null,topicCount:topics.length,count:newsFeed(store).length,errors:[],fingerprint};
 store.setSetting('newsStatus',status);
 const work=(async()=>{
  const parser=new Parser();let index=0,successful=0;
  const errors=[];
  await Promise.all(Array.from({length:Math.min(3,topics.length)},async()=>{
   while(index<topics.length){const topic=topics[index++];
    try{
     // Only public instrument names are queried, never account/quantity/balance data.
     const searchName=topic.category==='mutual_fund'?topic.name.replace(/\s*-\s*(?:Direct|Regular).*/i,''):topic.category==='asset'?topic.name.replace(/\b\d+\s*(?:tb|gb)\b/gi,'').trim():topic.name;
     const query=`"${searchName.replaceAll('"','')}" when:7d`;
     const feed=await parser.parseString(await fetchFeed(`https://news.google.com/rss/search?q=${encodeURIComponent(query)}&hl=en-IN&gl=IN&ceid=IN:en`));
     for(const item of feed.items.slice(0,8)){
      let u;try{u=new URL(item.link);}catch{continue;}
      if(u.protocol!=='https:'||!item.title||!relevantNews(topic,item.title,item.contentSnippet||''))continue;
      const stamp=Date.parse(item.isoDate||item.pubDate||'');
      if(Number.isFinite(stamp)&&(stamp>now+86400000||stamp<now-30*86400000))continue;
      const id=hash(u.href),existing=store.db.prepare('SELECT data FROM news WHERE id=?').get(id);
      const old=existing?JSON.parse(existing.data):{};
      const row={id,title:item.title.slice(0,500),url:u.href,publishedAt:Number.isFinite(stamp)?new Date(stamp).toISOString():null,topicKeys:[...new Set([...(old.topicKeys||[]),topic.key])],related:topic.name,source:'Google News RSS',summary:(item.contentSnippet||'').slice(0,600),fetchedAt:new Date(now).toISOString()};
      store.db.prepare('INSERT INTO news VALUES(?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data').run(id,JSON.stringify(row));
     }
     successful++;
    }catch(e){errors.push({topic:topic.name,message:e.message});}
   }
  }));
  const state=errors.length?(successful?'partial':'failed'):'ready';
  const result={...status,state,count:newsFeed(store).length,errors,finishedAt:new Date().toISOString(),lastSuccessAt:successful?new Date(now).toISOString():status.lastSuccessAt,nextRefreshAt:new Date(now+(errors.length?5:30)*60000).toISOString()};
  store.setSetting('newsStatus',result);return result;
 })().catch(error=>{const result={...status,state:'failed',errors:[{topic:'News',message:error.message}],nextRefreshAt:new Date(now+300000).toISOString()};store.setSetting('newsStatus',result);return result;}).finally(()=>runs.delete(store));
 runs.set(store,work);return work;
}
export async function refreshNews(store){const n=await ensureNews(store,{force:true});return {key:'news',status:n.state==='failed'?'failed':n.state==='partial'?'partial':'updated',count:n.count,errors:n.errors};}
