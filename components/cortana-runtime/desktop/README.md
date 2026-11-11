# Cortana desktop

The Windows desktop shell starts its own authenticated Python assistant, keeps a
small floating button and a tray icon available, and runs the React interface from
bundled files. It uses Electron 44.9.1. Node.js 22.12 or later is required for the
development tools.

From this folder:

```powershell
npm ci
npm run build
npm start
```

The project must have a working `../agent/.venv/Scripts/python.exe`. The desktop
launches Uvicorn without reload on an ephemeral loopback port; it does not require
a separately started API or Vite server. Startup failures appear in the interface.
Closing the main window hides it. Use **Quit Cortana** in the tray to end both
desktop and its owned backend.

Enable Windows sign-in startup in Settings or launch once with
`npm start -- --enable-autostart`. Startup launches this checkout in the background.
Keep this folder and the Electron binary in place. This is user sign-in startup,
not a Windows service running before login.

`Ctrl+Alt+Space` opens/hides Cortana. `Ctrl+Alt+S` captures the current primary
screen and opens Cortana to ask a question. The floating button has a drag handle
and a separate screen button. Cortana hides both windows before capturing, then
attaches an in-memory screenshot to the next question. Narrow direct phrases such
as “look at my screen” also capture; negated commands and general screenshot
questions do not.

The wake toggle persists across restarts. Push-to-talk works independently. Windows
lock pauses listening and cancels active requests. Real microphone quality, Hindi
voice availability and end-to-end recognition depend on the configured local models
and need testing on the user's voice.

The **Connect** tab opens WhatsApp, Gmail and Instagram in Cortana's managed
browser so the user can sign in directly. It shows connection status and prepares
exact-text drafts. Ambiguous recipients appear as explicit choices; login-required
drafts can resume using their original saved text. The same draft cards appear in
chat responses. Review and Send remain manual actions in the destination app.
The desktop bridge exposes no message-sending endpoint.

The renderer is sandboxed, uses a restricted `app://` protocol and CSP, and cannot
read the API bearer token. Requests travel through a route-limited preload bridge;
only main injects a per-launch token. External navigation, new windows and camera
permission are denied. Development mode (`npm run dev:all`) trusts only the local
Vite page; a browser preview has no desktop capabilities.

Checks:

```powershell
npm run lint
npm test
npm run build
npm run test:desktop
npm run test:integrations
```

The desktop smoke test launches real hidden Electron windows and the local backend,
checks authenticated IPC, denied arbitrary requests, virtual-microphone permission
and rendering, rotates the backend/token through a restart, then quits. It uses a virtual audio device and does not capture the
desktop, register startup or call a model. Its UI image is `../tmp/desktop-smoke.png`.

The integration UI test uses fake app status, fake contact candidates and an
in-process backend. It verifies unavailable-service recovery, login resume,
recipient selection and exact message preservation without accessing an account.

`npm run test:screen` is a separate real-screen acceptance test. It briefly shows a
full-screen synthetic Python error fixture on the primary display, captures it
through Cortana's normal desktop bridge, closes the fixture, then asks the local
model to explain it. It uses isolated conversation data, saves no screenshot,
and verifies that the captured image cannot be reused. Run it when briefly showing
the fixture is acceptable; it does not access the microphone or use cloud models.

The existing `dist` packaging command is not the supported installation route for
this milestone: it still needs a distributable Python runtime and backend resource
bundle before an NSIS installer can run independently of this checkout.
