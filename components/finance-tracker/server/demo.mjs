// Separate, explicitly labelled workspace used for browser validation.
import {resolve} from 'node:path';
process.env.DAYBOOK_DB=resolve('test-results/browser-demo.sqlite');
process.env.DAYBOOK_NO_SCHEDULER='1';process.env.DAYBOOK_DEMO='1';
const {openStore}=await import('./store.mjs');const {createApp}=await import('./index.mjs');
const store=openStore();const server=createApp(store).listen(4312,'127.0.0.1',()=>console.log('Isolated demonstration: http://127.0.0.1:4312'));
process.on('SIGINT',()=>server.close(()=>{store.db.close();process.exit(0);}));
