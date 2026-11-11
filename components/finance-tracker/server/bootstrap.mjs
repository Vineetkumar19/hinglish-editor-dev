import {fileURLToPath} from 'node:url';
import {startServer} from './index.mjs';
process.chdir(fileURLToPath(new URL('..',import.meta.url)));
let running=false;
try{const r=await fetch('http://127.0.0.1:4310/api/health',{signal:AbortSignal.timeout(2000)});const health=await r.json();running=health.service==='finance-tracker'||health.name==='Daybook';}catch{}
if(!running)startServer();
