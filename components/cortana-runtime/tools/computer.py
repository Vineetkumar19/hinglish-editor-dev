"""Computer Control Layer — the shared "do what my mouse would do" toolkit.

This is the piece the architecture doc calls Phase 1, and every later
specialist (career agent filling a form, content agent driving an editor,
entertainment agent picking a video) is meant to call these tools rather
than growing its own private copy of mouse/keyboard/window handling.

DESIGN: structured first, pixels last.
=====================================
There are three ways to click something on screen, and they are NOT equally
good. In order of preference:

  1. Keyboard shortcut     — Ctrl+T for a new tab, Ctrl+3 for the 3rd tab.
                             Useful when the correct window is verified.
  2. UI Automation tree    — Windows exposes an accessibility tree with the
                             real name and real screen rectangle of every
                             control. "Click the button called Subscribe"
                             becomes an exact lookup, not a guess.
  3. Raw coordinates       — click_at(x, y). Last resort, because a vision
                             model asked "where is the button?" gives you
                             an approximate answer, and an approximate
                             click lands on the wrong thing.

list_screen_elements() exists so the model can *read* what's clickable
(option 2) instead of squinting at a screenshot and estimating (option 3).
When something is genuinely invisible to UI Automation — Adobe apps,
canvas-drawn interfaces, most game UIs — the honest answer is to tell the
user where to click, not to fake a coordinate.

SAFETY
======
Unrestricted keyboard control is a shell by another name: Win+R, type
"cmd", Enter, and every guarantee in core/permissions.py about there being
no command-execution tool is worthless. So keyboard input is guarded:

  * BLOCKED_COMBOS  — key combinations whose whole purpose is reaching a
                      command prompt or the power-user menu.
  * Terminal guard  — type_text refuses when the focused window looks like
                      a console/terminal/SSH session, because typing there
                      IS running commands.
  * pyautogui.FAILSAFE stays ON — slamming the physical mouse into the
    top-left corner of the screen aborts an in-progress pyautogui action.
    That is a hardware-level stop that does not depend on any of this code
    behaving correctly.

Generic typing, clicking and keyboard/browser actions require a review tied
to the exact target window. Approved application and website launches use
their dedicated tools. The title guard is an additional check; it is not a
complete sandbox for every application with an embedded terminal.
"""

import platform
import time
import json
import os

from core.permissions import RiskLevel
from core.tool_registry import ConfirmedActionStale, tool
from core.tasks import check_cancelled
from core.communication_policy import DraftOnlyViolation, assert_generic_input_allowed

WINDOWS = platform.system() == "Windows"

# Key combos that lead somewhere a mis-heard sentence must never reach.
# Compared as sets so "win+r" and "r+win" are both caught.
BLOCKED_COMBOS = [
    {"win", "r"},              # Run dialog -> arbitrary command
    {"win", "x"},              # Power-user menu -> Terminal/PowerShell
    {"ctrl", "alt", "delete"}, # Secure attention sequence
    {"ctrl", "shift", "esc"},  # Task Manager (can end/alter processes)
]

# If the focused window looks like one of these, typing into it is running
# commands, which is exactly what this project refuses to do.
TERMINAL_MARKERS = (
    "command prompt", "powershell", "windows terminal", "cmd.exe", "conhost",
    "wsl", "ubuntu", "debian", "git bash", "mintty", "conemu", "cmder",
    "terminal", "putty", "ssh",
)

# Keys pyautogui understands, so a mis-heard word becomes a clear error
# rather than a silent no-op.
VALID_KEYS = {
    "ctrl", "alt", "shift", "win", "tab", "enter", "return", "esc", "escape",
    "space", "backspace", "delete", "up", "down", "left", "right", "home",
    "end", "pageup", "pagedown", "insert", "capslock", "printscreen",
    *[str(n) for n in range(10)],
    *[chr(c) for c in range(ord("a"), ord("z") + 1)],
    *[f"f{n}" for n in range(1, 13)],
    "plus", "minus", "equal", "comma", "period", "slash", "backslash",
}

MAX_TYPE_LENGTH = 500
MAX_ELEMENTS = 120
MAX_TREE_DEPTH = 48


class NotOnWindows(Exception):
    pass


class BlockedKeyCombo(Exception):
    pass


class TerminalFocused(Exception):
    pass


