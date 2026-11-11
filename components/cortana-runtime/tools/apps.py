"""open_application — spec section 8.1.

Launches an application from the config-driven allowlist only. Anything
not in config/settings.json's permissions.approved_app_allowlist is
refused before any subprocess is touched.

Known applications use an explicit executable and fixed arguments with
shell=False. Start Menu discovery is a separate reviewed setup step;
model input can select an alias but cannot supply executable arguments.
"""

import platform
import subprocess
import shutil
from pathlib import Path

from core.alias_match import resolve_alias
from core.app_config import approved_apps
from core.tool_registry import tool
from core.permissions import RiskLevel
from core.processes import public_environment, shell_open


class AppNotApproved(Exception):
    pass


def open_application(name: str) -> dict:
    apps = approved_apps()
    # Fuzzy alias resolution — the model says "VS Code", "vscode", "code",
    # and exact-key lookup rejected most of those.
    key = resolve_alias(name, apps)
    command = apps.get(key) if key else None

    if command is None:
        raise AppNotApproved(
            f"'{name}' is not in the approved app allowlist "
            f"(config/settings.json permissions.approved_app_allowlist). "
            f"Known apps: {', '.join(sorted(apps)) or '(none configured)'}"
        )

    if platform.system() != "Windows":
        return {
            "launched": False,
            "app": key,
            "command": command,
            "note": "Not running on Windows — skipped actual launch (sandbox verification only).",
        }

    if key in {'whatsapp', 'instagram'}:
        from core import app_windows
        app_windows.last_platform = key
        if key == 'instagram':
            from core.communication_targets import open_target, target
            if target(key)['transport'] == 'chrome':
                result = open_target(key)
                return {'launched': result['status'] == 'opened', 'app': key, 'verification': result['note']}
        if app_windows.focus_existing(key):
            return {'launched': True, 'app': key, 'verification': 'Focused the existing installed app window'}

    if isinstance(command, dict) and "uri" in command:
        uri = command["uri"]
        if uri not in {"ms-settings:", "ms-screenclip:", "whatsapp:", "telegram:", "postman:"}:
            raise AppNotApproved("This application protocol is not approved.")
        shell_open(uri)
        return {"launched": True, "app": key, "verification": "Windows accepted the launch request"}
    if isinstance(command, str):
        # Older configuration is only accepted for a single executable.
        # Shell commands such as `start chrome` must be migrated to argv.
        command = [command]
    if not isinstance(command, list) or not command or not all(isinstance(x, str) for x in command):
        raise AppNotApproved("Application must be configured as executable arguments.")
    executable = command[0]
    resolved = str(Path(executable)) if Path(executable).is_file() else shutil.which(executable)
    if not resolved:
        raise FileNotFoundError(f"{key} is not installed at its configured path.")
    proc = subprocess.Popen([resolved, *command[1:]], shell=False, env=public_environment())
    return {"launched": True, "app": key, "pid": proc.pid, "verification": "Process launch accepted"}


tool(
    name="open_application",
    description="Open an approved desktop application by its friendly name (e.g. 'chrome', 'vs code', 'calculator').",
    risk=RiskLevel.LOW,
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Friendly app name from the approved allowlist."}
        },
        "required": ["name"],
    },
)(open_application)


def close_application(name: str, title: str = '') -> dict:
    """Request a normal window close; never terminate processes or dismiss prompts."""
    import time
    import psutil
    import win32con
    import win32gui
    import win32process
    from core import tasks
    apps = approved_apps()
    key = resolve_alias(name, apps)
    command = apps.get(key) if key else None
    if not isinstance(command, list) or not command:
        return {'closed': False, 'note': 'Choose a configured desktop application to close.'}
    if key != 'whatsapp' and any(arg.casefold().startswith('shell:appsfolder\\') for arg in command[1:]):
        return {'closed': False, 'note': f'Cortana does not have a verified close route for {key}.'}
    executable = Path(command[0]).name.casefold()
    if executable in {'cmd.exe', 'powershell.exe', 'pwsh.exe', 'windowsterminal.exe', 'electron.exe'}:
        return {'closed': False, 'note': 'Cortana cannot close that protected application.'}
    if key == 'whatsapp':
        executable = 'whatsapp.root.exe'
    elif key == 'instagram':
        executable = 'chrome.exe'
    allowed_exes = {executable}
    if key == 'calculator':
        allowed_exes.add('calculatorapp.exe')
    matches = []
    def visit(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd) or not win32gui.GetWindowText(hwnd):
            return
        actual_title = win32gui.GetWindowText(hwnd)
        if title and actual_title.casefold() != title.casefold():
            return
        try:
            proc = psutil.Process(win32process.GetWindowThreadProcessId(hwnd)[1])
            if proc.name().casefold() not in allowed_exes:
                # UWP Calculator's top-level HWND belongs to the shared frame
                # host. Require an actual Calculator child in that exact frame.
                if key != 'calculator' or actual_title != 'Calculator' or proc.name().casefold() != 'applicationframehost.exe':
                    return
                calculator_children = []
                def child(child_hwnd, _):
                    try:
                        owner = psutil.Process(win32process.GetWindowThreadProcessId(child_hwnd)[1])
                        if owner.name().casefold() == 'calculatorapp.exe':
                            calculator_children.append(child_hwnd)
                    except psutil.Error:
                        pass
                win32gui.EnumChildWindows(hwnd, child, None)
                if not calculator_children:
                    return
            if key == 'instagram' and not __import__('core.app_windows', fromlist=['instagram_title']).instagram_title(actual_title.casefold()):
                return
            if executable == 'explorer.exe' and win32gui.GetClassName(hwnd) != 'CabinetWClass':
                return
            if key != 'instagram' and executable == 'chrome.exe' and not actual_title.endswith(' - Google Chrome'):
                return
            matches.append((hwnd, actual_title, proc.pid))
        except psutil.Error:
            pass
    win32gui.EnumWindows(visit, None)
    if not matches:
        return {'closed': False, 'note': f'No matching {key} window is open.'}
    if len(matches) != 1:
        return {'closed': False, 'note': 'More than one window matches. Specify the exact window title; nothing was closed.',
                'windows': [item[1] for item in matches]}
    hwnd, actual_title, pid = matches[0]
    tasks.check_cancelled()
    if not win32gui.IsWindow(hwnd) or win32process.GetWindowThreadProcessId(hwnd)[1] != pid or win32gui.GetWindowText(hwnd) != actual_title:
        return {'closed': False, 'note': 'The window changed. Please retry.'}
    win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
    for _ in range(10):
        time.sleep(.1)
        tasks.check_cancelled()
        if not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
            return {'closed': True, 'note': f'Closed {actual_title}.', 'title': actual_title}
    return {'closed': False, 'note': 'Close requested. The app is still open; resolve any Save or confirmation prompt yourself.', 'title': actual_title}


tool(name='close_application', description='Close one approved app window normally, preserving any Save prompt. If several windows match, ask for an exact title; never force-kill.',
     risk=RiskLevel.LOW, parameters={'type': 'object', 'properties': {
         'name': {'type': 'string'}, 'title': {'type': 'string', 'description': 'Exact title from list_windows, only when needed to disambiguate.'}}, 'required': ['name']})(close_application)
