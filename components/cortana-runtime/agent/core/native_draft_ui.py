"""Fixed Windows accessibility actions for composing, with no Send action."""
import re
import time
from collections import deque
from urllib.parse import urlsplit

from core.draft_adapters import DraftProblem, normalized


class NativeDraftUI:
    def __init__(self):
        import uiautomation as auto
        self.auto = auto
        self.deadline = 0
        self.trace = []
        self._node_cache = {}
        self._last_gmail = None

    def mark(self, stage, **details):
        if hasattr(self, 'started'):
            self.trace.append({'stage': stage, 'seconds': round(time.monotonic() - self.started, 3), **details})

    def check(self):
        if time.monotonic() > self.deadline:
            raise DraftProblem("The app took too long to respond. No further draft steps were started.")

    def diagnose(self, draft):
        """Local structural diagnostics: never record field values or passwords."""
        import json
        from pathlib import Path
        try:
            self.deadline = time.monotonic() + 3
            root = self.window(draft['platform'], draft['transport'])
            names = []
            needle = draft.get('recipient', '').split(' ')[0].casefold()
            for control in self.nodes(root):
                name = control.Name or ''
                if (control.ControlTypeName == 'EditControl' or re.search(r'^(?:search|type a message|new chat|messages)', name, re.I)
                        or (needle and name.casefold().startswith(needle))):
                    rect = control.BoundingRectangle
                    names.append({'name':name[:80],'type':control.ControlTypeName,'id':control.AutomationId,
                                  'rect':[rect.left,rect.top,rect.right,rect.bottom]})
            (Path(__file__).resolve().parents[2] / 'tmp' / 'live-native-controls.json').write_text(json.dumps(names,ensure_ascii=True),encoding='utf-8')
        except Exception:
            pass

    def nodes(self, root, maximum=3500):
        cache = getattr(self, '_node_cache', {})
        key = tuple(root.GetRuntimeId())
        if key in cache:
            return cache[key]
        self.mark('walk_start')
        queue = deque([(root, 0)])
        result = []
        visited = set()
        while queue and len(visited) < maximum:
            self.check()
            control, depth = queue.popleft()
            try:
                identity = tuple(control.GetRuntimeId())
                if not identity or identity in visited:
                    continue
                visited.add(identity)
                if not control.IsOffscreen:
                    result.append(control)
                if depth < 96:
                    queue.extend((child, depth + 1) for child in control.GetChildren())
            except Exception:
                self.check()
                continue
        if queue:
            raise DraftProblem("The app has too many controls to verify safely. Open only the intended conversation.")
        cache[key] = result
        self.mark('walk_end', count=len(result))
        return result

    def controls(self, root, types):
        if getattr(self, '_platform', '') == 'whatsapp':
            # WhatsApp's embedded provider is more complete and faster through
            # its bounded child tree than repeated native FindAll calls.
            found = []
            for control in self.nodes(root):
                try:
                    if not types or control.ControlTypeName in types:
                        found.append(control)
                except Exception:
                    # WebView updates can detach individual providers while
                    # leaving the current header and composer usable.
                    continue
            return found
        # Query only relevant UIA control types in one native call. Walking and
        # rereading the whole changing inbox leaves stale unrelated elements.
        if types and hasattr(root, 'Element'):
            from uiautomation.uiautomation import _AutomationClient
            client = _AutomationClient.instance().IUIAutomation
            condition = None
            for kind in sorted(types):
                item = client.CreatePropertyCondition(30003, getattr(self.auto.ControlType, kind))
                condition = item if condition is None else client.CreateOrCondition(condition,item)
            elements = root.Element.FindAll(4,condition)
            self.mark('typed_controls', types=sorted(types), count=elements.Length)
            if elements.Length > 3500:
                raise DraftProblem('Too many editable controls are open to verify safely.')
            controls = []
            for index in range(elements.Length):
                self.check()
                try:
                    controls.append(self.auto.Control.CreateControlFromElement(elements.GetElement(index)))
                except Exception:
                    # A loading Gmail inbox can invalidate unrelated controls
                    # between FindAll and conversion. Verify each requested
                    # field below rather than failing on a vanished inbox row.
                    continue
            return controls
        return self.nodes(root)

    def find(self, root, names, types=None, optional=False):
        found = []
        seen = set()
        def label(control):
            value = control.Name or ''
            if (not value and getattr(self, '_platform', '') == 'instagram'
                    and control.ControlTypeName == 'EditControl' and control.HelpText == 'Search'):
                return 'Search'
            return value
        candidates = self.controls(root, types)
        for control in candidates:
            try:
                if not control.IsOffscreen and (not types or control.ControlTypeName in types) and re.fullmatch(names,label(control),re.I):
                    box = control.BoundingRectangle
                    key = (control.Name, control.ControlTypeName, box.left,box.top,box.right,box.bottom)
                    if key in seen:
                        continue
                    seen.add(key)
                    found.append(control)
            except Exception:
                continue
        if not found and not optional and hasattr(root, 'Element'):
            # Chromium's native typed query can omit controls across embedded
            # provider boundaries. Retry the bounded tree before concluding a
            # composer is absent and opening another blank email.
            for control in self.nodes(root):
                try:
                    if (not control.IsOffscreen and (not types or control.ControlTypeName in types)
                            and re.fullmatch(names, label(control), re.I)):
                        box = control.BoundingRectangle
                        key = (control.Name, control.ControlTypeName, box.left, box.top, box.right, box.bottom)
                        if key not in seen:
                            seen.add(key)
                            found.append(control)
                except Exception:
                    continue
        if len(found) != 1:
            import json
            from pathlib import Path
            (Path(__file__).resolve().parents[2] / 'tmp' / 'live-selector.json').write_text(json.dumps({
                'selector':names, 'matches':len(found),
                'controls':[{'name':c.Name,'type':c.ControlTypeName,'rect':str(c.BoundingRectangle)} for c in found],
            }),encoding='utf-8')
            if optional and not found:
                return None
            raise DraftProblem("Could not uniquely verify the app's " + names +
                               " control. Open the intended conversation and resume.")
        self.mark('found', selector=names)
        return found[0]

    def read(self, control):
        readable = False
        patterns = (('ValuePattern', 'LegacyIAccessiblePattern', 'TextPattern')
                    if control.ControlTypeName == 'HyperlinkControl'
                    else ('ValuePattern', 'TextPattern', 'LegacyIAccessiblePattern'))
        for pattern_name in patterns:
            try:
                pattern = control.GetPattern(getattr(self.auto.PatternId, pattern_name))
                if pattern:
                    readable = True
                    if pattern_name == "TextPattern":
                        value = normalized(pattern.DocumentRange.GetText(-1))
                    else:
                        value = normalized(pattern.Value or "")
                    # Chromium contenteditable uses an invisible marker for an
                    # empty composer. Preserve formatting inside actual text.
                    value = value.strip('\u200b\ufeff\u200e\u200f\n\r\t ')
                    if (pattern_name == 'ValuePattern' and getattr(self, '_platform', '') == 'gmail'
                            and control.Name in {'Subject', 'To', 'To recipients'}):
                        # Gmail's TextPattern returns the placeholder for these
                        # empty input/combobox fields. Their ValuePattern is the
                        # actual input value and is authoritative even if empty.
                        return value
                    if value:
                        return value
            except Exception:
                continue
        if readable:
            return ''
        raise DraftProblem("This app does not expose verifiable editable text.")

    def window(self, platform, transport, *, sender='', window_handle=None):
        import psutil
        found = []
        for control in self.auto.GetRootControl().GetChildren():
            self.check()
            try:
                name = control.Name or ""
                executable = psutil.Process(control.ProcessId).name().casefold()
                if transport == "application":
                    match = (platform == "whatsapp" and name.casefold() == "whatsapp"
                             and executable == "whatsapp.root.exe") or (
                             platform == "instagram" and "instagram" in name.casefold()
                             and executable == "chrome.exe" and name.casefold().startswith("instagram")
                             and not name.casefold().endswith(' - google chrome'))
                else:
                    match = executable == "chrome.exe" and platform in name.casefold()
                    command = psutil.Process(control.ProcessId).cmdline()
                    if any(arg.startswith("--user-data-dir=") for arg in command):
                        match = False
                    if platform == 'gmail' and sender:
                        match = match and sender.casefold() in self.emails(name)
                    if window_handle:
                        match = match and control.NativeWindowHandle == window_handle
                if match:
                    found.append(control)
            except Exception:
                continue
        if len(found) > 1:
            import win32gui
            active = win32gui.GetForegroundWindow()
            foreground = []
            if active and win32gui.IsWindow(active):
                for control in found:
                    try:
                        if (control.NativeWindowHandle == active or win32gui.IsChild(control.NativeWindowHandle, active)
                                or win32gui.GetAncestor(active, 3) == control.NativeWindowHandle):
                            foreground.append(control)
                    except Exception:
                        continue
            if len(foreground) == 1:
                found = foreground
        if len(found) != 1:
            raise DraftProblem("Open one " + platform + " window in the selected app/profile, then resume. "
                               "Cortana will not guess between windows.")
        root = found[0]
        import win32gui
        if win32gui.IsIconic(root.NativeWindowHandle):
            win32gui.ShowWindow(root.NativeWindowHandle,9)
            time.sleep(.15)
        if transport == "chrome" or platform == "instagram":
            address = self.find(root, r"Address and search bar", {"EditControl"})
            url = self.read(address)
            if "://" not in url:
                url = "https://" + url
            parsed = urlsplit(url)
            host = {"gmail": "mail.google.com", "calendar":"calendar.google.com", "whatsapp": "web.whatsapp.com",
                    "instagram": "www.instagram.com"}[platform]
            hosts = {host, "instagram.com"} if platform == "instagram" else {host}
            if parsed.scheme != "https" or parsed.hostname not in hosts:
                raise DraftProblem("The selected Chrome tab is not the expected service.")
        return root

    def focus(self, root, control):
        self.check()
        import win32gui
        if win32gui.IsIconic(root.NativeWindowHandle):
            win32gui.ShowWindow(root.NativeWindowHandle, 9)
        try:
            win32gui.SetForegroundWindow(root.NativeWindowHandle)
        except Exception:
            # An already-focused WebView child may reject activating its outer
            # host. The verified focus/process-family checks below remain required.
            pass
        # Restoring an existing Chrome window does not always raise it above
        # Cortana. Raise only the verified target before any physical input.
        try:
            win32gui.BringWindowToTop(root.NativeWindowHandle)
            if win32gui.GetForegroundWindow() != root.NativeWindowHandle:
                import win32api
                import win32con
                win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
                win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
                win32gui.SetForegroundWindow(root.NativeWindowHandle)
        except Exception:
            pass
        def belongs(hwnd):
            if not hwnd or not win32gui.IsWindow(hwnd):
                return False
            if (hwnd == root.NativeWindowHandle or win32gui.IsChild(root.NativeWindowHandle, hwnd)
                    or win32gui.GetAncestor(hwnd, 3) == root.NativeWindowHandle):
                return True
            if (root.Name or '').casefold() == 'whatsapp':
                import psutil
                import win32process
                try:
                    pid = win32process.GetWindowThreadProcessId(hwnd)[1]
                    return pid == root.ProcessId or any(parent.pid == root.ProcessId for parent in psutil.Process(pid).parents())
                except psutil.Error:
                    return False
            return False
        focused = None
        if (root.Name or '').casefold() == 'whatsapp':
            # SetFocus on this embedded provider activates its Chrome host,
            # which can leave the visible app without a keyboard caret. Use
            # the observed field's physical hit target, without SetFocus.
            rect = control.BoundingRectangle
            point = (int(rect.xcenter()), int(rect.ycenter()))
            if not belongs(win32gui.WindowFromPoint(point)):
                raise DraftProblem('The message field is covered by another window. No text was entered.')
            control.Click(simulateMove=False, waitTime=.15)
            self.mark('field_clicked', target=list(point), cursor=list(self.auto.GetCursorPos()),
                foreground=win32gui.GetForegroundWindow(),
                root_rect=list(win32gui.GetWindowRect(root.NativeWindowHandle)),
                foreground_rect=list(win32gui.GetWindowRect(win32gui.GetForegroundWindow())))
            for _ in range(6):
                if belongs(win32gui.GetForegroundWindow()) and self.is_focused(control):
                    return
                time.sleep(.05)
            focused = self.auto.GetFocusedControl()
            box = focused.BoundingRectangle
            # This Store wrapper reports native keyboard focus on its WebView
            # host pane, even when the caret is in the clicked virtual edit.
            # Accept only that native child of the selected visible window,
            # after a physical hit-checked click inside the verified field.
            native = focused.NativeWindowHandle
            if (focused.ControlTypeName == 'PaneControl' and native
                    and win32gui.IsChild(root.NativeWindowHandle, native)
                    and box.left <= point[0] <= box.right and box.top <= point[1] <= box.bottom
                    and win32gui.GetForegroundWindow() == root.NativeWindowHandle):
                self._clicked_field = (tuple(control.GetRuntimeId()), root.NativeWindowHandle, native)
                self.mark('native_host_focus_verified', host=native)
                return
            self.mark('field_focus_mismatch', name=focused.Name, kind=focused.ControlTypeName,
                runtime=focused.GetRuntimeId(), expected_runtime=control.GetRuntimeId(),
                rect=[box.left,box.top,box.right,box.bottom])
            raise DraftProblem('The visible WhatsApp field did not receive keyboard focus. No text was entered.')
        for attempt in range(3):
            try:
                control.SetFocus()
                time.sleep(.15)
                focused = self.auto.GetFocusedControl()
                if belongs(win32gui.GetForegroundWindow()) and self.is_focused(control):
                    return
                rect = control.BoundingRectangle
                if attempt == 0 and belongs(win32gui.WindowFromPoint((int(rect.xcenter()), int(rect.ycenter())))):
                    control.Click(simulateMove=False, waitTime=.15)
            except DraftProblem:
                raise
            except Exception:
                time.sleep(.1)
        try:
            from pathlib import Path
            import json
            def structure(item):
                try:
                    rect = item.BoundingRectangle
                    return {'name':item.Name,'type':item.ControlTypeName,'runtime':item.GetRuntimeId(),
                            'process':item.ProcessId,'rect':[rect.left,rect.top,rect.right,rect.bottom]}
                except Exception:
                    return {'unavailable': True}
            (Path(__file__).resolve().parents[2] / 'tmp' / 'live-focus-error.json').write_text(json.dumps({
                'expected_window':root.NativeWindowHandle,'foreground':win32gui.GetForegroundWindow(),
                'foreground_title':win32gui.GetWindowText(win32gui.GetForegroundWindow()),
                'foreground_class':win32gui.GetClassName(win32gui.GetForegroundWindow()),
                'foreground_root':win32gui.GetAncestor(win32gui.GetForegroundWindow(), 2),
                'foreground_root_owner':win32gui.GetAncestor(win32gui.GetForegroundWindow(), 3),
                'target':structure(control),'focused':structure(focused),
            }),encoding='utf-8')
        except Exception:
            pass
        raise DraftProblem("Focus changed. No text was entered. Your recipient and message were kept for retry.")

    def is_focused(self, control):
        focused = self.auto.GetFocusedControl()
        clicked = getattr(self, '_clicked_field', None)
        if clicked and tuple(control.GetRuntimeId()) == clicked[0]:
            import win32gui
            if (focused.ControlTypeName == 'PaneControl'
                    and focused.NativeWindowHandle == clicked[2]
                    and win32gui.IsChild(clicked[1], clicked[2])
                    and win32gui.GetForegroundWindow() == clicked[1]):
                return True
        for _ in range(6):
            if tuple(focused.GetRuntimeId()) == tuple(control.GetRuntimeId()):
                return True
            # Embedded Chromium exposes the same physical input through two
            # providers with different runtime IDs. Match its actual focused
            # edit only when type, process and nonzero rectangle agree exactly.
            if (focused.ControlTypeName == control.ControlTypeName
                    and focused.ProcessId == control.ProcessId):
                a, b = focused.BoundingRectangle, control.BoundingRectangle
                if (a.width() > 0 and a.height() > 0
                        and all(abs(x-y) <= 2 for x,y in zip(
                            (a.left,a.top,a.right,a.bottom), (b.left,b.top,b.right,b.bottom)))
                        and (not focused.Name or not control.Name or focused.Name == control.Name)):
                    return True
            focused = focused.GetParentControl()
            if not focused:
                return False
        return False

    def invoke(self, control):
        self.check()
        if re.search(r"\b(send|post|submit|delete)\b", control.Name or "", re.I):
            raise DraftProblem("Sending and submission controls are unavailable.")
        for name, method in (("InvokePattern", "Invoke"), ("SelectionItemPattern", "Select"),
                             ("LegacyIAccessiblePattern", "DoDefaultAction")):
            try:
                pattern = control.GetPattern(getattr(self.auto.PatternId, name))
                if pattern:
                    getattr(pattern, method)()
                    self._node_cache = {}
                    return
            except Exception:
                continue
        raise DraftProblem("The app does not expose a safe action for this control.")

    def instagram_search(self, root, *, optional=False):
        threads = self.find(root, r'Thread list', optional=True)
        return self.find(threads or root, r'Search|Clear search', {'EditControl'}, optional=optional)

    def fill(self, root, control, text, replace=False):
        field_name = control.Name or ''
        if not field_name and getattr(self, '_platform', '') == 'instagram' and control.HelpText == 'Search':
            field_name = 'Search'
        self.mark('fill', field=field_name, length=len(text))
        self.check()
        valid_edit = control.ControlTypeName == 'EditControl' or (control.ControlTypeName == 'ComboBoxControl' and control.Name in {'To recipients','To'})
        if not valid_edit or control.IsPassword:
            raise DraftProblem("The target is not a verified message/search field.")
        instagram_search = (getattr(self, '_platform', '') == 'instagram' and replace
                            and field_name in {'Search', 'Clear search'})
        def refresh_search():
            nonlocal control
            control = self.instagram_search(root)
            bounds, box = root.BoundingRectangle, control.BoundingRectangle
            if (control.IsPassword or box.left >= bounds.left + bounds.width() * .5
                    or box.top >= bounds.top + bounds.height() * .5):
                raise DraftProblem('The current Instagram recipient-search field could not be verified.')
        def read_current():
            try:
                return self.read(control)
            except Exception:
                if not instagram_search:
                    raise
                refresh_search()
                return self.read(control)
        previous = self.read(control)
        if previous == normalized(text):
            return
        if previous and not replace:
            import json
            from pathlib import Path
            (Path(__file__).resolve().parents[2] / 'tmp' / 'live-existing-field.json').write_text(json.dumps({
                'name':control.Name, 'length':len(previous), 'matches_requested':previous == normalized(text),
                'only_formatting':not previous.strip('\u200b\ufeff\u200e\u200f\n\r\t '),
                'is_placeholder':previous == normalized(control.Name),
            }),encoding='utf-8')
            raise DraftProblem("This field already contains text. The existing draft was preserved.")
        try:
            self.focus(root, control)
        except DraftProblem:
            if not instagram_search:
                raise
            # Opening Instagram's inbox search replaces the original edit with
            # a new recipient-search edit. Reacquire the unique current field;
            # never type through a stale control or an unverified focus.
            refresh_search()
            previous = self.read(control)
            self.focus(root, control)
            self.mark('search_control_refreshed')
        for name in ("ValuePattern", "LegacyIAccessiblePattern"):
            try:
                pattern = control.GetPattern(getattr(self.auto.PatternId, name))
                if pattern and (name != "ValuePattern" or not pattern.IsReadOnly):
                    pattern.SetValue(text)
                    time.sleep(.15)
                    current = read_current()
                    if current == normalized(text):
                        self._node_cache = {}
                        return
                    if current != previous:
                        raise DraftProblem("The app did not preserve the exact text. Review it manually.")
            except DraftProblem:
                raise
            except Exception:
                if read_current() != previous:
                    raise DraftProblem("The field changed during input. Review it manually before retrying.")
                continue
        # Paste literal text for both single/multiple lines; never generate Enter.
        # Keep bitmap content as DIB bytes so copied screenshots also survive.
        from core.draft_clipboard import temporary_text
        import win32con
        import win32api
        self.focus(root, control)
        with temporary_text(text):
            # Recheck after clipboard acquisition; another desktop action may
            # have moved focus while its owner rendered the copied data.
            self.focus(root, control)
            if not self.is_focused(control):
                raise DraftProblem('Focus changed. No text was pasted.')
            import win32gui
            import win32process
            foreground = win32gui.GetForegroundWindow()
            self.mark('paste_start', window=root.NativeWindowHandle,
                foreground=foreground,
                foreground_title=win32gui.GetWindowText(foreground),
                foreground_class=win32gui.GetClassName(foreground),
                foreground_process=win32process.GetWindowThreadProcessId(foreground)[1],
                target_window=control.NativeWindowHandle,
                modifiers={name: bool(win32api.GetAsyncKeyState(key) & 0x8000)
                           for name, key in [('shift', win32con.VK_SHIFT), ('alt', win32con.VK_MENU)]})
            if any(win32api.GetAsyncKeyState(key) & 0x8000 for key in (win32con.VK_SHIFT, win32con.VK_MENU)):
                raise DraftProblem('Release Shift/Alt before retrying. No text was pasted.')
            if replace and previous:
                self.auto.SendKeys('{Ctrl}a', charMode=False, waitTime=.1)
            down = self.auto.SendInput(self.auto.KeyboardInput(0x11, 0x1d, self.auto.KeyboardEventFlag.KeyDown))
            try:
                pressed = self.auto.SendInput(self.auto.KeyboardInput(0x56, 0x2f, self.auto.KeyboardEventFlag.KeyDown))
                released = self.auto.SendInput(self.auto.KeyboardInput(0x56, 0x2f, self.auto.KeyboardEventFlag.KeyUp))
            finally:
                up = self.auto.SendInput(self.auto.KeyboardInput(0x11, 0x1d, self.auto.KeyboardEventFlag.KeyUp))
            self.mark('paste_keys', accepted=[down, pressed, released, up])
            if not all((down, pressed, released, up)):
                raise DraftProblem('Windows blocked Cortana keyboard input. No message was sent.')
            for _ in range(8):
                time.sleep(.1)
                self.check()
                actual = read_current()
                if actual == normalized(text):
                    self.mark('paste_verified', length=len(actual))
                    self._node_cache = {}
                    return
            self.mark('paste_unverified', length=len(actual), focused=self.is_focused(control),
                      foreground=win32gui.GetForegroundWindow())
            raise DraftProblem("The app did not verify the exact pasted text. Review the composer manually.")

    def identity(self, root, draft):
        platform = draft["platform"]
        expected = draft["recipient"].lstrip("@")
        if platform == "gmail":
            sender = draft["sender"]
            def matches(control):
                try:
                    labels = (control.Name or '', getattr(control, 'HelpText', '') or '')
                    return not control.IsOffscreen and any(
                        re.match(r'Google Account\b', label, re.I)
                        and self.emails(label) == {sender.casefold()} for label in labels)
                except Exception:
                    return False
            account = any(matches(control) for control in self.controls(root, {'ButtonControl', 'HyperlinkControl'}))
            if not account:
                account = any(matches(control) for control in self.nodes(root))
            if not account:
                raise DraftProblem("The configured Google account could not be verified in this window.")
        else:
            # A header in the conversation area, not a matching sidebar row.
            if platform == 'instagram':
                address = self.read(self.find(root, r'Address and search bar', {'EditControl'}))
                page = urlsplit(address if '://' in address else 'https://' + address)
                # Floating chat previews on profile pages are unrelated to the
                # profile being viewed. Require the actual DM thread surface.
                if not page.path.startswith('/direct/t/'):
                    raise DraftProblem('The requested Instagram conversation is not open in the Messages section.')
            if platform == 'whatsapp':
                # Current Windows WhatsApp sometimes exposes the recipient in
                # the composer's accessible label instead of the title text.
                bounds = root.BoundingRectangle
                composers = []
                for c in self.controls(root, {'EditControl'}):
                    try:
                        if (not c.IsOffscreen and re.match(r'Type a message to ', c.Name or '', re.I)
                                and c.BoundingRectangle.left > bounds.left + bounds.width() * .32
                                and c.BoundingRectangle.top > bounds.top + bounds.height() * .5):
                            composers.append(c)
                    except Exception:
                        continue
                if composers:
                    if len(composers) == 1 and (composers[0].Name or '').casefold() == ('Type a message to ' + expected).casefold():
                        self.mark('recipient_verified')
                        return
                    base = re.sub(r'\s*\(you\)\s*$', '', expected, flags=re.I)
                    self_label = (len(composers) == 1 and base != expected
                        and (composers[0].Name or '').casefold() == ('Type a message to ' + base).casefold())
                    if not self_label:
                        raise DraftProblem('The selected WhatsApp conversation is not the requested recipient.')
                    # Self-chat composers omit (You); require the unique
                    # right-hand header's Message yourself label below.
            def expected_heading(control):
                label = re.sub(r'\s+', ' ', (control.Name or '').strip().lstrip('@')).casefold()
                if label == expected.casefold():
                    return True
                if (platform == 'instagram' and control.ControlTypeName == 'HyperlinkControl'
                        and re.fullmatch(r'[A-Za-z0-9._]+', expected)):
                    try:
                        profile = urlsplit(self.read(control))
                        return (profile.scheme == 'https' and profile.hostname in {'instagram.com', 'www.instagram.com'}
                                and profile.path.strip('/').casefold() == expected.casefold())
                    except Exception:
                        return False
                if platform == 'whatsapp':
                    base = re.sub(r'\s*\(you\)\s*$', '', expected, flags=re.I)
                    return label == (base + ' (You) Message yourself').casefold()
                return False
            headings = []
            for c in self.controls(root, {"ButtonControl", "TextControl", "HyperlinkControl"}):
                try:
                    if (not c.IsOffscreen and expected_heading(c)
                            and c.BoundingRectangle.left > root.BoundingRectangle.left + root.BoundingRectangle.width() * .32
                            and root.BoundingRectangle.top <= c.BoundingRectangle.top < root.BoundingRectangle.top + root.BoundingRectangle.height() * .3):
                        headings.append(c)
                except Exception:
                    continue
            unique = []
            for heading in headings:
                box = heading.BoundingRectangle
                def overlaps(other):
                    rect = other.BoundingRectangle
                    intersection = max(0,min(box.right,rect.right)-max(box.left,rect.left)) * max(0,min(box.bottom,rect.bottom)-max(box.top,rect.top))
                    area = min(box.width()*box.height(),rect.width()*rect.height())
                    return area > 0 and intersection / area > .8
                if not any(overlaps(other) for other in unique):
                    unique.append(heading)
            headings = unique
            if len(headings) != 1:
                raise DraftProblem("Select the exact " + expected + " conversation in the app, then resume. "
                                   "The active recipient is not uniquely verified.")

    @staticmethod
    def emails(text):
        return set(re.findall(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9.-]+\.[a-z]{2,63}",
                              text.casefold()))

    def compose_container(self, body):
        container = body
        for _ in range(32):
            self.check()
            container = container.GetParentControl()
            if not container:
                break
            # Gmail's composer exposes role=dialog through UI Automation.
            if (container.LocalizedControlType.casefold() == "dialog"
                    or container.GetPropertyValue(30101) == 'dialog'
                    or ((container.Name or '').startswith('Compose:') and container.ControlTypeName in {'WindowControl','PaneControl'})):
                return container
            if container.ControlTypeName == "WindowControl":
                break
        raise DraftProblem("Gmail's compose area could not be isolated. No email text was entered.")

    def compose_addresses(self, container, body, subject, to, sender):
        excluded = {tuple(c.GetRuntimeId()) for field in (body, subject, to)
                    for c in self.nodes(field)}
        addresses = set()
        for control in self.nodes(container):
            if tuple(control.GetRuntimeId()) in excluded:
                continue
            # Restrict to leaves/controls, excluding aggregate container names.
            if control.ControlTypeName not in {"TextControl", "ButtonControl", "HyperlinkControl", "EditControl", "GroupControl"}:
                continue
            name = (control.Name or "") + ' ' + (control.HelpText or '')
            found = self.emails(name)
            if re.match(r"From\b", name, re.I):
                if found != {sender.casefold()}:
                    raise DraftProblem("The email From address is not the configured sender.")
                continue
            if control.ControlTypeName == "EditControl":
                found |= self.emails(self.read(control))
            addresses |= found
        return addresses

    def gmail_fields(self, root, draft):
        def await_body(seconds):
            until = min(self.deadline, time.monotonic() + seconds)
            while True:
                self.check()
                body = self.find(root, r'Message Body', {'EditControl'}, optional=True)
                if body or time.monotonic() >= until:
                    return body
                time.sleep(.2)
        body = await_body(1)
        if not body:
            if draft.get("prepared"):
                raise DraftProblem("The prepared email is no longer open; it will not be recreated.")
            for control in self.controls(root, {'PaneControl', 'WindowControl', 'GroupControl'}):
                try:
                    existing_compose = not control.IsOffscreen and (control.Name or '').startswith('Compose:')
                except Exception:
                    continue
                if existing_compose:
                    body = await_body(3)
                    if not body:
                        raise DraftProblem('An email composer is already open, but its message field could not be verified. No additional compose window was opened.')
                    break
            if not body:
                self.invoke(self.find(root, r"Compose", {"ButtonControl"}))
                body = await_body(4)
                if not body:
                    raise DraftProblem('Gmail opened Compose, but its message field did not finish loading. No additional compose window was opened.')
        container = self.compose_container(body)
        subject = self.find(container, r"Subject", {"EditControl"})
        to = self.find(container, r"To recipients|To", {"EditControl", "ComboBoxControl"}, optional=True)
        if not to:
            # Gmail collapses the recipient editor after focus leaves it.
            # Expand the exact recipient summary, then inspect all To/Cc/Bcc
            # chips before verifying or saving the previously prepared draft.
            labels = [control for control in self.controls(container, {'TextControl'})
                if not control.IsOffscreen and (control.Name or '').casefold() == draft['recipient'].casefold()
                and control.BoundingRectangle.width() > 0 and control.BoundingRectangle.height() > 0
                and control.BoundingRectangle.bottom <= subject.BoundingRectangle.top]
            if len(labels) != 1:
                raise DraftProblem('The collapsed Gmail recipient details could not be uniquely verified.')
            self.focus(root, subject)
            import win32gui
            box = labels[0].BoundingRectangle
            point = (int(box.xcenter()), int(box.ycenter()))
            hit = win32gui.WindowFromPoint(point)
            self.mark('recipient_summary_hit', point=point, root=root.NativeWindowHandle,
                      hit=hit, foreground=win32gui.GetForegroundWindow(),
                      hit_class=win32gui.GetClassName(hit) if hit else '')
            if hit != root.NativeWindowHandle and not win32gui.IsChild(root.NativeWindowHandle, hit):
                raise DraftProblem('The Gmail recipient summary is covered. No draft was changed.')
            labels[0].Click(simulateMove=False, waitTime=.15)
            self._node_cache = {}
            for _ in range(10):
                to = self.find(container, r'To recipients|To', {'EditControl', 'ComboBoxControl'}, optional=True)
                if to:
                    break
                time.sleep(.2)
            if not to:
                raise DraftProblem('Gmail did not expand its recipient editor. No additional Compose was opened.')
        if self.read(to).strip().casefold() == draft['recipient'].casefold():
            # Clicking the collapsed summary temporarily turns its one
            # existing chip into editable address text. Commit that exact
            # unchanged address by focus movement before chip verification.
            # Also handle an editor left expanded by an interrupted retry.
            self.focus(root, subject)
            time.sleep(.2)
            self._node_cache = {}
        return container, body, subject, to

    def verify_gmail_recipient(self, fields, draft):
        from _ctypes import COMError
        container, body, subject, to = fields
        for attempt in range(3):
            self._node_cache = {}
            try:
                if (self.read(to) or self.compose_addresses(container, body, subject, to, draft['sender'])
                        != {draft['recipient'].casefold()}):
                    raise DraftProblem('Gmail must expose exactly the requested recipient, with no extra To/Cc/Bcc addresses.')
                return
            except COMError as error:
                if attempt == 2:
                    raise DraftProblem('Gmail changed its recipient controls during verification. The composer was preserved.') from error
                time.sleep(.15)

    def calendar_availability(self, request):
        from datetime import date
        self.started = time.monotonic()
        self.deadline = self.started + 18
        self.trace = []
        self._platform = 'calendar'
        day = date.fromisoformat(request['date'])
        label = f'{day:%A, %B} {day.day}'
        expected_heading = rf'Schedule starting {re.escape(label)}, {day.year}, \d+ events?'
        while True:
            self.check()
            self._node_cache = {}
            try:
                root = self.window('calendar','chrome')
                self.identity(root, {'platform':'gmail','sender':request['sender'],'recipient':''})
                heading = self.find(root, expected_heading, {'TextControl','HeaderControl'}, optional=True)
                if heading or any(re.fullmatch(expected_heading, control.Name or '', re.I)
                                  for control in self.nodes(root)):
                    break
            except DraftProblem:
                if time.monotonic() >= self.deadline - 1:
                    raise
            time.sleep(.25)
        controls = self.nodes(root)
        if any('could not load the data' in (control.Name or '').casefold() for control in controls):
            raise DraftProblem('Google Calendar did not load the schedule. Availability is unknown.')
        day_exists = any((control.Name or '') == label and control.ControlTypeName == 'ButtonControl'
                         for control in controls)
        if not day_exists:
            raise DraftProblem('The requested date was not visible in the loaded schedule.')
        events = list(dict.fromkeys((control.Name or '') for control in controls
                      if control.ControlTypeName == 'ButtonControl' and
                      f'{day:%B} {day.day}, {day.year}' in (control.Name or '') and
                      'Calendar:' in (control.Name or '')))
        return {'status':'schedule_observed', 'verified':True, 'date':day.isoformat(),
                'events':events, 'note':'This covers calendars shown in Google Calendar Schedule.'}

    def save_previous_gmail(self, root, draft):
        previous = self._last_gmail or draft.get('_previous_gmail')
        if not previous or previous['draft_id'] == draft.get('draft_id'):
            return
        body = self.find(root, r'Message Body', {'EditControl'}, optional=True)
        if not body:
            self._last_gmail = None
            return
        if previous.get('_window', root.NativeWindowHandle) != root.NativeWindowHandle:
            raise DraftProblem('A different Gmail composer is open. It was preserved; save or close it before continuing.')
        fields = self.gmail_fields(root, previous)
        self.verify_gmail_recipient(fields, previous)
        if (self.read(fields[1]) != normalized(previous['body'])
                or self.read(fields[2]) != normalized(previous['subject'])):
            raise DraftProblem('The previous email was edited. It was preserved; save or close it before continuing.')
        self.identity(root, previous)
        self.invoke(self.find(fields[0], r'Save & close', {'ButtonControl'}))
        for _ in range(10):
            self._node_cache = {}
            if not self.find(root, r'Message Body', {'EditControl'}, optional=True):
                self._last_gmail = None
                self.mark('previous_gmail_saved')
                return
            time.sleep(.2)
        raise DraftProblem('The previous email did not finish saving/closing. No additional Compose was opened.')

    def close_site(self, host):
        import psutil
        import win32gui
        import win32api
        import win32con
        matches = []
        for root in self.auto.GetRootControl().GetChildren():
            self.check()
            try:
                if not (root.Name or '').endswith(' - Google Chrome'):
                    continue
                process = psutil.Process(root.ProcessId)
                if process.name().casefold() != 'chrome.exe' or any(arg.startswith('--user-data-dir=') for arg in process.cmdline()):
                    continue
                address = self.find(root, r'Address and search bar', {'EditControl'}, optional=True)
                if not address:
                    continue
                value = self.read(address)
                parsed = urlsplit(value if '://' in value else 'https://' + value)
                if parsed.scheme in {'http', 'https'} and parsed.hostname == host:
                    matches.append((root, address, value))
            except Exception:
                continue
        if len(matches) != 1:
            return {'closed': False, 'note': 'No unique selected Chrome tab matches ' + host + '. Select the intended tab first; nothing was closed.'}
        root, address, value = matches[0]
        self.focus(root, address)
        if self.read(address) != value or win32gui.GetForegroundWindow() != root.NativeWindowHandle:
            raise DraftProblem('The selected tab changed. Nothing was closed.')
        self.check()
        # Fixed close-tab shortcut only. Normal browser before-unload prompts
        # remain for the owner; no Return, click or force-close follows it.
        win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
        try:
            win32api.keybd_event(0x57, 0, 0, 0)
            win32api.keybd_event(0x57, 0, win32con.KEYEVENTF_KEYUP, 0)
        finally:
            win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
        for _ in range(8):
            time.sleep(.15)
            self.check()
            if not win32gui.IsWindow(root.NativeWindowHandle):
                return {'closed': True, 'note': 'Closed the selected ' + host + ' tab.'}
            self._node_cache = {}
            fresh = self.find(root, r'Address and search bar', {'EditControl'}, optional=True)
            if fresh and self.read(fresh) != value:
                return {'closed': True, 'note': 'Closed the selected ' + host + ' tab.'}
        return {'closed': False, 'note': 'Close requested. The tab is still visible; resolve any browser prompt yourself.'}

    def prepare(self, draft):
        self.started = time.monotonic()
        self.trace = []
        self._node_cache = {}
        self._platform = draft['platform']
        self._clicked_field = None
        self.deadline = self.started + 26
        self.mark('start')
        selected_recipient = None
        if draft.get('operation') == 'close_site':
            return self.close_site(draft['host'])
        platform = draft["platform"]
        # A newly launched normal browser may need several seconds before its
        # page and accessibility controls exist. Never open another copy here.
        until = self.started + 12
        while True:
            try:
                if platform == 'gmail':
                    root = self.window(platform, draft['transport'], sender=draft['sender'],
                                       window_handle=draft.get('window_handle'))
                else:
                    root = self.window(platform, draft['transport'])
                break
            except DraftProblem:
                if time.monotonic() >= until:
                    raise
                time.sleep(.45)
        if platform == 'instagram' and "couldn't load" in (root.Name or '').casefold() and not draft.get('prepared'):
            import win32gui
            try:
                win32gui.SetForegroundWindow(root.NativeWindowHandle)
            except Exception:
                root.SetFocus()
            foreground = win32gui.GetForegroundWindow()
            if foreground != root.NativeWindowHandle and not win32gui.IsChild(root.NativeWindowHandle,foreground):
                raise DraftProblem('Instagram must be foreground before its failed inbox can be reloaded.')
            import win32api
            import win32con
            win32api.keybd_event(win32con.VK_CONTROL,0,0,0)
            try:
                win32api.keybd_event(0x52,0,0,0)
                win32api.keybd_event(0x52,0,win32con.KEYEVENTF_KEYUP,0)
            finally:
                win32api.keybd_event(win32con.VK_CONTROL,0,win32con.KEYEVENTF_KEYUP,0)
            time.sleep(2)
            if "couldn't load" in (root.Name or '').casefold():
                raise DraftProblem('Instagram returned Page could not load after retrying. No message was entered.')
        if draft.get('operation') == 'inbox':
            if platform == 'instagram':
                link = self.find(root, r'Messages(?:\s+Direct messaging.*)?', {'HyperlinkControl'})
                url = self.read(link)
                if (urlsplit(url).hostname not in {'instagram.com', 'www.instagram.com'}
                        or not re.fullmatch(r'/direct/(?:inbox/?|t/\d+/?)', urlsplit(url).path)):
                    raise DraftProblem('The Instagram Messages destination could not be verified.')
                self.invoke(link)
                return {'status': 'opened', 'note': 'Opened the Messages section in your installed Instagram app.'}
            return {'status':'opened', 'note':'Your WhatsApp chat list is open.'}
        if platform == "gmail":
            for attempt in range(8):
                try:
                    self.identity(root, draft)
                    break
                except DraftProblem:
                    if attempt == 7:
                        raise
                    time.sleep(.5)
            self.save_previous_gmail(root, draft)
            fields = self.gmail_fields(root, draft)
            container, body, subject, to = fields
            if draft.get("prepared"):
                self.verify_gmail_recipient(fields, draft)
                if self.read(subject) != normalized(draft["subject"]):
                    raise DraftProblem("The email subject changed; it will not be recreated.")
            else:
                values = [self.read(field) for field in (body, subject, to)]
                addresses = self.compose_addresses(container, body, subject, to, draft['sender'])
                self.mark('gmail_existing_fields', body_length=len(values[0]),
                          subject_length=len(values[1]), to_length=len(values[2]),
                          address_count=len(addresses))
                if any(values) or addresses:
                    raise DraftProblem("An email draft already contains text or recipients. It was preserved; close/save it before retrying.")
                self.fill(root, to, draft["recipient"])
                self.focus(root, subject)  # Commit To by focus movement, never Enter.
                time.sleep(.2)
                self.verify_gmail_recipient(fields, draft)
                self.identity(root, draft)
                self.fill(root, subject, draft["subject"])
        else:
            try:
                self.identity(root, draft)
            except DraftProblem:
                if draft.get("prepared"):
                    raise DraftProblem("The original conversation is no longer selected; the draft will not be recreated.")
                search = None
                if platform == 'whatsapp':
                    bounds = root.BoundingRectangle
                    candidates = [c for c in self.controls(root, {'EditControl'})
                        if not c.IsOffscreen and not c.IsPassword
                        and c.BoundingRectangle.left < bounds.left + bounds.width() * .45
                        and c.BoundingRectangle.top < bounds.top + bounds.height() * .4]
                    if len(candidates) == 1:
                        search = candidates[0]
                if platform == 'instagram':
                    search = self.instagram_search(root, optional=True)
                elif not search:
                    search = self.find(root, r"Search|Clear search|Search or start a new chat|Search chats",
                                       {"EditControl"}, optional=True)
                if not search and platform == 'instagram':
                    link = self.find(root, r'Messages(?:\s+Direct messaging.*)?', {'HyperlinkControl'})
                    url = urlsplit(self.read(link))
                    if (url.hostname not in {'instagram.com','www.instagram.com'}
                            or not re.fullmatch(r'/direct/(?:inbox/?|t/\d+/?)', url.path)):
                        raise DraftProblem('The Instagram inbox link could not be verified.')
                    self.invoke(link)
                    time.sleep(.7)
                    search = self.instagram_search(root, optional=True)
                if not search and platform == 'whatsapp':
                    # WhatsApp removes the placeholder accessible name when its
                    # search has focus. Verify the single edit in the chat-list
                    # search region, rather than relying on that disappearing name.
                    bounds = root.BoundingRectangle
                    candidates = [c for c in self.nodes(root) if c.ControlTypeName == 'EditControl'
                        and not c.IsPassword and c.BoundingRectangle.left < bounds.left + bounds.width() * .45
                        and c.BoundingRectangle.top < bounds.top + bounds.height() * .4]
                    if len(candidates) == 1:
                        search = candidates[0]
                if not search:
                    raise DraftProblem("Open the app's recipient search or intended conversation, then resume.")
                query = draft['recipient'].lstrip('@')
                if platform == 'whatsapp':
                    query = re.sub(r'\s*\(you\)\s*$', '', query, flags=re.I)
                self.fill(root, search, query, replace=True)
                time.sleep(.5)
                exact = draft["recipient"].lstrip("@").casefold()
                def instagram_row(control):
                    if platform != 'instagram':
                        return False
                    label = (control.Name or '').strip().casefold()
                    bounds = root.BoundingRectangle
                    if control.BoundingRectangle.left >= bounds.left + bounds.width() * .5:
                        return False
                    for prefix in ('user-profile-picture ', 'user avatar '):
                        if not label.startswith(prefix):
                            continue
                        label = label[len(prefix):]
                        if label == exact or label.startswith(exact + ' '):
                            return True
                        # Search results include display name, exact username,
                        # then optional bio. Header profile URL is independently
                        # checked after selection and before any message entry.
                        return bool(re.fullmatch(r'[a-z0-9._]+', exact) and re.search(
                            r'(?<![\w.])' + re.escape(exact) + r'(?![\w.])', label))
                    return False
                for search_attempt in range(9 if platform == 'instagram' else 1):
                    self._node_cache = {}
                    rows = []
                    for control in self.nodes(root):
                        try:
                            kind, name = control.ControlTypeName, control.Name or ''
                            if kind not in {'ListItemControl', 'DataItemControl', 'ButtonControl', 'HyperlinkControl'}:
                                continue
                            if (instagram_row(control) if platform == 'instagram' else
                                    (name.strip().lstrip('@').casefold() == exact
                                    or (platform == 'whatsapp' and kind in {'ListItemControl', 'DataItemControl'}
                                        and name.casefold().startswith(exact + ' ')))):
                                rows.append(control)
                        except Exception:
                            continue
                    if rows or search_attempt == 8:
                        break
                    time.sleep(.25)
                if platform == 'instagram' and re.fullmatch(r'[a-z0-9._]+', exact):
                    account_labels = []
                    for row in rows:
                        # A username mentioned in mutual-follow/bio text is not
                        # the account's own username. Prefer its exact rendered
                        # text label over that broad aggregate-name fallback.
                        if ((row.Name or '').casefold().endswith(' ' + exact)
                                or any(child.ControlTypeName == 'TextControl'
                                    and (child.Name or '').strip().casefold() == exact
                                    for child in self.nodes(row))):
                            account_labels.append(row)
                    if account_labels:
                        rows = account_labels
                unique_rows = []
                for row in rows:
                    box = row.BoundingRectangle
                    def same_visible_row(other):
                        rect = other.BoundingRectangle
                        overlap = max(0,min(box.right,rect.right)-max(box.left,rect.left)) * max(0,min(box.bottom,rect.bottom)-max(box.top,rect.top))
                        area = min(box.width()*box.height(),rect.width()*rect.height())
                        return area > 0 and overlap / area > .8
                    if not any(same_visible_row(other) for other in unique_rows):
                        unique_rows.append(row)
                rows = unique_rows
                if not rows:
                    raise DraftProblem('I could not find an exact contact named ' + draft['recipient'] +
                        '. Correct the name or choose the conversation in the app. I kept your message; nothing was typed or sent.')
                choose_top = platform == 'whatsapp' and draft.get('top_result') and len(rows) > 1
                if len(rows) > 1 and not choose_top:
                    raise DraftProblem('More than one contact matches ' + draft['recipient'] +
                        '. Say “The recipient is” followed by the full contact name, or select the exact chat in the app. '
                        'Your message is still held for review.')
                if platform == 'whatsapp':
                    # WhatsApp exposes an inert accessibility selection action
                    # on some contact rows. Click the verified visible row in
                    # the native wrapper; never focus the hidden Chrome host.
                    import win32gui
                    if choose_top:
                        bounds = root.BoundingRectangle
                        rows = [item for item in rows if item.ControlTypeName in {'DataItemControl', 'ListItemControl'}
                                and bounds.top + bounds.height() * .15 < item.BoundingRectangle.ycenter() < bounds.bottom
                                and bounds.left < item.BoundingRectangle.xcenter() < bounds.left + bounds.width() * .45]
                        if not rows:
                            raise DraftProblem('The top WhatsApp result could not be verified as a visible chat row.')
                        rows.sort(key=lambda item: (item.BoundingRectangle.top, -item.BoundingRectangle.width()))
                    row = rows[0]
                    row_label = (row.Name or '').strip().casefold()
                    box, bounds = row.BoundingRectangle, root.BoundingRectangle
                    point = (int(box.xcenter()), int(box.ycenter()))
                    hit = win32gui.WindowFromPoint(point)
                    if (not (bounds.left < point[0] < bounds.left + bounds.width() * .45)
                            or not (bounds.top + bounds.height() * .15 < point[1] < bounds.bottom)
                            or not (hit == root.NativeWindowHandle or win32gui.IsChild(root.NativeWindowHandle, hit))):
                        raise DraftProblem('The matched contact row is covered or outside the chat list. No message was entered.')
                    row.Click(simulateMove=False, waitTime=.15)
                    self._node_cache = {}
                    self.mark('contact_row_clicked')
                else:
                    self.invoke(rows[0])
                time.sleep(.3)
                if choose_top:
                    composer = self.find(root, r'Type a message to .+', {'EditControl'})
                    match = re.fullmatch(r'Type a message to (.+)', composer.Name or '', re.I)
                    actual = match[1].strip() if match else ''
                    candidate = actual.casefold()
                    if (not candidate or not (candidate == exact or candidate.startswith(exact + ' '))
                            or not (row_label == candidate or row_label.startswith(candidate + ' '))):
                        raise DraftProblem('The opened WhatsApp chat did not match the top search result.')
                    selected_recipient = actual
                    draft = {**draft, 'recipient': actual}
                if platform == 'instagram' and re.fullmatch(r'[A-Za-z0-9._]+', draft['recipient'].lstrip('@')):
                    address = self.read(self.find(root, r'Address and search bar', {'EditControl'}))
                    page = urlsplit(address if '://' in address else 'https://' + address)
                    if page.path.strip('/').casefold() == exact:
                        # Some accounts open their profile before a new DM.
                        # Only the exact requested profile may open Message;
                        # this button opens a composer and never sends it.
                        self.invoke(self.find(root, r'Message', {'ButtonControl'}))
                        time.sleep(.5)
                for header_attempt in range(6 if platform == 'instagram' else 1):
                    try:
                        self.identity(root, draft)
                        break
                    except DraftProblem:
                        if platform != 'instagram' or header_attempt == 5:
                            raise
                        time.sleep(.2)
            body = self.find(root, r"Type a message(?: to .+)?|Type a message\.{3}|Message(?:\.{3}|\u2026)?",
                             {"EditControl"})
        self.identity(root, draft)
        if draft.get("prepared"):
            if self.read(body) != normalized(draft["body"]):
                raise DraftProblem("This draft changed or was sent manually; it will not be recreated.")
        else:
            if platform == "gmail":
                self.verify_gmail_recipient(fields, draft)
            self.fill(root, body, draft["body"])
        self.identity(root, draft)
        if platform == "gmail":
            self.verify_gmail_recipient(fields, draft)
            self._last_gmail = {**draft, 'prepared': True, '_window': root.NativeWindowHandle}
        result = {"status": "draft_ready", "note": "Draft ready. Verify it and press Send in the app."}
        if selected_recipient:
            result.update(selected_recipient=selected_recipient,
                          note=f'Draft ready in the top WhatsApp result, {selected_recipient}. Verify it and press Send.')
        return result
