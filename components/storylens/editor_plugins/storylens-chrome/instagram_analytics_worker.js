// Analytics runs in a job-owned tab. Restore the previous tab if the user has not switched away.
async function storylensInstagramAnalytics(job) {
  const origin = 'https://www.instagram.com';
  const profileUrl = `${origin}/${job.account}/`;
  const [previous] = await chrome.tabs.query({active: true, lastFocusedWindow: true});
  const tab = await chrome.tabs.create({url: profileUrl, active: true, ...(previous ? {windowId: previous.windowId} : {})});
  let original = '';
  const notes = [];
  const pathOf = value => value.replace(/\/+$/, '');

  async function read(action, data) {
    try { return await step(job, tab.id, action, data); }
    catch (error) {
      if (!disconnected(error)) throw error;
      await reconnect(tab.id);
      return step(job, tab.id, action, data);
    }
  }

  async function navigate(path) {
    const url = new URL(path, origin);
    if (url.origin !== origin) throw Error('Instagram analytics received an invalid destination.');
    const phase = await api('phase', {id: job.id, lease: job.lease, status: 'running', message: 'Reading Instagram analytics in Chrome.'});
    if (phase.stop) throw Error('Instagram analytics read stopped.');
    await chrome.tabs.update(tab.id, {url: url.href});
    for (let attempt = 0; attempt < 35; attempt++) {
      const current = await instagramPage(tab.id);
      const committed = new URL(current.url);
      if (pathOf(committed.pathname) === pathOf(url.pathname) && committed.search === url.search) {
        await reconnect(tab.id);
        return;
      }
      await delay(400);
    }
    throw Error('Instagram did not open the selected analytics page. Check Chrome for sign-in or verification.');
  }

  async function switchTo(account) {
    const active = await read('inspect');
    if (active.account === account) return;
    try { await nativeSwitch(tab.id, {...job, account}); }
    catch (error) { if (!disconnected(error)) throw error; }
    let stable = 0;
    for (let attempt = 0; attempt < 24; attempt++) {
      try {
        const current = await command(tab.id, 'analyticsIdentity');
        stable = current.account === account ? stable + 1 : 0;
        if (stable === 2) return;
      } catch (error) {
        if (!disconnected(error)) throw error;
        await reconnect(tab.id);
      }
      await delay(500);
    }
    throw Error('Instagram did not confirm the requested signed-in account.');
  }

  let rolling = {};
  let content = [];
  let snapshot;
  try {
    await reconnect(tab.id);
    const profile = await read('analyticsProfile', {account: job.account});
    snapshot = profile.snapshot;
    original = profile.signed_in || (await read('inspect').catch(() => ({}))).account;
    if (profile.reels) {
      try {
        await navigate(profile.reels);
        content = (await read('analyticsReels', {account: job.account})).content;
      } catch (error) { notes.push(`Reels: ${error.message}`.slice(0, 260)); }
    }
    try {
      // Switch only between the two already-bound accounts. Restore the original session afterward.
      if (original !== job.account) {
        if (!['fantasy_legends91', 'vineet_editz19'].includes(original)) throw Error('No paired signed-in account is available.');
        await navigate('/');
        await switchTo(job.account);
      }
      await navigate('/accounts/insights/?timeframe=30');
      rolling = (await read('analyticsAccount', {account: job.account})).metrics;
      let missed = 0;
      for (const reel of content.slice(0, 6)) {
        try {
          await navigate(reel.path);
          try { await step(job, tab.id, 'analyticsOpenReel', {account: job.account, id: reel.id}); }
          catch (error) { if (!disconnected(error)) throw error; }
          let opened = false;
          for (let attempt = 0; attempt < 20; attempt++) {
            const current = await chrome.tabs.get(tab.id);
            if (!current.pendingUrl && /^https:\/\/www\.instagram\.com\/insights\/media\/\d+\/$/.test(current.url || '')) {
              opened = true;
              break;
            }
            await delay(300);
          }
          if (!opened) throw Error('Instagram did not open this Reel’s Insights page.');
          await reconnect(tab.id);
          Object.assign(reel, (await read('analyticsReadReel', {account: job.account})).metrics);
        } catch (_) { missed++; }
      }
      if (missed) notes.push('Some Reel detail metrics were unavailable in the browser.');
    } catch (error) {
      notes.push(`Insights for @${job.account}: ${error.message}`.slice(0, 260));
    } finally {
      if (original && original !== job.account) {
        try {
          await navigate('/');
          if ((await read('inspect')).account === job.account) await switchTo(original);
        } catch (_) { notes.push(`Chrome could not confirm that it returned to @${original}. Check the active Instagram account.`); }
      }
    }
    await api('finish', {id: job.id, lease: job.lease, result: {status: 'complete', account: job.account,
      snapshot, rolling, content: content.map(({path, ...item}) => item), notes}});
  } finally {
    if (previous && (await chrome.tabs.get(tab.id).catch(() => null))?.active) {
      await chrome.tabs.update(previous.id, {active: true}).catch(() => {});
    }
    await chrome.tabs.remove(tab.id).catch(() => {});
  }
}
