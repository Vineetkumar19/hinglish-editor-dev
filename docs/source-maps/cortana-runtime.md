# cortana-runtime source map

Use this map to jump from a module to its definitions. Links refer to this source snapshot. Static imports and definitions show where code lives. Runtime acceptance is recorded separately.

## agent/core/__init__.py

[Open source](../../components/cortana-runtime/agent/core/__init__.py)


## agent/core/alias_match.py

[Open source](../../components/cortana-runtime/agent/core/alias_match.py)

Imports re.

- [_levenshtein](../../components/cortana-runtime/agent/core/alias_match.py#L27) — function
- [_normalize](../../components/cortana-runtime/agent/core/alias_match.py#L43) — function
- [resolve_alias](../../components/cortana-runtime/agent/core/alias_match.py#L49) — function — Returns the matching key from `aliases`, or None.

## agent/core/app_config.py

[Open source](../../components/cortana-runtime/agent/core/app_config.py)

Imports json, pathlib, threading, core.config, core.pathresolve.

- [_config_file](../../components/cortana-runtime/agent/core/app_config.py#L21) — function
- [load_app_config](../../components/cortana-runtime/agent/core/app_config.py#L28) — function — Loads config/settings.json (or the example fallback), cached until
- [approved_apps](../../components/cortana-runtime/agent/core/app_config.py#L48) — function
- [approved_folder_aliases](../../components/cortana-runtime/agent/core/app_config.py#L52) — function
- [approved_search_roots](../../components/cortana-runtime/agent/core/app_config.py#L56) — function — Configured search roots, resolved to paths that actually exist.

## agent/core/app_windows.py

[Open source](../../components/cortana-runtime/agent/core/app_windows.py)

Imports win32gui, win32process, psutil, ctypes, win32api, win32con.

- [instagram_title](../../components/cortana-runtime/agent/core/app_windows.py#L5) — function
- [current_platform](../../components/cortana-runtime/agent/core/app_windows.py#L9) — function
- [focus_existing](../../components/cortana-runtime/agent/core/app_windows.py#L26) — function
- [visit](../../components/cortana-runtime/agent/core/app_windows.py#L33) — function
- [is_target_foreground](../../components/cortana-runtime/agent/core/app_windows.py#L60) — function

## agent/core/architecture_commands.py

[Open source](../../components/cortana-runtime/agent/core/architecture_commands.py)

Imports re.

- [parse](../../components/cortana-runtime/agent/core/architecture_commands.py#L5) — function
- [summarize](../../components/cortana-runtime/agent/core/architecture_commands.py#L57) — function

## agent/core/browser_bridge.py

[Open source](../../components/cortana-runtime/agent/core/browser_bridge.py)

Imports json, time, uuid, core, core.tasks.

- [profile_status](../../components/cortana-runtime/agent/core/browser_bridge.py#L9) — function
- [command](../../components/cortana-runtime/agent/core/browser_bridge.py#L17) — function
- [exchange](../../components/cortana-runtime/agent/core/browser_bridge.py#L43) — function — Called only by the native host, never by a website/API route.

## agent/core/browser_session.py

[Open source](../../components/cortana-runtime/agent/core/browser_session.py)

Imports atexit, asyncio, json, os, pathlib, queue, subprocess, sys, threading, time, uuid, psutil, core.processes, core, core.draft_adapters, core.tool_registry, contextlib, playwright.sync_api.

- [BrowserUnavailable](../../components/cortana-runtime/agent/core/browser_session.py#L32) — class
- [_remember_tree_unlocked](../../components/cortana-runtime/agent/core/browser_session.py#L36) — function
- [_remember_tree](../../components/cortana-runtime/agent/core/browser_session.py#L81) — function
- [managed_browser_active](../../components/cortana-runtime/agent/core/browser_session.py#L86) — function
- [managed_browser_process_ids](../../components/cortana-runtime/agent/core/browser_session.py#L91) — function
- [_read_responses](../../components/cortana-runtime/agent/core/browser_session.py#L97) — function
- [_start](../../components/cortana-runtime/agent/core/browser_session.py#L110) — function
- [close_browser](../../components/cortana-runtime/agent/core/browser_session.py#L126) — function — Stop only this managed browser tree; retain IDs until death is confirmed.
- [browser_request](../../components/cortana-runtime/agent/core/browser_session.py#L160) — function
- [_parent_watchdog](../../components/cortana-runtime/agent/core/browser_session.py#L219) — function
- [_worker](../../components/cortana-runtime/agent/core/browser_session.py#L243) — function

## agent/core/cloud_fallback.py

[Open source](../../components/cortana-runtime/agent/core/cloud_fallback.py)

- [CloudFallbackNotConfigured](../../components/cortana-runtime/agent/core/cloud_fallback.py#L5) — class
- [is_configured](../../components/cortana-runtime/agent/core/cloud_fallback.py#L9) — function
- [call_cloud_fallback](../../components/cortana-runtime/agent/core/cloud_fallback.py#L13) — function

## agent/core/communication_policy.py

[Open source](../../components/cortana-runtime/agent/core/communication_policy.py)

Imports importlib, core.tasks.

- [DraftOnlyViolation](../../components/cortana-runtime/agent/core/communication_policy.py#L11) — class
- [assert_generic_input_allowed](../../components/cortana-runtime/agent/core/communication_policy.py#L15) — function

## agent/core/communication_targets.py

[Open source](../../components/cortana-runtime/agent/core/communication_targets.py)

Imports re, subprocess, pathlib, urllib.parse, core.app_config, core.processes, tools.apps, psutil, win32gui, win32process.

- [preferences](../../components/cortana-runtime/agent/core/communication_targets.py#L13) — function
- [chrome_profile_args](../../components/cortana-runtime/agent/core/communication_targets.py#L17) — function
- [target](../../components/cortana-runtime/agent/core/communication_targets.py#L26) — function
- [sender_email](../../components/cortana-runtime/agent/core/communication_targets.py#L34) — function
- [website](../../components/cortana-runtime/agent/core/communication_targets.py#L41) — function
- [open_target](../../components/cortana-runtime/agent/core/communication_targets.py#L50) — function
- [existing_gmail](../../components/cortana-runtime/agent/core/communication_targets.py#L71) — function

## agent/core/compress.py

[Open source](../../components/cortana-runtime/agent/core/compress.py)

Imports logging, core.config, headroom.

- [_get_compress_fn](../../components/cortana-runtime/agent/core/compress.py#L33) — function
- [compress_history](../../components/cortana-runtime/agent/core/compress.py#L50) — function — Compresses older conversation turns. Returns `history` unchanged if

## agent/core/config.py

[Open source](../../components/cortana-runtime/agent/core/config.py)

Imports pathlib, pydantic, pydantic_settings, urllib.parse.

- [Settings](../../components/cortana-runtime/agent/core/config.py#L9) — class
- [local_bind_only](../../components/cortana-runtime/agent/core/config.py#L63) — function
- [local_model_only](../../components/cortana-runtime/agent/core/config.py#L70) — function

## agent/core/db.py

[Open source](../../components/cortana-runtime/agent/core/db.py)

Imports sqlite3, time, contextlib, pathlib, core.config, json, hashlib, sys, os.

- [init_db](../../components/cortana-runtime/agent/core/db.py#L81) — function
- [_migrate](../../components/cortana-runtime/agent/core/db.py#L90) — function — Additive, idempotent column migrations for tables that predate a
- [_ensure_schema](../../components/cortana-runtime/agent/core/db.py#L104) — function — Creates the tables if they aren't there yet.
- [get_conn](../../components/cortana-runtime/agent/core/db.py#L120) — function
- [add_message](../../components/cortana-runtime/agent/core/db.py#L132) — function
- [get_recent_messages](../../components/cortana-runtime/agent/core/db.py#L142) — function
- [clear_session](../../components/cortana-runtime/agent/core/db.py#L153) — function
- [add_fact](../../components/cortana-runtime/agent/core/db.py#L168) — function
- [all_facts](../../components/cortana-runtime/agent/core/db.py#L189) — function
- [delete_fact](../../components/cortana-runtime/agent/core/db.py#L210) — function
- [mark_facts_used](../../components/cortana-runtime/agent/core/db.py#L217) — function
- [add_reminder](../../components/cortana-runtime/agent/core/db.py#L233) — function
- [list_reminders](../../components/cortana-runtime/agent/core/db.py#L244) — function
- [due_reminders](../../components/cortana-runtime/agent/core/db.py#L255) — function — Reminders past their time that haven't been announced yet.
- [complete_reminder](../../components/cortana-runtime/agent/core/db.py#L271) — function
- [get_audit](../../components/cortana-runtime/agent/core/db.py#L278) — function
- [log_audit](../../components/cortana-runtime/agent/core/db.py#L295) — function — Best-effort audit write.
- [_confirmation_session](../../components/cortana-runtime/agent/core/db.py#L334) — function
- [create_pending_confirmation](../../components/cortana-runtime/agent/core/db.py#L341) — function
- [get_pending_confirmation](../../components/cortana-runtime/agent/core/db.py#L355) — function
- [claim_pending_confirmation](../../components/cortana-runtime/agent/core/db.py#L380) — function — A single SQL compare-and-set owns approval or rejection.
- [resolve_pending_confirmation](../../components/cortana-runtime/agent/core/db.py#L398) — function
- [revoke_pending_confirmations](../../components/cortana-runtime/agent/core/db.py#L409) — function — Stop invalidates every unconsumed review in this desktop session.

## agent/core/desktop_drafts.py

[Open source](../../components/cortana-runtime/agent/core/desktop_drafts.py)

Imports asyncio, atexit, json, os, pathlib, queue, subprocess, sys, threading, time, uuid, core.processes, core, core.communication_targets, core.draft_adapters, core.tool_registry, psutil, core.native_draft_ui, datetime, tools.communication.

- [DesktopDraftUnavailable](../../components/cortana-runtime/agent/core/desktop_drafts.py#L23) — class
- [_read](../../components/cortana-runtime/agent/core/desktop_drafts.py#L27) — function
- [cancel_drafts](../../components/cortana-runtime/agent/core/desktop_drafts.py#L37) — function
- [_start](../../components/cortana-runtime/agent/core/desktop_drafts.py#L64) — function
- [_prepare_in_app](../../components/cortana-runtime/agent/core/desktop_drafts.py#L79) — function
- [draft_request](../../components/cortana-runtime/agent/core/desktop_drafts.py#L108) — function
- [_watch_parent](../../components/cortana-runtime/agent/core/desktop_drafts.py#L214) — function
- [worker](../../components/cortana-runtime/agent/core/desktop_drafts.py#L230) — function

## agent/core/diagnostics.py

[Open source](../../components/cortana-runtime/agent/core/diagnostics.py)

Imports json, platform, shutil, subprocess, time, datetime, httpx, psutil, core, core.config, core.tasks, core.windows_counters, core.model_profiles, core.resource_broker, win32evtlog, xml.etree.ElementTree.

- [_gpu](../../components/cortana-runtime/agent/core/diagnostics.py#L16) — function
- [_models](../../components/cortana-runtime/agent/core/diagnostics.py#L35) — function
- [_power_mode](../../components/cortana-runtime/agent/core/diagnostics.py#L45) — function
- [_events](../../components/cortana-runtime/agent/core/diagnostics.py#L58) — function
- [findings](../../components/cortana-runtime/agent/core/diagnostics.py#L85) — function
- [sample_system](../../components/cortana-runtime/agent/core/diagnostics.py#L122) — function
- [_sample_system](../../components/cortana-runtime/agent/core/diagnostics.py#L128) — function
- [compare_reports](../../components/cortana-runtime/agent/core/diagnostics.py#L203) — function
- [inspect_process](../../components/cortana-runtime/agent/core/diagnostics.py#L215) — function
- [prepare_unload](../../components/cortana-runtime/agent/core/diagnostics.py#L224) — function
- [unload_model](../../components/cortana-runtime/agent/core/diagnostics.py#L236) — function
- [means](../../components/cortana-runtime/agent/core/diagnostics.py#L207) — function

## agent/core/draft_adapters.py

[Open source](../../components/cortana-runtime/agent/core/draft_adapters.py)

Imports dataclasses, re, time, unicodedata, urllib.parse, uuid.

- [DraftProblem](../../components/cortana-runtime/agent/core/draft_adapters.py#L23) — class
- [validate_payload](../../components/cortana-runtime/agent/core/draft_adapters.py#L27) — function
- [visible](../../components/cortana-runtime/agent/core/draft_adapters.py#L51) — function
- [one](../../components/cortana-runtime/agent/core/draft_adapters.py#L55) — function
- [content](../../components/cortana-runtime/agent/core/draft_adapters.py#L62) — function
- [normalized](../../components/cortana-runtime/agent/core/draft_adapters.py#L67) — function
- [Draft](../../components/cortana-runtime/agent/core/draft_adapters.py#L72) — class
- [DraftBrowser](../../components/cortana-runtime/agent/core/draft_adapters.py#L100) — class
- [response](../../components/cortana-runtime/agent/core/draft_adapters.py#L86) — function
- [__init__](../../components/cortana-runtime/agent/core/draft_adapters.py#L101) — function
- [guard](../../components/cortana-runtime/agent/core/draft_adapters.py#L107) — function
- [page](../../components/cortana-runtime/agent/core/draft_adapters.py#L115) — function
- [connection](../../components/cortana-runtime/agent/core/draft_adapters.py#L125) — function
- [handle](../../components/cortana-runtime/agent/core/draft_adapters.py#L142) — function
- [fill](../../components/cortana-runtime/agent/core/draft_adapters.py#L199) — function
- [click](../../components/cortana-runtime/agent/core/draft_adapters.py#L203) — function
- [ready](../../components/cortana-runtime/agent/core/draft_adapters.py#L207) — function
- [gmail_fields](../../components/cortana-runtime/agent/core/draft_adapters.py#L215) — function
- [gmail_recipient](../../components/cortana-runtime/agent/core/draft_adapters.py#L221) — function
- [prepare_gmail](../../components/cortana-runtime/agent/core/draft_adapters.py#L228) — function
- [whatsapp_body](../../components/cortana-runtime/agent/core/draft_adapters.py#L243) — function
- [whatsapp_identity](../../components/cortana-runtime/agent/core/draft_adapters.py#L246) — function
- [prepare_whatsapp](../../components/cortana-runtime/agent/core/draft_adapters.py#L251) — function
- [instagram_body](../../components/cortana-runtime/agent/core/draft_adapters.py#L315) — function
- [instagram_identity](../../components/cortana-runtime/agent/core/draft_adapters.py#L318) — function
- [prepare_instagram](../../components/cortana-runtime/agent/core/draft_adapters.py#L326) — function
- [verify](../../components/cortana-runtime/agent/core/draft_adapters.py#L375) — function
- [snapshot](../../components/cortana-runtime/agent/core/draft_adapters.py#L261) — function

## agent/core/draft_clipboard.py

[Open source](../../components/cortana-runtime/agent/core/draft_clipboard.py)

Imports contextlib, time, core.draft_adapters, win32clipboard, win32con.

- [_open](../../components/cortana-runtime/agent/core/draft_clipboard.py#L8) — function
- [_snapshot](../../components/cortana-runtime/agent/core/draft_clipboard.py#L19) — function
- [temporary_text](../../components/cortana-runtime/agent/core/draft_clipboard.py#L42) — function

## agent/core/draft_commands.py

[Open source](../../components/cortana-runtime/agent/core/draft_commands.py)

Imports re.

- [parse_recipient_correction](../../components/cortana-runtime/agent/core/draft_commands.py#L11) — function
- [parse_draft_command](../../components/cortana-runtime/agent/core/draft_commands.py#L36) — function
- [parse_recipient_only](../../components/cortana-runtime/agent/core/draft_commands.py#L62) — function

## agent/core/draft_transactions.py

[Open source](../../components/cortana-runtime/agent/core/draft_transactions.py)

Imports hashlib, json, time, core, core.tasks, core.tool_registry.

- [payload_hash](../../components/cortana-runtime/agent/core/draft_transactions.py#L12) — function
- [_validated](../../components/cortana-runtime/agent/core/draft_transactions.py#L16) — function
- [prepare](../../components/cortana-runtime/agent/core/draft_transactions.py#L32) — function
- [edit](../../components/cortana-runtime/agent/core/draft_transactions.py#L36) — function
- [approve](../../components/cortana-runtime/agent/core/draft_transactions.py#L46) — function
- [cancel](../../components/cortana-runtime/agent/core/draft_transactions.py#L59) — function
- [revoke_all](../../components/cortana-runtime/agent/core/draft_transactions.py#L67) — function
- [send_approved](../../components/cortana-runtime/agent/core/draft_transactions.py#L81) — function — No model tool gets an arbitrary adapter or bypasses its capability gate.

## agent/core/embeddings.py

[Open source](../../components/cortana-runtime/agent/core/embeddings.py)

Imports json, math, core, core.config, core.tasks, httpx, core.resource_broker, core.model_profiles, core.personal_documents, core.stt.

- [embed](../../components/cortana-runtime/agent/core/embeddings.py#L11) — function
- [build](../../components/cortana-runtime/agent/core/embeddings.py#L33) — function
- [search](../../components/cortana-runtime/agent/core/embeddings.py#L55) — function
- [cosine](../../components/cortana-runtime/agent/core/embeddings.py#L64) — function

## agent/core/file_index.py

[Open source](../../components/cortana-runtime/agent/core/file_index.py)

Imports hashlib, os, time, pathlib, core, core.app_config, core.tasks, tools.files.

- [_schema](../../components/cortana-runtime/agent/core/file_index.py#L12) — function
- [index_files](../../components/cortana-runtime/agent/core/file_index.py#L17) — function
- [search_index](../../components/cortana-runtime/agent/core/file_index.py#L77) — function

## agent/core/local_data.py

[Open source](../../components/cortana-runtime/agent/core/local_data.py)

Imports json, time, pathlib, core, core.config, datetime.

- [inventory](../../components/cortana-runtime/agent/core/local_data.py#L11) — function
- [export_data](../../components/cortana-runtime/agent/core/local_data.py#L18) — function
- [preview_retention](../../components/cortana-runtime/agent/core/local_data.py#L29) — function
- [prepare_prune](../../components/cortana-runtime/agent/core/local_data.py#L40) — function
- [prune](../../components/cortana-runtime/agent/core/local_data.py#L45) — function

## agent/core/local_store.py

[Open source](../../components/cortana-runtime/agent/core/local_store.py)

Imports json, sqlite3, time, contextlib, pathlib, uuid, core.config.

- [connection](../../components/cortana-runtime/agent/core/local_store.py#L32) — function
- [put](../../components/cortana-runtime/agent/core/local_store.py#L50) — function
- [put_in_transaction](../../components/cortana-runtime/agent/core/local_store.py#L57) — function — Update a record inside an already-open write transaction.
- [get](../../components/cortana-runtime/agent/core/local_store.py#L70) — function
- [records](../../components/cortana-runtime/agent/core/local_store.py#L78) — function
- [remove](../../components/cortana-runtime/agent/core/local_store.py#L85) — function
- [recover](../../components/cortana-runtime/agent/core/local_store.py#L92) — function

## agent/core/model_profiles.py

[Open source](../../components/cortana-runtime/agent/core/model_profiles.py)

Imports json, shutil, subprocess, threading, time, pathlib, httpx, psutil, core, core.config, core.tasks, core.resource_broker, core.performance.

- [ModelAdmissionError](../../components/cortana-runtime/agent/core/model_profiles.py#L19) — class — The shared machine cannot admit the requested model right now.
- [_client](../../components/cortana-runtime/agent/core/model_profiles.py#L30) — function
- [inventory](../../components/cortana-runtime/agent/core/model_profiles.py#L34) — function
- [_free_gpu_mib](../../components/cortana-runtime/agent/core/model_profiles.py#L47) — function
- [admit](../../components/cortana-runtime/agent/core/model_profiles.py#L61) — function
- [initialize_selection](../../components/cortana-runtime/agent/core/model_profiles.py#L91) — function
- [reviewed_license](../../components/cortana-runtime/agent/core/model_profiles.py#L103) — function
- [_observe_residency](../../components/cortana-runtime/agent/core/model_profiles.py#L116) — function
- [switch_profile](../../components/cortana-runtime/agent/core/model_profiles.py#L131) — function
- [prepare_inference](../../components/cortana-runtime/agent/core/model_profiles.py#L195) — function
- [ensure_gpu_residency](../../components/cortana-runtime/agent/core/model_profiles.py#L225) — function — Prove placement before generating a potentially long spoken answer.
- [resident](../../components/cortana-runtime/agent/core/model_profiles.py#L227) — function

## agent/core/native_draft_ui.py

[Open source](../../components/cortana-runtime/agent/core/native_draft_ui.py)

Imports re, time, collections, urllib.parse, core.draft_adapters, uiautomation, json, pathlib, psutil, win32gui, core.draft_clipboard, win32con, win32api, _ctypes, datetime, uiautomation.uiautomation, win32process.

- [NativeDraftUI](../../components/cortana-runtime/agent/core/native_draft_ui.py#L10) — class
- [__init__](../../components/cortana-runtime/agent/core/native_draft_ui.py#L11) — function
- [mark](../../components/cortana-runtime/agent/core/native_draft_ui.py#L19) — function
- [check](../../components/cortana-runtime/agent/core/native_draft_ui.py#L23) — function
- [diagnose](../../components/cortana-runtime/agent/core/native_draft_ui.py#L27) — function — Local structural diagnostics: never record field values or passwords.
- [nodes](../../components/cortana-runtime/agent/core/native_draft_ui.py#L47) — function
- [controls](../../components/cortana-runtime/agent/core/native_draft_ui.py#L77) — function
- [find](../../components/cortana-runtime/agent/core/native_draft_ui.py#L117) — function
- [read](../../components/cortana-runtime/agent/core/native_draft_ui.py#L167) — function
- [window](../../components/cortana-runtime/agent/core/native_draft_ui.py#L198) — function
- [focus](../../components/cortana-runtime/agent/core/native_draft_ui.py#L260) — function
- [is_focused](../../components/cortana-runtime/agent/core/native_draft_ui.py#L370) — function
- [invoke](../../components/cortana-runtime/agent/core/native_draft_ui.py#L399) — function
- [instagram_search](../../components/cortana-runtime/agent/core/native_draft_ui.py#L415) — function
- [fill](../../components/cortana-runtime/agent/core/native_draft_ui.py#L419) — function
- [identity](../../components/cortana-runtime/agent/core/native_draft_ui.py#L535) — function
- [emails](../../components/cortana-runtime/agent/core/native_draft_ui.py#L627) — function
- [compose_container](../../components/cortana-runtime/agent/core/native_draft_ui.py#L631) — function
- [compose_addresses](../../components/cortana-runtime/agent/core/native_draft_ui.py#L647) — function
- [gmail_fields](../../components/cortana-runtime/agent/core/native_draft_ui.py#L668) — function
- [verify_gmail_recipient](../../components/cortana-runtime/agent/core/native_draft_ui.py#L738) — function
- [calendar_availability](../../components/cortana-runtime/agent/core/native_draft_ui.py#L753) — function
- [save_previous_gmail](../../components/cortana-runtime/agent/core/native_draft_ui.py#L790) — function
- [close_site](../../components/cortana-runtime/agent/core/native_draft_ui.py#L816) — function
- [prepare](../../components/cortana-runtime/agent/core/native_draft_ui.py#L865) — function
- [label](../../components/cortana-runtime/agent/core/native_draft_ui.py#L120) — function
- [belongs](../../components/cortana-runtime/agent/core/native_draft_ui.py#L283) — function
- [refresh_search](../../components/cortana-runtime/agent/core/native_draft_ui.py#L430) — function
- [read_current](../../components/cortana-runtime/agent/core/native_draft_ui.py#L437) — function
- [await_body](../../components/cortana-runtime/agent/core/native_draft_ui.py#L669) — function
- [structure](../../components/cortana-runtime/agent/core/native_draft_ui.py#L351) — function
- [matches](../../components/cortana-runtime/agent/core/native_draft_ui.py#L540) — function
- [expected_heading](../../components/cortana-runtime/agent/core/native_draft_ui.py#L586) — function
- [overlaps](../../components/cortana-runtime/agent/core/native_draft_ui.py#L614) — function
- [instagram_row](../../components/cortana-runtime/agent/core/native_draft_ui.py#L999) — function
- [same_visible_row](../../components/cortana-runtime/agent/core/native_draft_ui.py#L1052) — function

## agent/core/parent_watchdog.py

[Open source](../../components/cortana-runtime/agent/core/parent_watchdog.py)

Imports os, threading, ctypes.

- [_windows_api](../../components/cortana-runtime/agent/core/parent_watchdog.py#L12) — function
- [_ancestor_pids](../../components/cortana-runtime/agent/core/parent_watchdog.py#L32) — function
- [start_parent_watchdog](../../components/cortana-runtime/agent/core/parent_watchdog.py#L76) — function — Return a cleanup function; manual developer starts may omit the host PID.
- [ProcessEntry](../../components/cortana-runtime/agent/core/parent_watchdog.py#L36) — class
- [wait](../../components/cortana-runtime/agent/core/parent_watchdog.py#L111) — function
- [stop](../../components/cortana-runtime/agent/core/parent_watchdog.py#L127) — function

## agent/core/pathresolve.py

[Open source](../../components/cortana-runtime/agent/core/pathresolve.py)

Imports os, pathlib, core.config.

- [is_protected_path](../../components/cortana-runtime/agent/core/pathresolve.py#L16) — function — Credential/version-control internals are outside ordinary file tools.
- [is_protected_edit_path](../../components/cortana-runtime/agent/core/pathresolve.py#L49) — function — Ordinary code edits cannot alter Windows or Cortana's trust boundary.
- [candidate_paths](../../components/cortana-runtime/agent/core/pathresolve.py#L70) — function
- [resolve_dir](../../components/cortana-runtime/agent/core/pathresolve.py#L101) — function — First existing directory among the configured path and its variants.

## agent/core/performance.py

[Open source](../../components/cortana-runtime/agent/core/performance.py)

Imports json, threading, time, collections, core.config.

- [record](../../components/cortana-runtime/agent/core/performance.py#L12) — function

## agent/core/permissions.py

[Open source](../../components/cortana-runtime/agent/core/permissions.py)

Imports enum.

- [RiskLevel](../../components/cortana-runtime/agent/core/permissions.py#L21) — class
- [Decision](../../components/cortana-runtime/agent/core/permissions.py#L28) — class
- [check](../../components/cortana-runtime/agent/core/permissions.py#L48) — function

## agent/core/personal_documents.py

[Open source](../../components/cortana-runtime/agent/core/personal_documents.py)

Imports hashlib, json, re, datetime, pathlib, core, core.tasks, tools.documents, pytesseract, pypdf, core.windows_ocr, PIL, docx, pdf2image, core.config.

- [identity](../../components/cortana-runtime/agent/core/personal_documents.py#L15) — function
- [_ocr_image](../../components/cortana-runtime/agent/core/personal_documents.py#L28) — function
- [extract](../../components/cortana-runtime/agent/core/personal_documents.py#L44) — function
- [invalidate](../../components/cortana-runtime/agent/core/personal_documents.py#L83) — function
- [_invalidate_tasks](../../components/cortana-runtime/agent/core/personal_documents.py#L96) — function
- [fresh](../../components/cortana-runtime/agent/core/personal_documents.py#L106) — function
- [index_document](../../components/cortana-runtime/agent/core/personal_documents.py#L119) — function
- [search_documents](../../components/cortana-runtime/agent/core/personal_documents.py#L154) — function
- [answer_with_sources](../../components/cortana-runtime/agent/core/personal_documents.py#L171) — function
- [propose_task](../../components/cortana-runtime/agent/core/personal_documents.py#L180) — function
- [confirm_task](../../components/cortana-runtime/agent/core/personal_documents.py#L203) — function
- [list_tasks](../../components/cortana-runtime/agent/core/personal_documents.py#L214) — function
- [acknowledge_task](../../components/cortana-runtime/agent/core/personal_documents.py#L222) — function
- [finish_task](../../components/cortana-runtime/agent/core/personal_documents.py#L232) — function
- [forget_document](../../components/cortana-runtime/agent/core/personal_documents.py#L242) — function

## agent/core/processes.py

[Open source](../../components/cortana-runtime/agent/core/processes.py)

Imports os, subprocess, sys.

- [public_environment](../../components/cortana-runtime/agent/core/processes.py#L7) — function
- [shell_open](../../components/cortana-runtime/agent/core/processes.py#L14) — function — Use Windows file/protocol associations without leaking agent secrets.

## agent/core/quick_commands.py

[Open source](../../components/cortana-runtime/agent/core/quick_commands.py)

Imports re, core.app_config, tools.web.

- [command_text](../../components/cortana-runtime/agent/core/quick_commands.py#L26) — function
- [parse_launch](../../components/cortana-runtime/agent/core/quick_commands.py#L38) — function
- [parse_close](../../components/cortana-runtime/agent/core/quick_commands.py#L83) — function

## agent/core/recall.py

[Open source](../../components/cortana-runtime/agent/core/recall.py)

Imports math, re.

- [tokenize](../../components/cortana-runtime/agent/core/recall.py#L30) — function
- [_score](../../components/cortana-runtime/agent/core/recall.py#L43) — function
- [retrieve_relevant](../../components/cortana-runtime/agent/core/recall.py#L66) — function — Returns the most relevant facts for this query, best first.

## agent/core/resource_broker.py

[Open source](../../components/cortana-runtime/agent/core/resource_broker.py)

Imports contextlib, pathlib, os, threading, time, sys, httpx, core.config, core.model_profiles, msvcrt.

- [_release_streams](../../components/cortana-runtime/agent/core/resource_broker.py#L15) — function
- [_unload_owned](../../components/cortana-runtime/agent/core/resource_broker.py#L25) — function
- [_expire_warm_lease](../../components/cortana-runtime/agent/core/resource_broker.py#L43) — function
- [retain_for_next_turn](../../components/cortana-runtime/agent/core/resource_broker.py#L70) — function — Keep a short warm interval, still reserved from other GPU workloads.
- [release_when_idle](../../components/cortana-runtime/agent/core/resource_broker.py#L82) — function — Stop extends no warm reservation; active work retains its safety lease.
- [shutdown_owned_gpu](../../components/cortana-runtime/agent/core/resource_broker.py#L88) — function
- [GPUUnavailable](../../components/cortana-runtime/agent/core/resource_broker.py#L97) — class — Expected resource waiting state, not an internal server failure.
- [gpu_slot](../../components/cortana-runtime/agent/core/resource_broker.py#L102) — function

## agent/core/screen_context.py

[Open source](../../components/cortana-runtime/agent/core/screen_context.py)

Imports base64, io, secrets, threading, time, dataclasses, PIL, mss, mss.tools.

- [Capture](../../components/cortana-runtime/agent/core/screen_context.py#L16) — class
- [_expire](../../components/cortana-runtime/agent/core/screen_context.py#L26) — function
- [capture](../../components/cortana-runtime/agent/core/screen_context.py#L33) — function
- [consume](../../components/cortana-runtime/agent/core/screen_context.py#L57) — function
- [discard](../../components/cortana-runtime/agent/core/screen_context.py#L66) — function
- [encode](../../components/cortana-runtime/agent/core/screen_context.py#L71) — function

## agent/core/screen_intent.py

[Open source](../../components/cortana-runtime/agent/core/screen_intent.py)

Imports re.

- [screen_action_requested](../../components/cortana-runtime/agent/core/screen_intent.py#L5) — function

## agent/core/secret_store.py

[Open source](../../components/cortana-runtime/agent/core/secret_store.py)

Imports base64, json, os, re, threading, pathlib, uuid, core.config, win32crypt.

- [_path](../../components/cortana-runtime/agent/core/secret_store.py#L15) — function
- [_read](../../components/cortana-runtime/agent/core/secret_store.py#L19) — function
- [save](../../components/cortana-runtime/agent/core/secret_store.py#L24) — function
- [read](../../components/cortana-runtime/agent/core/secret_store.py#L42) — function
- [names](../../components/cortana-runtime/agent/core/secret_store.py#L52) — function

## agent/core/security.py

[Open source](../../components/cortana-runtime/agent/core/security.py)

Imports hmac, os, urllib.parse, starlette.responses.

- [LocalSessionAuth](../../components/cortana-runtime/agent/core/security.py#L15) — class
- [__init__](../../components/cortana-runtime/agent/core/security.py#L16) — function
- [__call__](../../components/cortana-runtime/agent/core/security.py#L20) — function
- [secure_send](../../components/cortana-runtime/agent/core/security.py#L71) — function

## agent/core/stt.py

[Open source](../../components/cortana-runtime/agent/core/stt.py)

Imports logging, os, sys, threading, time, pathlib, av, numpy, core.config, httpx, psutil, core.model_profiles, core.resource_broker, core.performance, faster_whisper.

- [RecordingError](../../components/cortana-runtime/agent/core/stt.py#L24) — class — The uploaded recording has no usable audio.
- [SpeechUnavailable](../../components/cortana-runtime/agent/core/stt.py#L28) — class — No installed speech decoder can run within the current resources.
- [_prepare_cuda_libraries](../../components/cortana-runtime/agent/core/stt.py#L32) — function — Locate private/existing runtime DLLs without changing Windows PATH.
- [_load_audio_bounded](../../components/cortana-runtime/agent/core/stt.py#L46) — function — Decode locally with a duration cap before Whisper allocates model features.
- [_language](../../components/cortana-runtime/agent/core/stt.py#L85) — function — Whisper expects None for detection, rather than the literal string 'auto'.
- [_get_model](../../components/cortana-runtime/agent/core/stt.py#L91) — function
- [_decode](../../components/cortana-runtime/agent/core/stt.py#L122) — function
- [transcribe](../../components/cortana-runtime/agent/core/stt.py#L166) — function
- [_model_cached](../../components/cortana-runtime/agent/core/stt.py#L226) — function
- [_release_gpu_models](../../components/cortana-runtime/agent/core/stt.py#L232) — function
- [gpu_model_loaded](../../components/cortana-runtime/agent/core/stt.py#L240) — function
- [preview](../../components/cortana-runtime/agent/core/stt.py#L245) — function — Provisional text only; drop overlapping work rather than queueing it.
- [warmup](../../components/cortana-runtime/agent/core/stt.py#L265) — function
- [runtime_status](../../components/cortana-runtime/agent/core/stt.py#L290) — function
- [append](../../components/cortana-runtime/agent/core/stt.py#L61) — function

## agent/core/tasks.py

[Open source](../../components/cortana-runtime/agent/core/tasks.py)

Imports asyncio, contextvars, threading, time, dataclasses, fastapi, core, core.draft_transactions, core.resource_broker.

- [Work](../../components/cortana-runtime/agent/core/tasks.py#L12) — class
- [begin](../../components/cortana-runtime/agent/core/tasks.py#L25) — function
- [finish](../../components/cortana-runtime/agent/core/tasks.py#L50) — function
- [cancel](../../components/cortana-runtime/agent/core/tasks.py#L60) — function
- [check_cancelled](../../components/cortana-runtime/agent/core/tasks.py#L73) — function
- [cancel_all](../../components/cortana-runtime/agent/core/tasks.py#L79) — function
- [may_capture_screen](../../components/cortana-runtime/agent/core/tasks.py#L89) — function
- [may_prepare_communication](../../components/cortana-runtime/agent/core/tasks.py#L94) — function — Only an explicit user communication request permits message drafting.

## agent/core/tool_registry.py

[Open source](../../components/cortana-runtime/agent/core/tool_registry.py)

Imports dataclasses, math, threading, contextlib, typing, core, core.permissions, core.tasks, hashlib, json, time, uuid.

- [ForbiddenTool](../../components/cortana-runtime/agent/core/tool_registry.py#L39) — class — Raised at import time if someone registers a capability that must
- [Tool](../../components/cortana-runtime/agent/core/tool_registry.py#L46) — class
- [serialized_effects](../../components/cortana-runtime/agent/core/tool_registry.py#L75) — function — Share action serialization with authenticated direct draft endpoints.
- [_check_communication_intent](../../components/cortana-runtime/agent/core/tool_registry.py#L80) — function
- [tool](../../components/cortana-runtime/agent/core/tool_registry.py#L85) — function
- [to_ollama_tools](../../components/cortana-runtime/agent/core/tool_registry.py#L108) — function — Ollama's /api/chat `tools` field expects OpenAI-style function specs.
- [list_tools](../../components/cortana-runtime/agent/core/tool_registry.py#L128) — function
- [ToolNotFound](../../components/cortana-runtime/agent/core/tool_registry.py#L135) — class
- [ToolDenied](../../components/cortana-runtime/agent/core/tool_registry.py#L139) — class
- [ToolNeedsConfirmation](../../components/cortana-runtime/agent/core/tool_registry.py#L146) — class
- [ConfirmationNotFound](../../components/cortana-runtime/agent/core/tool_registry.py#L155) — class
- [ConfirmationExpiredOrResolved](../../components/cortana-runtime/agent/core/tool_registry.py#L159) — class
- [ToolArgumentsInvalid](../../components/cortana-runtime/agent/core/tool_registry.py#L163) — class
- [ConfirmedActionStale](../../components/cortana-runtime/agent/core/tool_registry.py#L167) — class
- [_execute_recorded](../../components/cortana-runtime/agent/core/tool_registry.py#L171) — function
- [_validate](../../components/cortana-runtime/agent/core/tool_registry.py#L199) — function — Validate the supported tool schema subset, without coercion.
- [dispatch](../../components/cortana-runtime/agent/core/tool_registry.py#L244) — function — Runs a registered tool after enforcing its permission decision, and
- [execute_confirmed](../../components/cortana-runtime/agent/core/tool_registry.py#L293) — function — Runs the tool call a human has just approved via /api/confirm.
- [reject_confirmed](../../components/cortana-runtime/agent/core/tool_registry.py#L335) — function
- [decorator](../../components/cortana-runtime/agent/core/tool_registry.py#L87) — function
- [__init__](../../components/cortana-runtime/agent/core/tool_registry.py#L140) — function
- [__init__](../../components/cortana-runtime/agent/core/tool_registry.py#L147) — function

## agent/core/tool_router.py

[Open source](../../components/cortana-runtime/agent/core/tool_router.py)

Imports core.tool_registry, core.config, re.

- [score_tools](../../components/cortana-runtime/agent/core/tool_router.py#L175) — function
- [select_tools](../../components/cortana-runtime/agent/core/tool_router.py#L198) — function — Tool specs worth offering this turn.

## agent/core/tools_loader.py

[Open source](../../components/cortana-runtime/agent/core/tools_loader.py)

Imports sys, core.config, tools.

- [load_all_tools](../../components/cortana-runtime/agent/core/tools_loader.py#L18) — function

## agent/core/tts.py

[Open source](../../components/cortana-runtime/agent/core/tts.py)

Imports io, os, re, tempfile, threading, wave, functools, concurrent.futures, pathlib, types, core.config, comtypes.client, ctypes, pyttsx3, piper.

- [VoiceUnavailable](../../components/cortana-runtime/agent/core/tts.py#L21) — class
- [_initialize_com](../../components/cortana-runtime/agent/core/tts.py#L25) — function
- [_get_engine](../../components/cortana-runtime/agent/core/tts.py#L36) — function
- [_voice_languages](../../components/cortana-runtime/agent/core/tts.py#L44) — function
- [_pick_voice_id](../../components/cortana-runtime/agent/core/tts.py#L64) — function
- [hindi_model_path](../../components/cortana-runtime/agent/core/tts.py#L78) — function
- [_synthesize_hindi](../../components/cortana-runtime/agent/core/tts.py#L86) — function — Ungated local Piper voice; attribution/license are stored beside the weights.
- [_sapi_voices](../../components/cortana-runtime/agent/core/tts.py#L103) — function
- [_synthesize_windows](../../components/cortana-runtime/agent/core/tts.py#L116) — function — Render directly to a WAV; no pyttsx3 message pump or speaker playback.
- [_synthesize_on_worker](../../components/cortana-runtime/agent/core/tts.py#L151) — function
- [_run](../../components/cortana-runtime/agent/core/tts.py#L201) — function
- [_routine_audio](../../components/cortana-runtime/agent/core/tts.py#L212) — function
- [synthesize](../../components/cortana-runtime/agent/core/tts.py#L216) — function
- [_list_voices_on_worker](../../components/cortana-runtime/agent/core/tts.py#L229) — function
- [list_voices](../../components/cortana-runtime/agent/core/tts.py#L261) — function

## agent/core/wakeword_match.py

[Open source](../../components/cortana-runtime/agent/core/wakeword_match.py)

Imports re, unicodedata.

- [_levenshtein](../../components/cortana-runtime/agent/core/wakeword_match.py#L15) — function
- [match_wake_word](../../components/cortana-runtime/agent/core/wakeword_match.py#L25) — function — Only a leading wake phrase activates; numbers, Hindi and punctuation stay intact.
- [matches](../../components/cortana-runtime/agent/core/wakeword_match.py#L41) — function

## agent/core/windows_counters.py

[Open source](../../components/cortana-runtime/agent/core/windows_counters.py)

Imports math, win32pdh.

- [WindowsCounters](../../components/cortana-runtime/agent/core/windows_counters.py#L5) — class
- [__init__](../../components/cortana-runtime/agent/core/windows_counters.py#L16) — function
- [sample](../../components/cortana-runtime/agent/core/windows_counters.py#L34) — function
- [close](../../components/cortana-runtime/agent/core/windows_counters.py#L57) — function
- [__enter__](../../components/cortana-runtime/agent/core/windows_counters.py#L62) — function
- [__exit__](../../components/cortana-runtime/agent/core/windows_counters.py#L65) — function

## agent/core/windows_ocr.py

[Open source](../../components/cortana-runtime/agent/core/windows_ocr.py)

Imports asyncio, os, tempfile, pathlib, core.config, winrt.windows.storage, winrt.windows.graphics.imaging, winrt.windows.media.ocr.

- [recognize](../../components/cortana-runtime/agent/core/windows_ocr.py#L9) — function
- [read](../../components/cortana-runtime/agent/core/windows_ocr.py#L16) — function
- [bounded](../../components/cortana-runtime/agent/core/windows_ocr.py#L35) — function

## agent/core/workspace_scheduler.py

[Open source](../../components/cortana-runtime/agent/core/workspace_scheduler.py)

Imports asyncio, time, uuid, core, core.workspaces, core.browser_bridge, fastapi.concurrency, fastapi.

- [configure](../../components/cortana-runtime/agent/core/workspace_scheduler.py#L8) — function
- [refresh_selected](../../components/cortana-runtime/agent/core/workspace_scheduler.py#L20) — function
- [_capture_due](../../components/cortana-runtime/agent/core/workspace_scheduler.py#L50) — function
- [run](../../components/cortana-runtime/agent/core/workspace_scheduler.py#L75) — function

## agent/core/workspaces.py

[Open source](../../components/cortana-runtime/agent/core/workspaces.py)

Imports hashlib, json, platform, pathlib, urllib.parse, pydantic, core, core.app_config, core.tasks, tools.files, tools.openpath, datetime, core.browser_bridge, core.tool_registry.

- [WorkspaceItem](../../components/cortana-runtime/agent/core/workspaces.py#L16) — class
- [validate_item](../../components/cortana-runtime/agent/core/workspaces.py#L35) — function
- [capture_workspace](../../components/cortana-runtime/agent/core/workspaces.py#L64) — function
- [find_workspace](../../components/cortana-runtime/agent/core/workspaces.py#L74) — function
- [resolve_workspace](../../components/cortana-runtime/agent/core/workspaces.py#L78) — function
- [capture_browser_workspace](../../components/cortana-runtime/agent/core/workspaces.py#L90) — function
- [preview_restore](../../components/cortana-runtime/agent/core/workspaces.py#L102) — function
- [restore_workspace](../../components/cortana-runtime/agent/core/workspaces.py#L127) — function
- [kind_supported](../../components/cortana-runtime/agent/core/workspaces.py#L29) — function

## agent/main.py

[Open source](../../components/cortana-runtime/agent/main.py)

Imports contextlib, asyncio, os, fastapi, core, core.config, core.tools_loader, core.security, core.parent_watchdog, core.browser_session, core.desktop_drafts, routers, uvicorn, core.workspace_scheduler, core.resource_broker, fastapi.concurrency.

- [lifespan](../../components/cortana-runtime/agent/main.py#L18) — function

## agent/routers/__init__.py

[Open source](../../components/cortana-runtime/agent/routers/__init__.py)


## agent/routers/assistant.py

[Open source](../../components/cortana-runtime/agent/routers/assistant.py)

Imports asyncio, uuid, fastapi, fastapi.concurrency, pydantic, core, core.tool_registry, tools.reminders, core.permissions.

- [FactIn](../../components/cortana-runtime/agent/routers/assistant.py#L28) — class
- [ReminderIn](../../components/cortana-runtime/agent/routers/assistant.py#L34) — class
- [ConfirmIn](../../components/cortana-runtime/agent/routers/assistant.py#L39) — class
- [get_facts](../../components/cortana-runtime/agent/routers/assistant.py#L47) — function
- [create_fact](../../components/cortana-runtime/agent/routers/assistant.py#L52) — function
- [remove_fact](../../components/cortana-runtime/agent/routers/assistant.py#L60) — function
- [get_reminders](../../components/cortana-runtime/agent/routers/assistant.py#L69) — function
- [create_reminder](../../components/cortana-runtime/agent/routers/assistant.py#L76) — function
- [get_due](../../components/cortana-runtime/agent/routers/assistant.py#L86) — function — Reminders that have come due and not yet been announced.
- [finish_reminder](../../components/cortana-runtime/agent/routers/assistant.py#L96) — function
- [confirm_action](../../components/cortana-runtime/agent/routers/assistant.py#L105) — function — Approve or reject a HIGH-risk tool call that's parked waiting for a
- [audit_log](../../components/cortana-runtime/agent/routers/assistant.py#L137) — function
- [capabilities](../../components/cortana-runtime/agent/routers/assistant.py#L142) — function — Everything Cortana can currently do, grouped for the UI's help panel.

## agent/routers/chat.py

[Open source](../../components/cortana-runtime/agent/routers/chat.py)

Imports asyncio, json, re, time, datetime, typing, uuid, httpx, fastapi, fastapi.concurrency, pydantic, core, core.config, core.quick_commands, core.screen_intent, core.recall, core.tool_registry, core.tool_router, core.app_config, core.resource_broker.

- [_pending_draft_reply](../../components/cortana-runtime/agent/routers/chat.py#L28) — function
- [_system_prompt](../../components/cortana-runtime/agent/routers/chat.py#L117) — function
- [ChatRequest](../../components/cortana-runtime/agent/routers/chat.py#L132) — class
- [ChatResponse](../../components/cortana-runtime/agent/routers/chat.py#L141) — class
- [OllamaUnavailable](../../components/cortana-runtime/agent/routers/chat.py#L152) — class
- [_call_ollama_raw](../../components/cortana-runtime/agent/routers/chat.py#L156) — function
- [_call_ollama_leased](../../components/cortana-runtime/agent/routers/chat.py#L164) — function
- [_call_ollama_with_slot](../../components/cortana-runtime/agent/routers/chat.py#L185) — function
- [_call_model](../../components/cortana-runtime/agent/routers/chat.py#L257) — function
- [_run_tool_calls](../../components/cortana-runtime/agent/routers/chat.py#L265) — function
- [_screen_requested](../../components/cortana-runtime/agent/routers/chat.py#L296) — function
- [_communication_requested](../../components/cortana-runtime/agent/routers/chat.py#L310) — function
- [_offered_tools](../../components/cortana-runtime/agent/routers/chat.py#L379) — function
- [_perform](../../components/cortana-runtime/agent/routers/chat.py#L387) — function
- [_communication_turn](../../components/cortana-runtime/agent/routers/chat.py#L544) — function
- [chat](../../components/cortana-runtime/agent/routers/chat.py#L693) — function
- [cancel_task](../../components/cortana-runtime/agent/routers/chat.py#L713) — function
- [capture_screen](../../components/cortana-runtime/agent/routers/chat.py#L720) — function

## agent/routers/drafts.py

[Open source](../../components/cortana-runtime/agent/routers/drafts.py)

Imports typing, fastapi, fastapi.concurrency, pydantic, core.desktop_drafts, core.draft_adapters, re.

- [DraftRequest](../../components/cortana-runtime/agent/routers/drafts.py#L15) — class
- [RecipientChoice](../../components/cortana-runtime/agent/routers/drafts.py#L23) — class
- [request](../../components/cortana-runtime/agent/routers/drafts.py#L28) — function
- [integration_status](../../components/cortana-runtime/agent/routers/drafts.py#L40) — function
- [open_integration](../../components/cortana-runtime/agent/routers/drafts.py#L45) — function
- [prepare_draft](../../components/cortana-runtime/agent/routers/drafts.py#L50) — function
- [cancel_drafts](../../components/cortana-runtime/agent/routers/drafts.py#L59) — function
- [draft_key](../../components/cortana-runtime/agent/routers/drafts.py#L64) — function
- [resume_draft](../../components/cortana-runtime/agent/routers/drafts.py#L72) — function
- [select_recipient](../../components/cortana-runtime/agent/routers/drafts.py#L77) — function

## agent/routers/health.py

[Open source](../../components/cortana-runtime/agent/routers/health.py)

Imports fastapi, core.config, httpx, core, core.app_config.

- [warm_brain](../../components/cortana-runtime/agent/routers/health.py#L10) — function
- [health](../../components/cortana-runtime/agent/routers/health.py#L17) — function
- [ready](../../components/cortana-runtime/agent/routers/health.py#L22) — function
- [status](../../components/cortana-runtime/agent/routers/health.py#L27) — function

## agent/routers/introspection.py

[Open source](../../components/cortana-runtime/agent/routers/introspection.py)

Imports fastapi, core, core.permissions, core.tool_registry.

- [get_tools](../../components/cortana-runtime/agent/routers/introspection.py#L21) — function
- [get_permissions](../../components/cortana-runtime/agent/routers/introspection.py#L26) — function
- [get_audit](../../components/cortana-runtime/agent/routers/introspection.py#L34) — function
- [get_memory](../../components/cortana-runtime/agent/routers/introspection.py#L57) — function
- [delete_memory](../../components/cortana-runtime/agent/routers/introspection.py#L62) — function

## agent/routers/local_architecture.py

[Open source](../../components/cortana-runtime/agent/routers/local_architecture.py)

Imports asyncio, uuid, fastapi, fastapi.concurrency, pydantic, core, core.tool_registry, tools.documents, core.personal_documents.

- [Action](../../components/cortana-runtime/agent/routers/local_architecture.py#L22) — class
- [stop](../../components/cortana-runtime/agent/routers/local_architecture.py#L30) — function
- [state](../../components/cortana-runtime/agent/routers/local_architecture.py#L35) — function
- [due_tasks](../../components/cortana-runtime/agent/routers/local_architecture.py#L43) — function
- [action](../../components/cortana-runtime/agent/routers/local_architecture.py#L50) — function
- [CaptureBrowser](../../components/cortana-runtime/agent/routers/local_architecture.py#L68) — class
- [capture_browser](../../components/cortana-runtime/agent/routers/local_architecture.py#L79) — function

## agent/routers/stubs.py

[Open source](../../components/cortana-runtime/agent/routers/stubs.py)

Imports fastapi.

- [_not_implemented](../../components/cortana-runtime/agent/routers/stubs.py#L29) — function
- [agent_tasks](../../components/cortana-runtime/agent/routers/stubs.py#L38) — function
- [files](../../components/cortana-runtime/agent/routers/stubs.py#L43) — function
- [documents](../../components/cortana-runtime/agent/routers/stubs.py#L48) — function
- [integrations](../../components/cortana-runtime/agent/routers/stubs.py#L53) — function

## agent/routers/voice.py

[Open source](../../components/cortana-runtime/agent/routers/voice.py)

Imports logging, tempfile, pathlib, fastapi, fastapi.concurrency, fastapi.responses, pydantic, core, core.config, core.wakeword_match, time, core.performance.

- [SpeechRequest](../../components/cortana-runtime/agent/routers/voice.py#L42) — class
- [_save_upload_to_tmp](../../components/cortana-runtime/agent/routers/voice.py#L47) — function
- [_transcribe_off_loop](../../components/cortana-runtime/agent/routers/voice.py#L64) — function — Runs Whisper on a worker thread instead of the event loop.
- [speech_to_text](../../components/cortana-runtime/agent/routers/voice.py#L92) — function
- [wake_check](../../components/cortana-runtime/agent/routers/voice.py#L102) — function
- [speech_preview](../../components/cortana-runtime/agent/routers/voice.py#L114) — function
- [text_to_speech](../../components/cortana-runtime/agent/routers/voice.py#L127) — function
- [voice_config](../../components/cortana-runtime/agent/routers/voice.py#L148) — function
- [voices](../../components/cortana-runtime/agent/routers/voice.py#L163) — function

## scripts/browser_native_host.py

[Open source](../../components/cortana-runtime/scripts/browser_native_host.py)

Imports json, os, struct, sys, pathlib, core.browser_bridge, msvcrt.

- [main](../../components/cortana-runtime/scripts/browser_native_host.py#L12) — function

## scripts/discover_apps.py

[Open source](../../components/cortana-runtime/scripts/discover_apps.py)

Imports argparse, json, os, re, sys, tempfile, pathlib, win32com.client.

- [safe_candidate](../../components/cortana-runtime/scripts/discover_apps.py#L29) — function
- [proposed_aliases](../../components/cortana-runtime/scripts/discover_apps.py#L52) — function
- [merge_config](../../components/cortana-runtime/scripts/discover_apps.py#L86) — function
- [inventory](../../components/cortana-runtime/scripts/discover_apps.py#L99) — function
- [main](../../components/cortana-runtime/scripts/discover_apps.py#L127) — function

## scripts/prepare_architecture_pdf_fixtures.py

[Open source](../../components/cortana-runtime/scripts/prepare_architecture_pdf_fixtures.py)

Imports pathlib, pypdf, pypdf.generic, PIL.


## scripts/prepare_live_acceptance_plan.py

[Open source](../../components/cortana-runtime/scripts/prepare_live_acceptance_plan.py)

Imports json, pathlib.


## scripts/protect_legacy_credential.py

[Open source](../../components/cortana-runtime/scripts/protect_legacy_credential.py)

Imports os, re, sys, pathlib, uuid, core.config, core.

- [main](../../components/cortana-runtime/scripts/protect_legacy_credential.py#L13) — function

## scripts/register_browser_host.py

[Open source](../../components/cortana-runtime/scripts/register_browser_host.py)

Imports argparse, json, re, sys, pathlib, winreg.

- [main](../../components/cortana-runtime/scripts/register_browser_host.py#L13) — function

## scripts/run_contract_tests.py

[Open source](../../components/cortana-runtime/scripts/run_contract_tests.py)

Imports sys, tempfile, faulthandler, pathlib, pytest.


## scripts/smoke_draft_intent.py

[Open source](../../components/cortana-runtime/scripts/smoke_draft_intent.py)

Imports asyncio, json, re, sys, time, unicodedata, pathlib, unittest.mock, uuid, core, core.tools_loader, routers.

- [main](../../components/cortana-runtime/scripts/smoke_draft_intent.py#L29) — function
- [draft_only](../../components/cortana-runtime/scripts/smoke_draft_intent.py#L35) — function

## scripts/smoke_local_vision.py

[Open source](../../components/cortana-runtime/scripts/smoke_local_vision.py)

Imports base64, io, json, time, pathlib, httpx, PIL.


## tests/conftest.py

[Open source](../../components/cortana-runtime/tests/conftest.py)

Imports sys, pathlib, pytest, core.config, core.

- [isolate_architecture_store](../../components/cortana-runtime/tests/conftest.py#L10) — function

## tests/manual_browser_worker_smoke.py

[Open source](../../components/cortana-runtime/tests/manual_browser_worker_smoke.py)

Imports json, os, pathlib, sys, time, subprocess, psutil, core.


## tests/manual_voice_smoke.py

[Open source](../../components/cortana-runtime/tests/manual_voice_smoke.py)

Imports io, json, sys, time, wave, pathlib, core, core.wakeword_match.

- [main](../../components/cortana-runtime/tests/manual_voice_smoke.py#L21) — function

## tests/test_app_discovery.py

[Open source](../../components/cortana-runtime/tests/test_app_discovery.py)

Imports sys, tempfile, unittest, pathlib, unittest.mock, scripts.discover_apps, tools.apps, core.quick_commands.

- [AppDiscoveryTests](../../components/cortana-runtime/tests/test_app_discovery.py#L15) — class
- [setUp](../../components/cortana-runtime/tests/test_app_discovery.py#L16) — function
- [tearDown](../../components/cortana-runtime/tests/test_app_discovery.py#L22) — function
- [test_verified_no_argument_app_gets_natural_alias](../../components/cortana-runtime/tests/test_app_discovery.py#L25) — function
- [test_arguments_scripts_installers_and_missing_targets_are_excluded](../../components/cortana-runtime/tests/test_app_discovery.py#L30) — function
- [test_ambiguous_installations_do_not_get_shared_alias](../../components/cortana-runtime/tests/test_app_discovery.py#L41) — function
- [test_merge_preserves_roots_and_existing_approval](../../components/cortana-runtime/tests/test_app_discovery.py#L51) — function
- [test_unknown_app_cannot_execute_process](../../components/cortana-runtime/tests/test_app_discovery.py#L60) — function
- [test_known_app_uses_fixed_shell_free_argv](../../components/cortana-runtime/tests/test_app_discovery.py#L67) — function
- [test_new_apps_work_through_deterministic_multilingual_parser](../../components/cortana-runtime/tests/test_app_discovery.py#L76) — function

## tests/test_communication_intent.py

[Open source](../../components/cortana-runtime/tests/test_communication_intent.py)

Imports pathlib, sys, pytest, routers.chat.

- [test_positive_draft_requests](../../components/cortana-runtime/tests/test_communication_intent.py#L31) — function
- [test_mentions_negations_and_analysis_do_not_authorize_drafting](../../components/cortana-runtime/tests/test_communication_intent.py#L67) — function

## tests/test_desktop_drafts.py

[Open source](../../components/cortana-runtime/tests/test_desktop_drafts.py)

Imports asyncio, contextlib, pathlib, sys, threading, time, unittest, unittest.mock, types, core, core.native_draft_ui, core.draft_adapters, tools.web.

- [RoutingTests](../../components/cortana-runtime/tests/test_desktop_drafts.py#L20) — class
- [SessionTests](../../components/cortana-runtime/tests/test_desktop_drafts.py#L80) — class
- [Control](../../components/cortana-runtime/tests/test_desktop_drafts.py#L143) — class
- [NativeTests](../../components/cortana-runtime/tests/test_desktop_drafts.py#L167) — class
- [test_plain_gmail_launch_and_search_use_configured_sender](../../components/cortana-runtime/tests/test_desktop_drafts.py#L21) — function
- [test_installed_apps_are_preferred_without_browser_launch](../../components/cortana-runtime/tests/test_desktop_drafts.py#L29) — function
- [test_instagram_browser_override_uses_the_same_chrome_profile](../../components/cortana-runtime/tests/test_desktop_drafts.py#L39) — function
- [test_gmail_uses_main_profile_and_requested_sender_without_debugging](../../components/cortana-runtime/tests/test_desktop_drafts.py#L49) — function
- [test_website_fallback_does_not_need_gmail_configuration](../../components/cortana-runtime/tests/test_desktop_drafts.py#L62) — function
- [test_invalid_profile_is_rejected_before_launch](../../components/cortana-runtime/tests/test_desktop_drafts.py#L70) — function
- [tearDown](../../components/cortana-runtime/tests/test_desktop_drafts.py#L81) — function
- [test_cancel_only_terminates_owned_worker](../../components/cortana-runtime/tests/test_desktop_drafts.py#L84) — function
- [test_cancel_invalidates_queued_action_before_open](../../components/cortana-runtime/tests/test_desktop_drafts.py#L98) — function
- [test_cancel_wins_over_worker_completion](../../components/cortana-runtime/tests/test_desktop_drafts.py#L121) — function
- [test_cancelled_generation_cannot_start_a_worker](../../components/cortana-runtime/tests/test_desktop_drafts.py#L136) — function
- [__init__](../../components/cortana-runtime/tests/test_desktop_drafts.py#L144) — function
- [GetRuntimeId](../../components/cortana-runtime/tests/test_desktop_drafts.py#L157) — function
- [GetChildren](../../components/cortana-runtime/tests/test_desktop_drafts.py#L160) — function
- [GetParentControl](../../components/cortana-runtime/tests/test_desktop_drafts.py#L163) — function
- [setUp](../../components/cortana-runtime/tests/test_desktop_drafts.py#L168) — function
- [test_duplicate_provider_nodes_are_deduplicated](../../components/cortana-runtime/tests/test_desktop_drafts.py#L176) — function
- [test_optional_lookup_cannot_hide_multiple_composers](../../components/cortana-runtime/tests/test_desktop_drafts.py#L182) — function
- [test_provider_cycle_is_bounded](../../components/cortana-runtime/tests/test_desktop_drafts.py#L187) — function
- [test_truncated_tree_cannot_be_treated_as_unique](../../components/cortana-runtime/tests/test_desktop_drafts.py#L192) — function
- [test_send_control_is_never_invoked](../../components/cortana-runtime/tests/test_desktop_drafts.py#L197) — function
- [test_existing_text_is_preserved_before_focus_or_input](../../components/cortana-runtime/tests/test_desktop_drafts.py#L204) — function
- [test_prepared_message_never_searches_or_switches_chats](../../components/cortana-runtime/tests/test_desktop_drafts.py#L212) — function
- [gmail](../../components/cortana-runtime/tests/test_desktop_drafts.py#L220) — function
- [test_gmail_preserves_existing_recipient_even_with_empty_fields](../../components/cortana-runtime/tests/test_desktop_drafts.py#L234) — function
- [test_gmail_rejects_extra_cc_recipient_on_resume](../../components/cortana-runtime/tests/test_desktop_drafts.py#L240) — function
- [test_gmail_rejects_wrong_sender](../../components/cortana-runtime/tests/test_desktop_drafts.py#L248) — function
- [test_gmail_resume_verifies_without_recreating](../../components/cortana-runtime/tests/test_desktop_drafts.py#L254) — function
- [test_gmail_body_addresses_do_not_count_as_recipients](../../components/cortana-runtime/tests/test_desktop_drafts.py#L265) — function
- [effects](../../components/cortana-runtime/tests/test_desktop_drafts.py#L101) — function
- [request](../../components/cortana-runtime/tests/test_desktop_drafts.py#L104) — function
- [completed](../../components/cortana-runtime/tests/test_desktop_drafts.py#L124) — function

## tests/test_draft_transactions.py

[Open source](../../components/cortana-runtime/tests/test_draft_transactions.py)

Imports time, types, pytest, core.

- [payload](../../components/cortana-runtime/tests/test_draft_transactions.py#L7) — function
- [test_twenty_drafts_never_invoke_a_send](../../components/cortana-runtime/tests/test_draft_transactions.py#L14) — function
- [test_live_change_invalidates_approval](../../components/cortana-runtime/tests/test_draft_transactions.py#L22) — function
- [test_expired_approval_cannot_send](../../components/cortana-runtime/tests/test_draft_transactions.py#L34) — function
- [test_uncertain_send_is_never_replayed](../../components/cortana-runtime/tests/test_draft_transactions.py#L41) — function
- [test_manual_send_is_reconciled_without_another_send](../../components/cortana-runtime/tests/test_draft_transactions.py#L53) — function
- [test_unaccepted_adapter_cannot_use_approval](../../components/cortana-runtime/tests/test_draft_transactions.py#L60) — function
- [unknown](../../components/cortana-runtime/tests/test_draft_transactions.py#L44) — function

## tests/test_laptop_pipeline.py

[Open source](../../components/cortana-runtime/tests/test_laptop_pipeline.py)

Imports asyncio, io, json, sys, time, pathlib, uuid, httpx, pytest, PIL, core, core.config, core.quick_commands, core.tool_registry, core.permissions, routers, tools, tools.screenshot, contextlib, core.architecture_commands.

- [test_explicit_multilingual_launch](../../components/cortana-runtime/tests/test_laptop_pipeline.py#L37) — function
- [test_no_partial_or_negative_launch](../../components/cortana-runtime/tests/test_laptop_pipeline.py#L47) — function
- [test_screen_feature_mentions_and_negations_are_not_capture_requests](../../components/cortana-runtime/tests/test_laptop_pipeline.py#L55) — function
- [test_browser_launch_never_uses_shell](../../components/cortana-runtime/tests/test_laptop_pipeline.py#L59) — function
- [test_invalid_navigation_urls](../../components/cortana-runtime/tests/test_laptop_pipeline.py#L75) — function
- [test_bad_model_json_is_a_tool_error](../../components/cortana-runtime/tests/test_laptop_pipeline.py#L80) — function
- [test_unoffered_tool_cannot_dispatch](../../components/cortana-runtime/tests/test_laptop_pipeline.py#L88) — function
- [test_batch_stops_at_first_approval](../../components/cortana-runtime/tests/test_laptop_pipeline.py#L94) — function
- [test_cloud_flags_cannot_enable_network_fallback](../../components/cortana-runtime/tests/test_laptop_pipeline.py#L108) — function
- [test_cancellation_interrupts_model_and_rejects_replay](../../components/cortana-runtime/tests/test_laptop_pipeline.py#L122) — function
- [test_screen_capture_is_single_use_and_expires](../../components/cortana-runtime/tests/test_laptop_pipeline.py#L142) — function
- [test_arbitrary_image_path_cannot_be_read](../../components/cortana-runtime/tests/test_laptop_pipeline.py#L155) — function
- [test_ollama_payload_is_local_bounded_and_no_thinking](../../components/cortana-runtime/tests/test_laptop_pipeline.py#L161) — function
- [test_direct_launch_does_not_need_model](../../components/cortana-runtime/tests/test_laptop_pipeline.py#L181) — function
- [test_social_greeting_never_waits_for_the_reasoning_model](../../components/cortana-runtime/tests/test_laptop_pipeline.py#L191) — function
- [test_compound_gmail_instruction_is_routed_to_drafting](../../components/cortana-runtime/tests/test_laptop_pipeline.py#L197) — function
- [test_partial_launch_is_not_executed](../../components/cortana-runtime/tests/test_laptop_pipeline.py#L204) — function
- [test_gmail_followup_keeps_recipient_and_formal_body_until_email_is_given](../../components/cortana-runtime/tests/test_laptop_pipeline.py#L210) — function
- [test_spoken_contact_correction_preserves_pending_message](../../components/cortana-runtime/tests/test_laptop_pipeline.py#L245) — function
- [test_open_voice_draft_does_not_treat_unrelated_speech_as_its_message](../../components/cortana-runtime/tests/test_laptop_pipeline.py#L264) — function
- [test_spoken_calendar_time_preserves_tomorrow_and_start_time](../../components/cortana-runtime/tests/test_laptop_pipeline.py#L278) — function
- [test_computer_input_routing_includes_inspection_and_focus](../../components/cortana-runtime/tests/test_laptop_pipeline.py#L284) — function
- [test_explicit_draft_intent_allows_manual_send_boundary](../../components/cortana-runtime/tests/test_laptop_pipeline.py#L300) — function
- [test_draft_mentions_are_not_automatic_authorization](../../components/cortana-runtime/tests/test_laptop_pipeline.py#L310) — function
- [test_draft_batch_stops_before_any_further_action](../../components/cortana-runtime/tests/test_laptop_pipeline.py#L314) — function
- [test_draft_requests_offer_no_generic_input](../../components/cortana-runtime/tests/test_laptop_pipeline.py#L327) — function
- [pending](../../components/cortana-runtime/tests/test_laptop_pipeline.py#L96) — function
- [unavailable](../../components/cortana-runtime/tests/test_laptop_pipeline.py#L111) — function
- [run](../../components/cortana-runtime/tests/test_laptop_pipeline.py#L114) — function
- [waiting](../../components/cortana-runtime/tests/test_laptop_pipeline.py#L124) — function
- [run](../../components/cortana-runtime/tests/test_laptop_pipeline.py#L128) — function
- [residency](../../components/cortana-runtime/tests/test_laptop_pipeline.py#L165) — function
- [handler](../../components/cortana-runtime/tests/test_laptop_pipeline.py#L169) — function
- [run](../../components/cortana-runtime/tests/test_laptop_pipeline.py#L172) — function
- [run](../../components/cortana-runtime/tests/test_laptop_pipeline.py#L184) — function
- [extract](../../components/cortana-runtime/tests/test_laptop_pipeline.py#L216) — function
- [prepare](../../components/cortana-runtime/tests/test_laptop_pipeline.py#L222) — function
- [run](../../components/cortana-runtime/tests/test_laptop_pipeline.py#L227) — function
- [prepare](../../components/cortana-runtime/tests/test_laptop_pipeline.py#L249) — function
- [draft](../../components/cortana-runtime/tests/test_laptop_pipeline.py#L316) — function

## tests/test_local_architecture.py

[Open source](../../components/cortana-runtime/tests/test_local_architecture.py)

Imports asyncio, json, sys, time, pathlib, unittest.mock, pytest, core, core.tool_registry, core.tools_loader, routers.local_architecture, routers, core.resource_broker, contextlib, core.browser_bridge, tools.files, core.config.

- [selected](../../components/cortana-runtime/tests/test_local_architecture.py#L16) — function
- [test_document_evidence_and_source_change_invalidation](../../components/cortana-runtime/tests/test_local_architecture.py#L24) — function
- [test_task_requires_exact_evidence_and_revision_and_invalidates](../../components/cortana-runtime/tests/test_local_architecture.py#L35) — function
- [test_permission_revocation_filters_prior_index](../../components/cortana-runtime/tests/test_local_architecture.py#L47) — function
- [test_reimport_invalidates_confirmed_deadline_from_previous_version](../../components/cortana-runtime/tests/test_local_architecture.py#L53) — function
- [test_failed_reimport_rolls_back_record_chunks_and_tasks](../../components/cortana-runtime/tests/test_local_architecture.py#L63) — function
- [test_due_reminder_read_does_not_silently_acknowledge](../../components/cortana-runtime/tests/test_local_architecture.py#L77) — function
- [test_audit_does_not_copy_source_or_message_payload](../../components/cortana-runtime/tests/test_local_architecture.py#L89) — function
- [test_periodic_workspace_capture_requires_opt_in_and_preserves_selection](../../components/cortana-runtime/tests/test_local_architecture.py#L101) — function
- [test_file_metadata_scan_continues_large_folder_and_filters_deleted_files](../../components/cortana-runtime/tests/test_local_architecture.py#L119) — function
- [test_conflicting_sources_remain_distinct](../../components/cortana-runtime/tests/test_local_architecture.py#L136) — function
- [test_workspace_revision_and_missing_item](../../components/cortana-runtime/tests/test_local_architecture.py#L145) — function
- [test_workspace_rejects_unsafe_pages](../../components/cortana-runtime/tests/test_local_architecture.py#L154) — function
- [test_workspace_executable_not_a_document](../../components/cortana-runtime/tests/test_local_architecture.py#L159) — function
- [test_restore_uses_review_and_exact_revision](../../components/cortana-runtime/tests/test_local_architecture.py#L165) — function
- [test_diagnostics_separates_observation_and_hypothesis](../../components/cortana-runtime/tests/test_local_architecture.py#L176) — function
- [test_diagnostics_distinguishes_commit_pressure_from_available_ram](../../components/cortana-runtime/tests/test_local_architecture.py#L183) — function
- [test_diagnostics_does_not_promote_one_disk_spike_to_sustained_pressure](../../components/cortana-runtime/tests/test_local_architecture.py#L191) — function
- [test_named_workspace_restore_reviews_exact_revision_without_model](../../components/cortana-runtime/tests/test_local_architecture.py#L199) — function
- [test_duplicate_workspace_names_require_exact_id](../../components/cortana-runtime/tests/test_local_architecture.py#L213) — function
- [test_shared_gpu_wait_has_explanatory_service_response](../../components/cortana-runtime/tests/test_local_architecture.py#L222) — function
- [test_restart_marks_unknown_and_invalidates_approvals](../../components/cortana-runtime/tests/test_local_architecture.py#L237) — function
- [test_browser_unknown_is_not_requeued](../../components/cortana-runtime/tests/test_local_architecture.py#L246) — function
- [test_global_stop_revokes_unconsumed_review_cards](../../components/cortana-runtime/tests/test_local_architecture.py#L256) — function
- [test_secret_vault_stores_only_dpapi_ciphertext](../../components/cortana-runtime/tests/test_local_architecture.py#L267) — function
- [test_document_tools_cannot_import_cortana_private_runtime](../../components/cortana-runtime/tests/test_local_architecture.py#L275) — function
- [test_repeated_stop_holds_gpu_lease_until_bounded_inference_exits](../../components/cortana-runtime/tests/test_local_architecture.py#L282) — function
- [fail](../../components/cortana-runtime/tests/test_local_architecture.py#L67) — function
- [occupied](../../components/cortana-runtime/tests/test_local_architecture.py#L227) — function
- [lease](../../components/cortana-runtime/tests/test_local_architecture.py#L287) — function
- [scenario](../../components/cortana-runtime/tests/test_local_architecture.py#L294) — function
- [inference](../../components/cortana-runtime/tests/test_local_architecture.py#L296) — function

## tests/test_message_drafts.py

[Open source](../../components/cortana-runtime/tests/test_message_drafts.py)

Imports asyncio, os, pathlib, sys, tempfile, threading, contextlib, unittest, unittest.mock, core.draft_adapters, core, queue, types, tools.message_drafts, core.tool_registry, core.processes, playwright.sync_api, urllib.parse.

- [DraftValidationTests](../../components/cortana-runtime/tests/test_message_drafts.py#L47) — class
- [BrowserFixtureTests](../../components/cortana-runtime/tests/test_message_drafts.py#L162) — class
- [test_payload_preserves_exact_message](../../components/cortana-runtime/tests/test_message_drafts.py#L48) — function
- [test_outgoing_script_policy_preserves_multilingual_recipient](../../components/cortana-runtime/tests/test_message_drafts.py#L53) — function
- [test_import_only_cleanup_never_terminates_other_session](../../components/cortana-runtime/tests/test_message_drafts.py#L61) — function
- [test_cancel_invalidates_operation_queued_behind_browser_lock](../../components/cortana-runtime/tests/test_message_drafts.py#L68) — function
- [test_cancelled_chat_stops_owned_browser](../../components/cortana-runtime/tests/test_message_drafts.py#L92) — function
- [test_cancel_wins_against_concurrent_browser_completion](../../components/cortana-runtime/tests/test_message_drafts.py#L112) — function
- [test_rejects_ambiguous_email_and_header_injection](../../components/cortana-runtime/tests/test_message_drafts.py#L134) — function
- [test_rejects_unknown_fields_and_platform](../../components/cortana-runtime/tests/test_message_drafts.py#L139) — function
- [test_tool_requires_explicit_communication_context](../../components/cortana-runtime/tests/test_message_drafts.py#L148) — function
- [test_worker_launch_environment_excludes_backend_credentials](../../components/cortana-runtime/tests/test_message_drafts.py#L156) — function
- [setUpClass](../../components/cortana-runtime/tests/test_message_drafts.py#L164) — function
- [tearDownClass](../../components/cortana-runtime/tests/test_message_drafts.py#L174) — function
- [setUp](../../components/cortana-runtime/tests/test_message_drafts.py#L178) — function
- [tearDown](../../components/cortana-runtime/tests/test_message_drafts.py#L188) — function
- [prepare](../../components/cortana-runtime/tests/test_message_drafts.py#L194) — function
- [test_gmail_exact_recipient_body_and_resume](../../components/cortana-runtime/tests/test_message_drafts.py#L197) — function
- [test_gmail_existing_draft_is_preserved](../../components/cortana-runtime/tests/test_message_drafts.py#L206) — function
- [test_gmail_changed_recipient_prevents_body_fill](../../components/cortana-runtime/tests/test_message_drafts.py#L213) — function
- [test_whatsapp_ambiguity_requires_opaque_selection](../../components/cortana-runtime/tests/test_message_drafts.py#L219) — function
- [test_whatsapp_preserves_existing_unsent_text](../../components/cortana-runtime/tests/test_message_drafts.py#L231) — function
- [test_instagram_requires_selected_verified_username](../../components/cortana-runtime/tests/test_message_drafts.py#L239) — function
- [test_instagram_wrong_active_username_refuses_fill](../../components/cortana-runtime/tests/test_message_drafts.py#L245) — function
- [test_login_resume_retains_exact_text](../../components/cortana-runtime/tests/test_message_drafts.py#L251) — function
- [test_modified_or_manually_sent_draft_is_not_recreated](../../components/cortana-runtime/tests/test_message_drafts.py#L260) — function
- [test_whatsapp_duplicate_names_fail_closed](../../components/cortana-runtime/tests/test_message_drafts.py#L267) — function
- [test_whatsapp_reordered_candidates_fail_closed](../../components/cortana-runtime/tests/test_message_drafts.py#L274) — function
- [test_expired_or_foreign_candidate_cannot_be_selected](../../components/cortana-runtime/tests/test_message_drafts.py#L282) — function
- [effects](../../components/cortana-runtime/tests/test_message_drafts.py#L72) — function
- [request](../../components/cortana-runtime/tests/test_message_drafts.py#L75) — function
- [waiting](../../components/cortana-runtime/tests/test_message_drafts.py#L98) — function
- [completes](../../components/cortana-runtime/tests/test_message_drafts.py#L118) — function
- [intercept](../../components/cortana-runtime/tests/test_message_drafts.py#L181) — function

## tests/test_security_tools.py

[Open source](../../components/cortana-runtime/tests/test_security_tools.py)

Imports asyncio, concurrent.futures, os, pathlib, sys, threading, time, json, subprocess, types, httpx, pytest, fastapi, core, core.permissions, core.security, core.tool_registry, core.communication_policy, tools, main.

- [request_auth](../../components/cortana-runtime/tests/test_security_tools.py#L36) — function
- [test_auth_required_and_valid_session](../../components/cortana-runtime/tests/test_security_tools.py#L52) — function
- [test_auth_fail_closed_if_launcher_did_not_supply_token](../../components/cortana-runtime/tests/test_security_tools.py#L60) — function
- [test_origin_rejected_even_with_valid_token](../../components/cortana-runtime/tests/test_security_tools.py#L67) — function
- [test_dns_rebinding_and_remote_client_rejected](../../components/cortana-runtime/tests/test_security_tools.py#L72) — function
- [test_duplicate_security_headers_rejected](../../components/cortana-runtime/tests/test_security_tools.py#L77) — function
- [test_every_real_api_route_requires_session_auth](../../components/cortana-runtime/tests/test_security_tools.py#L82) — function
- [isolated](../../components/cortana-runtime/tests/test_security_tools.py#L108) — function
- [test_component_path_boundaries_and_traversal](../../components/cortana-runtime/tests/test_security_tools.py#L127) — function
- [test_symlink_escape_is_rejected](../../components/cortana-runtime/tests/test_security_tools.py#L136) — function
- [test_sensitive_stores_are_blocked_inside_approved_root](../../components/cortana-runtime/tests/test_security_tools.py#L159) — function
- [test_project_resolution_cannot_bypass_roots](../../components/cortana-runtime/tests/test_security_tools.py#L164) — function
- [test_explicit_project_path_takes_priority_over_a_matching_alias](../../components/cortana-runtime/tests/test_security_tools.py#L171) — function
- [test_own_runtime_cannot_be_modified_even_if_drive_is_approved](../../components/cortana-runtime/tests/test_security_tools.py#L182) — function
- [test_system_edits_blocked_even_if_read_scope_contains_them](../../components/cortana-runtime/tests/test_security_tools.py#L189) — function
- [test_file_open_cannot_launch_executable_or_script](../../components/cortana-runtime/tests/test_security_tools.py#L201) — function
- [test_preview_does_not_read_outside_scope](../../components/cortana-runtime/tests/test_security_tools.py#L208) — function
- [pending_edit](../../components/cortana-runtime/tests/test_security_tools.py#L222) — function
- [test_reviewed_edit_applies_once_and_keeps_exact_backup](../../components/cortana-runtime/tests/test_security_tools.py#L228) — function
- [test_modified_file_invalidates_approved_diff](../../components/cortana-runtime/tests/test_security_tools.py#L241) — function
- [test_undo_requires_review_and_preserves_later_user_changes](../../components/cortana-runtime/tests/test_security_tools.py#L252) — function
- [test_undo_success_restores_original](../../components/cortana-runtime/tests/test_security_tools.py#L264) — function
- [test_invalid_tool_arguments_never_create_approval](../../components/cortana-runtime/tests/test_security_tools.py#L274) — function
- [test_confirmation_cannot_survive_desktop_session_restart](../../components/cortana-runtime/tests/test_security_tools.py#L287) — function
- [test_rejection_is_final](../../components/cortana-runtime/tests/test_security_tools.py#L297) — function
- [test_atomic_claim_only_executes_once_under_concurrent_approval](../../components/cortana-runtime/tests/test_security_tools.py#L307) — function
- [test_generic_input_never_runs_without_approval](../../components/cortana-runtime/tests/test_security_tools.py#L342) — function
- [test_generic_input_stale_window_prevents_execution](../../components/cortana-runtime/tests/test_security_tools.py#L353) — function
- [test_generic_input_cannot_target_cortana_processes_with_disguised_title](../../components/cortana-runtime/tests/test_security_tools.py#L364) — function
- [test_source_read_refuses_oversized_file_before_loading_contents](../../components/cortana-runtime/tests/test_security_tools.py#L373) — function
- [test_generic_input_cannot_bypass_draft_only_policy](../../components/cortana-runtime/tests/test_security_tools.py#L398) — function
- [test_previous_approval_cannot_send_after_browser_becomes_protected](../../components/cortana-runtime/tests/test_security_tools.py#L408) — function
- [test_unknown_managed_browser_owner_fails_closed](../../components/cortana-runtime/tests/test_security_tools.py#L421) — function
- [test_explicit_communication_task_cannot_use_generic_input](../../components/cortana-runtime/tests/test_security_tools.py#L429) — function
- [test_draft_tool_requires_explicit_user_intent_before_any_work](../../components/cortana-runtime/tests/test_security_tools.py#L438) — function
- [test_forged_confirmation_cannot_grant_communication_intent](../../components/cortana-runtime/tests/test_security_tools.py#L456) — function
- [test_keyboard_tool_refuses_window_switch_followed_by_enter](../../components/cortana-runtime/tests/test_security_tools.py#L468) — function
- [test_generic_text_cannot_embed_submit_or_navigation_keys](../../components/cortana-runtime/tests/test_security_tools.py#L474) — function
- [test_coordinate_click_cannot_target_a_different_window](../../components/cortana-runtime/tests/test_security_tools.py#L479) — function
- [test_model_website_requests_need_review_but_exact_user_launch_can_proceed](../../components/cortana-runtime/tests/test_security_tools.py#L497) — function
- [test_launch_exception_cannot_bypass_file_edit_review](../../components/cortana-runtime/tests/test_security_tools.py#L509) — function
- [test_cancelled_task_cannot_start_another_tool](../../components/cortana-runtime/tests/test_security_tools.py#L517) — function
- [test_keyboard_tool_refuses_unsupported_unicode_and_unbounded_input](../../components/cortana-runtime/tests/test_security_tools.py#L531) — function
- [test_external_launches_do_not_inherit_session_credentials](../../components/cortana-runtime/tests/test_security_tools.py#L537) — function
- [test_real_app_lifespan_refuses_missing_auth_token](../../components/cortana-runtime/tests/test_security_tools.py#L551) — function
- [test_backend_exits_when_desktop_or_intermediate_launcher_dies](../../components/cortana-runtime/tests/test_security_tools.py#L563) — function — Only toy subprocesses are launched and terminated; no live apps touched.
- [any_route](../../components/cortana-runtime/tests/test_security_tools.py#L42) — function
- [run](../../components/cortana-runtime/tests/test_security_tools.py#L45) — function
- [run](../../components/cortana-runtime/tests/test_security_tools.py#L95) — function
- [record](../../components/cortana-runtime/tests/test_security_tools.py#L213) — function
- [action](../../components/cortana-runtime/tests/test_security_tools.py#L312) — function
- [fail_read](../../components/cortana-runtime/tests/test_security_tools.py#L378) — function
- [ApiFunction](../../components/cortana-runtime/tests/test_security_tools.py#L481) — class
- [run](../../components/cortana-runtime/tests/test_security_tools.py#L554) — function
- [approve](../../components/cortana-runtime/tests/test_security_tools.py#L321) — function
- [__init__](../../components/cortana-runtime/tests/test_security_tools.py#L482) — function
- [__call__](../../components/cortana-runtime/tests/test_security_tools.py#L484) — function

## tests/test_voice_latency.py

[Open source](../../components/cortana-runtime/tests/test_voice_latency.py)

Imports asyncio, json, sys, pathlib, httpx, pytest, core.

- [test_reply_requires_full_gpu_residency](../../components/cortana-runtime/tests/test_voice_latency.py#L15) — function
- [test_cold_model_checks_placement_before_answer](../../components/cortana-runtime/tests/test_voice_latency.py#L35) — function
- [test_stop_unloads_warm_weights_before_releasing_shared_slot](../../components/cortana-runtime/tests/test_voice_latency.py#L55) — function
- [test_priority_pause_prevents_new_gpu_work](../../components/cortana-runtime/tests/test_voice_latency.py#L69) — function
- [handler](../../components/cortana-runtime/tests/test_voice_latency.py#L17) — function
- [run](../../components/cortana-runtime/tests/test_voice_latency.py#L24) — function
- [handler](../../components/cortana-runtime/tests/test_voice_latency.py#L37) — function
- [run](../../components/cortana-runtime/tests/test_voice_latency.py#L48) — function

## tests/test_voice_pipeline.py

[Open source](../../components/cortana-runtime/tests/test_voice_pipeline.py)

Imports io, sys, tempfile, threading, time, unittest, wave, contextlib, concurrent.futures, pathlib, types, unittest.mock, fastapi, fastapi.testclient, core, core.config, core.wakeword_match, routers, core.model_profiles.

- [wav_bytes](../../components/cortana-runtime/tests/test_voice_pipeline.py#L27) — function
- [WakeWordTests](../../components/cortana-runtime/tests/test_voice_pipeline.py#L37) — class
- [SpeechRecognitionTests](../../components/cortana-runtime/tests/test_voice_pipeline.py#L52) — class
- [SpeechSynthesisTests](../../components/cortana-runtime/tests/test_voice_pipeline.py#L166) — class
- [VoiceEndpointTests](../../components/cortana-runtime/tests/test_voice_pipeline.py#L187) — class
- [test_preserves_multilingual_command_exactly](../../components/cortana-runtime/tests/test_voice_pipeline.py#L38) — function
- [test_ordinary_words_or_mention_in_sentence_do_not_activate](../../components/cortana-runtime/tests/test_voice_pipeline.py#L44) — function
- [test_short_hindi_command_is_not_stripped](../../components/cortana-runtime/tests/test_voice_pipeline.py#L48) — function
- [setUp](../../components/cortana-runtime/tests/test_voice_pipeline.py#L53) — function
- [test_language_auto_and_hindi_are_forwarded_correctly](../../components/cortana-runtime/tests/test_voice_pipeline.py#L61) — function
- [test_low_confidence_noise_is_discarded](../../components/cortana-runtime/tests/test_voice_pipeline.py#L80) — function
- [test_model_loader_uses_local_files_only](../../components/cortana-runtime/tests/test_voice_pipeline.py#L87) — function
- [test_current_pyav_decodes_pcm_and_rejects_long_audio](../../components/cortana-runtime/tests/test_voice_pipeline.py#L97) — function
- [test_cuda_failure_retries_on_cpu_but_bad_audio_does_not](../../components/cortana-runtime/tests/test_voice_pipeline.py#L108) — function
- [test_wake_and_command_decode_are_serialized](../../components/cortana-runtime/tests/test_voice_pipeline.py#L122) — function
- [test_low_ram_uses_lightweight_local_speech_without_disabling_gpu_retry](../../components/cortana-runtime/tests/test_voice_pipeline.py#L143) — function
- [test_short_audio_uses_lightweight_decoder_without_cold_gpu_start](../../components/cortana-runtime/tests/test_voice_pipeline.py#L155) — function
- [test_voice_selection_matches_language_before_gender](../../components/cortana-runtime/tests/test_voice_pipeline.py#L167) — function
- [test_hindi_uses_local_piper_without_opening_sapi](../../components/cortana-runtime/tests/test_voice_pipeline.py#L176) — function
- [setUp](../../components/cortana-runtime/tests/test_voice_pipeline.py#L188) — function
- [test_empty_and_large_audio_rejected_before_transcription](../../components/cortana-runtime/tests/test_voice_pipeline.py#L193) — function
- [test_temp_recording_removed_on_decode_failure](../../components/cortana-runtime/tests/test_voice_pipeline.py#L202) — function
- [test_both_capture_modes_report_resource_errors_as_retryable](../../components/cortana-runtime/tests/test_voice_pipeline.py#L214) — function
- [test_preview_is_provisional_and_temp_audio_is_removed](../../components/cortana-runtime/tests/test_voice_pipeline.py#L221) — function
- [test_tts_limits_and_missing_voice_are_explicit](../../components/cortana-runtime/tests/test_voice_pipeline.py#L233) — function
- [test_wake_endpoint_preserves_hindi_remainder](../../components/cortana-runtime/tests/test_voice_pipeline.py#L243) — function
- [decode](../../components/cortana-runtime/tests/test_voice_pipeline.py#L126) — function
- [fail](../../components/cortana-runtime/tests/test_voice_pipeline.py#L204) — function
- [recognize](../../components/cortana-runtime/tests/test_voice_pipeline.py#L223) — function

## tools/__init__.py

[Open source](../../components/cortana-runtime/tools/__init__.py)


## tools/apps.py

[Open source](../../components/cortana-runtime/tools/apps.py)

Imports platform, subprocess, shutil, pathlib, core.alias_match, core.app_config, core.tool_registry, core.permissions, core.processes, time, psutil, win32con, win32gui, win32process, core, core.communication_targets.

- [AppNotApproved](../../components/cortana-runtime/tools/apps.py#L24) — class
- [open_application](../../components/cortana-runtime/tools/apps.py#L28) — function
- [close_application](../../components/cortana-runtime/tools/apps.py#L95) — function — Request a normal window close; never terminate processes or dismiss prompts.
- [visit](../../components/cortana-runtime/tools/apps.py#L121) — function
- [child](../../components/cortana-runtime/tools/apps.py#L135) — function

## tools/code.py

[Open source](../../components/cortana-runtime/tools/code.py)

Imports difflib, hashlib, json, os, tempfile, uuid, pathlib, core.app_config, core.config, core.permissions, core.tool_registry, core.tasks, core.pathresolve, tools.dev, tools.files.

- [PathNotApproved](../../components/cortana-runtime/tools/code.py#L63) — class
- [NotATextFile](../../components/cortana-runtime/tools/code.py#L67) — class
- [EditAmbiguous](../../components/cortana-runtime/tools/code.py#L71) — class
- [EditNotFound](../../components/cortana-runtime/tools/code.py#L75) — class
- [NoBackupFound](../../components/cortana-runtime/tools/code.py#L79) — class
- [EditStale](../../components/cortana-runtime/tools/code.py#L83) — class
- [_assert_approved](../../components/cortana-runtime/tools/code.py#L87) — function
- [_assert_text_file](../../components/cortana-runtime/tools/code.py#L96) — function
- [read_code_file](../../components/cortana-runtime/tools/code.py#L113) — function — Reads a source file with line numbers. start_line/end_line (1-based,
- [list_repo_files](../../components/cortana-runtime/tools/code.py#L153) — function — Lists files in a project folder (alias, full path, or a folder name
- [_walk_pruned](../../components/cortana-runtime/tools/code.py#L193) — function
- [_make_diff](../../components/cortana-runtime/tools/code.py#L204) — function
- [_read_source](../../components/cortana-runtime/tools/code.py#L218) — function
- [_replacement](../../components/cortana-runtime/tools/code.py#L230) — function
- [_prepare_edit](../../components/cortana-runtime/tools/code.py#L244) — function
- [_edit_preview](../../components/cortana-runtime/tools/code.py#L258) — function
- [_atomic_replace](../../components/cortana-runtime/tools/code.py#L262) — function — Stage completely, recheck the source, then replace in one filesystem step.
- [edit_code_file](../../components/cortana-runtime/tools/code.py#L280) — function — Replaces the first (and required-to-be-only) occurrence of `find`
- [_latest_edit](../../components/cortana-runtime/tools/code.py#L309) — function
- [_prepare_undo](../../components/cortana-runtime/tools/code.py#L324) — function
- [undo_last_edit](../../components/cortana-runtime/tools/code.py#L339) — function — Restores a file from the most recent backup edit_code_file made for

## tools/communication.py

[Open source](../../components/cortana-runtime/tools/communication.py)

Imports platform, subprocess, urllib.parse, core.processes, datetime, core.tool_registry, core.permissions, tools.reminders, core.communication_targets, core.app_config, pathlib, core.desktop_drafts.

- [BadRecipient](../../components/cortana-runtime/tools/communication.py#L39) — class
- [_launch](../../components/cortana-runtime/tools/communication.py#L43) — function — Hand a URL to Windows. Returns whether it actually launched.
- [_clean_phone](../../components/cortana-runtime/tools/communication.py#L51) — function — Digits only, with a default country code for bare 10-digit numbers.
- [compose_email](../../components/cortana-runtime/tools/communication.py#L65) — function
- [send_whatsapp](../../components/cortana-runtime/tools/communication.py#L107) — function
- [_calendar_range](../../components/cortana-runtime/tools/communication.py#L142) — function
- [_calendar_preview](../../components/cortana-runtime/tools/communication.py#L156) — function
- [create_calendar_event](../../components/cortana-runtime/tools/communication.py#L166) — function
- [_open_calendar_route](../../components/cortana-runtime/tools/communication.py#L194) — function
- [open_calendar](../../components/cortana-runtime/tools/communication.py#L209) — function
- [calendar_availability](../../components/cortana-runtime/tools/communication.py#L219) — function
- [open_telegram](../../components/cortana-runtime/tools/communication.py#L230) — function
- [stamp](../../components/cortana-runtime/tools/communication.py#L170) — function

## tools/computer.py

[Open source](../../components/cortana-runtime/tools/computer.py)

Imports platform, time, json, os, core.permissions, core.tool_registry, core.tasks, core.communication_policy, pyautogui, pygetwindow, ctypes, uiautomation.

- [NotOnWindows](../../components/cortana-runtime/tools/computer.py#L98) — class
- [BlockedKeyCombo](../../components/cortana-runtime/tools/computer.py#L102) — class
- [TerminalFocused](../../components/cortana-runtime/tools/computer.py#L106) — class
- [_require_windows](../../components/cortana-runtime/tools/computer.py#L110) — function
- [_pyautogui](../../components/cortana-runtime/tools/computer.py#L118) — function
- [_focused_window_title](../../components/cortana-runtime/tools/computer.py#L129) — function
- [_looks_like_terminal](../../components/cortana-runtime/tools/computer.py#L139) — function
- [list_windows](../../components/cortana-runtime/tools/computer.py#L146) — function — What's actually open right now, so the model can name a real window
- [focus_window](../../components/cortana-runtime/tools/computer.py#L161) — function — Bring a window to the front by (partial, case-insensitive) title.
- [press_keys](../../components/cortana-runtime/tools/computer.py#L204) — function — Press a key or key combination — 'ctrl+t', 'enter', 'alt+tab', 'f5'.
- [type_text](../../components/cortana-runtime/tools/computer.py#L245) — function — Type text into whatever currently has focus.
- [scroll_screen](../../components/cortana-runtime/tools/computer.py#L279) — function — Scroll the focused window. amount is roughly 'notches' of a wheel.
- [click_at](../../components/cortana-runtime/tools/computer.py#L294) — function — Click an exact screen coordinate. LAST RESORT.
- [_walk_controls](../../components/cortana-runtime/tools/computer.py#L319) — function — Collect named, on-screen controls from the UI Automation tree.
- [list_screen_elements](../../components/cortana-runtime/tools/computer.py#L358) — function — List the clickable controls in the focused window, by their REAL
- [click_element](../../components/cortana-runtime/tools/computer.py#L399) — function — Click a control in the focused window BY ITS NAME, using the real
- [browser_control](../../components/cortana-runtime/tools/computer.py#L481) — function — Drive the browser with keyboard shortcuts — the reliable path.
- [_window_snapshot](../../components/cortana-runtime/tools/computer.py#L509) — function — Bind generic input approval to a real window, process and rectangle.
- [_process_executable](../../components/cortana-runtime/tools/computer.py#L540) — function
- [_assert_point_target](../../components/cortana-runtime/tools/computer.py#L563) — function — A reviewed foreground window cannot authorize a click in another app.
- [_prepare_input](../../components/cortana-runtime/tools/computer.py#L580) — function
- [_confirmed_input](../../components/cortana-runtime/tools/computer.py#L605) — function
- [prepare](../../components/cortana-runtime/tools/computer.py#L581) — function
- [execute](../../components/cortana-runtime/tools/computer.py#L606) — function

## tools/dev.py

[Open source](../../components/cortana-runtime/tools/dev.py)

Imports os, platform, subprocess, urllib.parse, core.app_config, core.alias_match, core.pathresolve, core.tool_registry, core.permissions, core.processes, tools.files, shutil.

- [ProjectNotFound](../../components/cortana-runtime/tools/dev.py#L40) — class
- [_launch_url](../../components/cortana-runtime/tools/dev.py#L44) — function
- [open_github](../../components/cortana-runtime/tools/dev.py#L51) — function — Open a GitHub profile, repo, search, or a repo sub-page.
- [_resolve_project](../../components/cortana-runtime/tools/dev.py#L73) — function — Find a project folder: an alias, a full path, or a folder name under an approved root.
- [open_in_ide](../../components/cortana-runtime/tools/dev.py#L108) — function

## tools/documents.py

[Open source](../../components/cortana-runtime/tools/documents.py)

Imports pathlib, core.app_config, core.tool_registry, core.permissions, tools.files, pypdf, docx, openpyxl, pytesseract, pdf2image.

- [PathNotApproved](../../components/cortana-runtime/tools/documents.py#L32) — class
- [_assert_approved](../../components/cortana-runtime/tools/documents.py#L36) — function
- [_chunk](../../components/cortana-runtime/tools/documents.py#L45) — function
- [_payload](../../components/cortana-runtime/tools/documents.py#L52) — function — Chunks plus a truncation flag, sized for what the local model can read.
- [read_pdf](../../components/cortana-runtime/tools/documents.py#L65) — function
- [read_docx](../../components/cortana-runtime/tools/documents.py#L106) — function
- [read_xlsx](../../components/cortana-runtime/tools/documents.py#L125) — function

## tools/files.py

[Open source](../../components/cortana-runtime/tools/files.py)

Imports os, time, pathlib, core.app_config, core.pathresolve, core.tool_registry, core.permissions.

- [within_approved_roots](../../components/cortana-runtime/tools/files.py#L36) — function — Resolve symlinks/junctions and compare whole path components.
- [search_files](../../components/cortana-runtime/tools/files.py#L62) — function

## tools/folders.py

[Open source](../../components/cortana-runtime/tools/folders.py)

Imports os, platform, subprocess, core.alias_match, core.app_config, core.pathresolve, core.tool_registry, core.permissions, core.processes, tools.files.

- [FolderNotApproved](../../components/cortana-runtime/tools/folders.py#L33) — class
- [open_folder](../../components/cortana-runtime/tools/folders.py#L37) — function

## tools/local_architecture.py

[Open source](../../components/cortana-runtime/tools/local_architecture.py)

Imports core.permissions, core.tool_registry, core, datetime, core.browser_bridge.

- [register](../../components/cortana-runtime/tools/local_architecture.py#L8) — function
- [_finish_task_preview](../../components/cortana-runtime/tools/local_architecture.py#L40) — function
- [_task_preview](../../components/cortana-runtime/tools/local_architecture.py#L56) — function
- [_schedule_preview](../../components/cortana-runtime/tools/local_architecture.py#L83) — function
- [_restore_preview](../../components/cortana-runtime/tools/local_architecture.py#L100) — function
- [_switch_preview](../../components/cortana-runtime/tools/local_architecture.py#L129) — function
- [_browser_profiles](../../components/cortana-runtime/tools/local_architecture.py#L158) — function
- [_browser_tab](../../components/cortana-runtime/tools/local_architecture.py#L168) — function

## tools/memory.py

[Open source](../../components/cortana-runtime/tools/memory.py)

Imports core, core.recall, core.tool_registry, core.permissions.

- [remember_fact](../../components/cortana-runtime/tools/memory.py#L25) — function
- [recall_facts](../../components/cortana-runtime/tools/memory.py#L44) — function
- [forget_fact](../../components/cortana-runtime/tools/memory.py#L68) — function

## tools/message_drafts.py

[Open source](../../components/cortana-runtime/tools/message_drafts.py)

Imports core.desktop_drafts, core.draft_adapters, core.permissions, core.tasks, core.tool_registry.

- [open_communication_app](../../components/cortana-runtime/tools/message_drafts.py#L14) — function
- [prepare_message_draft](../../components/cortana-runtime/tools/message_drafts.py#L33) — function

## tools/openpath.py

[Open source](../../components/cortana-runtime/tools/openpath.py)

Imports os, platform, subprocess, pathlib, core.app_config, core.pathresolve, core.tool_registry, core.permissions, core.processes, tools.files.

- [PathNotApproved](../../components/cortana-runtime/tools/openpath.py#L39) — class
- [_resolve_existing](../../components/cortana-runtime/tools/openpath.py#L43) — function — The first variant of this path that exists (file or directory).
- [_within_roots](../../components/cortana-runtime/tools/openpath.py#L51) — function
- [open_path](../../components/cortana-runtime/tools/openpath.py#L55) — function

## tools/reminders.py

[Open source](../../components/cortana-runtime/tools/reminders.py)

Imports re, time, datetime, core, core.tool_registry, core.permissions.

- [TimeNotUnderstood](../../components/cortana-runtime/tools/reminders.py#L36) — class
- [_parse_clock](../../components/cortana-runtime/tools/reminders.py#L40) — function — '6pm', '18:30', '9 am' -> a datetime today (or tomorrow if past).
- [parse_when](../../components/cortana-runtime/tools/reminders.py#L59) — function — Natural-language time -> unix timestamp. Raises if not understood.
- [add_reminder](../../components/cortana-runtime/tools/reminders.py#L122) — function
- [list_reminders](../../components/cortana-runtime/tools/reminders.py#L136) — function
- [complete_reminder](../../components/cortana-runtime/tools/reminders.py#L144) — function

## tools/screenshot.py

[Open source](../../components/cortana-runtime/tools/screenshot.py)

Imports httpx, core.config, core, core.permissions, core.tool_registry.

- [take_screenshot](../../components/cortana-runtime/tools/screenshot.py#L9) — function
- [analyze_screenshot](../../components/cortana-runtime/tools/screenshot.py#L17) — function
- [look_at_screen](../../components/cortana-runtime/tools/screenshot.py#L46) — function

## tools/weather.py

[Open source](../../components/cortana-runtime/tools/weather.py)

Imports urllib.parse, httpx, core.tool_registry, core.permissions.

- [_describe](../../components/cortana-runtime/tools/weather.py#L22) — function
- [get_weather](../../components/cortana-runtime/tools/weather.py#L27) — function

## tools/web.py

[Open source](../../components/cortana-runtime/tools/web.py)

Imports platform, subprocess, urllib.parse, pathlib, core.tool_registry, core.permissions, core.processes, core.desktop_drafts, core.app_config, core.communication_targets.

- [close_website](../../components/cortana-runtime/tools/web.py#L69) — function
- [UnsafeUrl](../../components/cortana-runtime/tools/web.py#L79) — class
- [_normalize_url](../../components/cortana-runtime/tools/web.py#L83) — function
- [_build_url](../../components/cortana-runtime/tools/web.py#L112) — function
- [open_website](../../components/cortana-runtime/tools/web.py#L135) — function
- [_website_preview](../../components/cortana-runtime/tools/web.py#L167) — function

## Frontend and native source files

### browser-extension/popup.js

[Open source](../../components/cortana-runtime/browser-extension/popup.js)


### browser-extension/worker.js

[Open source](../../components/cortana-runtime/browser-extension/worker.js)

- [check](../../components/cortana-runtime/browser-extension/worker.js#L3)
- [safeUrl](../../components/cortana-runtime/browser-extension/worker.js#L7)
- [video](../../components/cortana-runtime/browser-extension/worker.js#L12)
- [execute](../../components/cortana-runtime/browser-extension/worker.js#L25)
- [matches](../../components/cortana-runtime/browser-extension/worker.js#L30)
- [tabs](../../components/cortana-runtime/browser-extension/worker.js#L52)
- [connect](../../components/cortana-runtime/browser-extension/worker.js#L154)
- [poll](../../components/cortana-runtime/browser-extension/worker.js#L181)

### desktop/electron/backend.cjs

[Open source](../../components/cortana-runtime/desktop/electron/backend.cjs)

- [delay](../../components/cortana-runtime/desktop/electron/backend.cjs#L7)
- [freePort](../../components/cortana-runtime/desktop/electron/backend.cjs#L9)
- [Backend](../../components/cortana-runtime/desktop/electron/backend.cjs#L20)

### desktop/electron/floating.js

[Open source](../../components/cortana-runtime/desktop/electron/floating.js)


### desktop/electron/main.cjs

[Open source](../../components/cortana-runtime/desktop/electron/main.cjs)

- [sleep](../../components/cortana-runtime/desktop/electron/main.cjs#L20)
- [senderRole](../../components/cortana-runtime/desktop/electron/main.cjs#L27)
- [requireMain](../../components/cortana-runtime/desktop/electron/main.cjs#L34)
- [sendMain](../../components/cortana-runtime/desktop/electron/main.cjs#L38)
- [showMain](../../components/cortana-runtime/desktop/electron/main.cjs#L42)
- [toggleMain](../../components/cortana-runtime/desktop/electron/main.cjs#L49)
- [protectWindow](../../components/cortana-runtime/desktop/electron/main.cjs#L55)
- [settingsPath](../../components/cortana-runtime/desktop/electron/main.cjs#L61)
- [saveSettings](../../components/cortana-runtime/desktop/electron/main.cjs#L63)
- [currentSettings](../../components/cortana-runtime/desktop/electron/main.cjs#L69)
- [applyLogin](../../components/cortana-runtime/desktop/electron/main.cjs#L78)
- [floatPosition](../../components/cortana-runtime/desktop/electron/main.cjs#L85)
- [registerShortcut](../../components/cortana-runtime/desktop/electron/main.cjs#L90)
- [createWindows](../../components/cortana-runtime/desktop/electron/main.cjs#L97)
- [createTray](../../components/cortana-runtime/desktop/electron/main.cjs#L153)
- [i](../../components/cortana-runtime/desktop/electron/main.cjs#L159)
- [captureScreen](../../components/cortana-runtime/desktop/electron/main.cjs#L175)
- [captureAndShow](../../components/cortana-runtime/desktop/electron/main.cjs#L199)
- [proxyRequest](../../components/cortana-runtime/desktop/electron/main.cjs#L205)
- [installIpc](../../components/cortana-runtime/desktop/electron/main.cjs#L256)

### desktop/electron/preload.cjs

[Open source](../../components/cortana-runtime/desktop/electron/preload.cjs)

- [listen](../../components/cortana-runtime/desktop/electron/preload.cjs#L2)
- [listener](../../components/cortana-runtime/desktop/electron/preload.cjs#L3)

### desktop/electron/security.cjs

[Open source](../../components/cortana-runtime/desktop/electron/security.cjs)

- [validateRequest](../../components/cortana-runtime/desktop/electron/security.cjs#L24)
- [trustedUrl](../../components/cortana-runtime/desktop/electron/security.cjs#L46)
- [resolveAsset](../../components/cortana-runtime/desktop/electron/security.cjs#L62)
- [loginOptions](../../components/cortana-runtime/desktop/electron/security.cjs#L77)
- [loginEntryEnabled](../../components/cortana-runtime/desktop/electron/security.cjs#L86)
- [samePath](../../components/cortana-runtime/desktop/electron/security.cjs#L87)

### desktop/src/api.js

[Open source](../../components/cortana-runtime/desktop/src/api.js)

- [apiFetch](../../components/cortana-runtime/desktop/src/api.js#L3)
- [onAbort](../../components/cortana-runtime/desktop/src/api.js#L23)

### desktop/src/App.jsx

[Open source](../../components/cortana-runtime/desktop/src/App.jsx)

- [App](../../components/cortana-runtime/desktop/src/App.jsx#L34)
- [updateState](../../components/cortana-runtime/desktop/src/App.jsx#L134)
- [checkStatus](../../components/cortana-runtime/desktop/src/App.jsx#L139)
- [checkDue](../../components/cortana-runtime/desktop/src/App.jsx#L173)
- [onKey](../../components/cortana-runtime/desktop/src/App.jsx#L208)
- [captureScreen](../../components/cortana-runtime/desktop/src/App.jsx#L235)
- [changeSetting](../../components/cortana-runtime/desktop/src/App.jsx#L248)

### desktop/src/DocumentReminders.jsx

[Open source](../../components/cortana-runtime/desktop/src/DocumentReminders.jsx)

- [DocumentReminders](../../components/cortana-runtime/desktop/src/DocumentReminders.jsx#L4)
- [refresh](../../components/cortana-runtime/desktop/src/DocumentReminders.jsx#L9)

### desktop/src/DraftCard.jsx

[Open source](../../components/cortana-runtime/desktop/src/DraftCard.jsx)

- [DraftCard](../../components/cortana-runtime/desktop/src/DraftCard.jsx#L5)
- [run](../../components/cortana-runtime/desktop/src/DraftCard.jsx#L13)
- [openApp](../../components/cortana-runtime/desktop/src/DraftCard.jsx#L29)

### desktop/src/draftState.js

[Open source](../../components/cortana-runtime/desktop/src/draftState.js)

- [platformInfo](../../components/cortana-runtime/desktop/src/draftState.js#L7)
- [connectionLabel](../../components/cortana-runtime/desktop/src/draftState.js#L11)
- [draftLabel](../../components/cortana-runtime/desktop/src/draftState.js#L22)
- [draftRequest](../../components/cortana-runtime/desktop/src/draftState.js#L32)
- [previewParts](../../components/cortana-runtime/desktop/src/draftState.js#L47)
- [stoppedDraft](../../components/cortana-runtime/desktop/src/draftState.js#L55)

### desktop/src/IntegrationsPanel.jsx

[Open source](../../components/cortana-runtime/desktop/src/IntegrationsPanel.jsx)

- [IntegrationsPanel](../../components/cortana-runtime/desktop/src/IntegrationsPanel.jsx#L6)
- [open](../../components/cortana-runtime/desktop/src/IntegrationsPanel.jsx#L42)
- [prepare](../../components/cortana-runtime/desktop/src/IntegrationsPanel.jsx#L57)

### desktop/src/LocalResult.jsx

[Open source](../../components/cortana-runtime/desktop/src/LocalResult.jsx)

- [localTime](../../components/cortana-runtime/desktop/src/LocalResult.jsx#L1)
- [LocalResult](../../components/cortana-runtime/desktop/src/LocalResult.jsx#L5)

### desktop/src/main.jsx

[Open source](../../components/cortana-runtime/desktop/src/main.jsx)


### desktop/src/Orb.jsx

[Open source](../../components/cortana-runtime/desktop/src/Orb.jsx)

- [makeSpherePoints](../../components/cortana-runtime/desktop/src/Orb.jsx#L34)
- [Orb](../../components/cortana-runtime/desktop/src/Orb.jsx#L51)
- [frame](../../components/cortana-runtime/desktop/src/Orb.jsx#L79)
- [depth](../../components/cortana-runtime/desktop/src/Orb.jsx#L133)
- [alpha](../../components/cortana-runtime/desktop/src/Orb.jsx#L162)

### desktop/src/pcmCapture.js

[Open source](../../components/cortana-runtime/desktop/src/pcmCapture.js)

- [wavBlob](../../components/cortana-runtime/desktop/src/pcmCapture.js#L3)
- [word](../../components/cortana-runtime/desktop/src/pcmCapture.js#L7)
- [recordPcmClip](../../components/cortana-runtime/desktop/src/pcmCapture.js#L21)
- [cleanup](../../components/cortana-runtime/desktop/src/pcmCapture.js#L32)
- [finish](../../components/cortana-runtime/desktop/src/pcmCapture.js#L36)
- [cancel](../../components/cortana-runtime/desktop/src/pcmCapture.js#L49)
- [spokenSummary](../../components/cortana-runtime/desktop/src/pcmCapture.js#L71)
- [speechQueue](../../components/cortana-runtime/desktop/src/pcmCapture.js#L84)
- [reset](../../components/cortana-runtime/desktop/src/pcmCapture.js#L91)
- [deliver](../../components/cortana-runtime/desktop/src/pcmCapture.js#L92)
- [clean](../../components/cortana-runtime/desktop/src/pcmCapture.js#L129)
- [done](../../components/cortana-runtime/desktop/src/pcmCapture.js#L130)
- [expire](../../components/cortana-runtime/desktop/src/pcmCapture.js#L132)

### desktop/src/screenIntent.js

[Open source](../../components/cortana-runtime/desktop/src/screenIntent.js)

- [wantsScreenContext](../../components/cortana-runtime/desktop/src/screenIntent.js#L3)

### desktop/src/SidePanel.jsx

[Open source](../../components/cortana-runtime/desktop/src/SidePanel.jsx)

- [timeAgo](../../components/cortana-runtime/desktop/src/SidePanel.jsx#L9)
- [SidePanel](../../components/cortana-runtime/desktop/src/SidePanel.jsx#L17)
- [forget](../../components/cortana-runtime/desktop/src/SidePanel.jsx#L48)
- [completeReminder](../../components/cortana-runtime/desktop/src/SidePanel.jsx#L56)

### desktop/src/useVoicePipeline.js

[Open source](../../components/cortana-runtime/desktop/src/useVoicePipeline.js)

- [delay](../../components/cortana-runtime/desktop/src/useVoicePipeline.js#L12)
- [abortError](../../components/cortana-runtime/desktop/src/useVoicePipeline.js#L13)
- [isUsableSpeech](../../components/cortana-runtime/desktop/src/useVoicePipeline.js#L17)
- [value](../../components/cortana-runtime/desktop/src/useVoicePipeline.js#L18)
- [recordClip](../../components/cortana-runtime/desktop/src/useVoicePipeline.js#L23)
- [settle](../../components/cortana-runtime/desktop/src/useVoicePipeline.js#L33)
- [finish](../../components/cortana-runtime/desktop/src/useVoicePipeline.js#L44)
- [cancel](../../components/cortana-runtime/desktop/src/useVoicePipeline.js#L51)
- [useVoicePipeline](../../components/cortana-runtime/desktop/src/useVoicePipeline.js#L74)
- [ensureStream](../../components/cortana-runtime/desktop/src/useVoicePipeline.js#L195)
- [capture](../../components/cortana-runtime/desktop/src/useVoicePipeline.js#L235)
- [requestJson](../../components/cortana-runtime/desktop/src/useVoicePipeline.js#L257)
- [transcribe](../../components/cortana-runtime/desktop/src/useVoicePipeline.js#L276)
- [speakForOperation](../../components/cortana-runtime/desktop/src/useVoicePipeline.js#L289)
- [stopAudio](../../components/cortana-runtime/desktop/src/useVoicePipeline.js#L330)
- [chatWithOperation](../../components/cortana-runtime/desktop/src/useVoicePipeline.js#L353)
- [sendTextMessage](../../components/cortana-runtime/desktop/src/useVoicePipeline.js#L375)
- [pushToTalkStart](../../components/cortana-runtime/desktop/src/useVoicePipeline.js#L385)
- [pushToTalkStop](../../components/cortana-runtime/desktop/src/useVoicePipeline.js#L409)
- [abortPreview](../../components/cortana-runtime/desktop/src/useVoicePipeline.js#L493)
- [run](../../components/cortana-runtime/desktop/src/useVoicePipeline.js#L534)

### desktop/src/voiceAddressing.js

[Open source](../../components/cortana-runtime/desktop/src/voiceAddressing.js)

- [commandWindowOpen](../../components/cortana-runtime/desktop/src/voiceAddressing.js#L4)
- [addressedSpeech](../../components/cortana-runtime/desktop/src/voiceAddressing.js#L8)

### desktop/src/Workbench.jsx

[Open source](../../components/cortana-runtime/desktop/src/Workbench.jsx)

- [Workbench](../../components/cortana-runtime/desktop/src/Workbench.jsx#L5)
- [stop](../../components/cortana-runtime/desktop/src/Workbench.jsx#L29)
- [perform](../../components/cortana-runtime/desktop/src/Workbench.jsx#L36)
- [decide](../../components/cortana-runtime/desktop/src/Workbench.jsx#L50)
- [selectedItems](../../components/cortana-runtime/desktop/src/Workbench.jsx#L63)
- [saveWorkspace](../../components/cortana-runtime/desktop/src/Workbench.jsx#L70)

### desktop/tests/api.test.mjs

[Open source](../../components/cortana-runtime/desktop/tests/api.test.mjs)


### desktop/tests/drafts.test.mjs

[Open source](../../components/cortana-runtime/desktop/tests/drafts.test.mjs)


### desktop/tests/electron-acceptance.cjs

[Open source](../../components/cortana-runtime/desktop/tests/electron-acceptance.cjs)

- [sleep](../../components/cortana-runtime/desktop/tests/electron-acceptance.cjs#L19)

### desktop/tests/electron-integrations.cjs

[Open source](../../components/cortana-runtime/desktop/tests/electron-integrations.cjs)

- [sleep](../../components/cortana-runtime/desktop/tests/electron-integrations.cjs#L61)

### desktop/tests/electron-smoke.cjs

[Open source](../../components/cortana-runtime/desktop/tests/electron-smoke.cjs)

- [sleep](../../components/cortana-runtime/desktop/tests/electron-smoke.cjs#L21)

### desktop/tests/electron-startup.cjs

[Open source](../../components/cortana-runtime/desktop/tests/electron-startup.cjs)


### desktop/tests/screenIntent.test.mjs

[Open source](../../components/cortana-runtime/desktop/tests/screenIntent.test.mjs)


### desktop/tests/security.test.cjs

[Open source](../../components/cortana-runtime/desktop/tests/security.test.cjs)

- [check](../../components/cortana-runtime/desktop/tests/security.test.cjs#L67)

### desktop/tests/voice-addressing.test.mjs

[Open source](../../components/cortana-runtime/desktop/tests/voice-addressing.test.mjs)


### desktop/tests/voice.test.mjs

[Open source](../../components/cortana-runtime/desktop/tests/voice.test.mjs)

- [FakeRecorder](../../components/cortana-runtime/desktop/tests/voice.test.mjs#L5)
- [NeverStart](../../components/cortana-runtime/desktop/tests/voice.test.mjs#L46)
- [BrokenRecorder](../../components/cortana-runtime/desktop/tests/voice.test.mjs#L54)

### desktop/tests/workspace-extension.test.cjs

[Open source](../../components/cortana-runtime/desktop/tests/workspace-extension.test.cjs)

- [extension](../../components/cortana-runtime/desktop/tests/workspace-extension.test.cjs#L7)
- [command](../../components/cortana-runtime/desktop/tests/workspace-extension.test.cjs#L27)

### desktop/vite.config.js

[Open source](../../components/cortana-runtime/desktop/vite.config.js)


### scripts/smoke_live_pipeline.cjs

[Open source](../../components/cortana-runtime/scripts/smoke_live_pipeline.cjs)

- [request](../../components/cortana-runtime/scripts/smoke_live_pipeline.cjs#L17)
- [chat](../../components/cortana-runtime/scripts/smoke_live_pipeline.cjs#L26)
