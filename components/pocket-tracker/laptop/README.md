# Pocket Tracker — laptop companion

Double-click Start-Pocket-Tracker.cmd in the project folder.

Website: http://127.0.0.1:43820. Keep the phone and laptop on the same Wi-Fi. This laptop is already paired after setup.

- Phone: side menu → Setup → Pair laptop enables authenticated TLS access.
- Another laptop: run the companion, open Pair laptop, paste the private code from the phone.
- Phone → Setup → Disconnect revokes the saved token.
- The laptop reads the existing phone ledger; it makes no Gmail API calls.
- Budget and recurring edits are saved encrypted on the phone.
- Dashboard responses are not cached to disk. Downloaded PDFs are ordinary local files.
- Companion binds only to 127.0.0.1. Phone uses TLS, a pinned certificate and a random pairing token.
- Credential: laptop/.private/pairing.json. Do not share or commit it.
- After a phone restart/force-stop, open Pocket Tracker to restart laptop access.
- If your router changes the phone's Wi-Fi address, pair again using the updated code.
- VPN, client isolation or guest Wi-Fi may block connections between devices.
- Gmail categories update through background sync, scheduled every 15 minutes, subject to Android delays.
- Warning categories are local indicators, not verified fraud. Use Open in Gmail for Gmail's unsubscribe controls.
