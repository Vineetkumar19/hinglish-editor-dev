# Pocket Tracker 0.4.0 — transaction recovery and reporting

Implemented 30 October 2026.

- Financial Gmail selection includes Slice sender alerts and card/IMPS-success subjects.
- Versioned, bounded 100-day financial backfill; SMS reimport retains existing identities.
- Incoming Gmail classification also retains financial alerts already fetched in that stream.
- Added Slice completed-refund and successful account/card/IMPS templates.
- Structured Axis UPI/NEFT references and counterparties, email repeated-amount handling,
  footer isolation, numeric and named-month dates.
- Evidence-based bank, payment app, instrument and channel metadata; explicit CC badges.
- Same-amount distinct references remain separate. SMS/email references merge once.
- Slice account-SMS/debit-card-email pairing requires matching bank, direction, amount,
  merchant, different sources and timestamps within 15 seconds, plus a unique candidate.
  Ambiguous evidence is excluded instead of double-counted.
- Bank/source/instrument/direction filters and time/amount sorting.
- Supplied Axis and Slice images, BHIM SVG; red debit / green credit outlines.
- Fifth mobile navigation item: Insights. On-screen monthly history, four donut breakdowns,
  green In/red Out cashflow, independent optional selected-month PDF export.
- PDF overview, donut, repeated transaction table headers, account summaries, exclusions
  and collection coverage. Existing encrypted message storage and TLS pairing retained.

Verification:
- Combined credit-card debit/refund and Axis+BHIM filters checked with synthetic records.
- All eight dashboard pages fit a 390px viewport; desktop Insights inspected at 1366px.
- Logo HTTP responses 200 with correct PNG/SVG MIME.
- PDF generated through paired phone, downloaded locally for inspection; first two pages
  rendered with bundled pypdfium2 and inspected. Private PDF artifact is not published.
- Final checks: 47 core tests, 20 Android test results, APK build and lint successful.
- Final live snapshot: 624 confirmed across available history, 211 in October; 163 excluded alerts (137 unresolved plus 26 pending/failed). Gmail selected-mail backfill up to date.
- Both existing user Chrome dashboard tabs refreshed successfully.
- Core and Android test/build output: task-build.log and device-validation.log.
- Wi-Fi service and localhost companion restarted after instrumentation.

A one-time verified bank-receipt import recovered missing Slice payments. It is not an automatic Slice history integration. Details and supporting evidence are available in the encrypted transfer reference. Future notification delivery and parsing still need observation.
