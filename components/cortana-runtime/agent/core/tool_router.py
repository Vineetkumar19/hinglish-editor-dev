"""Pick which tools to offer the model for a given message.

Why this exists: every tool's JSON schema is sent to Ollama on *every*
request, and again on every follow-up round. At 24 tools that's roughly
3-4k tokens of schema before the conversation even starts. On a 3B model
running on a laptop CPU, prompt processing at that size costs tens of
seconds per round — and with multi-round tool calling, minutes per reply.
It also measurably hurts accuracy: a small model given 24 near-identical
"open something" tools picks the wrong one far more often than one given
five.

So: score the tools against what the user actually said, and send a small
relevant subset. A core set is always included so basic conversation and
memory always work, and if nothing matches we fall back to the core set
plus the most generally useful tools rather than sending everything.

This is a latency/accuracy optimization only — it never grants access to
anything. Dispatch still enforces the full permission check regardless of
what was offered.
"""

from core.tool_registry import REGISTRY

# Always available: cheap, and needed for ordinary conversation.
CORE_TOOLS = {"recall_facts", "remember_fact"}

MILESTONE_TOOLS = {
    "index_document", "search_documents", "answer_with_sources", "list_document_tasks",
    "propose_document_task", "confirm_document_task", "find_workspace", "preview_restore",
    "restore_workspace", "sample_system", "compare_diagnostics", "model_profiles", "switch_model_profile",
    "capture_workspace", "capture_browser_workspace", "list_browser_profiles", "configure_workspace_capture",
    "index_file_metadata", "search_file_index", "build_document_embeddings", "semantic_document_search",
    "inspect_local_data", "export_local_data", "prune_local_history", "forget_document", "acknowledge_document_task",
    "open_path", "open_folder", "open_application", "close_application", "open_website",
    "search_files",
    "read_code_file", "list_repo_files", "edit_code_file", "undo_last_edit",
    "list_windows", "focus_window", "press_keys", "type_text", "scroll_screen",
    "list_screen_elements", "click_element", "click_at", "browser_control",
    "prepare_message_draft",
}
# Memory/integrations are intentionally not offered by this first laptop-control
# workflow. Retrieved memories remain untrusted context in the system prompt.
CORE_TOOLS = set()

