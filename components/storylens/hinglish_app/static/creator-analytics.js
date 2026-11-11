(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const token = document.documentElement.dataset.token;
  const headers = {'X-Hinglish-Token': token, 'Content-Type': 'application/json'};
  const integer = new Intl.NumberFormat('en-IN', {maximumFractionDigits: 0});
  const money = new Intl.NumberFormat('en-IN', {style: 'currency', currency: 'INR'});
  const hours = new Intl.NumberFormat('en-IN', {maximumFractionDigits: 1});
  const dayFormat = new Intl.DateTimeFormat('en-IN', {day: 'numeric', month: 'short', timeZone: 'UTC'});
  const monthFormat = new Intl.DateTimeFormat('en-IN', {month: 'long', year: 'numeric', timeZone: 'UTC'});
  const asDate = day => new Date(`${day}T00:00:00Z`);
  const shift = (day, amount) => new Date(asDate(day).getTime() + amount * 86400000).toISOString().slice(0, 10);
  const labelDay = day => dayFormat.format(asDate(day));
  const labelMonth = month => monthFormat.format(asDate(`${month}-01`));
  const display = (n, key) => !Number.isFinite(n) ? '—' : key === 'revenue' ? money.format(n) :
    key === 'watch_minutes' ? `${hours.format(n / 60)} h` : integer.format(n);
  const signed = n => Number.isFinite(n) ? `${n > 0 ? '+' : ''}${integer.format(n)}` : '—';
  const latestKey = rows => Object.keys(rows).sort().at(-1);
  const diff = (a, b) => Number.isFinite(a) && Number.isFinite(b) ? a - b : null;
  const net = row => diff(row?.gained, row?.lost);
  const fields = {
    views: 'Views', likes: 'Likes', comments: 'Comments', shares: 'Shares', saves: 'Saves',
    interactions: 'Interactions', profile_views: 'Profile visits', following: 'Following',
    gained: 'Subscribers gained', lost: 'Subscribers lost', watch_minutes: 'Watch time', revenue: 'Est. revenue',
    reach: 'Viewers', accounts_engaged: 'Accounts engaged', link_taps: 'Link taps',
  };
  const states = {analytics: 'Insights connected', counters: 'Counters connected', refreshing: 'Refreshing…',
    connecting: 'Waiting for consent…', waiting: 'Waiting for first refresh', needs_connection: 'Connection needed',
    unavailable: 'Refresh needs attention', paused: 'Disconnected'};
  const profiles = {cricket: 'Cricket', gaming: 'Gaming'};
  const periods = {monthly: 'Monthly', quarterly: 'Quarterly', annual: 'Annual'};
  let report;
  const query = new URLSearchParams(location.search);
  const directConnection = query.get('connect');
  const youtubeConsentLink = ['youtube-cricket', 'youtube-gaming'].includes(directConnection);
  let tab = youtubeConsentLink ? 'connections' : query.get('view') === 'analytics' ? 'analytics' : 'overview';
  let selected = 'youtube-cricket';
  let scope = 'all';
  let connectId;
  let expanded = false;
  let poll;
  let sequence = 0;
  let videoSequence = 0;

  function node(tag, text, className) {
    const el = document.createElement(tag);
    if (text !== undefined) el.textContent = text;
    if (className) el.className = className;
    return el;
  }

  function section(title, content, detail = '', className = '') {
    const block = node('section', undefined, `panel ${className}`);
    const head = node('div', undefined, 'section-head');
    head.append(node('h2', title));
    if (detail) head.append(node('span', detail, 'hint'));
    block.append(head, content);
    return block;
  }

  function action(label, fn, className) {
    const button = node('button', label, className);
    button.type = 'button';
    button.addEventListener('click', fn);
    return button;
  }

  function table(columns, rows, name) {
    const frame = node('div', undefined, 'table-wrap');
    frame.tabIndex = 0;
    frame.setAttribute('aria-label', name);
    const el = node('table');
    const row = el.createTHead().insertRow();
    for (const column of columns) {
      const heading = node('th', column);
      heading.scope = 'col';
      row.append(heading);
    }
    const body = el.createTBody();
    for (const cells of rows) {
      const item = body.insertRow();
      cells.forEach((cell, index) => {
        const entry = item.insertCell();
        entry.dataset.label = columns[index];
        entry.append(cell);
      });
    }
    frame.append(el);
    return frame;
  }

  function chart(points, metric, empty) {
    const content = node('div', undefined, 'chart');
    const available = points.filter(point => Number.isFinite(point.value));
    const plot = node('div', undefined, available.length ? 'plot' : 'plot plot-empty');
    if (!available.length) plot.append(node('p', empty, 'chart-empty'));
    else {
      const ceiling = Math.max(0, ...available.map(point => point.value));
      const floor = Math.min(0, ...available.map(point => point.value));
      const scale = ceiling - floor || 1;
      const baseline = -floor / scale * 100;
      plot.style.setProperty('--baseline', `${baseline}%`);
      const guides = node('span', undefined, 'plot-guides');
      guides.setAttribute('aria-hidden', 'true');
      plot.append(guides);
      const latest = available.at(-1);
      const readout = node('div', `${latest.label} · ${display(latest.value, metric)}`, 'hint chart-readout');
      for (const point of points) {
        const slot = node('span', undefined, 'bar-slot');
        const valid = Number.isFinite(point.value);
        const bar = node('span', undefined, valid ? 'bar' : 'bar missing');
        if (valid) {
          bar.style.height = `${Math.abs(point.value) / scale * 100}%`;
          bar.style.bottom = `${baseline + Math.min(0, point.value) / scale * 100}%`;
          if (point.value < 0) bar.classList.add('bar-negative');
          slot.tabIndex = 0;
        }
        slot.title = `${point.label} · ${valid ? display(point.value, metric) : 'No data'}`;
        slot.setAttribute('aria-label', slot.title);
        for (const event of ['pointerenter', 'focus', 'click']) {
          slot.addEventListener(event, () => { readout.textContent = slot.title; });
        }
        slot.append(bar);
        plot.append(slot);
      }
      content.append(readout);
    }
    const dates = node('div', undefined, 'plot-labels hint');
    dates.append(node('span', points[0]?.label), node('span', points.at(-1)?.label));
    content.append(plot, dates);
    return content;
  }

  function choose(next, account) {
    tab = next;
    if (account) selected = account;
    expanded = false;
    render();
    load();
  }

  function dayMetric(account, day, previous) {
    const observed = diff(account.snapshot[day]?.views, account.snapshot[previous]?.views);
    if (account.platform === 'youtube') {
      if (Number.isFinite(account.activity[day]?.views)) return {value: account.activity[day].views, type: 'Reported · Pacific'};
      if (Number.isFinite(observed)) return {value: observed, type: 'Between snapshots'};
      return {value: null, type: 'No day comparison'};
    }
    const sample = account.activity[day];
    return {value: sample?.views, type: sample ? `Across ${sample.tracked_reels} tracked Reels` : 'No day comparison'};
  }

  function overviewRows(accounts) {
    const yesterday = shift(report.today, -1);
    const prior = shift(yesterday, -1);
    return accounts.map(account => {
      const current = latestKey(account.snapshot);
      const snapshot = account.snapshot[current] || {};
      const before = account.snapshot[shift(report.today, -1)];
      const change = diff(account.snapshot[report.today]?.audience, before?.audience);
      const a = dayMetric(account, report.today, yesterday);
      const b = dayMetric(account, yesterday, prior);
      const lastInsights = account.browser_30d[latestKey(account.browser_30d)];
      const saved = account.platform === 'youtube' ?
        {value: snapshot.views, type: 'Channel lifetime'} : {value: lastInsights?.views, type: 'Rolling 30 days'};
      const name = node('div');
      name.append(action(account.name, () => {
        $('period').value = 'monthly';
        choose('reports', account.id);
      }, 'account-action account-name'), node('span', platformName(account), 'small'));
      const followers = node('div');
      followers.append(node('b', display(snapshot.audience), 'metric'), node('span', current ? labelDay(current) : 'No snapshot', 'small'));
      const delta = node('span', signed(change), change > 0 ? 'up' : change < 0 ? 'down' : 'blank');
      const cell = value => {
        const el = node('div', display(value.value));
        el.append(node('span', value.type, 'small'));
        return el;
      };
      return [name, followers, display(snapshot.following), delta, cell(b), cell(a), cell(saved)];
    });
  }

  function platformName(account) {
    return account.platform === 'youtube' ? 'YouTube' : 'Instagram';
  }

  function overview() {
    const stack = node('div', undefined, 'stack');
    for (const [profile, label] of Object.entries(profiles)) {
      if (scope !== 'all' && scope !== profile) continue;
      const accounts = report.accounts.filter(account => account.profile === profile);
      const columns = ['Account', 'Audience', 'Following', 'Audience change', 'Views yesterday', 'Views today', 'Saved views'];
      stack.append(section(label, table(columns, overviewRows(accounts), `${label} account overview`),
        'YouTube and Instagram', 'table pulse'));
    }
    stack.append(node('p', 'YouTube audience counts may be rounded. Instagram daily views track changes between snapshots of the same Reels.', 'hint'));
    return stack;
  }

  function comparison(items, ranked = false) {
    const list = node(ranked ? 'ol' : 'ul', undefined, ranked ? 'comparison ranking' : 'comparison');
    const ceiling = Math.max(1, ...items.map(item => item.value).filter(Number.isFinite));
    for (const [index, item] of items.entries()) {
      const row = node('li');
      if (item.platform === 'instagram') row.classList.add('instagram-series');
      const labels = node('div', undefined, 'comparison-label');
      const name = node('span', item.label);
      if (item.detail) name.append(node('span', item.detail, 'small'));
      if (ranked) labels.append(node('span', String(index + 1), 'rank'));
      labels.append(name, node('b', display(item.value)));
      row.append(labels);
      if (Number.isFinite(item.value)) {
        const track = node('div', undefined, 'comparison-track');
        const fill = node('span', undefined, 'comparison-fill');
        fill.style.width = `${item.value / ceiling * 100}%`;
        track.setAttribute('aria-hidden', 'true');
        track.append(fill);
        row.append(track);
      }
      list.append(row);
    }
    return list;
  }

  function accountSnapshot(account) {
    const day = latestKey(account.snapshot);
    const snapshot = account.snapshot[day] || {};
    const instagram = account.platform === 'instagram';
    const viewsDay = instagram ? latestKey(account.browser_30d) : day;
    const views = instagram ? account.browser_30d[viewsDay]?.views : snapshot.views;
    const strip = node('div', undefined, 'analytics-snapshot');
    const facts = [
      [instagram ? 'Followers' : 'Subscribers', snapshot.audience, day ? `Saved ${labelDay(day)}` : 'Awaiting a snapshot'],
      [instagram ? 'Views · last 30 days' : 'Channel views · lifetime', views,
        viewsDay ? `Saved ${labelDay(viewsDay)}` : 'Awaiting views data'],
      [instagram ? 'Following' : 'Videos', instagram ? snapshot.following : snapshot.posts, platformName(account)],
    ];
    for (const [label, value, note] of facts) {
      const item = node('div');
      item.append(node('span', label, 'hint'), node('strong', display(value)), node('span', note, 'small'));
      strip.append(item);
    }
    return strip;
  }

  function trendMetrics(account) {
    const metrics = [['audience', account.platform === 'youtube' ? 'Subscribers' : 'Followers', account.snapshot]];
    if (account.platform === 'youtube') {
      metrics.push(['views', 'Daily views', account.activity], ['watch_minutes', 'Daily watch time', account.activity],
        ['revenue', 'Daily estimated revenue', account.revenue]);
    } else {
      metrics.push(['following', 'Following', account.snapshot], ['views', 'Daily tracked Reel views', account.activity],
        ['rolling_views', '30-day Insights views', account.browser_30d]);
    }
    return metrics;
  }

  function analytics(account) {
    const metrics = trendMetrics(account);
    const previousMetric = $('metric').value;
    $('metric').replaceChildren(...metrics.map(([key, label]) => new Option(label, key)));
    if (metrics.some(([key]) => key === previousMetric)) $('metric').value = previousMetric;
    const [key, title, source] = metrics.find(([key]) => key === $('metric').value);
    const field = key === 'rolling_views' ? 'views' : key;
    const end = latestKey(source) || report.today;
    const points = Array.from({length: 30}, (_, index) => {
      const date = shift(end, index - 29);
      return {label: labelDay(date), value: source[date]?.[field]};
    });
    const basis = key === 'rolling_views' ? 'Each bar is a separate 30-day window' :
      source === account.snapshot ? 'Saved snapshots · IST' :
      account.platform === 'youtube' ? 'Reported daily activity · Pacific' : 'Observed daily change · IST';
    const samples = points.filter(point => Number.isFinite(point.value));
    let trendBody;
    if (samples.length >= 2) {
      trendBody = chart(points, field, '');
    } else {
      trendBody = node('div', undefined, 'trend-state');
      const observation = samples[0];
      trendBody.append(node('span', observation ? 'One recorded observation' : 'Waiting for data', 'hint'));
      if (observation) {
        trendBody.append(node('strong', display(observation.value, field)),
          node('span', `${observation.label} · A trend appears after the next dated reading.`, 'hint'));
      } else {
        trendBody.append(node('p', 'StoryLens will chart this metric when dated readings are available.', 'hint'));
      }
    }
    const trend = section(title, trendBody, basis, 'analytics-trend');

    const audience = ['cricket', 'gaming'].flatMap(profile => report.accounts.filter(item => item.profile === profile).map(item => {
      const day = latestKey(item.snapshot);
      return {label: item.name, detail: `${profiles[item.profile]} · ${platformName(item)}`,
        platform: item.platform, value: item.snapshot[day]?.audience};
    }));
    const audiencePanel = section('Audience by account', comparison(audience), 'Subscribers and followers', 'audience-panel');

    const top = Object.entries(account.content).map(([id, history]) => {
      const row = history[latestKey(history)];
      const label = row.title || `Video ${id}`;
      const detail = row.published ? labelDay(row.published.slice(0, 10)) : id;
      return {label, detail, value: row.views ?? row.grid_views};
    })
      .filter(row => Number.isFinite(row.value)).sort((a, b) => b.value - a.value).slice(0, 5);
    const contentPanel = section(account.platform === 'youtube' ? 'Most-viewed videos' : 'Most-viewed Reels',
      top.length ? comparison(top, true) : node('p', 'Content charts appear once view counts are available.', 'hint'),
      'Lifetime views · saved counters', 'ranking-panel');
    const surface = node('div', undefined, 'analytics-surface');
    const grid = node('div', undefined, 'analytics-grid');
    grid.append(audiencePanel, contentPanel);
    surface.append(accountSnapshot(account), grid, trend);
    return surface;
  }

  function daysFor(account, prefix) {
    return Object.entries(account.activity).filter(([day]) => day.startsWith(prefix));
  }

  function sum(rows, key) {
    const values = rows.map(([, row]) => row[key]).filter(Number.isFinite);
    return values.length ? values.reduce((a, b) => a + b, 0) : null;
  }

  function reportTotals(account, months) {
    const inPeriod = ([day]) => months.includes(day.slice(0, 7));
    const rows = Object.entries(account.activity).filter(inPeriod);
    const revenue = Object.entries(account.revenue).filter(inPeriod);
    const keys = account.platform === 'youtube' ? ['views', 'watch_minutes', 'likes', 'comments', 'shares', 'gained', 'lost', 'revenue'] : ['views'];
    const body = node('div', undefined, 'panel totals');
    for (const key of keys) {
      const box = node('div');
      box.append(node('span', account.platform === 'instagram' ? 'Tracked Reel views between snapshots' : fields[key], 'small'),
        node('b', display(sum(key === 'revenue' ? revenue : rows, key), key)));
      body.append(box);
    }
    return body;
  }

  function content(account, monthly) {
    const youtube = account.platform === 'youtube';
    const ids = monthly ? new Set([...Object.keys(account.video_activity), ...Object.keys(account.video_revenue)]) : new Set(Object.keys(account.content));
    const records = [...ids].map(id => {
      const snapshots = account.content[id] || {};
      const latest = snapshots[latestKey(snapshots)] || {};
      const days = [report.today, shift(report.today, -1)];
      return {name: latest.title || `Video ${id}`, published: latest.published, hasSnapshot: Boolean(latestKey(snapshots)), id,
        stats: monthly ? {...account.video_activity[id], ...account.video_revenue[id]} : {...latest, views: latest.views ?? latest.grid_views},
        daily: diff(snapshots[days[0]]?.[youtube ? 'views' : 'grid_views'], snapshots[days[1]]?.[youtube ? 'views' : 'grid_views'])};
    }).sort((a, b) => (b.stats.views ?? -1) - (a.stats.views ?? -1));
    const keys = youtube ? (monthly ? ['views', 'likes', 'comments', 'shares', 'watch_minutes', 'net', 'revenue'] :
      ['views', 'daily', 'likes', 'comments']) : ['views', 'daily', 'likes', 'comments', 'shares', 'saves', 'reach'];
    const columns = ['Content', ...keys.map(key => ({net: 'Net subs', daily: 'Views Δ', reach: 'Viewers'}[key] || fields[key]))];
    const rows = records.slice(0, expanded ? records.length : 8).map(row => {
      const title = node('div', undefined, 'media-name');
      if (youtube && row.hasSnapshot) title.append(action(row.name, () => showVideo(account, row), 'account-action'));
      else title.textContent = row.name;
      if (row.published) title.append(node('span', labelDay(row.published.slice(0, 10)), 'small'));
      return [title, ...keys.map(key => key === 'net' ? signed(net(row.stats)) : key === 'daily' ? signed(row.daily) : display(row.stats[key], key))];
    });
    const title = monthly ? 'Top videos this month' : youtube ? 'Latest available video counters' : 'Recent Instagram post counters';
    const body = rows.length ? table(columns, rows, title) : node('p', monthly ? 'No video report saved for this month. Refresh this account to request it.' :
      'Content appears after this account has successfully refreshed.', 'hint section-note');
    const panel = section(title, body, monthly ? 'Views and revenue rankings · up to 200 each' : 'Lifetime counters · Δ since yesterday’s snapshot', 'table');
    if (records.length > 8) {
      const controls = node('div', undefined, 'content-tools');
      controls.append(action(expanded ? 'Show fewer' : `Show all ${records.length}`, () => { expanded = !expanded; render(); }));
      panel.append(controls);
    }
    return panel;
  }

  async function showVideo(account, row) {
    const current = ++videoSequence;
    const dialog = $('video-dialog');
    const body = $('video-detail');
    $('video-title').textContent = row.name;
    body.replaceChildren(node('p', 'Loading this video’s reports…', 'hint'));
    if (!dialog.open) dialog.showModal();
    try {
      const response = await api(`video?${new URLSearchParams({account: account.id, id: row.id})}`);
      const data = await response.json();
      if (current !== videoSequence || !dialog.open) return;
      const groups = [
        ['Latest video counters', data.counter, ['views', 'likes', 'comments'], `Snapshot · ${labelDay(data.captured)} IST`],
        ['Lifetime Analytics', data.lifetime, ['views', 'watch_minutes', 'likes', 'comments', 'shares', 'gained', 'lost', 'revenue'],
          data.requested_through ? `Requested through ${labelDay(data.requested_through)} · reporting can lag` : 'YouTube Analytics'],
      ];
      body.replaceChildren(...groups.map(([title, values, keys, detail]) => {
        const totals = node('div', undefined, 'totals');
        for (const key of keys) {
          const cell = node('div');
          cell.append(node('span', fields[key], 'small'), node('b', display(values[key], key)));
          totals.append(cell);
        }
        return section(title, totals, detail);
      }));
      const points = Object.entries(data.daily).map(([day, values]) => ({label: labelDay(day), value: values.views}));
      body.append(section('Recent daily views', chart(points, 'views', 'YouTube has not supplied daily views for this video.'), 'Pacific reporting days'));
      for (const note of data.notes) body.append(node('p', note, 'hint'));
    } catch (error) {
      if (current === videoSequence && dialog.open) body.replaceChildren(node('p', error.message, 'hint'));
    }
  }

  function monthly(account) {
    const month = report.month;
    const next = new Date(Date.UTC(Number(month.slice(0, 4)), Number(month.slice(5)), 0)).getUTCDate();
    const points = Array.from({length: next}, (_, i) => {
      const day = `${month}-${String(i + 1).padStart(2, '0')}`;
      return {label: labelDay(day), value: account.activity[day]?.views};
    });
    const priorMonth = shift(`${month}-01`, -1).slice(0, 7);
    const rows = daysFor(account, month);
    const comparable = rows.filter(([day, row]) => Number.isFinite(row.views) &&
      Number.isFinite(account.activity[`${priorMonth}${day.slice(7)}`]?.views));
    const delta = comparable.length ? comparable.reduce((total, [day, row]) =>
      total + row.views - account.activity[`${priorMonth}${day.slice(7)}`].views, 0) : null;
    const stack = node('div', undefined, 'stack');
    stack.append(reportTotals(account, [month]));
    const charts = node('div', undefined, 'details-grid');
    const views = section('Daily views', chart(points, 'views', 'No daily activity reported for this month.'), `${rows.length} days returned`);
    if (Number.isFinite(delta)) views.append(node('p', `${signed(delta)} views across ${comparable.length} matching calendar days versus ${labelMonth(priorMonth)}.`, 'hint summary-note'));
    const yt = account.platform === 'youtube';
    charts.append(views);
    if (yt) {
      const watch = points.map((point, i) => ({...point, value: account.activity[`${month}-${String(i + 1).padStart(2, '0')}`]?.watch_minutes}));
      charts.append(section('Daily watch time', chart(watch, 'watch_minutes', 'No reported data for this metric.')));
    } else charts.append(rollingInsights(account, month));
    stack.append(charts);
    const days = Object.entries(account.snapshot).filter(([day]) => day.startsWith(month));
    const snapshotChart = days.map(([day, row]) => ({label: labelDay(day), value: row.audience}));
    const audience = section(yt ? 'Subscriber snapshots' : 'Follower snapshots', chart(snapshotChart, 'audience', 'Daily audience snapshots appear after the first refresh.'),
      yt ? 'Data API count may be rounded' : 'Daily local snapshots');
    stack.append(audience);
    stack.append(content(account, yt), ...(yt ? [content(account, false)] : []));
    return stack;
  }

  function rollingInsights(account, month) {
    const key = latestKey(Object.fromEntries(Object.entries(account.browser_30d).filter(([day]) => day.startsWith(month))));
    if (!key) return section('Instagram Insights · Last 30 days', node('p', 'No account Insights snapshot for this month yet.', 'hint'));
    const metrics = account.browser_30d[key];
    const totals = node('div', undefined, 'totals');
    for (const field of Object.keys(metrics)) {
      const cell = node('div');
      cell.append(node('span', fields[field], 'small'), node('b', display(metrics[field], field)));
      totals.append(cell);
    }
    return section('Instagram Insights · Last 30 days', totals, `Read in Chrome · ${labelDay(key)}`);
  }

  function reportMonths(year, quarter) {
    const first = quarter ? (Number(quarter) - 1) * 3 + 1 : 1;
    return Array.from({length: quarter ? 3 : 12}, (_, i) => `${year}-${String(first + i).padStart(2, '0')}`);
  }

  function periodSummary(account, quarter) {
    const months = reportMonths(report.year, quarter);
    const points = months.map(month => ({label: labelMonth(month).split(' ')[0].slice(0, 3), value: sum(daysFor(account, month), 'views')}));
    const rows = months.map(month => {
      const data = daysFor(account, month);
      const last = Object.entries(account.snapshot).filter(([date]) => date.startsWith(month)).at(-1)?.[1];
      const earned = Object.entries(account.revenue).filter(([date]) => date.startsWith(month));
      const yt = account.platform === 'youtube';
      return [labelMonth(month), display(data.length || null), display(sum(data, 'views')), display(last?.audience),
        ...(yt ? [signed(diff(sum(data, 'gained'), sum(data, 'lost'))), display(sum(data, 'watch_minutes'), 'watch_minutes'),
          display(sum(earned, 'revenue'), 'revenue')] : [display(last?.following)])];
    });
    const stack = node('div', undefined, 'stack');
    stack.append(reportTotals(account, months), section('Views by month', chart(points, 'views', 'No daily views for this period.')));
    const columns = ['Month', 'Days reported', account.platform === 'youtube' ? 'Views' : 'Tracked Reel views', 'Last audience snapshot', ...(account.platform === 'youtube' ?
      ['Net subscribers', 'Watch time', 'Est. revenue'] : ['Last following snapshot'])];
    stack.append(section('Monthly breakdown', table(columns, rows, 'Monthly breakdown'), 'Missing values are shown as dashes', 'table'));
    return stack;
  }

  function connections() {
    const list = node('div');
    for (const account of report.accounts) {
      const row = node('div', undefined, 'settings-row');
      const copy = node('div');
      copy.append(node('h3', `${account.name} · ${account.platform === 'youtube' ? 'YouTube' : 'Instagram'}`),
        node('p', states[account.state] || account.state, 'hint'));
      for (const note of account.notes) copy.append(node('p', note, 'hint'));
      if (account.notes.some(note => note.includes('accessNotConfigured'))) {
        const link = node('a', 'Enable YouTube Analytics API in Google Cloud ↗', 'hint');
        link.href = 'https://console.cloud.google.com/apis/library/youtubeanalytics.googleapis.com';
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        copy.append(link);
      }
      const actions = node('div', undefined, 'actions');
      const button = action(account.platform === 'youtube' ? 'Connect YouTube Analytics' : 'Read Instagram in Chrome', () => connect(account));
      button.disabled = ['connecting', 'refreshing'].includes(account.state);
      button.dataset.voiceLabel = button.textContent + ' for ' + account.name;
      button.dataset.voiceReview = '';
      actions.append(button);
      if (account.verified) actions.append(action('Remove local data', async () => {
        if (!window.confirm(`Remove local analytics and pause dashboard collection for ${account.name}? This removes saved StoryLens analytics only.`)) return;
        await update('disconnect', {account: account.id, confirm: true});
      }));
      row.append(copy, actions);
      list.append(row);
    }
    const info = node('p', undefined, 'hint summary-note');
    const terms = node('a', 'YouTube Terms of Service');
    terms.href = 'https://www.youtube.com/t/terms';
    terms.rel = 'noreferrer';
    info.append('Data is stored in this StoryLens installation. YouTube analytics use is subject to the ', terms, '.');
    list.append(info);
    return section('Account access', list, 'Analytics permissions are separate from publishing');
  }

  function render() {
    if (!report) return;
    const account = report.accounts.find(item => item.id === selected);
    const period = $('period').value;
    const quarter = $('quarter').value;
    const reports = tab === 'reports';
    const monthlyReport = reports && period === 'monthly';
    const quarterlyReport = reports && period === 'quarterly';
    const annualReport = reports && period === 'annual';
    const periodLabel = monthlyReport ? labelMonth(report.month) : quarterlyReport ? `Q${quarter} ${report.year}` : report.year;
    const titles = {overview: 'Overview', analytics: 'Analytics', reports: 'Reports', connections: 'Connections'};
    const summaries = {
      overview: `Audience and views · ${labelDay(report.today)} IST`,
      analytics: 'Compare account audiences, explore recent trends, and see which videos drew the most views.',
      reports: `${account.name} · ${periods[period]} · ${periodLabel} · saved data`,
      connections: 'Connect the exact accounts to load private insights.',
    };
    $('title').textContent = titles[tab];
    $('summary').textContent = summaries[tab];
    $('overview-scope').hidden = tab !== 'overview';
    $('controls').hidden = !reports && tab !== 'analytics';
    $('period-control').hidden = !reports;
    $('month-control').hidden = !monthlyReport;
    $('quarter-control').hidden = !quarterlyReport;
    $('year-control').hidden = !quarterlyReport && !annualReport;
    $('download').hidden = !annualReport;
    $('metric-control').hidden = tab !== 'analytics';
    $('account').value = selected;
    $('refresh').textContent = monthlyReport ? 'Refresh this month' :
      tab === 'overview' && scope !== 'all' ? `Refresh ${profiles[scope]}` : 'Refresh accounts';
    $('refresh').disabled = report.accounts.some(item => item.state === 'refreshing');
    for (const button of document.querySelectorAll('[data-tab]')) {
      if (button.dataset.tab === tab) button.setAttribute('aria-current', 'page');
      else button.removeAttribute('aria-current');
    }
    const views = {overview, analytics: () => analytics(account), connections,
      reports: () => monthlyReport ? monthly(account) : periodSummary(account, quarterlyReport ? quarter : null)};
    $('dashboard').replaceChildren(views[tab]());
  }

  async function api(path, body) {
    const response = await fetch(`/api/analytics/${path}`, {headers, method: body ? 'POST' : 'GET',
      ...(body ? {body: JSON.stringify(body)} : {})});
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.error || 'Analytics is unavailable. Try refreshing.');
    }
    return response;
  }

  function notice(message) {
    $('notice').textContent = message;
    $('notice').hidden = !message;
  }

  function dateQuery() {
    const monthlyReport = tab === 'reports' && $('period').value === 'monthly';
    const year = (tab !== 'reports' ? today.slice(0, 4) :
      monthlyReport ? $('month').value.slice(0, 4) : $('year').value) || today.slice(0, 4);
    const month = monthlyReport ? $('month').value || today.slice(0, 7) : `${year}-01`;
    return new URLSearchParams({year, month});
  }

  async function load() {
    const current = ++sequence;
    clearTimeout(poll);
    try {
      const response = await api(`dashboard?${dateQuery()}`);
      const incoming = await response.json();
      if (current !== sequence) return;
      const firstLoad = !report;
      if (firstLoad) {
        $('account').replaceChildren(...incoming.accounts.map(item => new Option(item.name, item.id)));
      }
      report = incoming;
      render();
      if (firstLoad && youtubeConsentLink) {
        connect(report.accounts.find(item => item.id === directConnection));
      }
      poll = setTimeout(load, report.accounts.some(item => ['refreshing', 'connecting'].includes(item.state)) ? 2200 : 60000);
    } catch (error) {
      notice(error.message);
    }
  }

  async function update(route, data) {
    notice('');
    try {
      await api(route, data);
      await load();
      return true;
    } catch (error) {
      notice(error.message);
      return false;
    }
  }

  function connect(account) {
    connectId = account.id;
    const youtube = account.platform === 'youtube';
    $('connect-title').textContent = `Connect ${account.name}`;
    const channel = account.id === 'youtube-gaming' ? 'Vineet Kumar (@vineet_91)' : 'Fantasy Legends';
    $('connect-copy').textContent = youtube ? `Choose ${channel} when Google asks for the channel, then allow read-only Analytics. Existing publishing access is separate.` :
      'StoryLens reads this account through the existing signed-in Chrome connection. Keep the paired Chrome profile running.';
    $('money-label').hidden = !youtube;
    $('instagram-help').hidden = youtube;
    $('monetary').checked = account.id === 'youtube-cricket';
    $('connect-dialog').showModal();
  }

  const today = new Intl.DateTimeFormat('sv-SE', {timeZone: 'Asia/Kolkata'}).format(new Date());
  $('year').value = today.slice(0, 4);
  $('year').max = $('year').value;
  $('month').value = today.slice(0, 7);
  $('month').max = $('month').value;
  $('quarter').value = String(Math.ceil(Number(today.slice(5, 7)) / 3));
  for (const button of document.querySelectorAll('[data-tab]')) button.addEventListener('click', () => choose(button.dataset.tab));
  const scopeButtons = document.querySelectorAll('[data-scope]');
  for (const button of scopeButtons) button.addEventListener('click', () => {
    scope = button.dataset.scope;
    for (const option of scopeButtons) option.setAttribute('aria-pressed', String(option === button));
    render();
  });
  $('account').addEventListener('change', () => { selected = $('account').value; expanded = false; render(); });
  for (const id of ['month', 'year']) $(id).addEventListener('change', () => { if ($(id).checkValidity() && $(id).value) load(); });
  $('period').addEventListener('change', () => { expanded = false; render(); load(); });
  $('quarter').addEventListener('change', render);
  $('metric').addEventListener('change', render);
  $('refresh').addEventListener('click', async () => {
    $('refresh').disabled = true;
    const monthlyReport = tab === 'reports' && $('period').value === 'monthly';
    if (tab === 'overview' && scope !== 'all') {
      notice('');
      try {
        const accounts = report.accounts.filter(account => account.profile === scope);
        const results = await Promise.allSettled(accounts.map(account => api('refresh', {account: account.id})));
        await load();
        const failure = results.find(result => result.status === 'rejected');
        if (failure) notice(failure.reason.message);
      } finally {
        $('refresh').disabled = report.accounts.some(account => account.state === 'refreshing');
      }
      return;
    }
    const ok = await update('refresh', monthlyReport ? {account: selected, month: $('month').value} : {});
    if (!ok) $('refresh').disabled = false;
  });
  $('download').addEventListener('click', async () => {
    try {
      const response = await api(`export?${dateQuery()}`);
      const url = URL.createObjectURL(await response.blob());
      const link = node('a');
      link.href = url;
      link.download = `StoryLens-Analytics-${$('year').value}.csv`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) { notice(error.message); }
  });
  $('cancel-connect').addEventListener('click', () => $('connect-dialog').close());
  $('close-video').addEventListener('click', () => $('video-dialog').close());
  $('connect-form').addEventListener('submit', async event => {
    event.preventDefault();
    const youtube = connectId.startsWith('youtube');
    const data = {account: connectId, ...(youtube ? {monetary: $('monetary').checked} : {})};
    $('connect-dialog').close();
    const connected = await update(youtube ? 'connect-youtube' : 'connect-instagram', data);
    if (youtube && connected) notice('Complete the account consent in your browser.');
  });
  load();
})();
