'use strict';

const month = document.querySelector('#month');
const currentMonth = new Intl.DateTimeFormat('sv-SE', {timeZone: 'Asia/Kolkata'}).format(new Date()).slice(0, 7);
month.value = currentMonth;
month.max = currentMonth;
const currency = new Intl.NumberFormat('en-IN', {style: 'currency', currency: 'INR'});
const format = value => currency.format(value);
const status = name => document.querySelector(`#${name}-status`);
const requests = new Map();

function values(id, entries) {
  const list = document.getElementById(id);
  list.replaceChildren(...entries.map(([label, value, tone = '']) => {
    const item = document.createElement('div');
    const term = document.createElement('dt');
    const amount = document.createElement('dd');
    term.textContent = label;
    amount.textContent = value;
    amount.className = tone;
    item.append(term, amount);
    return item;
  }));
}

function showPocket(data) {
  values('pocket-values', [
    ['Money in', format(data.moneyIn / 100), 'amount-positive'],
    ['Money out', format(data.moneyOut / 100), 'amount-negative'],
    ['Monthly recurring', format(data.recurring / 100)],
    ['Monthly budget', data.budget ? format(data.budget / 100) : 'Not set'],
  ]);
  status('pocket').textContent = 'Phone connected';
  document.getElementById('pocket-summary').hidden = false;
}

function showFinanceTracker(data) {
  const {totals, coverage} = data;
  values('finance-tracker-values', [
    ['Recorded net worth', format(totals.netWorth), 'amount-positive'],
    ['Investments', format(totals.investment), 'amount-positive'],
    ['Cash and deposits', format(totals.cashAndDeposits)], ['Personal assets', format(totals.assets)],
    ['Outstanding debt', format(totals.debt), 'amount-negative'],
  ]);
  const prices = [
    coverage.missing ? `${coverage.missing} missing prices` : '',
    coverage.stale ? `${coverage.stale} stale prices` : '',
  ].filter(Boolean);
  status('finance-tracker').textContent = [`As of ${data.date}`, ...prices].join(' · ');
  document.getElementById('finance-tracker-values').hidden = false;
}

async function load(name, path, render, unavailable, panel, timeout) {
  requests.get(name)?.abort();
  const controller = new AbortController();
  requests.set(name, controller);
  const node = document.getElementById(panel);
  node.hidden = true;
  status(name).textContent = 'Refreshing…';
  try {
    const response = await fetch(path, {
      cache: 'no-store', signal: AbortSignal.any([controller.signal, AbortSignal.timeout(timeout)]),
      headers: {'X-StoryLens-Finance': '1'},
    });
    if (!response.ok) throw new Error('Source unavailable');
    const data = await response.json();
    if (requests.get(name) === controller) render(data);
  } catch {
    if (requests.get(name) === controller) {
      node.hidden = true;
      node.querySelectorAll('dl').forEach(element => element.replaceChildren());
      if (node.matches('dl')) node.replaceChildren();
      status(name).textContent = unavailable;
    }
  } finally {
    if (requests.get(name) === controller) requests.delete(name);
  }
}

function refreshPocket() {
  if (!month.value) month.value = currentMonth;
  load('pocket', `/api/pocket?month=${encodeURIComponent(month.value)}`, showPocket,
    'Phone ledger unavailable. Open Pocket Tracker to check pairing, then refresh here.', 'pocket-summary', 72000);
}

function refresh() {
  refreshPocket();
  load('finance-tracker', '/api/finance-tracker', showFinanceTracker,
    'Finance Tracker unavailable. Start Finance Tracker, then refresh here.', 'finance-tracker-values', 6000);
}

document.querySelector('#refresh').addEventListener('click', refresh);
month.addEventListener('change', refreshPocket);

window.addEventListener('message', event => {
  // Expose the two read-only summary controls to the StoryLens host.
  if (event.source !== window.top || event.source === window ||
      !['http://127.0.0.1:8765', 'http://localhost:8765'].includes(event.origin)) return;
  const { financeVoice, operation, value } = event.data || {};
  if (typeof financeVoice !== 'string' || !/^[a-f0-9-]{36}$/i.test(financeVoice)) return;
  let ok = false;
  if (operation === 'refresh') {
    refresh();
    ok = true;
  } else if (operation === 'month' && typeof value === 'string' && /^\d{4}-(0[1-9]|1[0-2])$/.test(value)) {
    month.value = value;
    ok = month.value === value;
    if (ok) refreshPocket();
  }
  event.source.postMessage({ financeVoiceResult: financeVoice, ok }, event.origin);
});
refresh();