def _require_windows():
    if not WINDOWS:
        raise NotOnWindows(
            "Computer control needs Windows (this is running on "
            f"{platform.system()}). Verified on the real machine, not here."
        )


def _pyautogui():
    import pyautogui

    # Hardware-level abort: shove the mouse into the top-left corner and any
    # in-flight pyautogui call raises instead of continuing.
    pyautogui.FAILSAFE = True
    # Small pause between actions; without it, apps miss synthesized input.
    pyautogui.PAUSE = 0.05
    return pyautogui


def _focused_window_title() -> str:
    try:
        import pygetwindow as gw

        win = gw.getActiveWindow()
        return (getattr(win, "title", "") or "").strip()
    except Exception:
        return ""


def _looks_like_terminal(title: str) -> bool:
    low = (title or "").lower()
    return any(marker in low for marker in TERMINAL_MARKERS)


# --------------------------------------------------------------- windows

def list_windows() -> dict:
    """What's actually open right now, so the model can name a real window
    instead of guessing at one."""
    _require_windows()
    import pygetwindow as gw

    titles = []
    for title in gw.getAllTitles():
        t = (title or "").strip()
        if t and t not in titles:
            titles.append(t)

    return {"count": len(titles), "windows": titles[:60], "focused": _focused_window_title()}


def focus_window(title: str) -> dict:
    """Bring a window to the front by (partial, case-insensitive) title.

    Verifies afterwards rather than trusting the call — the architecture
    doc's VERIFY stage, at its smallest useful scale.
    """
    _require_windows()
    import pygetwindow as gw

    wanted = (title or "").strip().lower()
    if not wanted:
        return {"focused": False, "error": "No window title given."}

    matches = [w for w in gw.getAllWindows() if wanted in (w.title or "").lower()]
    if not matches:
        available = [t for t in gw.getAllTitles() if t.strip()][:20]
        return {
            "focused": False,
            "error": f"No open window matching '{title}'.",
            "open_windows": available,
        }

    win = matches[0]
    try:
        if win.isMinimized:
            win.restore()
        win.activate()
    except Exception as e:
        return {"focused": False, "error": f"Could not focus '{win.title}': {e}"}

    time.sleep(0.25)
    now_focused = _focused_window_title()
    ok = wanted in now_focused.lower()
    return {
        "focused": ok,
        "window": win.title,
        "verified_focused_window": now_focused,
        "note": None if ok else "Asked Windows to focus it, but the foreground window didn't change — it may be blocked by a modal dialog.",
    }


# -------------------------------------------------------------- keyboard

def press_keys(keys: str) -> dict:
    """Press a key or key combination — 'ctrl+t', 'enter', 'alt+tab', 'f5'.

    This is the FIRST thing to reach for. Most of what a mouse does has a
    keyboard equivalent that works every time, with no coordinates and no
    guessing.
    """
    _require_windows()

    raw = (keys or "").strip().lower().replace(" ", "")
    if not raw:
        return {"pressed": False, "error": "No keys given."}

    parts = [p for p in raw.replace("-", "+").split("+") if p]
    normalized = {"control": "ctrl", "escape": "esc", "return": "enter", "windows": "win", "super": "win"}
    parts = [normalized.get(p, p) for p in parts]

    unknown = [p for p in parts if p not in VALID_KEYS]
    if unknown:
        return {"pressed": False, "error": f"Unrecognized key(s): {', '.join(unknown)}."}
    if len([part for part in parts if part not in {"ctrl", "alt", "shift", "win"}]) != 1:
        return {"pressed": False, "error": "Use one key with optional modifiers; key sequences are not allowed."}

    as_set = set(parts)
    for blocked in BLOCKED_COMBOS:
        if as_set == blocked:
            raise BlockedKeyCombo(
                f"'{'+'.join(parts)}' is permanently blocked — it opens a route to running "
                "arbitrary commands, which Cortana must never have. See tools/computer.py."
            )

    assert_generic_input_allowed(_window_snapshot())
    pyautogui = _pyautogui()
    if len(parts) == 1:
        pyautogui.press(parts[0])
    else:
        pyautogui.hotkey(*parts)

    return {"pressed": True, "keys": "+".join(parts), "focused_window": _focused_window_title()}


