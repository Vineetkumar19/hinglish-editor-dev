"""Keep generic computer tools out of communication draft workflows.

Only the dedicated draft service may fill a messaging composer. Its browser
stays protected after handoff, so a later approval card cannot press Send.
"""
from importlib import import_module

from core.tasks import may_prepare_communication


class DraftOnlyViolation(RuntimeError):
    pass


def assert_generic_input_allowed(snapshot: dict):
    if may_prepare_communication():
        raise DraftOnlyViolation(
            "Use the dedicated draft tool for this request. Cortana never sends messages."
        )
    title = str(snapshot.get("title", "")).casefold()
    executable = str(snapshot.get("executable", "")).casefold()
    if any(platform in title or platform in executable for platform in ("whatsapp", "gmail", "instagram", "telegram")):
        raise DraftOnlyViolation(
            "Generic input is blocked in messaging windows. Prepare a draft and press Send yourself."
        )
    try:
        browser = import_module("core.browser_session")
    except ModuleNotFoundError as error:
        if error.name == "core.browser_session":
            return  # The optional draft browser has not been installed.
        raise DraftOnlyViolation("Cannot verify the protected draft browser. No input was sent.") from error
    try:
        active = browser.managed_browser_active()
        processes = browser.managed_browser_process_ids()
    except Exception as error:
        raise DraftOnlyViolation("Cannot verify the protected draft browser. No input was sent.") from error
    if (active and not processes) or snapshot.get("process") in processes:
        raise DraftOnlyViolation(
            "This browser is reserved for message drafts. Cortana cannot click, type shortcuts, navigate, or send here."
        )
