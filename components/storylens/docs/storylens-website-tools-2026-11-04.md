# Storylens website tools — 4 November 2026

Implemented and activated on the existing localhost:8765 service with its exact prior command and --no-publisher-worker flag. Voiceover was renamed Voice Clone after the other feature edits; API keys, URLs and saved voice records remain compatible.

## Implemented

- Script Edit is Smart Edit. Beat Studio is retained. Cinematic Footage replaces the manual website/native utility entry for Cinematic Reels, while older saved cinematic/music APIs remain compatible.
- Cinematic Footage accepts 1–100 local videos or a folder. It ranks detail, exposure and stability; finds nonoverlapping regions up to five seconds; suppresses exact source copies and similar sampled views across files; saves Best Shots and Extras separately. It preserves source media and dimensions and uses serialized NVIDIA exports. Low-resolution descriptors and limited decode threads bound RAM. This is not semantic subject deduplication: different angles of the same subject can remain.
- Resolve Color Grade provides the hash-verified owner-approved 19-node DRX and a duplicate-timeline apply path, recovery export, editable balance/contrast/saturation and disabled Cineon/Kodak nodes. It accepts the saved SDR/CST setup and rejects unsupported HDR/Log profiles. This is the reusable structure, not a finished automatic shot-specific grade.
- Editor-tools navigation exposes Import Template, Template Aligner, Template Text, Copy Paste, Image Downloader, native 3D captions, Template Library, Animation Presets, Cinematic Text, Effects Library and Reel Recreate. The added native controls dispatch through the existing Storylens Adobe panel and its established project/transaction guards. An open connected native panel is required. Selecting Import Template or Aligner still requires its separate Run control.
- Browser commands bind to one panel/project, use durable once-only receipts, reject stale connections and retain uncertain outcomes without automatic replay. Recent command payload caching is bounded. Current connection status appears beside the feature.
- Result bars use four compact icon-only destinations with accessible names. Ordinary supported XML can prepare an AE JSX through the existing layer manifest; unsupported effects stop rather than substitute. Opening AE while Premiere runs, or the reverse, is blocked without closing either app.
- Existing dark UI retained; tool search, independently scrolling navigation, compact tool views and narrow-screen layout added. The large introduction is hidden while tools are visible.

## Verified scope

Actual isolated web application and actual main web application were exercised with generated real video. Main job fb750aca913249439ea7391baf817b1a completed in about 1.5 seconds with one five-second Best Shot, two five-second Extras and one exact source duplicate excluded. This small fixture is not a real 100-video travel-bank benchmark. Isolated playback, Download, Extras and actual AE handoff preparation worked. The real DRX downloaded and the HDR/Log safeguard stopped safely. Twenty-six supplementary tests and JS syntax checks passed. Desktop and 390px screenshots were inspected through the supported browser controller; no independent browser inspector was used.

## Still requiring native verification

No Storylens Adobe panel was connected at the recorded check. Actual browser-to-Adobe execution, native import/playback in all four editors, and applying the node graph in a real Resolve timeline were not performed. Native tools require reopening/reconnecting the installed Storylens panel after the server update. Do not call these live workflows verified from the mock command receipt or prepared JSX alone.

All publishing authority and unrelated task states remain unchanged. No model or native application was launched for this task. Evidence: output/workbench-20261103/status.json. Main extraction result: output/workbench/fb750aca913249439ea7391baf817b1a.

Temporary verification server exited and the agent-created browser tab was closed. Main 8765 and the original user downloader tab remain. No global Computer Use switch state is claimed.
