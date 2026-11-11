"""Keep AE's Project scroll after Paste without changing project content."""
import argparse
import json
import math
import ntpath
import sys
import time

from .adobe_folder_cleanup import title_matches


def thumb_position(fraction, bar, thumb, axis):
    if fraction is None or not math.isfinite(fraction) or not 0<=fraction<=1:
        return None
    if axis=='vertical':
        size=thumb[3]-thumb[1];travel=bar[3]-bar[1]-size
        return ((thumb[0]+thumb[2])/2,bar[1]+travel*fraction+size/2) if travel>2 else None
    size=thumb[2]-thumb[0];travel=bar[2]-bar[0]-size
    return (bar[0]+travel*fraction+size/2,(thumb[1]+thumb[3])/2) if travel>2 else None


def restore_positions(saved, current, write):
    """Repair only a reset to the top; keep any new nonzero user position."""
    restored = []
    for axis, old in saved.items():
        now = current.get(axis)
        if now is None or not math.isfinite(old) or not math.isfinite(now):
            continue
        if old > 0 and abs(now) < .001:
            write(axis, old)
            restored.append(axis)
    return restored


def settle_positions(saved, read, write, pause=time.sleep):
    """Catch AE's deferred repaint, then exit; never run a persistent watcher."""
    before=read();current=dict(before);restored=set();moved=set()
    for turn in range(3):
        if turn:
            pause(.15)
            current=read()
        for axis,old in saved.items():
            now=current.get(axis)
            if now is not None and math.isfinite(now) and now>0 and abs(now-old)>.1:moved.add(axis)
        targets={axis:value for axis,value in saved.items() if axis not in moved}
        changed=restore_positions(targets,current,write)
        restored.update(changed)
        if changed:current=read()
    verified=all(axis in moved or abs(current.get(axis,-1)-saved[axis])<.1 for axis in restored)
    return {'ok':verified,'restored':sorted(restored),'before':before,'after':current}


_native_runtime = None
_last_capture = None


