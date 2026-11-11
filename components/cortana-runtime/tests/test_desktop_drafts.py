"""App-first routing and conservative native draft behavior without real accounts."""
import asyncio
from contextlib import nullcontext
from pathlib import Path
import sys
import threading
import time
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))
sys.path.insert(0, str(ROOT))
from core import communication_targets as targets, desktop_drafts as sessions, tasks
from core.native_draft_ui import NativeDraftUI
from core.draft_adapters import DraftProblem


class RoutingTests(unittest.TestCase):
    def test_plain_gmail_launch_and_search_use_configured_sender(self):
        from tools.web import _build_url
        with patch.object(targets, "preferences", return_value={"gmail_sender": "owner@example.com"}):
            self.assertEqual(_build_url("gmail", "", ""),
                             "https://mail.google.com/mail/?authuser=owner%40example.com")
            self.assertEqual(_build_url("gmail", "meeting tomorrow", ""),
                             "https://mail.google.com/mail/?authuser=owner%40example.com#search/meeting+tomorrow")

    def test_installed_apps_are_preferred_without_browser_launch(self):
        for platform in ("whatsapp", "instagram"):
            with self.subTest(platform=platform), patch.object(targets, "approved_apps", return_value={platform: ["installed.exe"]}), \
                    patch.object(targets, 'preferences', return_value={}), \
                    patch("tools.apps.open_application", return_value={"launched": True}) as launch, \
                    patch.object(targets.subprocess, "Popen") as browser:
                self.assertEqual(targets.open_target(platform)["transport"], "application")
                launch.assert_called_once_with(platform)
                browser.assert_not_called()

    def test_instagram_browser_override_uses_the_same_chrome_profile(self):
        with patch.object(targets, 'approved_apps', return_value={'chrome': ['chrome.exe'], 'instagram': ['installed.exe']}), \
                patch.object(targets.Path, 'is_file', return_value=True), \
                patch.object(targets, 'preferences', return_value={'instagram_transport': 'chrome', 'chrome_profile_directory': 'Default'}), \
                patch.object(targets.subprocess, 'Popen') as launch:
            self.assertEqual(targets.open_target('instagram')['transport'], 'chrome')
            self.assertEqual(launch.call_args.args[0], [
                'chrome.exe', '--profile-directory=Default', 'https://www.instagram.com/direct/inbox/',
            ])

    def test_gmail_uses_main_profile_and_requested_sender_without_debugging(self):
        with patch.object(targets, "approved_apps", return_value={"chrome": ["chrome.exe"]}), \
                patch.object(targets.Path, "is_file", return_value=True), \
                patch.object(targets, "preferences", return_value={"gmail_sender": "owner@example.com", "chrome_profile_directory": "Default"}), \
                patch.object(targets.subprocess, "Popen") as launch:
            targets.open_target("gmail")
            self.assertEqual(launch.call_args.args[0], [
                "chrome.exe", "--profile-directory=Default",
                "--new-window",
                "https://mail.google.com/mail/?authuser=owner%40example.com",
            ])
            self.assertFalse(launch.call_args.kwargs["shell"])

    def test_website_fallback_does_not_need_gmail_configuration(self):
        with patch.object(targets, "approved_apps", return_value={"chrome": ["chrome.exe"]}), \
                patch.object(targets.Path, "is_file", return_value=True), \
                patch.object(targets, "preferences", return_value={}), \
                patch.object(targets.subprocess, "Popen") as launch:
            self.assertEqual(targets.open_target("whatsapp")["transport"], "chrome")
            self.assertEqual(launch.call_args.args[0], ["chrome.exe", "https://web.whatsapp.com/"])

    def test_invalid_profile_is_rejected_before_launch(self):
        with patch.object(targets, "approved_apps", return_value={"chrome": ["chrome.exe"]}), \
                patch.object(targets.Path, "is_file", return_value=True), \
                patch.object(targets, "preferences", return_value={"chrome_profile_directory": "../Other"}), \
                patch.object(targets.subprocess, "Popen") as launch:
            with self.assertRaises(ValueError):
                targets.open_target("gmail")
            launch.assert_not_called()