def type_text(text: str) -> dict:
    """Type text into whatever currently has focus.

    Refuses when a terminal has focus — typing into a shell is running
    commands, and no amount of framing changes that.
    """
    _require_windows()

    if not text:
        return {"typed": False, "error": "Nothing to type."}
    if len(text) > MAX_TYPE_LENGTH:
        return {"typed": False, "error": f"Text too long (limit {MAX_TYPE_LENGTH} characters)."}
    if not text.isascii():
        return {"typed": False, "error": "This keyboard tool currently supports ASCII text only. Use a reviewed source-file edit for Hindi or other Unicode text."}
    if any(ord(character) < 32 or ord(character) == 127 for character in text):
        return {"typed": False, "error": "Generic typing accepts one line without control characters. Message drafts use the dedicated draft tool."}

    focused = _focused_window_title()
    if _looks_like_terminal(focused):
        raise TerminalFocused(
            f"The focused window ('{focused}') looks like a terminal. Typing there would be "
            "running shell commands, which Cortana is permanently barred from doing. Focus a "
            "normal application first."
        )

    assert_generic_input_allowed(_window_snapshot())
    pyautogui = _pyautogui()
    check_cancelled()
    pyautogui.typewrite(text, interval=0.001)
    return {"typed": True, "characters": len(text), "focused_window": focused}


# ----------------------------------------------------------------- mouse

def scroll_screen(direction: str = "down", amount: int = 5) -> dict:
    """Scroll the focused window. amount is roughly 'notches' of a wheel."""
    _require_windows()

    d = (direction or "down").strip().lower()
    if d not in {"up", "down"}:
        return {"scrolled": False, "error": "direction must be 'up' or 'down'."}

    clicks = max(1, min(int(amount or 5), 30))
    assert_generic_input_allowed(_window_snapshot())
    pyautogui = _pyautogui()
    pyautogui.scroll(clicks if d == "up" else -clicks)
    return {"scrolled": True, "direction": d, "amount": amount}


def click_at(x: int, y: int, button: str = "left", double: bool = False) -> dict:
    """Click an exact screen coordinate. LAST RESORT.

    Prefer click_element (which uses real control positions) or a keyboard
    shortcut. A coordinate estimated from a screenshot is a guess, and a
    wrong guess clicks something the user didn't ask for.
    """
    _require_windows()
    pyautogui = _pyautogui()

    width, height = pyautogui.size()
    if not (0 <= x < width and 0 <= y < height):
        return {"clicked": False, "error": f"({x}, {y}) is outside the screen ({width}x{height})."}

    btn = (button or "left").strip().lower()
    if btn not in {"left", "right", "middle"}:
        return {"clicked": False, "error": "button must be left, right or middle."}

    _assert_point_target(x, y)
    pyautogui.click(x=x, y=y, button=btn, clicks=2 if double else 1)
    return {"clicked": True, "x": x, "y": y, "button": btn, "double": double}


# -------------------------------------------------------- UI Automation

def _walk_controls(control, depth: int, out: list, max_depth: int, visited=None):
    """Collect named, on-screen controls from the UI Automation tree."""
    if len(out) >= MAX_ELEMENTS or depth > max_depth:
        return
    if visited is None:
        visited = set()
    try:
        identity = tuple(control.GetRuntimeId())
        if identity in visited or len(visited) >= 3500:
            return
        visited.add(identity)
    except Exception:
        return
    try:
        children = control.GetChildren()
    except Exception:
        return

    for child in children:
        if len(out) >= MAX_ELEMENTS:
            return
        try:
            name = (child.Name or "").strip()
            ctrl_type = child.ControlTypeName.replace("ControlType", "")
            rect = child.BoundingRectangle
            visible = rect and rect.width() > 0 and rect.height() > 0
            if name and visible and child.ControlTypeName not in {'PaneControl', 'GroupControl', 'WindowControl', 'DocumentControl'}:
                out.append(
                    {
                        "name": name[:80],
                        "type": ctrl_type,
                        "center": [rect.xcenter(), rect.ycenter()],
                    }
                )
        except Exception:
            pass
        _walk_controls(child, depth + 1, out, max_depth, visited)


