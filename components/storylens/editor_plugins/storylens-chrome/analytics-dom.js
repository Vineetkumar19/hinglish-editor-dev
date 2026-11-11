// Instagram metrics from rendered pages in the existing signed-in Chrome profile.
(() => {
  const visible = element => Boolean(element?.getClientRects().length);
  const text = element => (element?.innerText || '').trim().replace(/\s+/g, ' ');
  const heading = (root, label) => [...root.querySelectorAll('h1,h2,h3,h4,[role="heading"]')]
    .filter(element => visible(element) && text(element) === label);

  function count(value) {
    const cleaned = String(value || '').trim();
    if (!/^(?:\d+|\d{1,3}(?:[,\u00a0\u202f ]\d{3})+|\d{1,2}(?:,\d{2})+,\d{3})$/.test(cleaned)) return null;
    const number = Number(cleaned.replace(/[^0-9]/g, ''));
    return Number.isSafeInteger(number) ? number : null;
  }

  function numbers(value, fields) {
    const lines = value.split(/\n+/).map(line => line.trim()).filter(Boolean);
    const result = {};
    for (const [label, key] of Object.entries(fields)) {
      const values = new Set(lines.flatMap((line, index) => {
        if (line === label) return [count(lines[index + 1])];
        return line.startsWith(`${label} `) ? [count(line.slice(label.length + 1))] : [];
      }).filter(Number.isFinite));
      if (values.size === 1) result[key] = [...values][0];
    }
    return result;
  }

  function block(doc, title) {
    const matches = heading(doc, title);
    if (matches.length !== 1) return '';
    for (let element = matches[0].parentElement, depth = 0; element && depth < 7; element = element.parentElement, depth++) {
      const value = element.innerText.trim();
      if (value.startsWith(title + '\n') && value.split('\n').length >= 3) return value;
    }
    return '';
  }

  function profile(doc, loc, account) {
    if (loc.pathname.replace(/\/+$/, '') !== '/' + account) return null;
    const headers = [...doc.querySelectorAll('main header')].filter(element => visible(element) && heading(element, account).length === 1);
    if (headers.length !== 1) return null;
    const snapshot = {};
    for (const [label, key] of Object.entries({posts: 'posts', followers: 'audience', following: 'following'})) {
      const values = new Set();
      for (const element of headers[0].querySelectorAll('span,a,li')) {
        if (!visible(element)) continue;
        const line = text(element);
        if (!line.endsWith(` ${label}`)) continue;
        const inner = element.querySelector('[title]');
        const value = count(element.title) ?? count(inner?.title) ?? count(line.slice(0, -(label.length + 1)));
        if (value !== null) values.add(value);
      }
      if (values.size === 1) snapshot[key] = [...values][0];
    }
    const reels = [...doc.querySelectorAll('main a[href]')].find(link => visible(link) && link.getAttribute('href') === `/${account}/reels/`);
    return Object.keys(snapshot).length ? {snapshot, reels: reels?.getAttribute('href') || ''} : null;
  }

  function reels(doc, loc, account) {
    if (loc.pathname.replace(/\/+$/, '') !== `/${account}/reels`) return null;
    const entries = new Map();
    for (const link of doc.querySelectorAll('a[href*="/reel/"]')) {
      const url = new URL(link.getAttribute('href'), 'https://www.instagram.com');
      if (url.origin !== 'https://www.instagram.com') continue;
      const href = url.pathname;
      const match = href.match(/^\/(?:(?<owner>[A-Za-z0-9._]+)\/)?reel\/(?<id>[A-Za-z0-9_-]{1,64})\/?$/);
      if (!visible(link) || !match || (match.groups.owner && match.groups.owner !== account) || entries.has(match.groups.id)) continue;
      if (!match.groups.owner && !link.closest('main,[role="main"]')) continue;
      const {id} = match.groups;
      const title = [...link.querySelectorAll('img[alt]')].map(img => img.alt).find(value => /\bClip$/.test(value)) || 'Instagram Reel';
      const views = count(text(link));
      const info = {id, path: `/${account}/reel/${id}/`, title: title.replace(/\s+Clip$/, '').slice(0, 160)};
      if (views !== null) info.grid_views = views;
      entries.set(id, info);
      if (entries.size >= 25) break;
    }
    return entries.size ? [...entries.values()] : null;
  }

  function accountInsights(doc, loc) {
    if (loc.pathname !== '/accounts/insights/' || new URLSearchParams(loc.search).get('timeframe') !== '30' ||
        heading(doc, 'Account insights').length !== 1) return null;
    const views = block(doc, 'Views');
    const interactions = block(doc, 'Interactions');
    const profile = block(doc, 'Profile');
    const metrics = {...numbers(views, {Views: 'views', Viewers: 'reach', 'Accounts reached': 'reach'}),
      ...numbers(interactions, {Interactions: 'interactions', 'Accounts engaged': 'accounts_engaged'}),
      ...numbers(profile, {'Profile visits': 'profile_views', 'External link taps': 'link_taps'})};
    return Object.keys(metrics).length ? metrics : null;
  }

  function reelInsights(doc, loc) {
    if (!/^\/insights\/media\/\d+\/$/.test(loc.pathname)) return null;
    const views = block(doc, 'Views');
    const interactions = block(doc, 'Interactions');
    const profile = block(doc, 'Profile');
    const metrics = {...numbers(views, {Views: 'views', Viewers: 'reach', 'Accounts reached': 'reach'}),
      ...numbers(interactions, {Interactions: 'interactions', Likes: 'likes', Comments: 'comments', Saves: 'saves', Shares: 'shares'}),
      ...numbers(profile, {Follows: 'gained'})};
    return Object.keys(metrics).length ? metrics : null;
  }

  globalThis.StorylensInstagramAnalytics = {profile, reels, accountInsights, reelInsights};
})();
