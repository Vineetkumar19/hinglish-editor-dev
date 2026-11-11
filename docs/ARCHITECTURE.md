# Architecture and request flows

## System layout

    Windows desktop wrapper or browser
                 |
       StoryLens local HTTP service
                 |
       request checks and job dispatch
                 |
       media processors / voice / native editor bridge
                 |
       files, previews, editable projects and saved job state

The StoryLens service runs on loopback port 8765. Agent Suite integration uses 8898. Finance summary uses 43822 and reads Pocket Tracker on 43820 and Finance Tracker on 4310. Cortana's standalone agent defaults to 8000. Ollama normally listens on 11434. Confirm current configuration before launching a service.

## Direct media request

static/app.js gathers the selected input, mode and output options and submits /api/jobs. AppState in server.py validates the request and creates a job. _run_job serializes the relevant work and coordinates GPU access. _execute_job selects the feature implementation, updates progress and saves results. The frontend polls the exact job and presents its result and export actions.

## Editor assistant

static/assistant.js submits a request with its attachments to the assistant API. assistant.py stores conversation and task state. assistant_plan.py constrains tool names and option values. The selected adapter builds a feature request. assistant_pipeline.py records phases and authorizations, resumes supported saved work, and checks stop status before continuation. Media execution and publishing are separate stages.

## Voice assistant

static/support-call.js captures microphone audio and sends a turn with the active feature, visible controls and dropdown choices. support_call_local.py coordinates transcription and interpretation. support_call_actions.py recognizes explicit actions. support_call_controls.py and support_call_knowledge.py supply feature and control evidence. support_call_router.py bounds semantic action output.

The browser executes approved actions through static/support-call-actions.js and reports the result. support_call_speech.py supplies speech recognition and voice playback. support_call_desktop.py delegates supported native app/file operations to the separate Cortana runtime.

## Publishing and scheduling

static/prepare-post.js uses prepare_post_http.py. The latter delegates to hinglish_publish/prepare_post.py and associated workflow modules. Preparation, editable metadata review, upload, release scheduling and verification have separate records. Scheduled Posts uses existing saved job and destination identities. Instagram uses the paired Chrome extension; YouTube has its own authenticated connector. Exact current readiness requires an account check.

## Agent Suite

static/ai-agents.js calls agents_http.py. The bridge starts or contacts the existing integrated suite service and opens its selected workspace. components/agents/server/storylens.py checks integration authorization. The agents, core workflow brain, graph state and approval/outbox logic are under components/agents. Social comment replies have a separate StoryLens service in hinglish_app/social_comments.py.

## Analytics

static/creator-analytics.js controls Overview, Analytics, Reports and Connections. analytics_http.py owns local SQLite state, refresh tasks and report selection. analytics_sources.py reads account sources through the authorized platform adapters. Source permission, refresh completion and visible report data are distinct states.

## Finance

hinglish_app/finance.py serves the read-only combined finance summary. It requests selected monthly totals from Pocket Tracker and net-worth totals from Finance Tracker. It keeps the two ledgers in their original applications.

Finance Tracker flows from src/App.tsx to server/index.mjs, then schema/domain checks in domain.mjs and persistence in store.mjs. Price/news providers and scheduled refreshes use their own modules.

Pocket Tracker flows from the Android screens and collection services into the local ledger. The laptop/server.cjs companion pairs to the phone, pins its certificate, and forwards permitted requests. Phone database and Android Keystore state remain on the phone.

## Native editors

editor_plugins contains Adobe CEP/UXP and Resolve integration sources. Native operations depend on the installed editor, matching extension, active project and actual media. An exported XML, DRX or project package must be checked in the receiving editor for its specific route.
