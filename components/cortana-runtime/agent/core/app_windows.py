"""Reuse verified communication app windows instead of launching duplicates."""
last_platform = None


def instagram_title(title):
    return title.startswith('instagram') and not title.endswith(' - google chrome')


def current_platform():
    import win32gui
    import win32process
    import psutil
    hwnd = win32gui.GetForegroundWindow()
    try:
        title = win32gui.GetWindowText(hwnd).casefold()
        name = psutil.Process(win32process.GetWindowThreadProcessId(hwnd)[1]).name().casefold()
        if instagram_title(title) and name == 'chrome.exe':
            return 'instagram'
        if title == 'whatsapp' and name == 'whatsapp.root.exe':
            return 'whatsapp'
    except psutil.Error:
        pass
    return last_platform


def focus_existing(platform):
    if platform not in {'whatsapp', 'instagram'}:
        return False
    import psutil
    import win32gui
    import win32process
    windows = []
    def visit(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd).casefold()
        try:
            name = psutil.Process(win32process.GetWindowThreadProcessId(hwnd)[1]).name().casefold()
            if ((platform == 'whatsapp' and title == 'whatsapp' and name == 'whatsapp.root.exe')
                    or (platform == 'instagram' and instagram_title(title) and name == 'chrome.exe')):
                windows.append(hwnd)
        except psutil.Error:
            pass
    win32gui.EnumWindows(visit, None)
    if not windows:
        return False
    if len(windows) > 1:
        foreground = win32gui.GetForegroundWindow()
        if foreground in windows:
            windows = [foreground]
        else:
            raise RuntimeError('More than one ' + platform + ' app window is open. Close the extra window or select the intended one; no new window was opened.')
    hwnd = windows[0]
    import ctypes
    ctypes.windll.user32.ShowWindowAsync(hwnd, 9)
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass
    def is_target_foreground():
        foreground = win32gui.GetForegroundWindow()
        if not foreground or not win32gui.IsWindow(foreground) or not win32gui.IsWindow(hwnd):
            return False
        try:
            return (foreground == hwnd or win32gui.IsChild(hwnd, foreground)
                    or win32gui.GetAncestor(foreground, 3) == hwnd)
        except Exception:
            return False
    if not is_target_foreground():
        # A user-requested app activation can be denied when Windows treats the
        # recognizer's worker as background. Give the fixed activation gesture
        # to the input queue, then retry only this verified application HWND.
        # Never use a blocking UIA SetFocus or alter Windows focus settings.
        import win32api
        import win32con
        try:
            win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
        finally:
            win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
        try:
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass
    if not is_target_foreground():
        raise RuntimeError('Instagram or WhatsApp is already open, but Windows did not activate its window. Nothing was typed or sent.')
    # Do not spawn a duplicate merely because Windows reports an embedded
    # browser/owner surface as foreground. Draft entry checks focus separately.
    return True
