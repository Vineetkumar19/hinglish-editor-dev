# Pocket Tracker 0.3 update

Implemented:
- Shared responsive glass-style dashboard for Android and private laptop website.
- Compact mobile sizes, safe areas, wrapped transaction metadata, Setup in side menu.
- Recurring monthly payment add/edit/pause/resume/remove and encrypted monthly budget.
- Insights, searchable/filterable transactions and retained PDF access.
- Automatic Safety categories; financial email selection remains independent.
- Recent incoming Gmail including Spam classified automatically; ordinary bodies discarded.
- Open in Gmail; no unsubscribe links followed by Pocket Tracker.
- Authenticated certificate-pinned TLS phone endpoint and localhost Node companion.
- Existing SMS, matching, payment notifications, PDF automation and signing identity preserved.
- Reference Financial Tracker folder unchanged.

Boundaries:
- Alert-based cash flow, not a bank balance or proof that every transfer was captured.
- Ambiguous alerts stay outside totals.
- Gmail background updates can be delayed by Android.
- Payment notes require an accessible alert containing the note.
- Recurring commitments are monthly plans, not actual debits.
- Current budget applies until changed; historical budget versions are not stored.
- Laptop requires same Wi-Fi and phone service. Re-pair if the phone IP changes.
- No paid middleware, hosting or cloud AI added.

Artifacts:
- app/build/outputs/apk/debug/app-debug.apk
- Start-Pocket-Tracker.cmd
- laptop/server.cjs and laptop/README.md
- design/contract.md, desktop.png, mobile.png, evidence.json

Final verification:
- 34 core tests passed.
- 18 physical-device tests passed, including viewport fit and Setup placement.
- Android build and lint passed.
- Paired Wi-Fi snapshot and saved PDF verified.
- Wrong token, wrong certificate, cross-origin read and unprotected write rejected.
- Published privacy page updated and HTTP 200 verified.
- Laptop density refinement: 192px sidebar, 147px summary strip, smaller headings/cards/rows; all eight screens fit at 1366px without horizontal overflow.
- Approved mobile layout preserved by desktop-only media rules.

Layout refinement approved direction:
- Main summary card on the left; four supporting cards in a 2 x 2 grid on the right.
- Laptop main card 218px high, with 103px supporting cards and 12px row gap.
- Below 1000px, main card stacks above the 2 x 2 grid.
- Checked widths 1366, 1024, 900 and 390: no horizontal overflow.
- Mobile layout retained, including its 146px main-card minimum.