def native_runtime():
    global _native_runtime
    if _native_runtime is not None:
        return _native_runtime
    import ctypes
    from ctypes import wintypes
    import comtypes.client
    comtypes.client.GetModule('UIAutomationCore.dll')
    from comtypes.gen import UIAutomationClient as U
    automation = comtypes.client.CreateObject(U.CUIAutomation, interface=U.IUIAutomation)
    user = ctypes.WinDLL('user32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    _native_runtime = (ctypes, U, automation, user, kernel)
    return _native_runtime


def project_view(project_id, snapshot=None):
    global _last_capture
    if sys.platform != 'win32' or not ntpath.isabs(project_id):
        return {'ok': False, 'reason': 'project-unavailable'}
    cached = _last_capture
    _last_capture = None
    if snapshot and cached:
        identity = cached['identity']
        if any(snapshot.get(k) != v for k, v in identity.items()) or not 0 <= time.time() - snapshot.get('captured', 0) < 60:
            return {'ok': False, 'reason': 'view-changed'}
        # Reuse the exact guarded controls captured immediately before this
        # Paste, rather than traversing every Adobe panel a second time.
        try:
            return settle_positions(snapshot.get('positions', {}), cached['read'], cached['write'])
        except Exception:
            # AE can replace scrollbar COM objects when a private holder is
            # inserted. Reacquire once, with all project/pane/search guards,
            # rather than abandon restoration or retry stale control objects.
            pass
    ctypes, U, automation, user, kernel = native_runtime()
    from ctypes import wintypes

    def title(window):
        buffer = ctypes.create_unicode_buffer(32768)
        user.GetWindowTextW(window.CurrentNativeWindowHandle, buffer, len(buffer))
        return buffer.value

    def is_ae(window):
        handle = kernel.OpenProcess(0x1000, False, window.CurrentProcessId)
        if not handle:
            return False
        try:
            buffer = ctypes.create_unicode_buffer(32768)
            size = wintypes.DWORD(len(buffer))
            return bool(kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size))) and ntpath.basename(buffer.value).lower() == 'afterfx.exe'
        finally:
            kernel.CloseHandle(handle)

    windows = automation.GetRootElement().FindAll(2, automation.CreatePropertyCondition(30003, 50032))
    matches = [windows.GetElement(i) for i in range(windows.Length)
               if title_matches(title(windows.GetElement(i)), project_id) and is_ae(windows.GetElement(i))]
    if len(matches) != 1:
        return {'ok': False, 'reason': 'window-changed'}
    window = matches[0]
    panes = window.FindAll(4, automation.CreatePropertyCondition(30005, 'AE Project'))
    panes = [panes.GetElement(i) for i in range(panes.Length) if not panes.GetElement(i).CurrentIsOffscreen]
    if len(panes) != 1:
        return {'ok': False, 'reason': 'project-panel-hidden'}
    pane = panes[0]
    edits = pane.FindAll(4, automation.CreateAndCondition(automation.CreatePropertyCondition(30003, 50004), automation.CreatePropertyCondition(30005, 'Search')))
    if edits.Length != 1:
        return {'ok': False, 'reason': 'search-unavailable'}
    search = edits.GetElement(0).GetCurrentPattern(10002).QueryInterface(U.IUIAutomationValuePattern).CurrentValue
    identity = {'project_id': project_id, 'pid': window.CurrentProcessId, 'hwnd': window.CurrentNativeWindowHandle, 'pane': list(pane.GetRuntimeId()), 'search': search}
    if snapshot:
        if any(snapshot.get(k) != v for k, v in identity.items()) or not 0 <= time.time() - snapshot.get('captured', 0) < 60:
            return {'ok': False, 'reason': 'view-changed'}
    bars = pane.FindAll(4, automation.CreatePropertyCondition(30003, 50014))
    patterns, values, native_bars, scroll_patterns, scroll_percent,thumb_fractions,thumb_details = {}, {}, {}, {}, {}, {}, {}
    def bounds(element):
        b=element.CurrentBoundingRectangle
        return (b.left,b.top,b.right,b.bottom)
    def thumb(bar):
        found=bar.FindAll(4,automation.CreateOrCondition(automation.CreatePropertyCondition(30003,50027),automation.CreatePropertyCondition(30005,'UI_ScrollThumb')))
        if found.Length!=1:raise RuntimeError('A unique Project scrollbar thumb is required')
        return found.GetElement(0)
    try:
        pane_scroll=pane.GetCurrentPattern(10004).QueryInterface(U.IUIAutomationScrollPattern)
        for axis,percent in [('horizontal',pane_scroll.CurrentHorizontalScrollPercent),('vertical',pane_scroll.CurrentVerticalScrollPercent)]:
            if 0<=percent<=100:scroll_patterns[axis]=pane_scroll;scroll_percent[axis]=float(percent)
    except Exception:
        pass
    for i in range(bars.Length):
        bar = bars.GetElement(i)
        if bar.CurrentIsOffscreen:
            continue
        axis = {1: 'horizontal', 2: 'vertical'}.get(bar.CurrentOrientation)
        if not axis:
            geometry = bar.CurrentBoundingRectangle
            axis = 'horizontal' if geometry.right - geometry.left > geometry.bottom - geometry.top else 'vertical'
        if axis in patterns:
            return {'ok': False, 'reason': 'ambiguous-scrollbar'}
        try:
            pattern = bar.GetCurrentPattern(10003).QueryInterface(U.IUIAutomationRangeValuePattern)
            kind = 'range'
        except Exception:
            pattern = bar.GetCurrentPattern(10002).QueryInterface(U.IUIAutomationValuePattern)
            kind = 'value'
        values[axis] = float(pattern.CurrentValue)
        patterns[axis] = (pattern, kind)
        native_bars[axis]=bar
        if not snapshot:
            try:
                b=bounds(bar);t=bounds(thumb(bar));start=1 if axis=='vertical' else 0;end=start+2
                travel=b[end]-b[start]-(t[end]-t[start])
                if travel>2:thumb_fractions[axis]=max(0,min(1,(t[start]-b[start])/travel))
            except Exception as error:
                children=bar.FindAll(2,automation.CreateTrueCondition())
                thumb_details[axis]={'error':str(error),'bar':str(bar.CurrentBoundingRectangle),'children':[]}
                for child_index in range(min(4,children.Length)):
                    child=children.GetElement(child_index)
                    thumb_details[axis]['children'].append({'name':child.CurrentName,'type':child.CurrentControlType,'class':child.CurrentClassName})
    if not patterns:
        return {'ok': False, 'reason': 'scrollbar-unavailable'}
    captured_cursor=(snapshot or {}).get('cursor')
    if captured_cursor is None:
        point=wintypes.POINT();user.GetCursorPos(ctypes.byref(point));captured_cursor=[point.x,point.y]
    def input_tick():
        class LastInput(ctypes.Structure):_fields_=[('size',wintypes.UINT),('tick',wintypes.DWORD)]
        info=LastInput();info.size=ctypes.sizeof(LastInput)
        if not user.GetLastInputInfo(ctypes.byref(info)):raise RuntimeError('Input activity could not be checked')
        return int(info.tick)
    captured_input=(snapshot or {}).get('input_tick')
    if captured_input is None:captured_input=input_tick()
    def drag_thumb(axis):
        # Only used for AE's custom, read-only accessibility scrollbar. A
        # captured thumb geometry is required; never guess a scroll percentage.
        fraction=(snapshot or {}).get('thumb_fractions',thumb_fractions).get(axis)
        bar=native_bars[axis];handle=window.CurrentNativeWindowHandle
        th=thumb(bar);b=bounds(bar);t=bounds(th);destination=thumb_position(fraction,b,t,axis)
        if destination is None:raise RuntimeError('Saved Project scrollbar geometry is unavailable')
        user.GetForegroundWindow.restype=wintypes.HWND
        user.WindowFromPoint.argtypes=[wintypes.POINT];user.WindowFromPoint.restype=wintypes.HWND
        user.GetAncestor.argtypes=[wintypes.HWND,wintypes.UINT];user.GetAncestor.restype=wintypes.HWND
        user.GetCursorPos.argtypes=[ctypes.POINTER(wintypes.POINT)]
        user.GetKeyState.argtypes=[ctypes.c_int];user.GetKeyState.restype=ctypes.c_short
        if user.GetForegroundWindow()!=handle or any(user.GetKeyState(key)&0x8000 for key in (1,2,4,0x10,0x11,0x12)):
            raise RuntimeError('Project scroll kept unchanged because AE lost focus or input is active')
        if input_tick()!=captured_input:raise RuntimeError('New input during Paste; Project scroll was not forced')
        start=((t[0]+t[2])/2,(t[1]+t[3])/2);hit=user.WindowFromPoint(wintypes.POINT(int(start[0]),int(start[1])))
        if hit!=handle and user.GetAncestor(hit,2)!=handle:raise RuntimeError('Project scrollbar is covered')
        cursor=wintypes.POINT();user.GetCursorPos(ctypes.byref(cursor))
        captured=captured_cursor
        if captured and (abs(cursor.x-captured[0])>3 or abs(cursor.y-captured[1])>3):raise RuntimeError('Mouse moved during Paste; Project scroll was not forced')
        focus=automation.GetFocusedElement()
        class Mouse(ctypes.Structure):
            _fields_=[('x',wintypes.LONG),('y',wintypes.LONG),('data',wintypes.DWORD),('flags',wintypes.DWORD),('time',wintypes.DWORD),('extra',ctypes.c_size_t)]
        class Keyboard(ctypes.Structure):
            _fields_=[('vk',wintypes.WORD),('scan',wintypes.WORD),('flags',wintypes.DWORD),('time',wintypes.DWORD),('extra',ctypes.c_size_t)]
        class EventData(ctypes.Union):_fields_=[('mouse',Mouse),('keyboard',Keyboard)]
        class Event(ctypes.Structure):_fields_=[('kind',wintypes.DWORD),('data',EventData)]
        user.SendInput.argtypes=[wintypes.UINT,ctypes.POINTER(Event),ctypes.c_int];user.SendInput.restype=wintypes.UINT
        left,top,width,height=[user.GetSystemMetrics(n) for n in (76,77,78,79)]
        def send(point,flags):
            event=Event();event.kind=0;event.data.mouse=Mouse(round((point[0]-left)*65535/max(1,width-1)),round((point[1]-top)*65535/max(1,height-1)),0,0xC001|flags,0,0)
            if user.SendInput(1,ctypes.byref(event),ctypes.sizeof(Event))!=1:raise RuntimeError('Project scrollbar input was not accepted')
        pressed=False
        try:
            send(start,2);pressed=True;time.sleep(.025);send(destination,0);time.sleep(.025);send(destination,4);pressed=False
        finally:
            if pressed:send(destination,4)
            send((cursor.x,cursor.y),0)
            if focus and user.GetForegroundWindow()==handle:
                try:focus.SetFocus()
                except Exception:pass
    def write(axis, value):
        # Recheck identity before writing only a scroll value; never activate AE.
        if not title_matches(title(window), project_id):
            raise RuntimeError('Project changed before scroll restoration')
        pattern, kind = patterns[axis]
        try:
            if kind == 'range':
                value = min(pattern.CurrentMaximum, max(pattern.CurrentMinimum, value))
                pattern.SetValue(value)
            else:
                value=float(value)
                pattern.SetValue(str(int(value)) if value.is_integer() else str(value))
        except Exception as error:
            try:
                legacy=native_bars[axis].GetCurrentPattern(10018).QueryInterface(U.IUIAutomationLegacyIAccessiblePattern)
                legacy.SetValue(str(int(value)) if float(value).is_integer() else str(value))
                return
            except Exception:
                pass
            scroll=scroll_patterns.get(axis)
            percent=(snapshot or {}).get('scroll_percent',scroll_percent).get(axis)
            if scroll is not None and percent is not None:
                try:
                    scroll.SetScrollPercent(percent if axis=='horizontal' else -1,percent if axis=='vertical' else -1)
                    return
                except Exception:
                    pass
            try:
                drag_thumb(axis)
                return
            except Exception as drag_error:
                raise RuntimeError(f'{axis} scroll restoration stopped: {drag_error}') from drag_error

    def read():
        try:
            if window.CurrentProcessId!=identity['pid'] or pane.CurrentIsOffscreen or list(pane.GetRuntimeId())!=identity['pane'] or not title_matches(title(window),project_id) or edits.GetElement(0).GetCurrentPattern(10002).QueryInterface(U.IUIAutomationValuePattern).CurrentValue!=search:
                raise RuntimeError('Project or search changed before scroll restoration')
            return {axis:float(pattern.CurrentValue) for axis,(pattern,_) in patterns.items()}
        except Exception as error:
            raise RuntimeError(f'Project scroll read failed: {error}') from error
    if not snapshot:
        _last_capture = {'identity': identity, 'read': read, 'write': write}
        return {'ok': True, **identity, 'captured': time.time(), 'positions': values,'scroll_percent':scroll_percent,
                'thumb_fractions':thumb_fractions,'thumb_details':thumb_details,'cursor':captured_cursor,'input_tick':captured_input,
                'controls':{axis:{'kind':kind,'scroll':axis in scroll_patterns} for axis,(_,kind) in patterns.items()}}
    return settle_positions(snapshot.get('positions',{}),read,write)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project-id')
    parser.add_argument('--snapshot')
    parser.add_argument('--worker', action='store_true')
    args = parser.parse_args()
    if args.worker:
        # Only the owning CEP panel's pipe is accepted. No socket, input hook,
        # model, image decoder or project content is held in this helper.
        for line in sys.stdin:
            request = {}
            try:
                if len(line) > 65536:
                    raise ValueError('Viewport request is too large')
                request = json.loads(line)
                if request.get('action') not in ('capture', 'restore'):
                    raise ValueError('Unsupported viewport action')
                result = project_view(request.get('project_id', ''), request.get('snapshot'))
            except Exception as error:
                result = {'ok': False, 'reason': 'scroll-unavailable', 'details': str(error)[:800]}
            print(json.dumps({'id': request.get('id'), 'result': result}, ensure_ascii=True), flush=True)
        return
    try:
        result = project_view(args.project_id, json.loads(args.snapshot) if args.snapshot else None)
    except Exception as error:
        result = {'ok': False, 'reason': 'scroll-unavailable', 'details': str(error)}
    print(json.dumps(result, ensure_ascii=True))


if __name__ == '__main__':
    main()
