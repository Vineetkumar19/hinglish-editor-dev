# Pocket Tracker 0.3 — design contract

- Purpose: observed money movements first; safety separate; setup outside daily navigation.
- Reference: user's Paisa project in Financial Tracker/expense-tracker. Violet palette, ledger, recurring planning and budgets.
- Direction: translucent surfaces, restrained purple cash-flow card, local system fonts, compact phone scale. No remote assets.
- Shared UI: bundled Android WebView assets and localhost laptop companion.
- Viewports: 390x844 mobile and 1440x900 desktop, plus physical Realme viewport.
- Navigation: side menu with Setup near top; phone bottom bar has Overview, Transactions, Reports, Safety.
- Data: confirmed cash flow, separate unconfirmed alerts, planned recurring commitments, monthly budget. Plans never become paid transactions automatically.
- Safety: automatic categories, escaped plain text, no remote email HTML/images.
- Accessibility: visible focus, labeled controls, modal dialogs, hidden sidebar excluded from keyboard focus, reduced-motion support.
- Acceptance: no horizontal overflow; clear loading, empty, error, partial, permission states; encrypted paired LAN access; financial regression tests preserved.
