"""Installed applications first; websites use the owner's ordinary Chrome."""
import re
import subprocess
from pathlib import Path
from urllib.parse import urlencode

from core.app_config import approved_apps, load_app_config
from core.processes import public_environment

PLATFORMS = {"whatsapp", "instagram", "gmail"}


def preferences():
    return load_app_config().get("communication", {})


def chrome_profile_args():
    profile = preferences().get("chrome_profile_directory", "")
    if not profile:
        return []
    if not re.fullmatch(r"Default|Profile \d+", profile):
        raise ValueError("Invalid Chrome profile directory.")
    return ["--profile-directory=" + profile]


def target(platform):
    if platform not in PLATFORMS:
        raise ValueError("Unknown communication app.")
    if platform != "gmail" and platform in approved_apps() and preferences().get(platform + '_transport') != 'chrome':
        return {"platform": platform, "transport": "application"}
    return {"platform": platform, "transport": "chrome"}


def sender_email():
    value = preferences().get("gmail_sender", "")
    if not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}", value):
        raise ValueError("Set the default Gmail sender in Cortana's communication settings.")
    return value


def website(platform):
    if platform == "gmail":
        return "https://mail.google.com/mail/?" + urlencode({"authuser": sender_email()})
    return {
        "whatsapp": "https://web.whatsapp.com/",
        "instagram": "https://www.instagram.com/direct/inbox/",
    }[platform]


def open_target(platform):
    destination = target(platform)
    if destination["transport"] == "application":
        from tools.apps import open_application
        result = open_application(platform)
        if not result.get("launched"):
            raise RuntimeError("The installed app did not open. No website fallback was launched.")
    else:
        chrome = approved_apps().get("chrome")
        if not isinstance(chrome, list) or not chrome or not Path(chrome[0]).is_file():
            raise RuntimeError("Your normal Chrome installation could not be found.")
        # No separate user-data-dir, incognito, debugging port or copied cookies.
        args = [chrome[0], *chrome_profile_args()]
        if platform == 'gmail':
            # Keep the owner's existing Chrome login, but don't let a different
            # active tab (or another desktop task) replace the compose surface.
            # Reuse the visible Gmail window instead of opening one per retry.
            import psutil
            import win32gui
            import win32process
            matches = []
            def existing_gmail(hwnd, _):
                if not win32gui.IsWindowVisible(hwnd):
                    return
                title = win32gui.GetWindowText(hwnd).casefold()
                if 'gmail' not in title or sender_email().casefold() not in title:
                    return
                try:
                    process = psutil.Process(win32process.GetWindowThreadProcessId(hwnd)[1])
                    if process.name().casefold() == 'chrome.exe' and not any(
                            arg.startswith('--user-data-dir=') for arg in process.cmdline()):
                        matches.append(hwnd)
                except psutil.Error:
                    pass
            win32gui.EnumWindows(existing_gmail, None)
            if matches:
                # All matches have the configured account. Bind the chosen
                # visible window so the worker cannot drift to another one.
                chosen = matches[0]
                win32gui.ShowWindow(chosen, 9)
                try:
                    win32gui.SetForegroundWindow(chosen)
                except Exception:
                    pass
                return {**destination, 'status': 'opened', 'window_handle':chosen,
                        'note': 'Reused Gmail in your signed-in Chrome profile.'}
            args.append('--new-window')
        args.append(website(platform))
        subprocess.Popen(args, env=public_environment(), shell=False)
    return {**destination, "status": "opened",
            "note": ("Opened the installed app; your existing app login is used."
                     if destination["transport"] == "application"
                     else "Opened your normal Chrome profile; your existing website logins are used.")
            + (f" Default Gmail sender: {sender_email()}." if platform == "gmail" else "")}