# Words that suggest a tool. Matching is substring-based on the lowercased
# message, so "emails" matches "email".
TOOL_KEYWORDS: dict[str, tuple[str, ...]] = {
    "capture_workspace": ("save workspace", "save this workspace", "remember workspace"),
    "capture_browser_workspace": ("save workspace", "save this workspace", "capture tabs", "save browser"),
    "list_browser_profiles": ("save workspace", "capture tabs", "save this workspace", "browser profile"),
    "configure_workspace_capture": ("periodic capture", "periodic snapshot", "automatic snapshot"),
    "index_file_metadata": ("index folder", "scan folder", "metadata index"),
    "search_file_index": ("indexed files", "find filename", "indexed folder"),
    "build_document_embeddings": ("semantic index", "embed document"),
    "semantic_document_search": ("semantic search", "search by meaning"),
    "inspect_local_data": ("stored data", "local data", "retention"),
    "export_local_data": ("export local data", "export my data"),
    "prune_local_history": ("prune history", "remove old receipts"),
    "forget_document": ("forget document", "remove from index"),
    "acknowledge_document_task": ("acknowledge reminder", "dismiss reminder"),
    "index_document": ("index document", "import document", "index this"),
    "search_documents": ("warranty", "receipt", "invoice", "selected documents"),
    "answer_with_sources": ("warranty", "proof", "document evidence", "source"),
    "list_document_tasks": ("document tasks", "deadlines", "overdue"),
    "propose_document_task": ("deadline", "task from", "expiry"),
    "confirm_document_task": ("confirm task", "approve deadline"),
    "find_workspace": ("workspace", "resume", "gcp learning"),
    "preview_restore": ("workspace", "resume", "gcp learning"),
    "restore_workspace": ("restore workspace", "resume workspace", "review my gcp", "resume my gcp", "gcp learning"),
    "sample_system": ("hanging", "slow laptop", "diagnose", "memory pressure", "slowdown"),
    "compare_diagnostics": ("compare diagnostics", "before and after"),
    "model_profiles": ("model profiles", "installed models", "9b", "14b"),
    "switch_model_profile": ("switch model", "use 14b", "use 9b"),
    "close_application": ("close", "band karo", "exit app"),
    "prepare_message_draft": ("whatsapp", "gmail", "email", "instagram", "message", "draft",
                              "व्हाट्सएप", "व्हाट्सऐप", "इंस्टाग्राम", "ईमेल", "मेल", "मैसेज"),
    "open_path": ("open", "c:", "d:", "e:", "f:", ".pdf", ".docx", ".xlsx", ".txt", "path", "file"),
    "open_folder": ("folder", "downloads", "documents", "desktop", "pictures", "screenshots",
                    "videos", "music", "drive", "directory"),
    "open_application": ("open", "launch", "start", "app", "notepad", "calculator", "chrome",
                         "vs code", "vscode", "intellij", "postman", "workbench", "whatsapp",
                         "capcut", "explorer", "terminal", "powershell", "cmd", "task manager",
                         "telegram", "paint", "settings"),
    "open_website": ("search", "google", "youtube", "wikipedia", "website", "browser", "chrome",
                     "incognito", "web", "site", "url", "http", "look up", "browse", "amazon",
                     "maps", "news", "linkedin", "instagram", "netflix", "spotify"),
    "search_files": ("find", "search", "locate", "file", "files", "pdf", "docx", "xlsx",
                     "document", "where is", "look for"),
    "read_pdf": ("pdf", "read", "summarize", "summary", "document", "contents"),
    "read_docx": ("docx", "word", "read", "summarize", "summary", "document"),
    "read_xlsx": ("xlsx", "excel", "spreadsheet", "sheet", "read", "summarize"),
    # look_at_screen is the one the model should reach for — it does both
    # steps itself. The two-step pair below is kept for the rare case of
    # re-asking about an already-captured image, and deliberately scores
    # lower on the everyday phrasings.
    "look_at_screen": ("screen", "see", "look", "watching", "what's on", "whats on", "showing",
                       "visible", "in front of", "right now", "this error", "what am i",
                       "can you see", "can u see", "reading", "display",
                       # "I can't find the X option" — a question about what's
                       # currently on screen, even though it never says "screen".
                       "can't find", "cant find", "where do i", "which option", "guide me",
                       "help me find", "premiere", "after effects", "photoshop"),
    "take_screenshot": ("screenshot", "capture", "screengrab"),
    "analyze_screenshot": ("screenshot", "that image", "that capture"),
    "get_weather": ("weather", "temperature", "rain", "forecast", "hot", "cold", "humid", "sunny"),
    "remember_fact": ("remember", "note that", "don't forget", "keep in mind", "my name is",
                      "save this"),
    # "my" used to be in here. It matches "can you see my screen", "my file",
    # "my code" — i.e. most sentences — so recall_facts scored on requests
    # that had nothing to do with memory and the model picked it over the
    # right tool. Keywords must be *distinctive*, not merely common.
    "recall_facts": ("remember", "recall", "what do you know", "did i tell", "forget"),
    "forget_fact": ("forget", "delete memory", "remove memory"),
    "add_reminder": ("remind", "reminder", "alarm", "alert me", "don't let me forget", "later"),
    "list_reminders": ("reminder", "reminders", "coming up", "my day", "schedule", "pending",
                       "todo", "to do"),
    "complete_reminder": ("done", "completed", "finished", "mark", "reminder"),
    "compose_email": ("email", "mail", "gmail", "write to", "send to", "message to", "compose"),
    "send_whatsapp": ("whatsapp", "message", "text", "msg", "send", "tell"),
    "create_calendar_event": ("calendar", "schedule", "meeting", "event", "appointment", "book",
                              "sync", "call at"),
    "open_calendar": ("calendar", "schedule", "my day", "agenda", "meetings"),
    "calendar_availability": ("calendar availability", "free on", "busy on", "calendar conflicts"),
    "find_browser_tab": ("find tab", "search tabs", "find browser tab"),
    "focus_browser_tab": ("focus tab", "switch to tab"),
    "read_browser_tab": ("read tab", "read this page"),
    "open_telegram": ("telegram",),
    "open_github": ("github", "repo", "repository", "pull request", "issues", "commit", "git"),
    "open_in_ide": ("vs code", "vscode", "intellij", "pycharm", "webstorm", "ide",
                    "open project"),
    "read_code_file": ("code", "file", "function", "class", "error", "bug", "fix", "line",
                       "script", "traceback", "exception", "read this", "what's wrong",
                       "whats wrong", "look at"),
    "list_repo_files": ("repo", "repository", "project", "files", "codebase", "structure",
                        "what's in", "whats in"),
    "edit_code_file": ("fix", "change", "edit", "update the code", "bug", "error", "wrong",
                       "replace", "rewrite", "correct this"),
    "undo_last_edit": ("undo", "revert", "that broke", "roll back", "put it back"),
    # --- Computer control (hands-free operation) ---------------------------
    "list_windows": ("window", "windows", "open apps", "what's open", "whats open", "switch to"),
    "focus_window": ("switch to", "go to", "focus", "bring up", "window", "minimize", "maximize"),
    "press_keys": ("press", "key", "shortcut", "ctrl", "alt", "enter", "escape", "tab", "hit",
                   "save", "copy", "paste", "undo", "select all", "f5", "refresh"),
    "type_text": ("type", "write", "enter text", "fill", "input", "search for", "put in"),
    "scroll_screen": ("scroll", "scroll down", "scroll up", "go down", "go up", "page down"),
    "list_screen_elements": ("click", "button", "option", "menu", "what can i", "clickable",
                             "element", "where is", "find the", "video", "link", "which one",
                             "third", "second", "first", "fourth"),
    "click_element": ("click", "press the", "select", "choose", "tap", "button", "open the",
                      "hit the", "play", "video", "link", "third", "second", "first", "fourth",
                      "recommended", "result"),
    "click_at": ("click at", "coordinate", "position"),
    "browser_control": ("tab", "browser", "chrome", "new tab", "close tab", "switch tab", "back",
                        "forward", "reload", "refresh", "address bar", "youtube", "website"),
}

