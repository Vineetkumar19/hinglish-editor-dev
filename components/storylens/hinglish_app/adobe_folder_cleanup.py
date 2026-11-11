"""AE Project-panel cleanup. Never edits, saves, or closes a project.

AE collapses its Project folders when a search ends. There is no FolderItem
expanded-state scripting API. Run after JSX returns, so AE's UI thread is idle.
"""
import argparse
import json
import ntpath
import re
import sys
import uuid
import time


def title_matches(title, project_id):
    title = str(title)
    if not title.startswith('Adobe After Effects ') or ' - ' not in title:
        return False
    path = title.split(' - ', 1)[1].rstrip().removesuffix('*').rstrip()
    if re.fullmatch(r'unsaved-\d+', str(project_id)):
        # Only the default unsaved AE title is eligible. Save As or another
        # named project immediately invalidates this short foreground operation.
        return bool(re.fullmatch(r'Untitled\s*Project(?:\s*\d+)?\.aep', path, re.IGNORECASE))
    return (ntpath.isabs(project_id) and
            ntpath.normcase(ntpath.normpath(path)) ==
            ntpath.normcase(ntpath.normpath(project_id)))


def collapse_search(search, same_project):
    if not same_project():
        return {'ok': False, 'message': 'The project changed. Open the intended project and press Collapse folders.'}
    if search.read():
        return {'ok': False, 'message': 'Clear the Project search before collapsing folders. Your search was kept.'}
    marker = 'sl' + uuid.uuid4().hex[:8]
    search.write(marker)
    if hasattr(search, 'commit'):
        search.commit()
    if not same_project():
        return {'ok': False, 'message': 'The project changed during folder cleanup. Check the Project search.'}
    if search.read() != marker:
        return {'ok': False, 'message': 'The Project search changed during cleanup. Your new search was kept.'}
    search.write('')
    if hasattr(search, 'commit'):
        search.commit()
    if search.read():
        return {'ok': False, 'message': 'Folder cleanup did not finish. Clear the Project search and try Collapse folders.'}
    return {'ok': True, 'message': 'Project folders collapsed.'}


def read_live_search(read, refresh):
    try:
        return read()
    except Exception:
        refresh()
        return read()


def ensure_search_focus(focus, matches, allowed, click):
    if not allowed():
        raise RuntimeError('Keep the intended After Effects project in front while folders close.')
    try:
        focus()
    except Exception:
        pass
    if matches():
        return
    if not allowed():
        raise RuntimeError('After Effects lost focus; folder cleanup stopped.')
    click()
    for _ in range(10):
        if not allowed():
            break
        if matches():
            return
        time.sleep(.03)
    raise RuntimeError('The Project search could not receive focus.')


