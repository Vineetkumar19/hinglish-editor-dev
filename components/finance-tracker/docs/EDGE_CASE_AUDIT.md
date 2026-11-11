# Edge-case audit — 31 October 2026

This records tested behavior, not a claim that every possible edge case has been eliminated. All interactive writes below used the isolated demonstration at port 4312. The personal ledger at port 4310 stayed empty.

## Verified changes

| Area | Behavior now covered |
| --- | --- |
| Input and identity | Real calendar dates, positive finite quantities, bounded money, future-date rejection, normalized stock symbols, duplicate holdings within an account, duplicate watch items, safe listing URLs. |
| Transactions | Exact decimal cost basis, fees, splits, sale ordering, overselling rejection, cash-linked purchase/payment rejection when a recorded balance becomes negative, and atomic rollback. Checks include intermediate dates, not only today's balance. |
| Concurrent work | Client submission guard plus persisted idempotency keys prevent duplicate POST effects. Editing or deleting a stale version returns a conflict instead of silently overwriting. |
| Recovery | Deleted records go to Recently deleted; restore keeps identity and rechecks references and ledger constraints. Duplicate restoration fails without losing the deleted copy. JSON backups include deleted entries. Restore uses a new database only, validates ledger consistency/settings, retains manual prices, and resets operational refresh caches. |
| Valuation | Manual gold quotes are isolated per holding/provider. Legacy observations migrate. Same-date manual overrides win deterministically. Old manual prices are stale; fully sold holdings are closed at zero instead of missing a quote. Future opening balances do not appear in historical totals. |
| Income, cards and assets | Report-only income can predate a bank reconciliation; cash credits cannot. Card credit limits stay outside net worth. Over-limit cards show zero available credit plus excess. Payment reminders follow changed due dates. Included asset components cannot form parent cycles. |
| Performance | Full sales appear on their actual date even without a fresh quote. A complete write-off can report −100%. Reinvestment after zero capital starts a disclosed new continuous period. Carried or sparse observations suppress misleading annualized volatility. |
| Public sources | Invalid NAV rows are skipped without erasing valid observations. Unknown/non-INR stock currency and empty valid closing-price data fail explicitly. Failures retain previous prices. Overlapping refresh calls share a job; failed scheduled runs retry. |
| News | Starts on app access, record changes and scheduler ticks; no model question required. Active holdings and watchlist entries are covered without the old ten-instrument cap. Refresh interval is 30 minutes, failure retry 5 minutes. Requests coalesce, each topic can fail independently, cached headlines remain available, duplicate articles merge related investments, and removed holdings stop appearing. |
| Forms and layout | Failed submissions retain input, unsaved edits have explicit Keep editing / Discard changes controls, polling does not replace open form input, connectivity errors preserve displayed state, mobile navigation hides closed links, and money does not split across lines. |

## Executed verification

- `npm test`: **62 passed, 0 failed**. Includes real local HTTP endpoints, SQLite migration, and subprocess backup/restore round trips; mocked network responses cover source failure and malformed-data branches.
- `npm run build`: TypeScript and production build passed.
- Added a synthetic Reliance Industries holding through the running UI. Its real public RSS headlines appeared automatically without clicking Ask locally, Check news or Refresh prices.
- Entered the same symbol in lowercase as another holding in the same account: duplicate rejected; entered form values remained visible.
- Tried a ₹1,00,000 purchase against recorded cash of ₹90,450: rejected; cash remained ₹90,450 and units were unchanged.
- Deleted the synthetic holding, found it in Settings → Recently deleted, restored it, and verified its original units, cost and value returned.
- Opened the same bank record in two tabs. Saved a new name in the first; the second received the stale-version conflict and retained its unsaved name.
- Kept an unsaved form, then explicitly discarded it; no entry was created.
- Enabled the Portfolio news dashboard widget and verified it persisted after reload. A nonmatching headline search showed a distinct empty-search state.
- Exercised phone-width navigation and the real ledger's empty news state. Closed navigation links were absent from the accessibility tree. Responsive override was reset afterwards.
- The live local AI test initially used a dollar sign for a rupee balance. Added explicit INR metadata, INR-labelled amounts and a currency instruction, then retested through Ask locally: it returned **INR 310,693.22**, the correct demo net worth, and correctly excluded credit limits. This is observed output, not a guarantee against future model mistakes.
- Browser error/warning log for the audited demo was empty at the final inspection point.

## Visual audit

The owner explicitly requested glassmorphism and gloss. This overrides the design skill's default bans only for translucent surfaces, gradients, button highlights and surface shadows; it does not waive overflow/readability checks.

Final inspector output: `test-results/glass-final/report.json`, **0 failures, 2 warnings**, at 1440/768/390 px. Desktop, tablet and mobile screenshots were visually inspected. The initial mobile amount wrap was found in the first render and fixed. Remaining warnings: the border heuristic treats translucent RGB rules as opaque; the short paid-off-card panel has modest empty space to align with its neighboring history panel. Tables intentionally scroll inside their container on narrow screens.

The final desktop screenshot contains synthetic balances, clearly labelled as a demonstration. It is not the owner's portfolio.

## Boundaries that remain

- Public RSS is a best-effort headline feed, not a complete exchange announcement/results calendar. Search can return irrelevant stories or no stories; publisher claims are not verified by the app. FD-specific news is not implemented.
- Provider-specific digital-gold redemption prices and retailer resale/retail extraction remain manual. A generic metal price is not treated as a guaranteed provider sell quote.
- Sources can be late, unavailable or stop providing free access. Observed dates and partial-valuation states remain visible; no lifetime source guarantee is made.
- This ledger currently rejects negative recorded bank cash; it does not model overdrafts or every loan/account product. Same-day cash is reconciled by date, not intraday timestamps.
- Corporate actions other than manually entered splits and dividend receipts need manual reconciliation. Multiple currencies, tax-lot optimization and tax filing are not implemented.
- Historical net-worth snapshots preserve what was recorded then; editing today's records does not reconstruct unknown historical bank balances or asset resale prices.
- Local reminders need the server running. No OS push delivery, unattended reboot test, physical-phone/LAN test or full accessibility certification was performed in this audit.
- SQLite and backup files remain unencrypted at the application layer. Backup restoration is currently a command-line workflow to a new file.
