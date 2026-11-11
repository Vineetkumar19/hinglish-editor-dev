# Latest audit

The 31 October glass/news/edge-case revision is recorded in [EDGE_CASE_AUDIT.md](EDGE_CASE_AUDIT.md), with 62 passing regression checks and new live UI evidence. The earlier implementation validation below is retained as history; its screenshots and counts describe the previous styling.

# Validation — 31 October 2026

Owner ledger: `data/daybook.sqlite`, no invented holdings or accounts. UI workflow data lives only in the labelled `test-results/browser-demo.sqlite` workspace (port 4312). Owner server uses port 4310.

## Automated checks

`npm test`: **14 passing** Node accounting/API tests. Covers exact decimal units, weighted-average disposal cost, split handling, same-day transaction ordering, historical price selection, missing/invalid observations, duplicate price updates, income gross/tax/net, card cash/debt invariance, asset component exclusion, FD maturity/payout, watchlist exclusion, flow-neutral returns, dividend-adjusted returns, common-date benchmark, volatility/drawdown sufficiency, offline source fallback, reference protection, rollback of an invalid deletion, new statement reconciliation, export and cross-origin write rejection.

`npm run build`: TypeScript and Vite production build passed.

Live JSON export → new SQLite restore → portfolio totals: **identical**. Both card payments restored. Restoring again to the existing file was rejected. Original database was not modified.

## Actual browser workflows

Performed through the running React interface with its actual backend, not mocked network responses:

| Workflow | Observed result |
|---|---|
| Empty workspace → add bank | ₹1,00,000 balance and net worth |
| Add holding, 10 units, ₹10,000 cost, ₹1,100 unit price | ₹11,000 market value, ₹1,000 unrealized gain; classification tags visible |
| Dividend gross ₹500, tax ₹50, credit bank | ₹450 net receipt; cash ₹1,00,450 |
| Card limit ₹1,00,000, debt ₹10,000 | ₹90,000 available; net worth ₹1,01,450; limit excluded |
| Edit actual due date | 3 November persisted after editing another field and saving |
| Record ₹5,000 payment | Cash ₹95,450, debt ₹5,000; net worth unchanged |
| Mobile reminder | Correct remaining ₹5,000 and 3 November due date |
| Pay remaining ₹5,000 on mobile | Debt zero, cash ₹90,450; no unread reminder |
| FD ₹1,00,000 at 8% quarterly, one year | ₹1,08,243.22; stopped accruing after 1 January maturity |
| Asset resale ₹1,00,000; retail ₹3,50,000; future ₹50,000 | Only ₹1,00,000 included in wealth |
| Add Infosys to watchlist, then Refresh prices | ₹1,146.50 dated 29 October; no contribution to net worth |
| Add 30 dated synthetic prices through UI | 30 return observations, 14.50% income-inclusive return, 36.49% annualized volatility, -7.41% max drawdown; synthetic series visibly labelled by workspace |
| Benchmark | Nifty 50 and synthetic portfolio drawn on common observed dates; common-date range shown |
| Classification | Sector: Technology and Strategy: Long term each show ₹11,000; overlap warning present |
| Dashboard | Hide Income, move Allocation above History, reload: changes persisted |
| Mobile | Open menu, navigate to cards, expand key benefits, view notification, fill payment and save successfully |
| News | Dated Infosys headlines returned with original outbound article links |
| Mutual-fund watchlist | MFapi scheme 119551 refreshed through the UI to ₹106.63, dated 29 October; excluded from wealth |

The complete demo portfolio after two payments has net worth **₹3,09,693.22**: cash ₹90,450 + investments ₹11,000 + FD ₹1,08,243.22 + resale asset ₹1,00,000, less zero card debt.

Browser testing found and fixed an actual date-input state issue. A separate test found and fixed new-record parent validation. Other corrected issues include historical-price fallback precedence, preserving opening units when editing a derived holding, changed-statement reminders, outdated reminder amounts, and next-cycle card balances.

## Public data checks

Direct live adapter checks in an in-memory database:

- MFapi scheme **119551**: 400 observations returned; exact returned identity was Aditya Birla Sun Life Banking & PSU Debt Fund — Direct Plan — IDCW-Re-investment.
- Yahoo **INFY.NS**: 495 observations returned.
- Yahoo **^NSEI**: 494 observations returned.
- Browser Refresh fetched stock/benchmark data and Google News RSS successfully.

These are observed successes, not provider uptime guarantees or recommendations. Fund/stock dates are preserved; they are not relabelled as today's market close.

## Desktop, tablet and phone-width rendering

Frontend inspector ran on the actual app at **1440, 768 and 390 px**. Final recorded report: **0 failures, 2 warnings**. The warnings concern small secondary labels and extra space in a short dashboard card beside a taller one. Main ledger values and actions remain readable; secondary source/date labels intentionally use smaller text.

Screenshots were visually inspected: `test-results/final-layout/desktop-fold.jpg`, `desktop-page-01.jpg`, `tablet-fold.jpg`, `mobile-fold.jpg`, `mobile-page-01.jpg`. There is no page-wide horizontal overflow; investment tables intentionally scroll within their own area on phones. The actual mobile menu, card benefits and payment form were exercised separately. Temporary viewport override was reset.

Visual assessment: clear monetary hierarchy, restrained blue data marks, consistent local Geist type, aligned surfaces, and honest empty/one-observation states. The first observation is shown as a dated value, not an empty chart. This is a functional finance dashboard, not a claim of reference-video fidelity or real-device verification.

## Windows operation

`Start-Daybook.ps1 -NoBrowser` successfully started the hidden local server. Two current-user scheduled tasks installed:

- **Daybook Daily Valuation**: 16:00, 18:00, 23:15 India Standard Time; start when available; interactive user; limited privileges.
- **Daybook Local Server**: at user sign-in; hidden launcher; no server runtime limit.

The valuation task was manually triggered and **LastTaskResult = 0**. NextRunTime was 31 October 2026 at 16:00 IST. The startup task also returned **0** after fixing its script-policy-dependent launcher. Both tasks use an explicitly hidden PowerShell launcher for Node, without changing execution policy. This verifies triggered task execution, not an unattended future run or reboot. No firewall rule was changed.

## Local AI and remaining scope

**`qwen3.5:9b-q4_K_M` downloaded and checksum verification succeeded.** The app's actual **Ask locally** button produced an English response using this model. It correctly stated recorded net worth of **₹3,09,693.22**, identified the **₹1,00,000 credit limit as excluded**, and noted the manually valued holding. The wording about news limitations was generic; summaries are explanatory output, not a source of prices or accounting truth. No cloud model was used.

Automatic retailer extraction, provider-specific gold sell-price feeds, complete exchange/results calendars, dedicated FD news, OS push notifications and real-phone LAN testing remain outside this first implementation. Manual prices, retail links, in-app reminders and responsive UI work. The full original vision is not described as complete.


## 4 November 2026 live re-audit

See [E2E_AUDIT_20261104.md](E2E_AUDIT_20261104.md) for current verification. Added actual stock/fund discovery, automatic card/product research, local-model ledger context and hidden startup recovery. 74 checks passed. Source outages, cached-discovery recovery, exact-statement requirements and the untouched owner ledger are explicitly recorded. Previous manual-only card/product limits are superseded only for the accessible routes demonstrated there.
