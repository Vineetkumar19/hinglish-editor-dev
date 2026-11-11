"""Short-lived plain-text paste with restoration of the owner's clipboard."""
from contextlib import contextmanager
import time

from core.draft_adapters import DraftProblem


def _open(clip):
    for attempt in range(8):
        try:
            clip.OpenClipboard()
            return
        except Exception:
            if attempt == 7:
                raise DraftProblem('The clipboard is busy. No text was pasted.')
            time.sleep(.025)


def _snapshot(clip, constants):
    saved, deferred, seen = [], [], set()
    format_id = clip.EnumClipboardFormats(0)
    while format_id and format_id not in seen:
        seen.add(format_id)
        value = clip.GetClipboardData(format_id)
        if isinstance(value, (str, bytes)):
            saved.append((format_id, value))
        else:
            deferred.append(format_id)
        format_id = clip.EnumClipboardFormats(format_id)
    # Windows synthesizes CF_BITMAP and CF_PALETTE from the copied DIB bytes.
    # Never retain an integer GDI handle: EmptyClipboard destroys that handle.
    # https://learn.microsoft.com/windows/win32/dataxchg/clipboard-formats
    has_dib = any(kind in {constants.CF_DIB, constants.CF_DIBV5} and isinstance(value, bytes)
                  for kind, value in saved)
    if any(not (has_dib and kind in {constants.CF_BITMAP, constants.CF_PALETTE})
           for kind in deferred):
        raise DraftProblem('This clipboard format cannot be restored safely. No text was pasted.')
    return saved


@contextmanager
def temporary_text(text):
    import win32clipboard as clip
    import win32con
    _open(clip)
    saved, changed, sequence = [], False, None
    try:
        saved = _snapshot(clip, win32con)
        clip.EmptyClipboard()
        changed = True
        # Prevent the temporary outgoing text from entering Windows clipboard
        # history/cloud sync. This changes no user/Windows preference.
        for name in ('CanIncludeInClipboardHistory', 'CanUploadToCloudClipboard'):
            clip.SetClipboardData(clip.RegisterClipboardFormat(name), b'\0\0\0\0')
        clip.SetClipboardText(text, win32con.CF_UNICODETEXT)
        sequence = clip.GetClipboardSequenceNumber()
    finally:
        # Even a failed SetClipboardText must restore the original contents.
        if changed and sequence is None:
            clip.EmptyClipboard()
            for kind, value in saved:
                clip.SetClipboardData(kind, value)
        clip.CloseClipboard()
    try:
        yield
    finally:
        _open(clip)
        try:
            # Do not overwrite something the owner copied during the paste.
            if clip.GetClipboardSequenceNumber() == sequence:
                clip.EmptyClipboard()
                for kind, value in saved:
                    clip.SetClipboardData(kind, value)
        finally:
            clip.CloseClipboard()