def list_screen_elements(max_depth: int = 48) -> dict:
    """List the clickable controls in the focused window, by their REAL
    names and positions, straight from Windows' accessibility tree.

    Use this before clicking anything. It turns "click the Subscribe
    button" from a guess into a lookup. If it comes back empty, the app
    doesn't expose an accessibility tree (common for Adobe apps, Electron
    apps with it disabled, canvas/game UIs) — say so rather than falling
    back to guessing coordinates.
    """
    _require_windows()
    try:
        import uiautomation as auto
    except ImportError:
        return {
            "elements": [],
            "error": "The 'uiautomation' package isn't installed. Run: pip install uiautomation",
        }

    try:
        window = auto.GetForegroundControl()
    except Exception as e:
        return {"elements": [], "error": f"Couldn't read the foreground window: {e}"}

    elements: list[dict] = []
    _walk_controls(window, 0, elements, max(1, min(int(max_depth or 48), MAX_TREE_DEPTH)))

    return {
        "window": _focused_window_title(),
        "count": len(elements),
        "elements": elements,
        "note": (
            "This window exposes no readable controls — it's probably a canvas-drawn or "
            "Adobe-style interface. Describe where the user should click instead of guessing "
            "coordinates."
        )
        if not elements
        else None,
    }


def click_element(name: str, exact: bool = False) -> dict:
    """Click a control in the focused window BY ITS NAME, using the real
    position Windows reports for it.

    This is the reliable way to click things. Call list_screen_elements
    first if unsure what a control is actually called.
    """
    _require_windows()
    try:
        import uiautomation as auto
    except ImportError:
        return {"clicked": False, "error": "The 'uiautomation' package isn't installed. Run: pip install uiautomation"}

    wanted = (name or "").strip()
    if not wanted:
        return {"clicked": False, "error": "No element name given."}
    if wanted.casefold().strip() in {"send", "send message", "send email", "भेजें", "भेजो"}:
        raise DraftOnlyViolation("Cortana never presses Send. Prepare a draft and send it yourself.")
    assert_generic_input_allowed(_window_snapshot())

    try:
        window = auto.GetForegroundControl()
    except Exception as e:
        return {"clicked": False, "error": f"Couldn't read the foreground window: {e}"}

    candidates: list[dict] = []
    _walk_controls(window, 0, candidates, MAX_TREE_DEPTH)

    low = wanted.lower()
    if exact:
        matches = [c for c in candidates if c["name"].lower() == low]
    else:
        matches = [c for c in candidates if low in c["name"].lower()]
        if not matches:
            matches = [c for c in candidates if c["name"].lower() in low]

    if not matches:
        return {
            "clicked": False,
            "error": f"No control named '{name}' in the focused window.",
            "available": [c["name"] for c in candidates[:25]],
        }

    # Prefer the closest name match rather than simply the first found.
    matches.sort(key=lambda c: abs(len(c["name"]) - len(wanted)))
    target = matches[0]

    pyautogui = _pyautogui()
    x, y = target["center"]
    _assert_point_target(x, y)
    pyautogui.click(x=x, y=y)

    return {
        "clicked": True,
        "element": target["name"],
        "type": target["type"],
        "at": [x, y],
        "other_matches": [m["name"] for m in matches[1:4]] or None,
    }


# --------------------------------------------------------------- browser

BROWSER_SHORTCUTS = {
    "new tab": "ctrl+t",
    "close tab": "ctrl+w",
    "reopen tab": "ctrl+shift+t",
    "next tab": "ctrl+tab",
    "previous tab": "ctrl+shift+tab",
    "last tab": "ctrl+9",
    "reload": "f5",
    "back": "alt+left",
    "forward": "alt+right",
    "address bar": "ctrl+l",
    "find": "ctrl+f",
    "zoom in": "ctrl+plus",
    "zoom out": "ctrl+minus",
    "fullscreen": "f11",
    "bookmark": "ctrl+d",
}


def browser_control(action: str = "", tab_number: int = 0) -> dict:
    """Drive the browser with keyboard shortcuts — the reliable path.

    Either pass an action name ('new tab', 'next tab', 'back', 'reload'...)
    or a tab_number 1-8 to jump straight to that tab.
    """
    _require_windows()

    if tab_number:
        n = int(tab_number)
        if not 1 <= n <= 8:
            return {"done": False, "error": "tab_number must be 1-8 (use action='last tab' for the last one)."}
        return {**press_keys(f"ctrl+{n}"), "action": f"switch to tab {n}"}

    act = (action or "").strip().lower()
    combo = BROWSER_SHORTCUTS.get(act)
    if not combo:
        return {
            "done": False,
            "error": f"Unknown browser action '{action}'.",
            "available": sorted(BROWSER_SHORTCUTS),
        }

    return {**press_keys(combo), "action": act}


