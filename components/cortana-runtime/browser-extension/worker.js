let port, timer, config, results = [], processing = false;
const cancelled = new Set();
function check(command) {
  if (!port || cancelled.has(command.id) || Date.now()/1000 >= command.expires_at) throw new Error('Operation stopped or expired');
  if (command.client_id && command.client_id !== config.client_id) throw new Error('Browser profile connection changed');
}
function safeUrl(value) {
  const url = new URL(value);
  if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password) throw new Error('Unsupported URL');
  return url;
}
async function video(tabId, seconds, expectedUrl) {
  const output = await chrome.scripting.executeScript({target: {tabId}, func: (time, expected) => {
    const wanted = new URL(expected);
    if (location.hostname !== wanted.hostname || new URL(location.href).searchParams.get('v') !== wanted.searchParams.get('v')) {
      throw new Error('The tab changed; no playback action was applied.');
    }
    const element = document.querySelector('video');
    if (!element) return {available: false};
    if (time !== null) { element.pause(); element.currentTime = time; }
    return {available: true, seconds: element.currentTime, paused: element.paused};
  }, args: [seconds ?? null, expectedUrl]});
  return output[0]?.result;
}
async function execute(command) {
  check(command);
  if (command.operation === 'find') {
    const query = String(command.arguments.query || '').trim().toLowerCase();
    if (!query) throw new Error('Enter a title or URL to find.');
    const matches = (await chrome.tabs.query({})).filter(tab => !tab.incognito &&
      /^(https?):\/\//i.test(tab.url || '') &&
      (tab.url.toLowerCase().includes(query) || (tab.title || '').toLowerCase().includes(query)));
    check(command);
    return {verified:true, browser:config.browser, profile:config.profile, match_count:matches.length,
      tabs:matches.slice(0,20).map(tab => ({tab_id:tab.id, url:tab.url, title:tab.title, active:tab.active}))};
  }
  if (command.operation === 'focus') {
    const tab = await chrome.tabs.get(command.arguments.tab_id);
    if (tab.incognito || tab.url !== safeUrl(command.arguments.expected_url).href) {
      throw new Error('The selected tab changed. Nothing was focused.');
    }
    check(command);
    await chrome.tabs.update(tab.id, {active:true});
    check(command);
    await chrome.windows.update(tab.windowId, {focused:true});
    const observed = await chrome.tabs.get(tab.id);
    const window = await chrome.windows.get(tab.windowId);
    return {verified:observed.active && observed.url === tab.url && window.focused,
      browser:config.browser, profile:config.profile, tab_id:tab.id, url:observed.url};
  }
  if (command.operation === 'capture_saved') {
    const tabs = (await chrome.tabs.query({})).filter(t => !t.incognito);
    const items = [];
    for (const saved of command.arguments.items || []) {
      check(command);
      const wanted = safeUrl(saved.target);
      const matches = tabs.filter(tab => {
        if (tab.url === saved.target) return true;
        try {
          const current = safeUrl(tab.url);
          return wanted.hostname === 'www.youtube.com' && wanted.pathname === '/watch' &&
            current.hostname === wanted.hostname && current.pathname === '/watch' &&
            current.searchParams.get('v') === wanted.searchParams.get('v');
        } catch { return false; }
      });
      if (matches.length !== 1) throw new Error('A saved tab is missing or ambiguous; previous snapshot preserved.');
      const tab = matches[0];
      let playback = null;
      if (wanted.hostname === 'www.youtube.com') {
        try { playback = await video(tab.id, null, tab.url); } catch { /* leave position unknown */ }
      }
      items.push({kind:'tab',target:tab.url,title:tab.title,browser:config.browser,profile:config.profile,
        tab_id:tab.id,group:String(tab.groupId),playback_seconds:playback?.available ? playback.seconds : null});
    }
    return {verified:true,items,capture_scope:'only previously selected saved tabs; no focus or playback changes'};
  }
  if (command.operation === 'capture') {
    const tabs = await chrome.tabs.query({highlighted: true, lastFocusedWindow: true});
    const items = [];
    for (const tab of tabs.filter(t => !t.incognito)) {
      check(command);
      try { safeUrl(tab.url); } catch { continue; }
      let playback = null;
      if (new URL(tab.url).hostname === 'www.youtube.com') {
        try { playback = await video(tab.id, null, tab.url); } catch { /* no host grant: timestamp unknown */ }
      }
      items.push({kind: 'tab', target: tab.url, title: tab.title, browser: config.browser,
        profile: config.profile, tab_id: tab.id, group: String(tab.groupId),
        playback_seconds: playback?.available ? playback.seconds : null});
    }
    return {verified: true, items, capture_scope: 'highlighted tabs in last focused window'};
  }
  if (command.operation === 'restore') {
    const url = safeUrl(command.arguments.url);
    const youtube = url.hostname === 'www.youtube.com' && url.pathname === '/watch';
    const tabs = (await chrome.tabs.query({})).filter(t => !t.incognito);
    const matches = tabs.filter(t => {
      if (t.url === url.href) return true;
      try { const other = new URL(t.url); return youtube && other.hostname === url.hostname &&
        other.pathname === '/watch' && other.searchParams.get('v') === url.searchParams.get('v'); } catch { return false; }
    });
    if (matches.length > 1) throw new Error('Multiple matching tabs; select one before restoring.');
    // Muting the newly opened YouTube tab avoids surprise audio during page loading.
    let tab = matches[0];
    check(command);
    if (!tab) {
      tab = await chrome.tabs.create({url: 'about:blank', active: true});
      check(command);
      if (youtube) await chrome.tabs.update(tab.id, {muted: true});
      check(command);
      tab = await chrome.tabs.update(tab.id, {url: url.href});
    } else await chrome.tabs.update(tab.id, {active: true});
    check(command);
    await chrome.windows.update(tab.windowId, {focused: true});
    for (let i = 0; i < 40; i++) {
      check(command);
      tab = await chrome.tabs.get(tab.id);
      if (tab.status === 'complete') break;
      await new Promise(resolve => setTimeout(resolve, 250));
    }
    let playback = null, warning = '';
    if (youtube) {
      try {
        check(command);
        // Even without a captured position, pause the current video.
        const observed = await video(tab.id, null, url.href);
        check(command);
        playback = await video(tab.id, command.arguments.playback_seconds ?? observed.seconds, url.href);
      } catch { warning = 'Playback position/pause could not be verified; new video tab remains muted.'; }
    }
    const observed = await chrome.tabs.get(tab.id);
    check(command);
    const observedUrl = safeUrl(observed.url);
    const samePage = observed.url === url.href || (youtube && observedUrl.hostname === url.hostname &&
      observedUrl.pathname === '/watch' && observedUrl.searchParams.get('v') === url.searchParams.get('v'));
    const positionMatches = command.arguments.playback_seconds == null ||
      Math.abs((playback?.seconds ?? -100) - command.arguments.playback_seconds) < 1;
    return {verified: samePage && observed.status === 'complete' && (!youtube || (playback?.paused === true && positionMatches)),
      tab_id: tab.id, url: observed.url, profile: config.profile, reused: matches.length === 1, playback, warning};
  }
  if (command.operation === 'read') {
    const tab = await chrome.tabs.get(command.arguments.tab_id);
    if (tab.incognito || !tab.active) throw new Error('Select the intended non-incognito tab first.');
    if (tab.url !== safeUrl(command.arguments.expected_url).href) throw new Error('The selected tab changed. Nothing was read.');
    check(command);
    const output = await chrome.scripting.executeScript({target: {tabId: tab.id}, func: expected =>
      location.href === expected ? document.body.innerText.slice(0, 12000) : null, args:[tab.url]});
    check(command);
    if (typeof output[0]?.result !== 'string') throw new Error('The selected page changed during observation.');
    return {verified: true, browser:config.browser, profile:config.profile, tab_id: tab.id, url: tab.url, text: output[0].result, untrusted: true};
  }
  throw new Error('Unsupported operation');
}
async function connect() {
  if (processing) throw new Error('A workspace operation is still running. Stop or finish it before reconnecting.');
  const next = await chrome.storage.local.get(['browser','profile','client_id','enabled']);
  if (config && (next.browser !== config.browser || next.profile !== config.profile)) {
    port?.disconnect(); port = null; clearInterval(timer);
    next.client_id = crypto.randomUUID();
    await chrome.storage.local.set({client_id:next.client_id});
  }
  config = next;
  if (!config.enabled || !config.profile) return;
  if (!config.client_id) { config.client_id = crypto.randomUUID(); await chrome.storage.local.set({client_id: config.client_id}); }
  if (port) return;
  port = chrome.runtime.connectNative('com.cortana.workspace');
  const linked = port;
  port.onDisconnect.addListener(() => { if (port === linked) { port = null; clearInterval(timer); } });
  port.onMessage.addListener(async message => {
    for (const id of message.cancelled || []) cancelled.add(id);
    if (processing) return;
    processing = true;
    try {
      for (const command of message.commands || []) {
        try { results.push({id: command.id, result: await execute(command)}); }
        catch (error) { results.push({id: command.id, error: error.message}); }
        finally { cancelled.delete(command.id); }
      }
    } finally { processing = false; }
  });
  const poll = () => { if (port) { port.postMessage({...config, results, busy:processing}); results = []; } };
  poll(); timer = setInterval(poll, 1000);
}
chrome.runtime.onMessage.addListener((message, sender, reply) => {
  if (sender.id !== chrome.runtime.id) return;
  if (message.operation === 'disconnect') { port?.disconnect(); port = null; clearInterval(timer); reply({note:'Disconnected'}); }
  else connect().then(() => reply({note:'Connection requested; verify status in Cortana.'})).catch(error=>reply({note:error.message}));
  return true;
});
chrome.runtime.onStartup.addListener(connect);