def collapse_project_folders(project_id):
    if sys.platform != 'win32':
        return {'ok': False, 'message': 'Automatic folder cleanup currently requires Windows.'}
    if not ntpath.isabs(project_id) and not re.fullmatch(r'unsaved-\d+', str(project_id)):
        return {'ok': False, 'message': 'Reconnect Storylens to the current After Effects project, then try Collapse folders.'}
    import ctypes
    from ctypes import wintypes
    import comtypes.client
    comtypes.client.GetModule('UIAutomationCore.dll')
    from comtypes.gen import UIAutomationClient as U
    automation = comtypes.client.CreateObject(U.CUIAutomation, interface=U.IUIAutomation)
    root = automation.GetRootElement()
    windows = root.FindAll(2, automation.CreatePropertyCondition(30003, 50032))
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    user = ctypes.WinDLL('user32', use_last_error=True)
    user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]

    def window_title(window):
        buffer = ctypes.create_unicode_buffer(32768)
        user.GetWindowTextW(window.CurrentNativeWindowHandle, buffer, len(buffer))
        return buffer.value

    def is_afterfx(window):
        handle = kernel.OpenProcess(0x1000, False, window.CurrentProcessId)
        if not handle:
            return False
        try:
            size = wintypes.DWORD(32768)
            buffer = ctypes.create_unicode_buffer(size.value)
            return bool(kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size))) and ntpath.basename(buffer.value).lower() == 'afterfx.exe'
        finally:
            kernel.CloseHandle(handle)

    matches = []
    for i in range(windows.Length):
        window = windows.GetElement(i)
        if title_matches(window_title(window), project_id) and is_afterfx(window):
            matches.append(window)
    if len(matches) != 1:
        return {'ok': False, 'message': 'Open the intended After Effects project, then press Collapse folders.'}
    window = matches[0]
    edit = pattern = None

    def refresh_search():
        nonlocal edit, pattern
        if not title_matches(window_title(window), project_id):
            raise RuntimeError('The project changed during folder cleanup.')
        panes = window.FindAll(4, automation.CreateOrCondition(automation.CreatePropertyCondition(30005, 'AE Project'), automation.CreatePropertyCondition(30005, 'Project')))
        visible_panes = [panes.GetElement(i) for i in range(panes.Length) if not panes.GetElement(i).CurrentIsOffscreen]
        pane = next((candidate for candidate in visible_panes if candidate.CurrentName == 'AE Project'), visible_panes[0] if len(visible_panes) == 1 else None)
        if not pane:
            raise RuntimeError('Show the Project panel in After Effects, then press Collapse folders.')
        edits = pane.FindAll(4, automation.CreateAndCondition(
            automation.CreatePropertyCondition(30003, 50004),
            automation.CreatePropertyCondition(30005, 'Search')))
        visible_edits = [edits.GetElement(i) for i in range(edits.Length) if not edits.GetElement(i).CurrentIsOffscreen]
        if len(visible_edits) != 1:
            raise RuntimeError('The Project search could not be identified. Show the Project panel and try Collapse folders.')
        edit = visible_edits[0]
        pattern = edit.GetCurrentPattern(10002).QueryInterface(U.IUIAutomationValuePattern)
    

    refresh_search()

    # ValuePattern.SetValue alone can change the text without AE processing its search.
    # Use real edit input, scoped to the exact foreground AE window and focused Search.
    user.GetForegroundWindow.restype = wintypes.HWND
    user.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user.GetAncestor.restype = wintypes.HWND
    user.GetKeyState.argtypes = [ctypes.c_int]
    user.GetKeyState.restype = ctypes.c_short
    class Keyboard(ctypes.Structure):
        _fields_ = [('vk', wintypes.WORD), ('scan', wintypes.WORD), ('flags', wintypes.DWORD), ('time', wintypes.DWORD), ('extra', ctypes.c_size_t)]
    class Mouse(ctypes.Structure):
        _fields_ = [('x', wintypes.LONG), ('y', wintypes.LONG), ('data', wintypes.DWORD), ('flags', wintypes.DWORD), ('time', wintypes.DWORD), ('extra', ctypes.c_size_t)]
    class Hardware(ctypes.Structure):
        _fields_ = [('message', wintypes.DWORD), ('low', wintypes.WORD), ('high', wintypes.WORD)]
    class EventData(ctypes.Union):
        _fields_ = [('keyboard', Keyboard), ('mouse', Mouse), ('hardware', Hardware)]
    class Event(ctypes.Structure):
        _fields_ = [('kind', wintypes.DWORD), ('data', EventData)]
    user.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(Event), ctypes.c_int]
    user.SendInput.restype = wintypes.UINT
    window_handle = window.CurrentNativeWindowHandle
    original_focus = automation.GetFocusedElement()
    user.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
    user.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]

    def focus_matches():
        focused = automation.GetFocusedElement()
        for _ in range(4):
            if not focused:
                break
            if automation.CompareElements(focused, edit):
                return True
            focused = automation.RawViewWalker.GetParentElement(focused)
        return False

    def click_search():
        if not foreground_matches() or not title_matches(window_title(window), project_id):
            raise RuntimeError('The project changed before folder cleanup.')
        if any(user.GetKeyState(key) & 0x8000 for key in (0x10, 0x11, 0x12)):
            raise RuntimeError('Release keyboard modifiers before Project folders close.')
        rect = edit.CurrentBoundingRectangle
        if rect.right <= rect.left or rect.bottom <= rect.top:
            raise RuntimeError('The Project search is not visible.')
        old = wintypes.POINT()
        user.GetCursorPos(ctypes.byref(old))
        x, y = (rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2
        user.SetCursorPos(x, y)
        events = (Event * 2)()
        events[0].kind = events[1].kind = 0
        events[0].data.mouse = Mouse(0, 0, 0, 0x0002, 0, 0)
        events[1].data.mouse = Mouse(0, 0, 0, 0x0004, 0, 0)
        if not foreground_matches() or not title_matches(window_title(window), project_id):
            raise RuntimeError('After Effects lost focus; folder cleanup stopped.')
        if user.SendInput(2, events, ctypes.sizeof(Event)) != 2:
            raise RuntimeError('The Project search did not accept the focus click.')
        now = wintypes.POINT()
        user.GetCursorPos(ctypes.byref(now))
        if (now.x, now.y) == (x, y):
            user.SetCursorPos(old.x, old.y)


    def foreground_matches():
        foreground = user.GetForegroundWindow()
        return foreground == window_handle or user.GetAncestor(foreground, 3) == window_handle

    def send(events):
        if not foreground_matches() or not title_matches(window_title(window), project_id):
            raise RuntimeError('After Effects lost focus; folder cleanup stopped without typing in another application.')
        if not focus_matches():
            raise RuntimeError('The Project search lost focus; folder cleanup stopped.')
        array = (Event * len(events))()
        for index, (vk, scan, flags) in enumerate(events):
            array[index].kind = 1
            array[index].data.keyboard = Keyboard(vk, scan, flags, 0, 0)
        if user.SendInput(len(array), array, ctypes.sizeof(Event)) != len(array):
            releases = (Event * 2)()
            for index, key in enumerate((0x41, 0x11)):
                releases[index].kind = 1
                releases[index].data.keyboard = Keyboard(key, 0, 2, 0, 0)
            user.SendInput(2, releases, ctypes.sizeof(Event))
            raise RuntimeError('After Effects did not accept the Project search input.')

    class Search:
        def read(self):
            return read_live_search(lambda: pattern.CurrentValue, refresh_search)
        def write(self, value):
            if not foreground_matches():
                raise RuntimeError('Keep After Effects in front while Project folders close.')
            if any(user.GetKeyState(key) & 0x8000 for key in (0x10, 0x11, 0x12)):
                raise RuntimeError('Release keyboard modifiers before Project folders close.')
            ensure_search_focus(edit.SetFocus, focus_matches,
                                lambda: foreground_matches() and title_matches(window_title(window), project_id), click_search)
            # Ctrl+A, release both keys, then replace only this checked Search field.
            send([(0x11, 0, 0), (0x41, 0, 0), (0x41, 0, 2), (0x11, 0, 2)])
            if value:
                send([event for char in value for event in ((0, ord(char), 4), (0, ord(char), 6))])
            else:
                send([(0x08, 0, 0), (0x08, 0, 2)])
            # AE commits the native query on Enter; a typed suggestion alone is not a filter.
            send([(0x0D, 0, 0), (0x0D, 0, 2)])
            deadline = time.monotonic() + 4
            while self.read() != value and time.monotonic() < deadline:
                time.sleep(.04)
            if self.read() != value:
                raise RuntimeError('After Effects did not finish updating the Project search.')
        def commit(self):
            # Let AE apply the filter before it is cleared; immediate clear was unreliable.
            time.sleep(.35)

    search = Search()
    try:
        return collapse_search(search, lambda: title_matches(window_title(window), project_id) and is_afterfx(window) and foreground_matches())
    finally:
        try:
            if original_focus and foreground_matches():
                original_focus.SetFocus()
        except Exception:
            pass



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project-id', required=True)
    args = parser.parse_args()
    try:
        result = collapse_project_folders(args.project_id)
    except Exception as error:
        result = {'ok': False, 'message': 'Folder cleanup could not finish. Your timeline is kept; try Collapse folders.', 'details': __import__('traceback').format_exc()}
    try:
        from pathlib import Path
        receipt = Path(__file__).resolve().parents[1] / 'cache/editor-panel/folder-cleanup-last.json'
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(json.dumps({'project_id': args.project_id, 'result': result, 'time': time.time()}), encoding='utf-8')
    except Exception:
        pass
    print(json.dumps(result, ensure_ascii=True))


if __name__ == '__main__':
    main()
