# Hinglish Editor – DEV copy

This folder is a **working copy** of `E:\remove silence`.
All new features are built **here only**. The original folder is never touched.

| | Folder |
|---|---|
| Original (safe, untouched) | `E:\remove silence` |
| Development copy (this one) | `E:\Hinglish Editor DEV` |

## What was copied (26 Sep 2026)

| Part | How |
|---|---|
| Code (`hinglish_*`), tests, docs, launchers (.bat), configs, plugins, tools | Full copy |
| `input\` (your test videos and scripts) | Full copy |
| `.venv\` (Python environment) | Full copy, pointed at this folder |
| `models\` (11 GB of AI models) | **Hard links**: the same files on disk, so they take no extra space. Deleting them here does not delete the original. |
| `output\`, `cache\`, `tmp\` | Left **empty**. They are old results and rebuild on the next run. |

Two paths were changed to point at this folder:
- `editor_plugins\premiere-cep\js\config.js`
- `tools\llama\runtime.json`

Baseline check: **116 / 116 tests passed** in this copy before any new work.

## Things to know

- The DEV app uses its **own port 8766**, and the original app uses 8765, so both can run at the same time (changed 26 Sep).
- **Don't run `Install Editor Plugins.bat` from here** unless you want Premiere/Resolve to use this DEV copy instead of the original.

## How the work is organised

- Each new feature gets a numbered note in this folder: `01 - <feature>.md`, `02 - <feature>.md`, …
  Each note says what was added, which files changed, and how to use and test it.
- `FEATURE LOG.md` lists every feature in order.
- Git (local only, nothing online) saves a checkpoint after each feature, so any step can be undone.
