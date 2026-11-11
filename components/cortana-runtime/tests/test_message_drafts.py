"""No account access: production URLs are intercepted with synthetic fixtures."""
import asyncio
import os
from pathlib import Path
import sys
import tempfile
import threading
from contextlib import nullcontext
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))
sys.path.insert(0, str(ROOT))
from core.draft_adapters import DraftBrowser, DraftProblem, validate_payload

MONITOR = """<script>
window.sent=0;window.enters=0;
document.addEventListener('click', e=>{if(e.target.id==='send') window.sent++});
document.addEventListener('keydown',e=>{if(e.key==='Enter')window.enters++});
</script>"""
GMAIL = """
<button onclick="document.querySelector('[role=dialog]').style.display='block'">Compose</button>
<div role="dialog" style="display:none">
<input aria-label="To recipients" onblur="if(this.value){let s=document.createElement('span');s.setAttribute('email',this.value);s.textContent=this.value;this.parentElement.appendChild(s);this.value=''}">
<input name="subjectbox">
<div role="textbox" contenteditable="true" aria-label="Message Body"></div>
<button id="send">Send</button></div>""" + MONITOR
WHATSAPP = """
<div id="side"><div role="textbox" contenteditable="true" aria-label="Search"></div></div>
<div id="pane-side">
<div role="listitem" onclick="choose(this)"><span title="Test Alex">Test Alex</span></div>
<div role="listitem" onclick="choose(this)"><span title="Test Alex Work">Test Alex Work</span></div>
</div><div id="main"><header><span title="Nobody">Nobody</span></header>
<footer><div role="textbox" contenteditable="true"></div><button id="send">Send</button></footer></div>
<script>function choose(row){let n=row.querySelector('span').title;let h=document.querySelector('header span');h.title=n;h.textContent=n}</script>""" + MONITOR
INSTAGRAM = """
<button onclick="document.querySelector('[role=dialog]').style.display='block'">New message</button>
<div role="dialog" style="display:none"><input name="queryBox" placeholder="Search...">
<a href="/test_alex/" onclick="event.preventDefault();window.selected='test_alex'">Test Alex</a>
<a href="/test_alex_work/" onclick="event.preventDefault();window.selected='test_alex_work'">Test Alex Work</a>
<button onclick="document.querySelector('[role=dialog]').style.display='none';let a=document.querySelector('main header a');a.href='/'+window.selected+'/';a.textContent=window.selected">Chat</button></div>
<main><header><a href="/nobody/">Nobody</a></header><textarea placeholder="Message..."></textarea><button id="send">Send</button></main>
""" + MONITOR


