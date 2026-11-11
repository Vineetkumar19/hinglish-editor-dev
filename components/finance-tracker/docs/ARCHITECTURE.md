# Finance Tracker architecture

Decision date: 31 October 2026. Local-only Windows application, INR base currency, Asia/Kolkata schedules. No trading, order execution, paid data dependency, cloud AI, budgeting, retirement planning or automatic broker login in this scope.

## Accepted scope

Original: manually maintained multi-platform stocks, funds, bonds, ETFs and metals; bank balances; contract-based FDs; other schemes; daily valuations and history; holding-related news; personal resale assets with product links and separately labelled future estimates; credit-card limits, actual statement due dates, benefits and reminders; local AI.

Selected additions ONLY: dividend/interest income; custom classifications; benchmark comparisons; risk measurements; configurable dashboard; watchlist; mobile-friendly access.

## Boundaries

React/TypeScript browser UI -> same-origin Node/Express API -> SQLite repository -> deterministic valuation/analytics services.

Scheduled worker -> public price/news adapters -> validate -> persist dated observations -> create/revise dated snapshot. Local Ollama consumes a bounded read-only summary; it never owns calculations, scheduling, account credentials or database writes.

One application and one database. Node 24 is available on the owner's laptop and provides SQLite without another database installation. Decimal.js handles money and quantities; floating-point is used only for statistical ratios and chart coordinates. React/Vite builds static files served by the same local server. No third-party fonts or analytics at runtime.

## Storage

- Typed records: accounts, positions (opening quantities/cost), investment transactions, income receipts, deposits, personal assets, cards, watchlist, news subscriptions. Records carry immutable IDs and validated JSON fields; SQLite transactions protect multi-record updates.
- Prices: instrument/provider key, applicable date, value, quote type, source URL, fetched time. Unique key prevents duplicate quotes. Manual observations remain distinguished from automatic feeds.
- Snapshots: date, invested value, net worth, valuation coverage and per-position values. Snapshots are not an inferred historical portfolio before opening data exists.
- Settings: custom classification definitions/labels, selected benchmark, dashboard widget order/visibility, model, scheduler preferences.
- Job history, news deduplication and audit log persist across restarts.

Opening positions support an as-of date and actual units. Purchases, sales and splits update derived quantity and weighted-average book cost without rewriting opening entries. Security identity uses provider plus symbol/scheme code, with optional ISIN. The same security can be held in several accounts; its price is fetched once. Watchlist references never count in net worth.

## Accounting rules

Net worth = investments + confirmed/assumed cash + accrued FD value + current personal resale estimates - outstanding card/other debt. Credit limits, retail listings and future resale scenarios are excluded. Asset components must not be counted again inside a parent asset.

Income receipts store gross, tax withheld, net and receipt date; dividend and interest reports aggregate by month/account/instrument. Recording a receipt can credit a chosen bank balance atomically, but never both credit cash and add the same receipt again to net worth. FD accrued interest is shown separately from received income. Paid-out FD interest is not capitalized.

FD estimate: principal * (1 + rate / compounding frequency)^(frequency * elapsed years), capped at contractual maturity; simple-interest and payout modes explicit. These are estimates, not bank redemption guarantees.

Market profit is not net-worth change. Purchases, sales, deposits and withdrawals are cash flows. Risk and benchmark analysis use a cash-flow-adjusted investment return series with common observation dates, not unadjusted total net worth. No numeric performance before sufficient, complete priced history exists. Report sample count, period and limitations. Annualized volatility requires 20 observed daily returns; maximum drawdown requires 2 returns. Benchmark indexed to 100 on the same starting date; distinguish price-return benchmark from total-return portfolio. Manual benchmark history import is available when online data is unavailable.

## Sources and freshness

- MFapi scheme history/latest NAV and AMFI NAV bulk file fallback; exact scheme code/name/plan required.
- Yahoo chart endpoint as an explicitly unofficial personal-use stock/ETF/benchmark adapter; preserve the original source and warn on unavailable access. Adapter can be replaced by official exchange bhavcopy imports or free broker data later.
- Manual dated prices for metal provider sell quotes, bonds and other schemes. Never represent spot gold as the exact Paytm/Jar payout.
- Public RSS announcements/news, matched against position/watchlist names and configured keywords; retain publisher/link/date. No claim of complete news coverage.
- Product URLs with exact model identity and manual observed retail price initially. Automated arbitrary retailer scraping is not a dependency and must never be presented as working without a supported connector.
- Price failure leaves last good observation intact. Stale/manual/estimated and mixed-date coverage visible. No zero substitution, no made-up history, no LLM-generated quotes.

## Scheduling

Default daily IST jobs: 16:00 first refresh, 18:00 retry, 23:15 NAV refresh. A daily reminder pass uses actual card due dates (7, 3, 1 days and overdue) with persisted per-card/per-due-date deduplication. Server checks jobs on startup and periodically. Windows Task Scheduler can start the app at login and run catch-up refreshes while UI is closed; tasks are installed explicitly via a supplied script. Powered-off devices cannot run. Run logs show partial failures. Exchange holidays/weekends affect freshness; report the source date without silently claiming today's close.

## Local security and mobile

Default bind 127.0.0.1; same-origin APIs, strict mutation content type/origin checks, no external scripts. User records never leave the machine except a requested backup. Market queries reveal instrument symbols, never quantities/account amounts. Ollama endpoint fixed to loopback; no cloud fallback. No card CVV/PIN/full-number fields. Sensitive files ignored by Git.

Responsive UI works at 390/768/1440 widths. Optional LAN mode requires an access token and explicit launch configuration; never silently open a firewall. Mobile access requires the laptop to be running and reachable. Do not claim real-phone/LAN verification based only on responsive browser testing.

## Validation gates

Unit/integration: decimal quantities, sale/split cost basis, FD maturity/payout, income tax/net, asset/debt totals, card payment cash/debt invariance, duplicate refreshes, failed sources preserving prices, cash-flow-neutral returns, common benchmark dates, insufficient-history suppression.

Real browser workflows against running backend: first-run empty state; add accounts/holdings; change prices; log income; save classification; add watchlist; add FD/assets/cards; record payment; customize dashboard and reload; fetch a real public fund quote; inspect news and local model status; desktop/mobile navigation and screenshots. Test/demo database isolated from owner's empty database. Synthetic records always visibly labelled and never mixed with user data.

## Delivery honesty

Application should expose working manual fallbacks for sources without stable access. No installed model, successful automatic retail scrape, installed schedule, real-phone access or tax-grade performance is claimed without evidence. Validation report tracks exact passes and remaining gaps.


## 4 November 2026: automatic research and startup

Record save/state polling → bounded per-store enrichment queue → quote adapters or public card/product discovery → persisted enrichment status/source facts → React polling. New quotes are fetched immediately; scheduled market refresh remains separate. `enrichment` is an operational SQLite cache, not part of financial truth. Discovery uses public search with a disk cache of successful matches, then fresh page retrieval and INR JSON-LD parsing. Search outages and unavailable pages remain explicit.

News follows investments/watchlist/assets independently of model questions. Exact product relevance and dated-headline deduplication protect the feed. The local assistant receives computed current balances plus relevant source observations within a bounded context, never write access. No training or cloud fallback is involved.

`Start Finance Tracker.vbs` starts `server/launch.mjs` hidden. It health-checks, starts a detached local server, and opens the default browser. Local summaries connect to an independently running Ollama server. This avoids this laptop's blocked Windows PowerShell `.ps1` path without changing policy. See E2E_AUDIT_20261104.md for actual live coverage and public-source limits.
