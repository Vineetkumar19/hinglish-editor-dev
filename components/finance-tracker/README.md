# Finance Tracker

A personal wealth ledger that runs on your laptop. React/TypeScript → Node/Express → SQLite. Decimal arithmetic handles the ledger; Ollama explains recorded facts without changing records.

## Open it

Double-click **Start Finance Tracker.vbs** in `D:\Investment` for a hidden launch, or run:

```powershell
node server/launch.mjs
```

Open **http://127.0.0.1:4310**. The Node launcher avoids the Windows PowerShell script-policy failure observed on this laptop. It starts a hidden local server and opens your browser. Local summaries require Ollama to be running independently. The owner database starts empty; the demonstration is separate.

Manual setup (Node 24+):

```powershell
npm ci
npm run build
npm start
```

The UI is a compiled production build. After changing frontend code, run `npm run build` and reload. Restart the server after backend changes. `npm run demo` serves a clearly labelled, independent demonstration workspace at port 4312.

## What is implemented

- Multi-platform holdings: stocks, funds, ETFs, bonds, gold/silver/copper and other schemes. Record opening quantities/cost, purchases, sales and splits. Filter by category, account name or classification.
- Income: dividend/interest receipts, gross/tax/net amounts, monthly history, optional credit to a bank balance without double-counting income.
- Bank balances: confirmed or conservative assumptions, dated opening balance and derived linked movements. Reconcile using a later date after recorded movements.
- FDs: simple or monthly/quarterly/yearly compounding; cumulative or paid-out interest; accrual capped at maturity. Enter the deposit separately from the bank's available cash.
- Assets: resale estimates plus automatic public listing discovery and INR prices from accessible structured product/vehicle pages. Retail and future estimates remain separate from net worth. Included components do not count twice.
- Cards: limit, outstanding, statement amount, actual due date, issuer-sourced benefits/published rates, in-app reminders and recorded payments. A payment reduces cash and debt equally. Recording a payment never sends money. Use a new as-of date after previous payments when entering the next statement.
- Classifications: user-defined dimensions and overlapping labels, independent of broker. Example: `Sector: Technology, Goal: Long term`.
- Analysis: cash-flow-adjusted return, daily-observation P&L, volatility, maximum drawdown/duration, and benchmark on common dates. Missing history shows no fabricated metric.
- Dashboard: hide and reorder sections; settings survive reloads. Daily net-worth snapshots preserve what was recorded at the time.
- Watchlist: shared quote cache, excluded from portfolio totals.
- News: public Google News RSS headlines appear automatically for active holdings, watchlist entries and personal-asset model names, refresh every 30 minutes while running, and retain cached stories on partial failures. Optional questions use local, read-only Ollama; no question is needed to load news.
- Glass desktop/tablet/mobile interface; JSON export, recoverable deletion in Settings, and optional authenticated LAN mode.
- Safe edits: duplicate submissions, stale-tab edits, overselling and negative recorded cash are rejected. Failed forms preserve input; unsaved edits have explicit discard controls.

See [the end-to-end audit](docs/E2E_AUDIT_20261104.md) for 74 regression checks, actual UI workflows and remaining source limitations.

## Add your real data

1. Add bank/broker accounts in **Cash & deposits**. A broker account can start with zero uninvested cash.
2. Add each holding with actual units, total cost and opening date. Enter its name, click **Find investment**, and select the exact exchange symbol or AMFI scheme. Check fund plan and growth/IDCW option carefully.
3. Saving starts quote and news retrieval automatically. Source dates remain visible; failed sources leave values unknown or retain older observations. **Refresh prices** remains available.
4. Enter digital-gold provider **sell** quotes and other unsupported instruments as dated manual prices. Public spot prices are not guaranteed redemption values.
5. Add FDs, resale assets and card statements. Bank balances must exclude money already held in a separately recorded investment/FD.

`Opening / fallback unit price` of 0 means unknown. Such holdings show a partial-valuation warning and are excluded from totals until priced. Manual observations remain explicitly marked. A later manual observation can take precedence over an older provider quote.

## Sources and local AI

MFapi with AMFI fallback supplies fund NAVs. Yahoo's unofficial chart endpoint supplies equity/ETF/index observations. No brokerage login or paid key is required. These public services have no lifetime availability guarantee; failed refreshes preserve previous observations. Use **Enter prices** to record dated prices if a source stops working.