class DraftValidationTests(unittest.TestCase):
    def test_payload_preserves_exact_message(self):
        text = "  Namaste\nPlease call me.  "
        result = validate_payload({"platform": "gmail", "recipient": "test@example.invalid", "body": text})
        self.assertEqual(result["body"], text)

    def test_outgoing_script_policy_preserves_multilingual_recipient(self):
        for platform, recipient in (("gmail", "test@example.invalid"), ("whatsapp", "अजय"), ("instagram", "@test")):
            with self.subTest(platform=platform), self.assertRaisesRegex(DraftProblem, "Outgoing"):
                validate_payload({"platform": platform, "recipient": recipient, "body": "नमस्ते"})
        data = validate_payload({"platform": "whatsapp", "recipient": "अजय", "body": "Namaste, kal call karna 🙂"})
        self.assertEqual(data["recipient"], "अजय")
        self.assertIn("🙂", data["body"])

    def test_import_only_cleanup_never_terminates_other_session(self):
        from core import browser_session
        with patch.object(browser_session, "_process", None), patch.object(browser_session, "_owned_processes", {}), \
                patch.object(browser_session, "_known_processes", {99999: 123.0}), patch("psutil.Process") as process:
            browser_session.close_browser()
            process.assert_not_called()

    def test_cancel_invalidates_operation_queued_behind_browser_lock(self):
        from core import browser_session
        entered = threading.Event()
        errors = []
        def effects():
            entered.set()
            return nullcontext()
        def request():
            try:
                browser_session.browser_request("open", {"platform": "gmail"})
            except browser_session.BrowserUnavailable as error:
                errors.append(str(error))
        with patch.object(browser_session, "_process", None), patch.object(browser_session, "_owned_processes", {}), \
                patch.object(browser_session, "_start") as start, patch("core.tool_registry.serialized_effects", effects):
            with browser_session._lock:
                thread = threading.Thread(target=request)
                thread.start()
                self.assertTrue(entered.wait(2))
                browser_session.close_browser()
            thread.join(2)
            self.assertFalse(thread.is_alive())
            self.assertTrue(errors)
            start.assert_not_called()

    def test_cancelled_chat_stops_owned_browser(self):
        import queue
        from core import browser_session, tasks
        from unittest.mock import Mock
        work = tasks.Work(task=None)
        token = tasks.current.set(work)
        def waiting(*args, **kwargs):
            work.cancelled.set()
            raise queue.Empty
        responses = Mock()
        responses.get.side_effect = waiting
        try:
            with patch.object(browser_session, "_start"), patch.object(browser_session, "_process", Mock()), \
                    patch.object(browser_session, "_responses", responses), patch.object(browser_session, "close_browser") as close:
                with self.assertRaises(asyncio.CancelledError):
                    browser_session.browser_request("open", {"platform": "gmail"})
                close.assert_called_once()
        finally:
            tasks.current.reset(token)

    def test_cancel_wins_against_concurrent_browser_completion(self):
        from core import browser_session, tasks
        from unittest.mock import Mock
        from types import SimpleNamespace
        work = tasks.Work(task=None)
        token = tasks.current.set(work)
        def completes(*args, **kwargs):
            work.cancelled.set()
            return {"id": "a" * 32, "result": {"status": "draft_ready"}}
        responses = Mock()
        responses.get.side_effect = completes
        try:
            with patch.object(browser_session, "_start"), patch.object(browser_session, "_process", Mock()), \
                    patch.object(browser_session, "_responses", responses), \
                    patch.object(browser_session, "uuid4", return_value=SimpleNamespace(hex="a" * 32)), \
                    patch.object(browser_session, "close_browser") as close:
                with self.assertRaises(asyncio.CancelledError):
                    browser_session.browser_request("open", {"platform": "gmail"})
                close.assert_called_once()
        finally:
            tasks.current.reset(token)

    def test_rejects_ambiguous_email_and_header_injection(self):
        for recipient in ("Alice <test@example.com>", "a@example.com,b@example.com", "a@example.com\nBcc:b@example.com", "a@example.com?subject=bad"):
            with self.subTest(recipient=recipient), self.assertRaises(DraftProblem):
                validate_payload({"platform": "gmail", "recipient": recipient, "body": "Hello"})

    def test_rejects_unknown_fields_and_platform(self):
        for data in (
            {"platform": "gmail", "recipient": "test@example.com", "body": "Hi", "send": True},
            {"platform": "shell", "recipient": "X", "body": "Hi"},
            {"platform": "gmail", "recipient": "test@example.com", "body": "Hi", "subject": "Subject\r\nBcc:evil"},
        ):
            with self.assertRaises(DraftProblem):
                validate_payload(data)

    def test_tool_requires_explicit_communication_context(self):
        from tools.message_drafts import prepare_message_draft
        from core.tool_registry import ToolDenied
        with patch("tools.message_drafts.draft_request") as request:
            with self.assertRaises(ToolDenied):
                prepare_message_draft("whatsapp", "Test Alex", "Hello")
            request.assert_not_called()

    def test_worker_launch_environment_excludes_backend_credentials(self):
        from core.processes import public_environment
        with patch.dict(os.environ, {"CORTANA_API_TOKEN": "never-copy-me", "CORTANA_CLOUD_API_KEY": "also-secret"}):
            self.assertFalse(any(key.startswith("CORTANA_") for key in public_environment()))


class BrowserFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(
            executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe",
            headless=True, chromium_sandbox=True,
            env={k: v for k, v in os.environ.items() if not k.startswith("CORTANA_")},
        )

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.context = self.browser.new_context(locale="en-US")
        self.fixtures = {"mail.google.com": GMAIL, "web.whatsapp.com": WHATSAPP, "www.instagram.com": INSTAGRAM}
        def intercept(route):
            from urllib.parse import urlsplit
            route.fulfill(status=200, content_type="text/html; charset=utf-8",
                          body=self.fixtures.get(urlsplit(route.request.url).hostname, "<h1>Sign in manually</h1>"))
        self.context.route("**/*", intercept)
        self.service = DraftBrowser(self.context)

    def tearDown(self):
        for page in self.context.pages:
            self.assertEqual(page.evaluate("window.sent || 0"), 0, "Send was activated")
            self.assertEqual(page.evaluate("window.enters || 0"), 0, "Enter was pressed")
        self.context.close()

    def prepare(self, platform, recipient, body="Hello\nPlease call me"):
        return self.service.handle("prepare", {"platform": platform, "recipient": recipient, "body": body, "subject": "Test subject" if platform == "gmail" else ""})

    def test_gmail_exact_recipient_body_and_resume(self):
        result = self.prepare("gmail", "test@example.invalid")
        self.assertEqual(result["status"], "draft_ready", result)
        before = self.service.pages["gmail"].url
        self.service.handle("open", {"platform": "gmail"})
        self.assertEqual(self.service.pages["gmail"].url, before)
        resumed = self.service.handle("resume", {"draft_id": result["draft_id"]})
        self.assertEqual(resumed["status"], "draft_ready")

    def test_gmail_existing_draft_is_preserved(self):
        first = self.prepare("gmail", "test@example.invalid", "Original")
        second = self.prepare("gmail", "other@example.invalid", "New")
        self.assertEqual(first["status"], "draft_ready", first)
        self.assertEqual(second["status"], "error", second)
        self.assertEqual(self.service.pages["gmail"].get_by_role("textbox", name="Message Body").inner_text(), "Original")

    def test_gmail_changed_recipient_prevents_body_fill(self):
        self.fixtures["mail.google.com"] = GMAIL.replace("s.setAttribute('email',this.value)", "s.setAttribute('email','wrong@example.invalid')")
        result = self.prepare("gmail", "test@example.invalid")
        self.assertEqual(result["status"], "error")
        self.assertEqual(self.service.pages["gmail"].get_by_role("textbox", name="Message Body").inner_text().strip(), "")

    def test_whatsapp_ambiguity_requires_opaque_selection(self):
        result = self.prepare("whatsapp", "Test Alex")
        self.assertEqual(result["status"], "choose_recipient", result)
        page = self.service.pages["whatsapp"]
        self.assertEqual(page.locator("#main footer [role=textbox]").inner_text(), "")
        choice = result["candidates"][1]
        result = self.service.handle("select", {"draft_id": result["draft_id"], "candidate_id": choice["id"]})
        self.assertEqual(result["status"], "draft_ready", result)
        self.assertEqual(page.locator("#main header span").get_attribute("title"), "Test Alex Work")
        with self.assertRaises(DraftProblem):
            self.service.handle("select", {"draft_id": result["draft_id"], "candidate_id": choice["id"]})

    def test_whatsapp_preserves_existing_unsent_text(self):
        self.service.handle("open", {"platform": "whatsapp"})
        page = self.service.pages["whatsapp"]
        page.locator("#main footer [role=textbox]").fill("Existing user draft")
        result = self.prepare("whatsapp", "Test Alex Work")
        self.assertEqual(result["status"], "error", result)
        self.assertEqual(page.locator("#main footer [role=textbox]").inner_text(), "Existing user draft")

    def test_instagram_requires_selected_verified_username(self):
        result = self.prepare("instagram", "Test Alex")
        self.assertEqual(result["status"], "choose_recipient", result)
        result = self.service.handle("select", {"draft_id": result["draft_id"], "candidate_id": result["candidates"][0]["id"]})
        self.assertEqual(result["status"], "draft_ready", result)

    def test_instagram_wrong_active_username_refuses_fill(self):
        self.fixtures["www.instagram.com"] = INSTAGRAM.replace("a.href='/'+window.selected+'/'", "a.href='/wrong_person/'")
        result = self.prepare("instagram", "@test_alex_work")
        self.assertEqual(result["status"], "error", result)
        self.assertEqual(self.service.pages["instagram"].locator("textarea").input_value(), "")

    def test_login_resume_retains_exact_text(self):
        self.fixtures["mail.google.com"] = "<h1>Sign in manually</h1>" + MONITOR
        result = self.prepare("gmail", "test@example.invalid", "  Exact\nPlease call me  ")
        self.assertEqual(result["status"], "needs_login", result)
        self.service.pages["gmail"].set_content(GMAIL)
        result = self.service.handle("resume", {"draft_id": result["draft_id"]})
        self.assertEqual(result["status"], "draft_ready", result)
        self.assertEqual(result["preview"]["body"], "  Exact\nPlease call me  ")

    def test_modified_or_manually_sent_draft_is_not_recreated(self):
        result = self.prepare("gmail", "test@example.invalid")
        self.service.pages["gmail"].get_by_role("textbox", name="Message Body").fill("")
        result = self.service.handle("resume", {"draft_id": result["draft_id"]})
        self.assertEqual(result["status"], "error")
        self.assertEqual(self.service.pages["gmail"].get_by_role("textbox", name="Message Body").inner_text().strip(), "")

    def test_whatsapp_duplicate_names_fail_closed(self):
        self.fixtures["web.whatsapp.com"] = WHATSAPP.replace("Test Alex Work", "Test Alex")
        result = self.prepare("whatsapp", "Test Alex")
        self.assertEqual(result["status"], "error", result)
        self.assertIn("same displayed name", result["note"])
        self.assertEqual(self.service.pages["whatsapp"].locator("#main footer [role=textbox]").inner_text(), "")

    def test_whatsapp_reordered_candidates_fail_closed(self):
        result = self.prepare("whatsapp", "Test Alex")
        page = self.service.pages["whatsapp"]
        page.evaluate("let p=document.querySelector('#pane-side');p.prepend(p.lastElementChild)")
        result = self.service.handle("select", {"draft_id": result["draft_id"], "candidate_id": result["candidates"][0]["id"]})
        self.assertEqual(result["status"], "error", result)
        self.assertEqual(page.locator("#main footer [role=textbox]").inner_text(), "")

    def test_expired_or_foreign_candidate_cannot_be_selected(self):
        result = self.prepare("whatsapp", "Test Alex")
        with self.assertRaises(DraftProblem):
            self.service.handle("select", {"draft_id": result["draft_id"], "candidate_id": "0" * 32})
        self.service.drafts[result["draft_id"]].created -= 901
        with self.assertRaises(DraftProblem):
            self.service.handle("resume", {"draft_id": result["draft_id"]})


if __name__ == "__main__":
    unittest.main()
