import { openStore } from './store.mjs';
import { refresh } from './providers.mjs';
import { checkReminders } from './scheduler.mjs';
try {
 const response=await fetch('http://127.0.0.1:4310/api/refresh',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}',signal:AbortSignal.timeout(240000)});
 if(!response.ok)throw new Error(`Running server returned ${response.status}`);
 console.log(JSON.stringify(await response.json()));
} catch(e) {
 if(e.cause?.code!=='ECONNREFUSED')throw e;
 const store=openStore();try{checkReminders(store);console.log(JSON.stringify(await refresh(store)));}finally{store.db.close();}
}
