(function (root, factory) {
  'use strict';
  const ui = factory();
  if (typeof module === 'object' && module.exports) module.exports = ui;
  else {
    root.StorylensPhone = ui;
    if (root.document.readyState === 'loading') root.document.addEventListener('DOMContentLoaded', () => ui.mount(root));
    else ui.mount(root);
  }
})(typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';
  const ACTIVE = new Set(['planning', 'running', 'transcribing', 'processing', 'queued']);
  const EXTENSIONS = new Set(['mp4','mov','mkv','webm','mp3','wav','m4a','ogg','png','jpg','jpeg','webp','txt','xml']);
  const ID = /^[A-Za-z0-9_-]{1,160}$/;
  const isId = value => typeof value === 'string' && ID.test(value);
  const array = value => Array.isArray(value) ? value : [];
  const text = value => typeof value === 'string' ? value : '';
  const basename = value => text(value).split(/[\\/]/).pop().replace(/[\u0000-\u001f\u007f]/g, '').slice(0, 240) || 'File';
  function redact(value) {
    return text(value)
      .replace(/\b(?:Bearer\s+)[^\s,;]+/gi, '[private credential]')
      .replace(/\b(?:token|csrf|password|session|api[_-]?key|engine[_-]?token)\s*[:=]\s*["']?[^\s,"';}]+/gi, '[private credential]')
      .replace(/[A-Za-z]:[\\/][^\n\r"<>|]*/g, '[local file]')
      .replace(/\\\\[^\s"<>]+/g, '[local file]')
      .replace(/\/(?:home|Users|mnt|var|opt|srv|api|output|cache|library|tools)\/[^\s"<>]*/gi, '[local detail]')
      .slice(0, 4000);
  }
  function consumePairFragment(location, history) {
    if (!location.hash) return '';
    const params = new URLSearchParams(location.hash.slice(1));
    const code = params.get('pair') || '';
    history.replaceState(null, '', location.pathname + location.search);
    return code.length <= 128 ? code : '';
  }
  function safeFileUrl(value, origin) {
    if (typeof value !== 'string' || !value || value.includes('#') || value.includes('\\')) return null;
    let candidate = value;
    if (candidate.startsWith(origin + '/')) candidate = candidate.slice(origin.length);
    if (!/^\/phone\/files\/[A-Za-z0-9_-]+(?:\?download=1)?$/.test(candidate)) return null;
    try {
      const url = new URL(candidate, origin);
      return url.origin === origin && !url.username && !url.password ? url.pathname + url.search : null;
    } catch (_) { return null; }
  }
  function previewKind(file) {
    const mime = text(file.mime).toLowerCase().split(';')[0];
    const ext = basename(file.name).split('.').pop().toLowerCase();
    if (['video/mp4','video/webm','video/quicktime'].includes(mime) && ['mp4','webm','mov'].includes(ext)) return 'video';
    if (['audio/mpeg','audio/mp3','audio/wav','audio/x-wav','audio/wave','audio/mp4','audio/x-m4a','audio/ogg'].includes(mime) && ['mp3','wav','m4a','ogg'].includes(ext)) return 'audio';
    if (['image/png','image/jpeg','image/webp','image/gif'].includes(mime) && ['png','jpg','jpeg','webp','gif'].includes(ext)) return 'image';
    return 'download';
  }
  function makeRequestId(crypto) {
    if (crypto && typeof crypto.randomUUID === 'function') return crypto.randomUUID();
    if (!crypto || typeof crypto.getRandomValues !== 'function') throw Error('This browser cannot create a secure request ID. Use a current browser.');
    return Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2,'0')).join('');
  }
  function validateFile(file) {
    if (!file || !Number.isSafeInteger(file.size) || file.size < 1) return 'Choose a non-empty file.';
    if (file.size > 256 * 1024 * 1024) return 'Choose a file no larger than 256 MiB.';
    const ext = text(file.name).split('.').pop().toLowerCase();
    return EXTENSIONS.has(ext) ? '' : 'Choose a supported video, audio, image, TXT or XML file.';
  }
  function progressInfo(value) {
    if (!value || typeof value !== 'object') return null;
    const total = value.total;
    const completed = value.completed;
    if (!Number.isSafeInteger(total) || total <= 0) return null;
    if (Number.isSafeInteger(completed) && completed >= 0 && completed <= total) return {completed, total, remaining:total-completed};
    if (Number.isSafeInteger(value.current) && value.current >= 0 && value.current <= total) return {current:value.current, total};
    return null;
  }
  function friendlyError(error, ambiguous) {
    const status = Number(error && error.status) || 0;
    const messages = {
      401:'Pair this phone again to continue.',
      403:'Your connection needs refreshing. Check progress, then try again.',
      404:'This chat or file is no longer available. Choose a recent chat.',
      413:'The file is too large. Choose a file up to 256 MiB.',
      415:'That file type is not supported. Choose another file.',
      429:'The laptop is busy. Wait a moment and check progress.'
    };
    const message = ambiguous ? 'The request may have reached your laptop. Check progress before retrying the same request.' : (messages[status] || 'The request could not finish. Check your private connection and try again.');
    const details = redact(text(error && error.details) || text(error && error.message));
    return {message, details:(status ? 'HTTP ' + status + (details ? '\n' : '') : '') + details};
  }
  function createClient(fetcher) {
    return async function api(route, options) {
      const opts = options || {};
      if (!/^\/phone\/(?:state|pair|logout|chats(?:\/[A-Za-z0-9_-]+(?:\/(?:messages|stop|attachments)(?:\?name=[^#]*)?)?)?)$/.test(route) || route.includes('\\')) throw Error('Only phone companion requests are allowed.');
      const method = opts.method || 'GET';
      if (method !== 'GET' && method !== 'POST') throw Error('Unsupported phone request.');
      if (method === 'POST' && route !== '/phone/pair' && !opts.csrf) throw Error('Pair this phone again.');
      const headers = {Accept:'application/json'};
      if (method === 'POST') headers['Content-Type'] = opts.binary ? 'application/octet-stream' : 'application/json';
      if (opts.csrf && method === 'POST') headers['X-Phone-CSRF'] = opts.csrf;
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), opts.binary ? 600000 : 30000);
      try {
        const response = await fetcher(route, {method, headers, credentials:'same-origin', cache:'no-store', redirect:'error', signal:controller.signal, ...(method === 'POST' ? {body:opts.binary ? opts.body : JSON.stringify(opts.body || {})} : {})});
        let data;
        try { data = await response.json(); } catch (_) { data = null; }
        if (!response.ok || !data || typeof data !== 'object') {
          const error = Error('The laptop did not return a usable response.');
          error.status = response.status;
          error.ambiguous = response.ok;
          error.details = data && text(data.error_details || data.details);
          throw error;
        }
        return data;
      } finally { clearTimeout(timer); }
    };
  }
  const read = (storage, key) => { try { return storage && storage.getItem(key) || ''; } catch (_) { return ''; } };
  const write = (storage, key, value) => { try { if (storage) storage.setItem(key, value); } catch (_) {} };
  const remove = (storage, key) => { try { if (storage) storage.removeItem(key); } catch (_) {} };
  function clearStorage(storage) {
    try {
      const keys = storage.data instanceof Map ? [...storage.data.keys()] : Array.from({length:storage.length}, (_, i) => storage.key(i));
      keys.filter(k => k === 'phone.chat' || k === 'phone.pending' || text(k).startsWith('phone.draft.')).forEach(k => storage.removeItem(k));
    } catch (_) {}
  }
  function restorePending(storage) {
    try {
      const saved = read(storage, 'phone.pending');
      if (!saved || saved.length > 200000) return null;
      const op = JSON.parse(saved);
      if (!['new','send','upload','stop'].includes(op.kind) || !isId(op.request_id) || (op.kind !== 'new' && !isId(op.chatId))) return null;
      if (op.kind === 'send' && (!op.body || op.body.request_id !== op.request_id || typeof op.body.message !== 'string' || !['general','cricket','gaming'].includes(op.body.profile) || !Array.isArray(op.body.attachments) || op.body.attachments.some(id => !isId(id)))) return null;
      return op;
    } catch (_) { return null; }
  }
  function createApp(options) {
    const {api, storage, pendingStorage} = options;
    const requestId = options.requestId || (() => makeRequestId(globalThis.crypto));
    const state = {paired:false,csrf:'',connected:false,assistant:false,network:true,chats:[],chat:null,currentId:'',draft:read(storage,'phone.draft.new'),profile:'general',selected:[],pending:restorePending(pendingStorage),busy:false,loading:false,error:null,notice:''};
    const selections = new Map();
    let epoch = 0;
    let refreshing = false;
    let destroyed = false;
    const notify = () => { if (!destroyed && options.onChange) options.onChange(state); };
    const draftKey = () => 'phone.draft.' + (state.currentId || 'new');
    function savePending(op) {
      state.pending = op;
      if (op) {
        // Session-scoped retry identity, never a pairing code, cookie or CSRF value.
        const saved = {...op}; delete saved.file;
        write(pendingStorage, 'phone.pending', JSON.stringify(saved));
      } else remove(pendingStorage, 'phone.pending');
    }
    function lock() {
      epoch++;
      state.paired=false;state.csrf='';state.chat=null;state.connected=false;state.selected=[];
    }
    function fail(error, ambiguous) {
      if (error.status === 401) lock();
      state.error = friendlyError(error, ambiguous && error.status !== 401);
      notify();
    }
    function applySnapshot(snapshot) {
      if (!snapshot || !isId(snapshot.id)) throw Error('The laptop returned an incomplete chat.');
      state.chat = snapshot; state.currentId = snapshot.id;
      write(storage,'phone.chat',snapshot.id);
      const index=state.chats.findIndex(chat=>chat.id===snapshot.id);
      const entry={id:snapshot.id,title:snapshot.title,status:snapshot.status,stage:snapshot.stage};
      if(index<0)state.chats.unshift(entry);else state.chats[index]={...state.chats[index],...entry};
    }
    function canWork() {
      if (!state.paired || !state.csrf || !state.connected || !state.network || state.busy || state.pending) return false;
      return true;
    }
    async function selectChat(id) {
      if (!isId(id) || state.busy || !state.paired || (state.pending && state.pending.chatId && state.pending.chatId !== id)) return;
      const ticket=++epoch;
      state.currentId=id;state.chat=null;state.loading=true;state.notice='';
      state.draft=read(storage,draftKey());state.selected=selections.get(id)||[];
      write(storage,'phone.chat',id);notify();
      try {
        const snapshot=await api('/phone/chats/'+id);
        if(ticket!==epoch || destroyed)return;
        applySnapshot(snapshot);state.network=true;
      } catch(error) { if(ticket===epoch)fail(error,false); }
      finally {if(ticket===epoch){state.loading=false;notify();}}
    }
    async function refresh() {
      if (refreshing || state.busy || destroyed) return;
      refreshing=true;
      const ticket=epoch;
      try {
        const status=await api('/phone/state');
        if(ticket!==epoch || destroyed)return;
        if(status.paired!==true || !text(status.csrf)) {lock();notify();return;}
        state.paired=true;state.csrf=status.csrf;state.connected=status.connected===true;state.assistant=status.assistant;state.network=true;
        state.chats=array(status.chats).filter(chat=>chat&&isId(chat.id));
        const active=typeof status.active_chat==='string'?status.active_chat:status.active_chat&&status.active_chat.id;
        const saved=state.currentId || (state.pending&&state.pending.chatId) || read(storage,'phone.chat') || active;
        if(!state.currentId && isId(saved)) {
          notify();await selectChat(saved);return;
        }
        if(state.currentId) {
          const id=state.currentId;
          const snapshot=await api('/phone/chats/'+id);
          if(ticket!==epoch || destroyed)return;
          applySnapshot(snapshot);
        }
        notify();
      } catch(error) {
        if(ticket===epoch) {
          state.network=error.status===401;
          if(error.status===401)lock();
          if(error.status!==401 && !state.pending)state.error=friendlyError(error,false);
          notify();
        }
      } finally {refreshing=false;}
    }
    function routeFor(op) {
      if(op.kind==='new')return '/phone/chats';
      const base='/phone/chats/'+op.chatId;
      if(op.kind==='send')return base+'/messages';
      if(op.kind==='stop')return base+'/stop';
      return base+'/attachments?name='+encodeURIComponent(op.name)+'&request_id='+encodeURIComponent(op.request_id);
    }
    async function perform(op) {
      if(state.busy || !state.paired || !state.connected || !state.network)return;
      if(op.kind==='upload'&&!op.file) {state.error={message:'Choose the same file again to retry this upload.',details:''};notify();return;}
      state.busy=true;state.error=null;state.notice='';epoch++;
      savePending(op);notify();
      try {
        const body=op.kind==='new'?{request_id:op.request_id}:op.kind==='stop'?{}:op.kind==='upload'?op.file:op.body;
        const result=await api(routeFor(op),{method:'POST',csrf:state.csrf,body,binary:op.kind==='upload'});
        if(op.kind==='upload') {
          if(!result || !isId(result.id))throw Error('The laptop did not confirm the attachment.');
          if(!state.selected.some(file=>file.id===result.id))state.selected.push(result);
          selections.set(op.chatId,state.selected);
        } else {
          applySnapshot(result);
          if(op.kind==='new') {
            state.draft=read(storage,draftKey());state.selected=selections.get(result.id)||[];
          }
          if(op.kind==='send') {
            if(state.draft===op.body.message){state.draft='';remove(storage,draftKey());}
            state.selected=state.selected.filter(file=>!op.body.attachments.includes(file.id));selections.set(op.chatId,state.selected);
          }
          if(op.kind==='stop')state.notice='Stop requested. The current step can finish; saved work stays available.';
        }
        savePending(null);
      } catch(error) {
        const ambiguous=error.ambiguous || !error.status || error.status>=500 || [408,409].includes(error.status);
        if(!ambiguous && error.status!==401)savePending(null);
        fail(error,ambiguous);
      } finally {state.busy=false;notify();}
    }
    async function pair(code) {
      if(state.busy)return;
      if(!text(code).trim()){state.error={message:'Enter the pairing code from your laptop.',details:''};notify();return;}
      state.busy=true;state.error=null;notify();
      try {const result=await api('/phone/pair',{method:'POST',body:{code}});if(result.paired!==true)throw Error('Pairing not confirmed.');state.csrf=text(result.csrf);state.paired=true;}
      catch(error){fail(error,false);}
      finally {state.busy=false;notify();}
      if(state.paired)await refresh();
    }
    async function logout() {
      if(state.busy||!state.paired)return;
      state.busy=true;notify();
      try {
        await api('/phone/logout',{method:'POST',csrf:state.csrf,body:{}});
        lock();clearStorage(storage);clearStorage(pendingStorage);selections.clear();
        state.pending=null;state.draft='';state.currentId='';state.chats=[];state.notice='';state.error=null;
      }catch(error){fail(error,false);}
      finally {state.busy=false;notify();}
    }
    return {
      state, init:refresh, refresh, checkProgress:refresh, selectChat, pair, logout,
      setDraft(value){state.draft=text(value);write(storage,draftKey(),state.draft);notify();},
      setProfile(value){if(['general','cricket','gaming'].includes(value))state.profile=value;notify();},
      async newChat(){if(canWork())await perform({kind:'new',request_id:requestId()});},
      async send(){
        if(!canWork()||!state.chat||(!state.draft.trim()&&!state.selected.length))return;
        const id=requestId();await perform({kind:'send',chatId:state.currentId,request_id:id,body:{request_id:id,message:state.draft,attachments:state.selected.map(file=>file.id),profile:state.profile}});
      },
      async upload(file){
        const invalid=validateFile(file);if(invalid){state.error={message:invalid,details:''};notify();return;}
        if(state.pending&&state.pending.kind==='upload'){
          const op=state.pending;
          if(file.name!==op.name||file.size!==op.size||Number(file.lastModified||0)!==Number(op.lastModified||0)){state.error={message:'Choose the original file to retry this request.',details:''};notify();return;}
          await perform({...op,file});return;
        }
        if(!canWork()||!state.chat)return;
        await perform({kind:'upload',chatId:state.currentId,request_id:requestId(),name:file.name,size:file.size,lastModified:file.lastModified||0,file});
      },
      addAttachment(id){if(state.busy||state.pending||!state.chat)return;const file=array(state.chat.attachments).find(item=>item&&isId(item.id)&&item.id===id);if(file&&!state.selected.some(item=>item.id===id)){state.selected.push(file);selections.set(state.currentId,state.selected);}notify();},
      removeAttachment(id){if(state.busy||state.pending)return;state.selected=state.selected.filter(file=>file.id!==id);selections.set(state.currentId,state.selected);notify();},
      async stop(){if(canWork()&&state.chat&&ACTIVE.has(state.chat.status))await perform({kind:'stop',chatId:state.currentId,request_id:requestId()});},
      async retry(){if(state.pending)await perform(state.pending);},
      destroy(){destroyed=true;epoch++;}
    };
  }
  function mount(win) {
    const doc=win.document;
    const el=id=>doc.getElementById(id);
    const pairCode=consumePairFragment(win.location,win.history);
    el('pair-code').value=pairCode;
    let local;let session;
    try{local=win.localStorage;}catch(_){}
    try{session=win.sessionStorage;}catch(_){}
    let app;let messagesKey='';let resultsKey='';let chatsKey='';let selectedKey='';let storedKey='';let lastError='';
    const make=(tag,className,value)=>{const node=doc.createElement(tag);if(className)node.className=className;if(value!==undefined)node.textContent=value;return node;};
    function showError(error) {
      const key=JSON.stringify(error);
      el('error-box').hidden=!error;
      if(key===lastError)return;
      lastError=key;el('error-details').open=false;
      el('error-text').textContent=error?error.message:'';
      el('error-technical').textContent=error?redact(error.details):'';
      el('error-details').hidden=!error||!error.details;
    }
    function messageError(message) {
      const error=friendlyError({message:text(message.error_details),status:0});
      const box=make('div','message-error');box.append(make('p','',error.message));
      if(error.details){const detail=make('details');detail.append(make('summary','','Technical details'),make('pre','',error.details));box.append(detail);}
      return box;
    }
    function renderMessages(messages) {
      const key=JSON.stringify(messages);
      if(key===messagesKey)return;messagesKey=key;
      const target=el('messages');const nearBottom=win.innerHeight+win.scrollY>=doc.documentElement.scrollHeight-160;
      const fragment=doc.createDocumentFragment();
      messages.forEach(message=>{
        if(!message||typeof message.text!=='string')return;
        const role=message.role==='user'?'user':'assistant';
        const article=make('article','message '+role);
        article.append(make('span','message-role',role==='user'?'You':'Editor'),make('p','message-text',role==='user'?message.text:redact(message.text)));
        if(message.error||message.error_code)article.append(messageError(message));
        fragment.append(article);
      });target.replaceChildren(fragment);
      if(nearBottom&&doc.activeElement!==el('message'))el('composer').scrollIntoView({block:'nearest'});
    }
    function renderFiles(files) {
      const key=JSON.stringify(files);if(key===resultsKey)return;resultsKey=key;
      const target=el('results');const fragment=doc.createDocumentFragment();let count=0;
      files.forEach(file=>{
        if(!file||!text(file.name))return;
        const media=safeFileUrl(file.url,win.location.origin);
        const download=safeFileUrl(file.download_url,win.location.origin)||media;
        if(!download)return;
        const card=make('article','file-card');const kind=previewKind(file);
        if(media&&kind!=='download'){
          const player=make(kind==='image'?'img':kind);
          if(kind==='image'){player.alt=basename(file.name);player.loading='lazy';}
          else {player.controls=true;player.preload='metadata';if(kind==='video')player.playsInline=true;}
          player.src=media;card.append(player);
        }
        const info=make('div','file-info');const name=make('div','file-name',basename(file.name));
        if(Number.isSafeInteger(file.size)&&file.size>=0)name.append(make('small','',formatSize(file.size)));
        const link=make('a','','Download');link.href=download;link.download=basename(file.name);link.referrerPolicy='no-referrer';
        info.append(name,link);card.append(info);fragment.append(card);count++;
      });target.replaceChildren(fragment);el('results-panel').hidden=count===0;
    }
    function render(state) {
      const ready=state.paired&&state.connected&&state.network;
      el('pair-panel').hidden=state.paired;el('workspace').hidden=!state.paired;el('logout').hidden=!state.paired;
      el('logout').disabled=state.busy;el('pair-submit').disabled=state.busy;el('pair-submit').textContent=state.busy&&!state.paired?'Pairing…':'Pair';
      el('connection-dot').className='dot '+(ready?'online':'offline');
      el('connection').textContent=!state.network?'Laptop unreachable · check Tailscale':!state.paired?'Private connection · pairing required':!state.connected?'Laptop editor disconnected':'Connected to your laptop';
      el('reconnect').hidden=ready||(!state.paired&&state.network);el('reconnect').disabled=state.busy;
      showError(state.error);
      el('retry-box').hidden=!state.pending||!state.paired;
      el('retry').disabled=state.busy||!ready||(state.pending&&state.pending.kind==='upload'&&!state.pending.file);
      el('check-progress').disabled=state.busy;
      el('retry-text').textContent=state.pending&&state.pending.kind==='upload'&&!state.pending.file?'An upload may have finished. Check progress, then attach the same file to retry.':'The request may have reached your laptop. Check progress before retrying. Retry keeps the same request ID.';
      el('new-chat').disabled=!ready||state.busy||!!state.pending;
      const chatKey=JSON.stringify([state.chats,state.currentId,state.busy,!!state.pending]);
      if(chatKey!==chatsKey){
        chatsKey=chatKey;const fragment=doc.createDocumentFragment();
        state.chats.forEach(chat=>{const button=make('button','',redact(text(chat.title))||'Phone chat');button.type='button';button.disabled=state.busy||!!state.pending;button.setAttribute('aria-current',String(chat.id===state.currentId));button.addEventListener('click',()=>{el('recent').open=false;app.selectChat(chat.id);});fragment.append(button);});
        el('chat-list').replaceChildren(fragment);el('chat-count').textContent=state.chats.length?'('+state.chats.length+')':'';
      }
      el('chat-title').textContent=state.chat?(redact(text(state.chat.title))||'Phone chat'):state.loading?'Opening chat…':'Your editor';
      const status=text(state.chat&&state.chat.status);
      const active=ACTIVE.has(status);
      el('chat-status').textContent=active?'Working':status==='failed'?'Needs attention':state.chat?'Saved':'';
      const task=state.chat&&state.chat.task_progress;
      const stage=redact(text(state.chat&&state.chat.stage)||text(task&&task.stage));
      el('progress-panel').hidden=!state.chat||(!active&&!stage);
      el('stage').textContent=stage||(active?'Working on your laptop':'Saved work');
      const measured=progressInfo(task);
      if(measured&&'completed'in measured){el('progress').max=measured.total;el('progress').value=measured.completed;el('progress-count').textContent=measured.completed+' / '+measured.total+' complete · '+measured.remaining+' remaining';}
      else {el('progress').removeAttribute('value');el('progress-count').textContent=measured?measured.current+' / '+measured.total+' reported':'Progress counts not reported';}
      el('progress').hidden=!active&&!measured;
      el('stop').hidden=!active;el('stop').disabled=!ready||state.busy||!!state.pending;
      const messages=array(state.chat&&state.chat.messages);
      renderMessages(messages);renderFiles(array(state.chat&&state.chat.files));
      el('empty-chat').hidden=messages.length>0;
      el('empty-chat').textContent=state.chat?'Send a message or attach a file. Your laptop does the work.':'Choose a recent chat or start a new one. Your laptop does the work.';
      // Keep the actual textarea and its selection/focus intact during every poll.
      if(el('message').value!==state.draft)el('message').value=state.draft;
      el('profile').value=state.profile;
      const selected=JSON.stringify([state.selected,state.busy,!!state.pending]);
      if(selected!==selectedKey){selectedKey=selected;const fragment=doc.createDocumentFragment();
        state.selected.forEach(file=>{const item=make('li');const button=make('button','','Remove');button.type='button';button.setAttribute('aria-label','Remove '+basename(file.name));button.disabled=state.busy||!!state.pending;button.addEventListener('click',()=>app.removeAttachment(file.id));item.append(make('span','',basename(file.name)),button);fragment.append(item);});el('attachments').replaceChildren(fragment);
      }
      const stored=array(state.chat&&state.chat.attachments).filter(file=>file&&isId(file.id));
      const storedSignature=JSON.stringify([stored,state.busy,!!state.pending,state.selected.map(file=>file.id)]);
      if(storedSignature!==storedKey){storedKey=storedSignature;const fragment=doc.createDocumentFragment();
        stored.forEach(file=>{const item=make('li');const button=make('button','','Attach');button.type='button';button.setAttribute('aria-label','Attach '+basename(file.name));button.disabled=state.busy||!!state.pending||state.selected.some(selected=>selected.id===file.id);button.addEventListener('click',()=>app.addAttachment(file.id));item.append(make('span','',basename(file.name)),button);fragment.append(item);});el('stored-attachment-list').replaceChildren(fragment);el('stored-attachments').hidden=!stored.length;
      }
      el('message').disabled=!state.chat;
      el('profile').disabled=state.busy||!!state.pending;
      el('attach').disabled=!ready||!state.chat||state.busy||(!!state.pending&&state.pending.kind!=='upload');
      el('send').disabled=!ready||!state.chat||state.busy||!!state.pending||(!state.draft.trim()&&!state.selected.length);
      el('composer-status').textContent=state.busy?(state.pending&&state.pending.kind==='upload'?'Uploading file…':'Sending request…'):state.pending?'Check progress before retrying':state.loading?'Opening chat…':'';
      el('notice').textContent=state.notice;
    }
    app=createApp({api:createClient(win.fetch.bind(win)),storage:local,pendingStorage:session,onChange:render});
    el('pair-form').addEventListener('submit',event=>{event.preventDefault();const code=el('pair-code').value;el('pair-code').value='';app.pair(code);});
    el('composer').addEventListener('submit',event=>{event.preventDefault();app.send();});
    el('message').addEventListener('input',()=>app.setDraft(el('message').value));
    el('profile').addEventListener('change',()=>app.setProfile(el('profile').value));
    el('new-chat').addEventListener('click',()=>app.newChat());
    el('logout').addEventListener('click',()=>app.logout());
    el('reconnect').addEventListener('click',()=>app.refresh());
    el('check-progress').addEventListener('click',()=>app.checkProgress());
    el('retry').addEventListener('click',()=>app.retry());
    el('stop').addEventListener('click',()=>app.stop());
    el('attach').addEventListener('click',()=>el('file-input').click());
    el('file-input').addEventListener('change',()=>{const file=el('file-input').files[0];el('file-input').value='';if(file)app.upload(file);});
    let timer;
    const startPolling=()=>{if(timer===undefined)timer=win.setInterval(()=>{if(!doc.hidden)app.refresh();},3000);};
    const visibility=()=>{if(!doc.hidden)app.refresh();};
    doc.addEventListener('visibilitychange',visibility);win.addEventListener('online',()=>app.refresh());
    win.addEventListener('pagehide',event=>{win.clearInterval(timer);timer=undefined;if(!event.persisted)app.destroy();});
    win.addEventListener('pageshow',event=>{if(event.persisted){startPolling();app.refresh();}});
    startPolling();
    render(app.state);app.init();
    return app;
  }
  function formatSize(size) {return size>=1048576?(size/1048576).toFixed(1)+' MiB':size>=1024?Math.ceil(size/1024)+' KiB':size+' bytes';}
  return {consumePairFragment,safeFileUrl,previewKind,makeRequestId,validateFile,progressInfo,redact,friendlyError,createClient,createApp,mount};
});
