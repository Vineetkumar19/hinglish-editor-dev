import Parser from 'rss-parser';
import {lookup} from 'node:dns/promises';
import {isIP} from 'node:net';
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {resolve} from 'node:path';

export const plain=s=>String(s||'').replace(/<script\b[\s\S]*?<\/script>/gi,' ').replace(/<style\b[\s\S]*?<\/style>/gi,' ').replace(/<[^>]+>/g,' ').replace(/&(?:amp|nbsp|quot|apos|lt|gt|rsquo|lsquo|ndash|mdash);/g,m=>({'&amp;':'&','&nbsp;':' ','&quot;':'"','&apos;':"'",'&lt;':'<','&gt;':'>','&rsquo;':"'",'&lsquo;':"'",'&ndash;':'–','&mdash;':'—'}[m])).replace(/&#(\d+);/g,(_,n)=>String.fromCodePoint(Math.min(Number(n),1114111))).replace(/\s+/g,' ').trim();
const normalized=s=>plain(s).toLowerCase().replace(/(\d)\s+(tb|gb|cc)\b/g,'$1$2').replace(/[^a-z0-9]+/g,' ');
export function matchesName(name,title){const tokens=normalized(name).split(' ').filter(t=>t.length>1&&!['credit','card','bank','limited','the','india','ssd'].includes(t)),target=normalized(title).split(' ');return tokens.length>0&&tokens.filter(t=>target.includes(t)).length/tokens.length>=.75&&tokens.filter(t=>/\d/.test(t)).every(t=>target.includes(t));}
export function publicAddress(address){if(address.includes(':'))return !/^(::|fc|fd|fe[89ab]|ff)/i.test(address);const a=address.split('.').map(Number);return a.length===4&&a.every(n=>n>=0&&n<=255)&&![0,10,127].includes(a[0])&&!(a[0]===169&&a[1]===254)&&!(a[0]===172&&a[1]>=16&&a[1]<=31)&&!(a[0]===192&&a[1]===168)&&!(a[0]===100&&a[1]>=64&&a[1]<=127)&&a[0]<224;}
export async function publicText(raw,{timeout=12000}={}){
 let url=new URL(raw);
 for(let hop=0;hop<4;hop++){
  if(url.protocol!=='https:'||url.username||url.password||(url.port&&url.port!=='443'))throw new Error('Use a public HTTPS source');
  const host=url.hostname.replace(/^\[|\]$/g,'');if(host==='localhost'||!host.includes('.')&&!isIP(host))throw new Error('Private sources are not allowed');
  const addresses=isIP(host)?[{address:host}]:await lookup(host,{all:true});if(!addresses.length||addresses.some(a=>!publicAddress(a.address)))throw new Error('Private sources are not allowed');
  const r=await fetch(url,{redirect:'manual',signal:AbortSignal.timeout(timeout),headers:{'User-Agent':'Mozilla/5.0 Finance Tracker personal research','Accept':'text/html,application/json,application/xml,*/*'}});
  if(r.status>=300&&r.status<400&&r.headers.get('location')){url=new URL(r.headers.get('location'),url);continue;}
  if(!r.ok)throw new Error(`Source returned HTTP ${r.status}`);if(Number(r.headers.get('content-length'))>5000000)throw new Error('Source is too large');
  const reader=r.body.getReader();let size=0,chunks=[];for(;;){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>5000000){await reader.cancel();throw new Error('Source is too large');}chunks.push(Buffer.from(value));}
  return {url:url.href,html:Buffer.concat(chunks).toString('utf8')};
 }
 throw new Error('Too many source redirects');
}
export async function searchWeb(query){
 const cacheFile=resolve('data/search-cache',createHash('sha256').update(query.toLowerCase().trim()).digest('hex')+'.json');let cached;
 try{cached=JSON.parse(readFileSync(cacheFile,'utf8'));if(Date.now()-Date.parse(cached.fetchedAt)<6*3600000)return cached.rows;}catch{}
 let rows=[];let errors=[];
 try{const {html}=await publicText('https://html.duckduckgo.com/html/?q='+encodeURIComponent(query));for(const m of html.matchAll(/<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>([\s\S]*?)<\/a>/gi)){let u=new URL(m[1].replaceAll('&amp;','&'),'https://duckduckgo.com');if(u.searchParams.has('uddg'))u=new URL(u.searchParams.get('uddg'));if(u.protocol==='https:')rows.push({title:plain(m[2]),url:u.href});}}catch(e){errors.push(e.message);}
 if(!rows.length)try{const {html}=await publicText('https://www.bing.com/search?format=rss&q='+encodeURIComponent(query));const feed=await new Parser().parseString(html);rows=feed.items.filter(r=>r.link?.startsWith('https:')).map(r=>({title:plain(r.title),url:r.link}));}catch(e){errors.push(e.message);}
 // Search feeds occasionally return generic brand pages instead of the query.
 // Never cache these as successful discovery or erase older useful matches.
 const relevant=[...new Map(rows.map(r=>[r.url,r])).values()].filter(r=>matchesName(query.replace(/\b(price India|benefits official)\b/gi,''),r.title)).slice(0,10);
 if(relevant.length){try{mkdirSync(resolve('data/search-cache'),{recursive:true});writeFileSync(cacheFile,JSON.stringify({query,rows:relevant,fetchedAt:new Date().toISOString()}));}catch{}return relevant;}
 if(cached?.rows?.length)return cached.rows.map(r=>({...r,cachedDiscoveryAt:cached.fetchedAt}));
 if(errors.length)throw new Error(errors.join('; '));return [];
}
export async function searchInstruments(query,provider='yahoo'){
 if(provider==='mfapi'){const {html}=await publicText('https://api.mfapi.in/mf/search?q='+encodeURIComponent(query));return JSON.parse(html).slice(0,15).map(r=>({name:r.schemeName,symbol:String(r.schemeCode),provider,exchange:'AMFI scheme'}));}
 const {html}=await publicText('https://query1.finance.yahoo.com/v1/finance/search?q='+encodeURIComponent(query)+'&quotesCount=15&newsCount=0');return (JSON.parse(html).quotes||[]).filter(r=>/\.(NS|BO)$/.test(r.symbol)&&['EQUITY','ETF'].includes(r.quoteType)).slice(0,12).map(r=>({name:r.longname||r.shortname,symbol:r.symbol,provider,exchange:r.exchDisp||r.exchange}));
}
export function productOffers(html,name,url){
 const found=[];const visit=o=>{if(!o||typeof o!=='object')return;if((Array.isArray(o['@type'])?o['@type']:[o['@type']]).some(t=>['Product','Vehicle','Car','Motorcycle'].includes(t))&&matchesName(name,o.name||'')){
  const offers=Array.isArray(o.offers)?o.offers:[o.offers];for(const f of offers){if(!f)continue;const price=Number(f.price??f.lowPrice);if(f.priceCurrency==='INR'&&Number.isFinite(price)&&price>0&&price<1e10)found.push({title:plain(o.name),url,price:String(price),currency:'INR',basis:f.lowPrice?'Published starting price':'Published listing price',availability:plain(f.availability||''),observedAt:new Date().toISOString()});}
 }for(const value of Object.values(o))if(typeof value==='object')Array.isArray(value)?value.forEach(visit):visit(value);};
 for(const m of html.matchAll(/<script[^>]*type=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi))try{visit(JSON.parse(m[1]));}catch{}
 return found;
}
const issuerDomains={'sbi':['sbicard.com'],'hdfc':['hdfcbank.com'],'icici':['icicibank.com'],'axis':['axisbank.com'],'amex':['americanexpress.com'],'american express':['americanexpress.com'],'idfc':['idfcfirstbank.com'],'hsbc':['hsbc.co.in'],'kotak':['kotak.com'],'yes bank':['yesbank.in'],'indusind':['indusind.com'],'rbl':['rblbank.com'],'au bank':['aubank.in']};
const issuerTerms={'sbicard.com':'https://www.sbicard.com/en/most-important-terms-and-conditions.page'};
const allowedIssuer=(url,domains)=>domains.some(d=>new URL(url).hostname===d||new URL(url).hostname.endsWith('.'+d));
export function cardPassages(html){return [...new Set(html.replace(/<head\b[\s\S]*?<\/head>/gi,'').replace(/<script\b[\s\S]*?<\/script>/gi,'').replace(/<style\b[\s\S]*?<\/style>/gi,'').split(/<\/(?:li|p|tr|h[1-6]|div)>|<br\s*\/?\s*>/i).map(plain).filter(s=>s.length>=25&&s.length<=1000&&/(cashback|cash back|reward|lounge|renewal|annual fee|joining fee|fuel surcharge|finance charges|interest.free|per month|per annum)/i.test(s)&&!/^Q\s*\d|^For (?:example|instance)/i.test(s)&&/\d|complimentary|unlimited|waiv|not applicable|excluded/i.test(s)))].slice(0,30);}
export async function discoverCard(card){
 const domains=Object.entries(issuerDomains).filter(([k])=>(card.issuer+' '+card.name).toLowerCase().includes(k)).flatMap(([,v])=>v);
 const results=(await searchWeb(`${card.name} benefits official`).catch(()=>[])).filter(r=>matchesName(card.name,r.title));
 const sources=results.filter(r=>allowedIssuer(r.url,domains)).slice(0,3);if(card.benefitsUrl&&allowedIssuer(card.benefitsUrl,domains))sources.unshift({title:'Saved issuer source',url:card.benefitsUrl});
 if(domains.includes('sbicard.com')&&/cashback/i.test(card.name))sources.unshift({title:'CASHBACK SBI Card official FAQ',url:'https://www.sbicard.com/en/faq/cashback-sbi-card-faq.page'});
 const facts=[],errors=[];let interest='';
 for(const source of [...sources.slice(0,3),...domains.filter(d=>issuerTerms[d]).map(d=>({title:'Issuer finance terms',url:issuerTerms[d],terms:true}))]){
  try{const page=await publicText(source.url);if(!allowedIssuer(page.url,domains))throw new Error('Redirect left issuer website');const text=plain(page.html);if(!source.terms&&!matchesName(card.name,text.slice(0,30000)))continue;
   const passages=cardPassages(page.html);if(!source.terms)for(const p of passages.slice(0,8))facts.push({text:p,url:page.url});
   const match=text.match(/(?:current rate of finance charges|finance charges.{0,80}?(?:upto|up to|at))[^.]{0,30}\d[\s\S]{0,130}?(?:per annum\]|p\.a\.\)|per annum\)|per annum)/i)||text.match(/\d(?:\.\d+)?%\s*(?:per month|p\.m\.)[^\n]{0,70}?\d+(?:\.\d+)?%\s*(?:per annum|p\.a\.)/i);
   if(match&&!interest){interest=match[0];facts.push({text:interest,url:page.url,type:'interest'});}
  }catch(e){errors.push({url:source.url,message:e.message});}
 }
 return {state:facts.some(f=>f.type!=='interest')?'ready':'partial',kind:'card',name:card.name,facts:facts.slice(0,15),interest,sources,alternatives:results.slice(0,6),errors,note:'Published issuer terms. Your exact due date, minimum due and balance must come from your own statement.'};
}
export async function discoverAsset(asset){
 const links=(await searchWeb(`${asset.name} price India`).catch(()=>[])).filter(r=>matchesName(asset.name,r.title)).slice(0,7);if(asset.url)links.unshift({title:asset.name+' · saved listing',url:asset.url});
 const offers=[],errors=[];await Promise.all(links.slice(0,5).map(async r=>{try{const p=await publicText(r.url);offers.push(...productOffers(p.html,asset.name,p.url));}catch(e){errors.push({url:r.url,message:e.message});}}));
 return {state:offers.length?'ready':'partial',kind:'asset',name:asset.name,links:[...new Map(links.map(r=>[r.url,r])).values()],offers:[...new Map(offers.map(r=>[r.url,r])).values()],errors,searchUrl:'https://www.google.com/search?q='+encodeURIComponent(asset.name+' price India'),note:'New/advertised prices are references only. Check variant, stock, condition and location. Discovery can reuse cached public links; prices are fetched from the linked pages. Your resale estimate is kept separate.'};
}
