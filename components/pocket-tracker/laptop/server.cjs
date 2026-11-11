'use strict';
const http=require('node:http'),https=require('node:https'),tls=require('node:tls'),crypto=require('node:crypto'),fs=require('node:fs'),path=require('node:path');
const PORT=43820,root=path.join(__dirname,'../app/src/main/assets/dashboard'),privateDir=path.join(__dirname,'.private'),pairFile=path.join(privateDir,'pairing.json');
const allowedHosts=new Set(['127.0.0.1:'+PORT,'localhost:'+PORT]),origins=new Set(['http://127.0.0.1:'+PORT,'http://localhost:'+PORT]);
function validate(p){if(!p||!/^([0-9]{1,3}\.){3}[0-9]{1,3}$/.test(p.host))throw Error('Use the phone’s Wi-Fi address.');const a=p.host.split('.').map(Number);if(a.some(x=>x>255)||!(a[0]===10||a[0]===192&&a[1]===168||a[0]===172&&a[1]>=16&&a[1]<=31))throw Error('Only private Wi-Fi addresses are allowed.');if(p.port!==43821||!/^[a-f0-9]{64}$/.test(p.fingerprint)||!/^[A-Za-z0-9_=-]{40,64}$/.test(p.token))throw Error('Invalid pairing code.');return p;}
function pairing(){try{return validate(JSON.parse(fs.readFileSync(pairFile,'utf8').replace(/^\uFEFF/,'')));}catch{throw Error('Pair your phone from Setup to get started.');}}
function phone(p,method,url,body){return new Promise((resolve,reject)=>{
 const agent=new https.Agent({keepAlive:false});
 // Trust only the exact certificate paired locally, not a public CA or a hostname.
 agent.createConnection=(options,callback)=>{let done=false;const finish=(err,s)=>{if(done)return;done=true;callback(err,s);};const s=tls.connect({host:p.host,port:p.port,rejectUnauthorized:false,minVersion:'TLSv1.2',maxVersion:'TLSv1.2'},()=>{const cert=s.getPeerCertificate(true),hash=cert.raw&&crypto.createHash('sha256').update(cert.raw).digest('hex');if(hash!==p.fingerprint){s.destroy();finish(Error('Phone certificate changed. Pair again on your phone.'));return;}finish(null,s);});s.setTimeout(15000,()=>s.destroy(Error('Phone connection timed out.')));s.on('error',err=>finish(err));};
 const req=https.request({hostname:p.host,port:p.port,path:url,method,agent,headers:{Authorization:'Bearer '+p.token,...(body?{'Content-Type':'application/json','Content-Length':Buffer.byteLength(body)}:{})}},res=>{const chunks=[];let bytes=0;res.on('data',b=>{bytes+=b.length;if(bytes>30000000)res.destroy(Error('Response exceeds local limit.'));else chunks.push(b);});res.on('error',reject);res.on('end',()=>{agent.destroy();resolve({status:res.statusCode,type:res.headers['content-type'],body:Buffer.concat(chunks)});});});req.setTimeout(65000,()=>req.destroy(Error('Phone is still preparing data. Retry shortly.')));req.on('error',e=>{agent.destroy();reject(e);});if(body)req.write(body);req.end();
});}
function send(res,status,value,type='application/json'){res.writeHead(status,{'Content-Type':type,'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','X-Frame-Options':'DENY'});res.end(typeof value==='string'||Buffer.isBuffer(value)?value:JSON.stringify(value));}
async function read(req){let s='';for await(const b of req){s+=b;if(s.length>65536)throw Error('Request too large.');}return s;}
const server=http.createServer(async(req,res)=>{try{
 if(!allowedHosts.has(req.headers.host))return send(res,403,{error:'Invalid local host.'});
 if(req.headers.origin&&!origins.has(req.headers.origin))return send(res,403,{error:'Cross-site access blocked.'});
 if(req.headers['sec-fetch-site']==='cross-site')return send(res,403,{error:'Cross-site access blocked.'});
 if(req.method==='POST'&&req.headers['x-pocket-request']!=='1')return send(res,403,{error:'Missing request protection.'});
 if(req.url==='/pair'&&req.method==='POST'){const p=validate(JSON.parse(await read(req)));const check=await phone(p,'GET','/api/snapshot');if(check.status!==200)throw Error('Pairing rejected by your phone.');fs.mkdirSync(privateDir,{recursive:true,mode:0o700});fs.writeFileSync(pairFile,JSON.stringify(p),{mode:0o600});return send(res,200,{ok:true});}
 if(req.url.startsWith('/api/')){if(!((req.method==='GET'&&(req.url==='/api/snapshot'||/^\/api\/report\/PocketTracker_[0-9]{4}-[0-9]{2}(?:_preview)?_v[0-9]+\.pdf$/.test(req.url)))||(req.method==='POST'&&req.url==='/api/command')))return send(res,404,{});const p=pairing();const r=await phone(p,req.method,req.url,req.method==='POST'?await read(req):null);return send(res,r.status,r.body,r.type);}
 if(req.method!=='GET')return send(res,405,{});const name=req.url==='/'?'index.html':req.url.slice(1);if(!['index.html','style.css','app.js','axis.png','slice.png','bhim.svg'].includes(name))return send(res,404,{});send(res,200,fs.readFileSync(path.join(root,name)),name.endsWith('.css')?'text/css':name.endsWith('.js')?'application/javascript':name.endsWith('.png')?'image/png':name.endsWith('.svg')?'image/svg+xml':'text/html; charset=utf-8');
 }catch(e){send(res,503,{error:/Pair|pair|certificate|Wi-Fi|Invalid|private|large|protection/.test(e.message)?e.message:'Phone unavailable. Check that both devices share Wi-Fi and laptop access is enabled in Pocket Tracker.'});}
});
if(require.main===module)server.listen(PORT,'127.0.0.1',()=>console.log('Pocket Tracker: http://127.0.0.1:'+PORT));
module.exports={validate,phone,server};