class SessionTests(unittest.TestCase):
    def tearDown(self):
        sessions._drafts.clear()

    def test_cancel_only_terminates_owned_worker(self):
        worker = Mock(pid=123)
        worker.poll.return_value = None
        chrome = Mock()
        chrome.name.return_value = "chrome.exe"
        python = Mock()
        python.name.return_value = "python.exe"
        with patch.object(sessions, "_process", worker), patch("psutil.Process") as process:
            process.return_value.children.return_value = [python, chrome]
            sessions.cancel_drafts()
            worker.terminate.assert_called_once()
            python.terminate.assert_called_once()
            chrome.terminate.assert_not_called()

    def test_cancel_invalidates_queued_action_before_open(self):
        entered = threading.Event()
        errors = []
        def effects():
            entered.set()
            return nullcontext()
        def request():
            try:
                sessions.draft_request("open", {"platform": "gmail"})
            except sessions.DesktopDraftUnavailable as error:
                errors.append(error)
        with patch.object(sessions, "_process", None), patch("core.tool_registry.serialized_effects", effects), \
                patch.object(targets, "open_target") as launch:
            with sessions._lock:
                thread = threading.Thread(target=request)
                thread.start()
                self.assertTrue(entered.wait(2))
                sessions.cancel_drafts()
            thread.join(2)
            self.assertFalse(thread.is_alive())
            self.assertEqual(len(errors), 1)
            launch.assert_not_called()

    def test_cancel_wins_over_worker_completion(self):
        work = tasks.Work(task=None)
        token = tasks.current.set(work)
        def completed(**kwargs):
            work.cancelled.set()
            return {"id": "test", "result": {"status": "draft_ready"}}
        try:
            with patch.object(sessions, "_start"), patch.object(sessions, "_process", Mock()), \
                    patch.object(sessions, "_responses", Mock(get=completed)), \
                    patch.object(sessions, "uuid4", return_value=SimpleNamespace(hex="test")):
                with self.assertRaises(asyncio.CancelledError):
                    sessions._prepare_in_app({}, sessions._generation)
        finally:
            tasks.current.reset(token)

    def test_cancelled_generation_cannot_start_a_worker(self):
        with patch.object(sessions, "_start") as start:
            with self.assertRaises(sessions.DesktopDraftUnavailable):
                sessions._prepare_in_app({}, sessions._generation - 1)
            start.assert_not_called()


class Control:
    def __init__(self, key, name="", kind="TextControl", value="", children=()):
        self.key, self.Name, self.ControlTypeName = key, name, kind
        self.NativeWindowHandle = key
        self.value, self.children = value, list(children)
        self.IsOffscreen = False
        self.IsPassword = False
        self.HelpText = ''
        self.BoundingRectangle = SimpleNamespace(left=key * 100, top=100, right=key * 100 + 50, bottom=140)
        self.LocalizedControlType = "dialog" if kind == "PaneControl" else kind
        self.parent = None
        for child in children:
            child.parent = self

    def GetRuntimeId(self):
        return (self.key,)

    def GetChildren(self):
        return self.children

    def GetParentControl(self):
        return self.parent