# ------------------------------------------------------------ registration

def _window_snapshot(handle: int | None = None) -> dict:
    """Bind generic input approval to a real window, process and rectangle."""
    _require_windows()
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    hwnd = handle or user32.GetForegroundWindow()
    if not hwnd or not user32.IsWindow(hwnd):
        raise RuntimeError("The target window is no longer available.")
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    process = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process))
    rectangle = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rectangle)):
        raise RuntimeError("Could not read the target window.")
    return {
        "handle": int(hwnd), "process": process.value, "title": buffer.value,
        "executable": _process_executable(process.value),
        "rect": [rectangle.left, rectangle.top, rectangle.right, rectangle.bottom],
    }


def _process_executable(process_id: int) -> str:
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.windll.kernel32
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
    ]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000, False, process_id)  # Query-only, never elevate.
    if not handle:
        raise RuntimeError("Cannot verify the target application's process. No input was sent.")
    try:
        buffer = ctypes.create_unicode_buffer(32768)
        length = wintypes.DWORD(len(buffer))
        if not kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(length)):
            raise RuntimeError("Cannot verify the target application's process. No input was sent.")
        return os.path.basename(buffer.value)
    finally:
        kernel.CloseHandle(handle)


def _assert_point_target(x: int, y: int):
    """A reviewed foreground window cannot authorize a click in another app."""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    user32.WindowFromPoint.argtypes = [wintypes.POINT]
    user32.WindowFromPoint.restype = wintypes.HWND
    user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetAncestor.restype = wintypes.HWND
    point_handle = user32.WindowFromPoint(wintypes.POINT(int(x), int(y)))
    root_handle = user32.GetAncestor(point_handle, 2) if point_handle else None
    focused = _window_snapshot()
    if not root_handle or int(root_handle) != focused["handle"]:
        raise ConfirmedActionStale("The click is outside the reviewed foreground window. No input was sent.")
    assert_generic_input_allowed(focused)


def _prepare_input(action: str):
    def prepare(**args):
        snapshot = _window_snapshot()
        protected_processes = {os.getpid(), os.getppid()}
        desktop_pid = os.environ.get("CORTANA_DESKTOP_PID", "")
        if desktop_pid.isdecimal():
            protected_processes.add(int(desktop_pid))
        if (
            snapshot["process"] in protected_processes
            or not snapshot["title"]
            or snapshot["title"].lower().startswith("cortana")
        ):
            raise RuntimeError("Focus the application you want Cortana to control, then ask again.")
        if _looks_like_terminal(snapshot["title"]):
            raise TerminalFocused("Generic input into a terminal is blocked.")
        assert_generic_input_allowed(snapshot)
        preview = (
            f"{action} in window: {snapshot['title']}\n"
            f"Exact action: {json.dumps(args, ensure_ascii=False)}\n\n"
            "This may change data or submit a form. Approval applies once to this window."
        )
        return {**args, "_target_window": snapshot}, preview
    return prepare


def _confirmed_input(func):
    def execute(_target_window: dict | None = None, **args):
        if not _target_window:
            raise RuntimeError("A reviewed target window is required.")
        current = _window_snapshot(_target_window["handle"])
        assert_generic_input_allowed(current)
        if current != _target_window:
            raise ConfirmedActionStale("The target window changed after review. Ask Cortana to prepare the action again.")
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        if not user32.SetForegroundWindow(_target_window["handle"]):
            raise RuntimeError("Windows did not allow Cortana to focus the reviewed window. Focus it and retry.")
        time.sleep(0.1)
        if _window_snapshot() != _target_window:
            raise ConfirmedActionStale("The reviewed window is no longer focused. No input was sent.")
        check_cancelled()
        return func(**args)
    return execute

tool(
    name="list_windows",
    description="List the windows currently open, and which one is focused. Use before focus_window so you name a real one.",
    risk=RiskLevel.LOW,
    parameters={"type": "object", "properties": {}, "required": []},
)(list_windows)

