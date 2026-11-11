# Cortana — local laptop assistant

The first laptop-control milestone is under live repair and verification on this Windows machine. See [current behavior, validation and limits](docs/MILESTONE_1_STATUS.md). The broader specialist roadmap remains in [CORTANA_MASTER_PLAN.md](docs/CORTANA_MASTER_PLAN.md).

## Run

Double-click **StartCortana.cmd** in this folder. The desktop starts its authenticated Python backend automatically. You do not need a Vite server or a separate terminal. Keep Ollama installed and running for reasoning and screen questions; simple app/website launches do not need a model response.

Windows sign-in startup is enabled for this installation. A real reboot and the owner's microphone still need acceptance testing.

- **Floating Cortana button / Ctrl+Alt+Space:** show or hide the assistant.
- **Floating screen button / Ctrl+Alt+S:** capture the primary display and attach it to your next question.
- **Hold the microphone button:** speak in English, Hindi or Hinglish; release to submit.
- **Conversation on:** starts automatically and resumes listening after each reply, without a wake word on every turn. **Turn mic off/on** controls capture and remembers the owner's choice. Turn it off when addressing another person or assistant. Windows lock releases the microphone.
- **Stop / Escape:** cancel the current request and speech. Completed actions are not undone.
- **Close window:** hide to the tray. **Tray > Quit Cortana:** stop the app and its backend.
- **Settings > Start with Windows:** control startup after your Windows sign-in.

Try “Open ChatGPT”, “YouTube kholo”, “क्रोम खोलो”, or capture an editor window and ask “What is this error?” To edit code, provide the actual file or let Cortana find it, inspect the proposed diff, and approve it.

## Communication drafts

The **Connect** tab opens installed WhatsApp and Instagram apps for drafting. Gmail and website fallbacks use the owner's ordinary Chrome profile (`Default`, displayed as Vineet), preserving its existing website logins. Gmail targets **vineetdas1903@gmail.com** by default. These preferences are in `config/settings.json`.

Ask for a draft or use the exact-message form. The native accessibility adapter checks the recipient, preserves existing text, and enters a draft only when the controls can be verified. If Cortana requests assistance, select the intended conversation and choose **Continue in selected conversation**. Unsupported layouts stop with an explanation. Review the recipient and text and press **Send yourself**. **Stop / Escape** and Windows lock stop Cortana's draft worker while leaving the owner's apps and Chrome open. Already entered text may remain.

Outgoing WhatsApp and Instagram messages use **English or Hinglish in Roman letters**. Gmail messages and subjects use **English only**. You can still speak or type instructions to Cortana in English, Hindi or Hinglish. In the exact-message form, enter the final text in the required language.

Routing, native adapter safeguards, cancellation and the desktop UI have automated checks. Real-account lookup and composer acceptance for this new app-first path remain pending; earlier isolated-browser tests do not validate the native apps. The legacy isolated-browser implementation remains for regression coverage but is no longer called by draft routes or tools. General file tools still deny browser credentials and the old `browser-profile` directory. Generic messaging input is blocked, and the desktop bridge exposes no send endpoint.

## Current machine and runtime

Ryzen 9 8940HX, RTX 5070 Ti Laptop GPU (12 GB VRAM), 16 GB RAM, Windows 11. Cortana uses the installed Qwen3.5 9B Q6 vision/tool model through its own `cortana-local:9b` alias. The existing StoryLens model definitions are preserved. Python 3.12 is copied into `.runtime/python`; `agent/.venv` uses that private base. Electron is pinned in the desktop lockfile. Speech models are cached under `models/`.

`agent/.env` contains local runtime settings and any legacy credentials. Never publish it. Cloud inference is disabled in code for this milestone, including legacy fallback flags. Apps launch through fixed executable arguments; model-generated URLs and sensitive computer actions require a preview and approval.

The owner explicitly authorized file access across currently attached A:, C:, and E: on 20 October 2026. Windows account permissions still apply. Credentials, browser sessions, Windows system modifications and Cortana's own runtime/security source are protected from automatic file tools. File changes require approval; changed files invalidate a stale preview. Deletion, arbitrary shell execution and automatic message sending remain blocked; communication support is limited to preparing drafts for manual sending.

## Verification and maintenance

Run Python checks with `agent\.venv\Scripts\python.exe -m pytest tests -q`. In `desktop`, run `npm test`, `npm run lint`, and `npm run build`. `npm run test:desktop` exercises the real hidden desktop/backend; `npm run test:screen` briefly shows a controlled test fixture to exercise actual screen capture and local vision. `npm run test:integrations` checks the real desktop UI and IPC against simulated draft responses, without opening accounts or sending messages.

Dependency versions are pinned in `agent/requirements.lock.txt` and `desktop/package-lock.json`. The tested launcher runs this checkout; the existing NSIS configuration is not a supported distribution package. Moving this folder requires rebuilding the virtual environment and updating startup registration.

A source recovery ZIP from before these changes is in `tmp/recovery/`. It excludes environment secrets. Runtime test evidence is under `tmp/`; generated caches, environments, models, history and secrets are excluded from Git.