class NativeTests(unittest.TestCase):
    def setUp(self):
        self.ui = NativeDraftUI.__new__(NativeDraftUI)
        self.ui._last_gmail = None
        self.ui._node_cache = {}
        self.ui.trace = []
        self.ui.deadline = time.monotonic() + 20
        self.ui.auto = SimpleNamespace(PatternId=SimpleNamespace(InvokePattern=1, SelectionItemPattern=2))

    def test_duplicate_provider_nodes_are_deduplicated(self):
        a = Control(2, "Search", "EditControl")
        b = Control(2, "Search", "EditControl")
        root = Control(1, children=[a, b])
        self.assertIs(self.ui.find(root, "Search", {"EditControl"}), a)

    def test_optional_lookup_cannot_hide_multiple_composers(self):
        root = Control(1, children=[Control(2, "Message Body", "EditControl"), Control(3, "Message Body", "EditControl")])
        with self.assertRaises(DraftProblem):
            self.ui.find(root, "Message Body", {"EditControl"}, optional=True)

    def test_provider_cycle_is_bounded(self):
        root = Control(1)
        root.children.append(root)
        self.assertEqual(self.ui.nodes(root), [root])

    def test_truncated_tree_cannot_be_treated_as_unique(self):
        root = Control(1, children=[Control(2), Control(3)])
        with self.assertRaises(DraftProblem):
            self.ui.nodes(root, maximum=2)

    def test_send_control_is_never_invoked(self):
        control = Control(2, "Send")
        control.GetPattern = Mock()
        with self.assertRaises(DraftProblem):
            self.ui.invoke(control)
        control.GetPattern.assert_not_called()

    def test_existing_text_is_preserved_before_focus_or_input(self):
        edit = Control(2, "Message", "EditControl")
        self.ui.read = Mock(return_value="My unfinished draft")
        self.ui.focus = Mock()
        with self.assertRaises(DraftProblem):
            self.ui.fill(Control(1), edit, "New message")
        self.ui.focus.assert_not_called()

    def test_prepared_message_never_searches_or_switches_chats(self):
        self.ui.window = Mock(return_value=Control(1))
        self.ui.identity = Mock(side_effect=DraftProblem("Wrong conversation"))
        self.ui.find = Mock()
        with self.assertRaisesRegex(DraftProblem, "will not be recreated"):
            self.ui.prepare({"platform": "whatsapp", "transport": "application", "prepared": True})
        self.ui.find.assert_not_called()

    def gmail(self, extras=()):
        self.body = Control(3, "Message Body", "EditControl")
        self.subject = Control(4, "Subject", "EditControl")
        self.to = Control(5, "To recipients", "EditControl")
        self.dialog = Control(2, kind="PaneControl", children=[self.body, self.subject, self.to, *extras])
        self.root = Control(1, kind="WindowControl", children=[self.dialog])
        self.ui.window = Mock(return_value=self.root)
        self.ui.identity = Mock()
        self.ui.read = lambda c: c.value
        self.ui.fill = Mock()
        self.ui.focus = Mock()
        return {"draft_id": "gmail-test-draft", "platform": "gmail", "transport": "chrome", "recipient": "person@example.com",
                "sender": "owner@example.com", "body": "Hello", "subject": "Test"}

    def test_gmail_preserves_existing_recipient_even_with_empty_fields(self):
        draft = self.gmail([Control(6, "extra@example.com", "ButtonControl")])
        with self.assertRaisesRegex(DraftProblem, "already contains"):
            self.ui.prepare(draft)
        self.ui.fill.assert_not_called()

    def test_gmail_rejects_extra_cc_recipient_on_resume(self):
        draft = self.gmail([Control(6, "person@example.com", "ButtonControl"),
                            Control(7, "extra@example.com", "ButtonControl")])
        draft["prepared"] = True
        with self.assertRaisesRegex(DraftProblem, "no extra"):
            self.ui.prepare(draft)
        self.ui.fill.assert_not_called()

    def test_gmail_rejects_wrong_sender(self):
        draft = self.gmail([Control(6, "From: other@example.com", "ButtonControl")])
        with self.assertRaisesRegex(DraftProblem, "From address"):
            self.ui.prepare(draft)
        self.ui.fill.assert_not_called()

    def test_gmail_resume_verifies_without_recreating(self):
        draft = self.gmail([Control(6, "person@example.com", "ButtonControl")])
        draft["prepared"] = True
        self.subject.value, self.body.value = "Test", "Hello"
        self.assertEqual(self.ui.prepare(draft)["status"], "draft_ready")
        self.ui.fill.assert_not_called()
        self.body.value = ""
        with self.assertRaisesRegex(DraftProblem, "will not be recreated"):
            self.ui.prepare(draft)
        self.ui.fill.assert_not_called()

    def test_gmail_body_addresses_do_not_count_as_recipients(self):
        draft = self.gmail([Control(6, "person@example.com", "ButtonControl")])
        self.body.children.append(Control(7, "contact@example.com"))
        fields = self.dialog, self.body, self.subject, self.to
        self.ui.verify_gmail_recipient(fields, draft)


if __name__ == "__main__":
    unittest.main()