Selected model: **`qwen3.5:9b-q4_K_M`**, served by Ollama on `127.0.0.1:11434`. This is a sensible starting size for 12 GB VRAM; context is limited to 8,192 tokens. The app does not download models automatically or use a cloud fallback.

```powershell
ollama pull qwen3.5:9b-q4_K_M
```

Choose an installed model in Settings. The model receives current ledger balances, holdings, cards, deposits, asset estimates and relevant retrieved source facts/headlines within a bounded context; calculations and prices never depend on its output. Only public instrument/model/card names, symbols and selected public URLs go to external sources, not balances, quantities or card digits. No fine-tuning was performed: changing facts are retrieved and timestamped.

## Daily operation

The server checks every minute and catches up eligible jobs on startup: **16:00, 18:00 and 23:15 IST**. The final run accommodates later fund NAV publication. Actual source dates are always displayed; 16:00 does not guarantee every final price/NAV is available.

The browser can be closed while the server continues. For Windows login startup and standalone refresh tasks, run:

```powershell
.\scripts\Install-Schedule.ps1
```

This creates two named current-user tasks. **They were installed and checked on this laptop on 31 October 2026.** Both launch hidden. The server task was recovered and live-checked on 4 November 2026; it now retries failed launches up to three times. The script requires Windows India Standard Time and does not change firewall rules. Tasks run while you are signed in, catch missed starts, and cannot run on a powered-off laptop. OS task installation is separate from the in-process scheduler. Reminders in this version are **in-app**, not Windows push notifications or SMS.

## Mobile access and storage

Default access stays on `127.0.0.1`. Responsive layout does not by itself make the laptop reachable from a phone. Optional `scripts/Start-LAN.ps1` starts a second authenticated listener on port 4313 using a token you enter privately. Use a trusted private network; HTTP transport is not encrypted. No firewall rule is automatically opened. Real-phone connectivity depends on your network and is not implied by responsive browser validation.

Your ledger is in `data/daybook.sqlite`, with WAL sidecars while running. Do not copy only the `.sqlite` file while writes are active. Export JSON in Settings, or stop the server before copying the whole `data` directory. Restore a JSON export into a **new** database with `node server/restore.mjs backup.json data/restored.sqlite`; start the server with `DAYBOOK_DB` pointing at that file. Existing files are never overwritten by the restore command. Keep backups private. Files are not application-encrypted; OS disk protection remains useful. No full card numbers, PINs or CVVs are stored.

## Current limits

- Product search is best-effort. DuckDuckGo had a live outage during validation; Bing sometimes returned unrelated results. Successful discoveries are cached, linked pages are fetched afresh, and unverified prices are never guessed. Amazon/Flipkart product links were found; verified prices came from accessible retailer pages, not guaranteed Amazon/Flipkart extraction.
- Published card terms are not personalized APRs or statement access. Exact dues/dates must be entered from the actual statement. Unsupported issuers or inaccessible pages show partial results.
- Provider-specific digital-gold redemption, individual bonds and arbitrary scheme feeds are manual. No automatic bank or broker reconciliation.
- News coverage is best-effort, not a complete exchange announcement/results calendar. Dedicated FD policy feeds and event calendars are not yet implemented.
- Performance uses an end-of-period cash-flow convention and recorded income; the benchmark is a price index, not a total-return index. Unrecorded corporate actions can distort returns. Weighted-average book cost is not an Indian capital-gains tax report.
- FD estimates do not model every bank's day-count convention, premature penalties or tax. Matured deposits remain recorded until you reconcile them.
- JSON restore UI, guaranteed arbitrary-retailer coverage, OS push notifications and real-phone LAN validation are not included in this first version.

## Evidence and design

- [Architecture](docs/ARCHITECTURE.md)
- [Reviewed source projects and adopted patterns](docs/REFERENCE_REVIEW.md)
- [Validation record](docs/VALIDATION.md)

Run `npm test` for accounting/API checks and `npm run build` for TypeScript and production bundling. The validation record separately identifies workflows verified in the actual running application.

We independently implemented selected ideas from Wealthfolio, Portfolio Performance and Ghostfolio; their application source was not copied. Third-party dependencies retain their own licenses.