tool(
    name="focus_window",
    description=(
        "Bring a window to the front by part of its title (e.g. 'chrome', 'premiere', "
        "'wakeword_match'). Do this before clicking or typing into an app."
    ),
    risk=RiskLevel.LOW,
    parameters={
        "type": "object",
        "properties": {"title": {"type": "string", "description": "Part of the window title."}},
        "required": ["title"],
    },
)(focus_window)

tool(
    name="press_keys",
    description=(
        "Press a key or combination: 'enter', 'ctrl+s', 'alt+tab', 'ctrl+shift+p', 'f5'. "
        "PREFER THIS over clicking — keyboard shortcuts always work and never mis-click. "
        "Some combos that open a command prompt are permanently blocked."
    ),
    risk=RiskLevel.HIGH,
    parameters={
        "type": "object",
        "properties": {"keys": {"type": "string", "description": "e.g. 'ctrl+t' or 'enter'."}},
        "required": ["keys"],
    },
    prepare=_prepare_input("Press keyboard shortcut"),
)(_confirmed_input(press_keys))

tool(
    name="type_text",
    description=(
        "Type text into whatever is focused — a search box, the address bar, an editor. "
        "Refuses to type into terminal/console windows."
    ),
    risk=RiskLevel.HIGH,
    parameters={
        "type": "object",
        "properties": {"text": {"type": "string", "description": "The text to type."}},
        "required": ["text"],
    },
    prepare=_prepare_input("Type text"),
)(_confirmed_input(type_text))

tool(
    name="scroll_screen",
    description="Scroll the focused window up or down.",
    risk=RiskLevel.LOW,
    parameters={
        "type": "object",
        "properties": {
            "direction": {"type": "string", "description": "'up' or 'down'."},
            "amount": {"type": "integer", "description": "Wheel notches, default 5."},
        },
        "required": [],
    },
)(scroll_screen)

tool(
    name="list_screen_elements",
    description=(
        "List the actual clickable controls in the focused window with their real names, "
        "read from Windows' accessibility tree. CALL THIS BEFORE CLICKING so you click a "
        "control that really exists instead of guessing where it is."
    ),
    risk=RiskLevel.LOW,
    parameters={
        "type": "object",
        "properties": {"max_depth": {"type": "integer", "description": "Tree depth to search, default 8."}},
        "required": [],
    },
)(list_screen_elements)

tool(
    name="click_element",
    description=(
        "Click a control in the focused window by its name — 'Subscribe', 'Save', 'File'. "
        "This is the RELIABLE way to click. Use list_screen_elements first if unsure of the name."
    ),
    risk=RiskLevel.HIGH,
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "The control's visible name."},
            "exact": {"type": "boolean", "description": "Require an exact name match."},
        },
        "required": ["name"],
    },
    prepare=_prepare_input("Click named control"),
)(_confirmed_input(click_element))

tool(
    name="click_at",
    description=(
        "Click exact screen coordinates. LAST RESORT — only when click_element found nothing "
        "and a keyboard shortcut doesn't exist, because an estimated coordinate can click the "
        "wrong thing."
    ),
    risk=RiskLevel.HIGH,
    parameters={
        "type": "object",
        "properties": {
            "x": {"type": "integer", "description": "X coordinate."},
            "y": {"type": "integer", "description": "Y coordinate."},
            "button": {"type": "string", "description": "left | right | middle."},
            "double": {"type": "boolean", "description": "Double-click."},
        },
        "required": ["x", "y"],
    },
    prepare=_prepare_input("Click screen position"),
)(_confirmed_input(click_at))

tool(
    name="browser_control",
    description=(
        "Control the browser by keyboard: action='new tab'|'close tab'|'next tab'|'previous tab'|"
        "'back'|'forward'|'reload'|'address bar'|'find'|'fullscreen', or tab_number=1-8 to jump "
        "to that tab. Reliable — no clicking involved."
    ),
    risk=RiskLevel.HIGH,
    parameters={
        "type": "object",
        "properties": {
            "action": {"type": "string", "description": "The browser action name."},
            "tab_number": {"type": "integer", "description": "Jump to tab 1-8."},
        },
        "required": [],
    },
    prepare=_prepare_input("Browser keyboard action"),
)(_confirmed_input(browser_control))