# When nothing matches — often just conversation — offer a small, cheap
# set rather than everything. Kept short on purpose: chit-chat shouldn't
# pay the cost of a large tool payload.
# Ordinary conversation and knowledge questions do not need launch schemas.
FALLBACK_TOOLS = ()

MAX_TOOLS = 10

# A frontier cloud model doesn't need this narrowing for accuracy — but
# Gemini's OpenAI-compatibility function-calling layer is documented as
# strict and failure-prone with large/complex tool payloads (multiple
# reported 400s tied specifically to `tools`, independent of this project).
# Kept well above the local budget (relevant tools should basically always
# be included), but capped rather than "send literally everything" until
# that's confirmed safe.
MAX_TOOLS_CLOUD = 14


def score_tools(message: str) -> dict[str, int]:
    text = (message or "").lower()
    translations = {
        "खोल": " open ", "खोलो": " open ", "kholo": " open ",
        "स्क्रीन": " screen ", "दिख": " screen ", "समझा": " explain ",
        "एरर": " error ", "गलती": " error ", "ठीक": " fix ",
        "कोड": " code ", "बदल": " edit ", "ढूंढ": " find ",
        "फाइल": " file ", "फ़ाइल": " file ", "पढ़": " read ",
        "दबाओ": " press ", "लिखो": " type ", "क्लिक": " click ",
    }
    for word, hint in translations.items():
        if word in text:
            text += hint
    scores: dict[str, int] = {}
    for name, keywords in TOOL_KEYWORDS.items():
        if name not in REGISTRY or name not in MILESTONE_TOOLS:
            continue
        hits = sum(1 for kw in keywords if kw in text)
        if hits:
            scores[name] = hits
    return scores


def select_tools(message: str, max_tools: int | None = None) -> list[dict]:
    """Tool specs worth offering this turn.

    When a cloud model is doing the reasoning, offer everything — see
    MAX_TOOLS_CLOUD. When a small local model is, narrow aggressively.
    """
    from core.config import settings
    from core.tool_registry import to_ollama_tools

    if max_tools is None:
        max_tools = MAX_TOOLS

    scores = score_tools(message)
    # "Fix this setting" needs the live settings controls. The general word
    # "fix" by itself must not turn a settings request into a source-code edit.
    import re
    if (re.search(r'\bsettings?\b|सेटिंग', message, re.I)
            and not re.search(r'\b(?:code|source|script|file|repo|project|function)\b|कोड|फाइल', message, re.I)):
        for name in ("read_code_file", "edit_code_file", "list_repo_files"):
            scores.pop(name, None)
        for name in ("list_screen_elements", "click_element"):
            if name in REGISTRY:
                scores[name] = max(scores.get(name, 0), 2)

    chosen: list[str] = []
    for name in sorted(scores, key=lambda n: (-scores[n], n)):
        if len(chosen) >= max_tools:
            break
        chosen.append(name)

    # With a big budget (cloud), top up with everything else rather than
    # sending only keyword matches — the model should be able to reach a tool
    # whose name nobody thought to write a keyword for.
    if max_tools >= MAX_TOOLS_CLOUD:
        for name in REGISTRY:
            if name not in MILESTONE_TOOLS:
                continue
            if len(chosen) >= max_tools:
                break
            if name not in chosen:
                chosen.append(name)

    if not chosen:
        chosen = [t for t in FALLBACK_TOOLS if t in REGISTRY][:max_tools]

    input_tools = {"press_keys", "type_text", "scroll_screen", "click_element", "click_at", "browser_control"}
    companions = []
    if input_tools.intersection(chosen):
        companions = ["list_windows", "focus_window"]
        if {"click_element", "click_at"}.intersection(chosen):
            companions.append("list_screen_elements")
    if companions:
        companions = [name for name in companions if name in REGISTRY]
        chosen = companions + [name for name in chosen if name not in companions][:max_tools - len(companions)]

    # A source edit needs the actual file, not a guess based on screenshot
    # pixels. Keep discovery and reading available even in short "fix this"
    # requests, with the reviewed edit tool following those prerequisites.
    if "edit_code_file" in chosen:
        prerequisites = [name for name in ("search_files", "read_code_file") if name in REGISTRY]
        chosen = prerequisites + [name for name in chosen if name not in prerequisites][:max_tools - len(prerequisites)]

    # Core tools are always on the table, even if they displace a weak match.
    for name in CORE_TOOLS:
        if name in REGISTRY and name not in chosen:
            chosen.append(name)

    return to_ollama_tools(chosen)
