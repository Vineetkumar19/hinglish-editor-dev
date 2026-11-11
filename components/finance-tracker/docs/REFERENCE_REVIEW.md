# Selected reference implementations

Read on 31 October 2026; architectural patterns independently implemented, no upstream source copied.

## Wealthfolio

Repository https://github.com/wealthfolio/wealthfolio
Inspected commit bb41853d8f24dab9d0607fde3d5e627e210dd979.
Rust/Tauri core, React frontend, SQLite storage; AGPL-3.0.
Income source: `crates/core/src/portfolio/income/income_service.rs` and income UI directory. Service reads income activities through a repository, uses Decimal arithmetic, user timezone, scoped account filters and receipt-date currency conversion. Missing prior-year baseline returns no percentage rather than a fabricated growth value.
Adopt: dated receipt ledger, gross/tax/net, period/account grouping, absent baseline as null. Scope is dividend and interest tracking only.

## Portfolio Performance

Repository https://github.com/portfolio-performance/portfolio
Inspected tree commit a0b050cd6b338f54b31e99ad2906f17cb6fa2b42.
Java/Eclipse desktop; EPL-1.0.
Model sources: `name.abuchen.portfolio/src/name/abuchen/portfolio/model/Taxonomy.java`, `Dashboard.java`; configurable dashboard widgets in the UI module. Manuals: https://help.portfolio-performance.info/en/reference/view/reports/performance/dashboard/ and https://help.portfolio-performance.info/en/how-to/benchmarking/ .
Adopt: classifications independent from custody accounts, configurable widgets with persisted settings, same-period benchmark normalization, explicit volatility/drawdown definitions and reporting period. Implement our own smaller INR-focused analytics, not the entire PP accounting/tax feature set.

## Ghostfolio

Repository https://github.com/ghostfolio/ghostfolio
Inspected commit 9bae71c3dad7e8c7681ba01b01b765ab164c61d4.
Angular client, NestJS/Prisma/PostgreSQL backend with Redis; AGPL-3.0.
Source: `apps/api/src/app/endpoints/watchlist/watchlist.service.ts`, `apps/api/src/assets/site.webmanifest`.
Watchlist identifies assets by provider+symbol, resolves shared asset metadata, reuses data gathering and quote services, and attaches/detaches the watch reference independently from owned positions.
Adopt: watch records outside the ledger, shared price cache, responsive navigation and app manifest. No dependency on Ghostfolio's hosted service or premium feeds.

## Runtime references

https://nodejs.org/docs/latest-v24.x/api/sqlite.html
https://vite.dev/guide/
https://mikemcl.github.io/decimal.js/
https://docs.ollama.com/api/chat
https://www.mfapi.in/docs/

## Visual direction

Achromatic ledger, seed 127511226. Open-plane labelled sidebar, blue-grey paper ground, local Geist font, one blue data series, restrained flat surfaces. Main question: what is my wealth worth, and how current is that estimate? Signature: valuation coverage strip separating market observations, manual balances and estimates. No redraws. No fictional real-user holdings.
