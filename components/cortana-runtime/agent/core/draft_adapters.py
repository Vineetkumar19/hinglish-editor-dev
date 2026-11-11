"""Bounded, fixed browser interactions for drafts; there is no send operation.

Only contact-search metadata and the active draft are read. Page content never
becomes an instruction. Unknown layouts fail closed before a composer is filled.
This module intentionally imports neither settings nor the backend environment.
"""
from dataclasses import dataclass, field
import re
import time
import unicodedata
from urllib.parse import urlsplit
from uuid import uuid4

URLS = {
    "whatsapp": "https://web.whatsapp.com/",
    "gmail": "https://mail.google.com/mail/u/0/#inbox",
    "instagram": "https://www.instagram.com/direct/inbox/",
}
HOSTS = {"whatsapp": "web.whatsapp.com", "gmail": "mail.google.com", "instagram": "www.instagram.com"}
TTL_SECONDS = 15 * 60


class DraftProblem(ValueError):
    pass


def validate_payload(data):
    if not isinstance(data, dict) or set(data) - {"platform", "recipient", "body", "subject"}:
        raise DraftProblem("Unexpected draft fields.")
    platform, recipient, body, subject = (
        data.get("platform"), data.get("recipient"), data.get("body"), data.get("subject", "")
    )
    if platform not in URLS:
        raise DraftProblem("Choose WhatsApp, Gmail or Instagram.")
    if not isinstance(recipient, str) or not 1 <= len(recipient) <= 160:
        raise DraftProblem("Provide one recipient.")
    if recipient != recipient.strip() or any(ord(c) < 32 for c in recipient):
        raise DraftProblem("Recipient must be a single name or address without control characters.")
    if not isinstance(body, str) or not body.strip() or len(body) > 6000 or "\x00" in body:
        raise DraftProblem("Provide message text between 1 and 6000 characters.")
    if not isinstance(subject, str) or len(subject) > 300 or any(ord(c) < 32 for c in subject):
        raise DraftProblem("Subject must be a single line of at most 300 characters.")
    if any(char.isalpha() and "LATIN" not in unicodedata.name(char, "") for char in body + subject):
        required = "English" if platform == "gmail" else "English or Roman Hinglish"
        raise DraftProblem(f"Outgoing {platform} messages must use {required}. Hindi spoken instructions are supported; provide or translate the message text first.")
    if platform == "gmail" and not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,63}", recipient):
        raise DraftProblem("Gmail needs one exact email address, without a display name or other recipients.")
    return {"platform": platform, "recipient": recipient, "body": body, "subject": subject}


def visible(locator):
    return [locator.nth(i) for i in range(min(locator.count(), 100)) if locator.nth(i).is_visible()]


def one(locator, label):
    found = visible(locator)
    if len(found) != 1:
        raise DraftProblem(f"Could not identify one {label}. Nothing was sent; check the browser.")
    return found[0]


def content(locator):
    tag = locator.evaluate("(element) => element.tagName.toLowerCase()")
    return locator.input_value() if tag in {"input", "textarea"} else locator.inner_text()


def normalized(text):
    return text.replace("\r\n", "\n").replace("\u00a0", " ")


@dataclass
class Draft:
    platform: str
    recipient: str
    body: str
    subject: str = ""
    draft_id: str = field(default_factory=lambda: uuid4().hex)
    created: float = field(default_factory=time.monotonic)
    status: str = "needs_login"
    note: str = ""
    candidates: dict = field(default_factory=dict)
    selected: dict | None = None
    prepared: bool = False
    page: object = None

    def response(self):
        result = {
            "platform": self.platform, "draft_id": self.draft_id, "status": self.status,
            "recipient": self.recipient, "preview": {"body": self.body, "subject": self.subject},
            "note": self.note,
        }
        if self.status == "choose_recipient":
            result["candidates"] = [
                {"id": key, "label": value["label"], "detail": value["detail"]}
                for key, value in self.candidates.items()
            ]
        return result


class DraftBrowser:
    def __init__(self, context):
        self.context = context
        self.pages = {}
        self.drafts = {}
        self.deadline = 0.0

    def guard(self, platform=None, page=None):
        if time.monotonic() > self.deadline:
            raise DraftProblem("Draft preparation timed out. Review the browser before retrying.")
        if platform and page:
            url = urlsplit(page.url)
            if url.scheme != "https" or url.hostname != HOSTS[platform]:
                raise DraftProblem("The browser left the expected service. Complete sign-in manually.")

    def page(self, platform):
        page = self.pages.get(platform)
        if page is None or page.is_closed():
            self.guard()
            page = self.context.new_page()
            self.pages[platform] = page
            page.set_default_timeout(4000)
            page.goto(URLS[platform], wait_until="domcontentloaded", timeout=20000)
        return page

    def connection(self, platform):
        page = self.pages.get(platform)
        if page is None or page.is_closed():
            return {"platform": platform, "status": "not_open", "note": "Open the app and sign in manually."}
        try:
            self.guard(platform, page)
            if platform == "gmail":
                ready = visible(page.get_by_role("button", name=re.compile(r"^(Compose|लिखें)$"))) or visible(page.locator("input[name=subjectbox]"))
            elif platform == "whatsapp":
                ready = visible(page.locator("#pane-side"))
            else:
                ready = visible(page.get_by_role("button", name="New message", exact=True)) or visible(page.locator('[aria-label="New message"]'))
            return {"platform": platform, "status": "connected" if ready else "needs_login",
                    "note": "Signed-in interface detected." if ready else "Sign in manually in Cortana's browser, then click Resume."}
        except DraftProblem:
            return {"platform": platform, "status": "needs_login", "note": "Complete sign-in manually in Cortana's browser, then click Resume."}

    def handle(self, operation, payload, timeout=40):
        self.deadline = time.monotonic() + min(max(timeout, 1), 40)
        now = time.monotonic()
        self.drafts = {key: item for key, item in self.drafts.items() if now - item.created < TTL_SECONDS}
        if operation == "status":
            return {"integrations": [self.connection(name) for name in URLS],
                    "browser": {"status": "open", "note": "Dedicated browser; Cortana only prepares drafts. You press Send."}}
        if operation == "open":
            platform = payload.get("platform")
            if platform not in URLS or set(payload) != {"platform"}:
                raise DraftProblem("Unknown app.")
            page = self.page(platform)
            # Do not navigate an existing tab: it may contain the user's draft.
            page.bring_to_front()
            return self.connection(platform)
        if operation == "prepare":
            data = validate_payload(payload)
            if len(self.drafts) >= 100:
                raise DraftProblem("Too many pending drafts. Wait for older drafts to expire.")
            draft = Draft(**data)
            self.drafts[draft.draft_id] = draft
        elif operation in {"resume", "select"}:
            allowed = {"draft_id", "candidate_id"} if operation == "select" else {"draft_id"}
            if set(payload) != allowed:
                raise DraftProblem("Unexpected draft action fields.")
            draft = self.drafts.get(payload.get("draft_id"))
            if not draft:
                raise DraftProblem("This draft expired or Cortana restarted. Prepare it again with the exact text.")
            if operation == "select":
                if draft.prepared or draft.status != "choose_recipient":
                    raise DraftProblem("This draft is not awaiting recipient selection.")
                chosen = draft.candidates.get(payload.get("candidate_id"))
                if not chosen:
                    raise DraftProblem("That recipient option does not belong to this draft.")
                draft.selected = chosen
        else:
            raise DraftProblem("Unknown browser action.")
        try:
            page = self.page(draft.platform)
            page.bring_to_front()
            if self.connection(draft.platform)["status"] != "connected" and not draft.prepared:
                draft.status, draft.note = "needs_login", "Sign in manually, then click Resume. This draft can be resumed for 15 minutes."
                return draft.response()
            self.guard(draft.platform, page)
            if draft.prepared:
                self.verify(draft, page)
                draft.status = "draft_ready"
                identity = "contact name" if draft.platform == "whatsapp" else "recipient"
                draft.note = f"The original {identity} and exact draft text are still present. Review it and press Send yourself."
            else:
                getattr(self, f"prepare_{draft.platform}")(draft, page)
            return draft.response()
        except Exception as error:
            draft.status = "error"
            draft.note = str(error) if isinstance(error, DraftProblem) else "The page changed or did not respond. Check the browser; nothing was sent."
            return draft.response()

    def fill(self, draft, page, locator, text):
        self.guard(draft.platform, page)
        locator.fill(text, timeout=4000)

    def click(self, draft, page, locator):
        self.guard(draft.platform, page)
        locator.click(timeout=4000)

    def ready(self, draft, page):
        draft.page = page
        self.verify(draft, page)
        draft.prepared = True
        draft.status = "draft_ready"
        identity = "Contact name" if draft.platform == "whatsapp" else "Recipient"
        draft.note = f"{identity} and exact draft text verified in the browser. Review the intended person and press Send yourself. Cortana has not sent it."

    def gmail_fields(self, page):
        dialog = one(page.locator('[role="dialog"]').filter(has=page.locator("input[name=subjectbox]")), "Gmail compose window")
        subject = one(dialog.locator("input[name=subjectbox]"), "subject field")
        body = one(dialog.locator('[contenteditable="true"][role="textbox"][aria-label="Message Body"], [contenteditable="true"][role="textbox"][aria-label="संदेश का मुख्य भाग"]'), "message body")
        return dialog, subject, body

    def gmail_recipient(self, dialog, expected):
        # Committed address chips, not inferred names or raw text typed into To.
        chips = visible(dialog.locator("[email]"))
        addresses = [chip.get_attribute("email") for chip in chips]
        if len(addresses) != 1 or addresses[0].casefold() != expected.casefold():
            raise DraftProblem("Could not verify exactly one matching email recipient. Check the To field manually.")

    def prepare_gmail(self, draft, page):
        dialogs = visible(page.locator('[role="dialog"]').filter(has=page.locator("input[name=subjectbox]")))
        if not dialogs:
            self.click(draft, page, one(page.get_by_role("button", name=re.compile(r"^(Compose|लिखें)$")), "Compose button"))
        dialog, subject, body = self.gmail_fields(page)
        address = one(dialog.locator('input[aria-label="To recipients"], textarea[name="to"], input[name="to"]'), "To field")
        if content(body) or subject.input_value() or address.input_value() or visible(dialog.locator("[email]")):
            raise DraftProblem("An existing email draft is open. It was preserved. Save or close it manually before preparing this message.")
        self.fill(draft, page, address, draft.recipient)
        self.click(draft, page, subject)  # Commit address by moving focus, never Enter.
        self.gmail_recipient(dialog, draft.recipient)
        self.fill(draft, page, subject, draft.subject)
        self.fill(draft, page, body, draft.body)
        self.ready(draft, page)

    def whatsapp_body(self, page):
        return one(page.locator('#main footer [contenteditable="true"][role="textbox"]'), "WhatsApp message field")

    def whatsapp_identity(self, page, label):
        header = one(page.locator("#main header span[title]"), "active WhatsApp recipient")
        if header.get_attribute("title") != label:
            raise DraftProblem("The active WhatsApp recipient does not match the selected contact.")

    def prepare_whatsapp(self, draft, page):
        if not draft.selected:
            search = one(page.locator('#side [contenteditable="true"][role="textbox"]'), "contact search field")
            self.fill(draft, page, search, draft.recipient)
            # Search results update asynchronously; bind attached DOM elements
            # only after two matching bounded observations.
            page.wait_for_timeout(600)
            self.guard(draft.platform, page)
            if normalized(content(search)) != normalized(draft.recipient):
                raise DraftProblem("Contact search changed. Retry the exact recipient.")
            def snapshot():
                rows = visible(page.locator('#pane-side [role="listitem"], #pane-side [role="row"]'))
                if len(rows) >= 30:
                    raise DraftProblem("Too many contact results to verify. Use a more specific contact name.")
                result = []
                for row in rows:
                    titles = visible(row.locator("span[title]"))
                    if titles:
                        result.append((row, titles[0], titles[0].get_attribute("title") or ""))
                return result
            first = [item[2] for item in snapshot()]
            page.wait_for_timeout(500)
            rows = snapshot()
            labels = [item[2] for item in rows]
            if labels != first:
                raise DraftProblem("Contact results are still changing. Wait a moment and prepare the draft again.")
            if len(set(label.casefold() for label in labels)) != len(labels):
                raise DraftProblem("Several contacts share the same displayed name. Cortana cannot distinguish them safely; rename or select the contact manually.")
            candidates = {}
            for row, title, label in rows:
                if draft.recipient.casefold() not in label.casefold():
                    continue
                candidates[uuid4().hex] = {"label": label, "detail": "Displayed WhatsApp contact name; review the intended person in the browser.",
                                           "locator": row.element_handle(), "label_locator": title.element_handle(),
                                           "labels": labels}
            draft.candidates = candidates
            exact = [item for item in candidates.values() if item["label"].casefold() == draft.recipient.casefold()]
            if len(exact) == 1 and len(candidates) == 1:
                draft.selected = exact[0]
            elif candidates:
                draft.status, draft.note = "choose_recipient", "Choose the intended contact. No message has been typed."
                return
            else:
                raise DraftProblem("No matching contact was verified. Check the contact name and your WhatsApp login.")
        selected = draft.selected
        current_rows = visible(page.locator('#pane-side [role="listitem"], #pane-side [role="row"]'))
        current_labels = []
        for row in current_rows:
            titles = visible(row.locator("span[title]"))
            if titles:
                current_labels.append(titles[0].get_attribute("title") or "")
        if (current_labels != selected["labels"] or not selected["locator"]
                or not selected["locator"].evaluate("(element) => element.isConnected")
                or not selected["locator"].is_visible()
                or selected["label_locator"].get_attribute("title") != selected["label"]):
            raise DraftProblem("Contact results changed. Prepare the draft again to select the recipient.")
        self.click(draft, page, selected["locator"])
        self.whatsapp_identity(page, selected["label"])
        body = self.whatsapp_body(page)
        if content(body):
            raise DraftProblem("This chat already contains an unsent draft. It was preserved; clear or save it manually first.")
        self.fill(draft, page, body, draft.body)
        self.ready(draft, page)

    def instagram_body(self, page):
        return one(page.locator('textarea[placeholder="Message..."], [contenteditable="true"][role="textbox"][aria-label="Message"], [contenteditable="true"][role="textbox"][data-lexical-editor="true"]'), "Instagram message field")

    def instagram_identity(self, page, username):
        # Header scoping prevents a matching sidebar contact from proving the
        # active conversation. Unsupported layouts require manual handling.
        links = visible(page.locator('main header a[href], [role="main"] header a[href]'))
        identities = [item.get_attribute("href").strip("/").casefold() for item in links]
        if identities.count(username.casefold()) != 1:
            raise DraftProblem("Could not verify the active Instagram username. No message was typed; check the conversation manually.")

    def prepare_instagram(self, draft, page):
        if not draft.selected:
            existing = visible(page.locator('textarea[placeholder="Message..."], [contenteditable="true"][role="textbox"][aria-label="Message"], [contenteditable="true"][role="textbox"][data-lexical-editor="true"]'))
            if any(content(item) for item in existing):
                raise DraftProblem("An existing Instagram draft is open. It was preserved; save or clear it manually first.")
            new_message = page.get_by_role("button", name="New message", exact=True)
            if not visible(new_message):
                new_message = page.locator('[aria-label="New message"]')
            self.click(draft, page, one(new_message, "New message control"))
            dialog = one(page.get_by_role("dialog"), "recipient search dialog")
            search = one(dialog.locator('input[name="queryBox"], input[placeholder="Search..."]'), "recipient search field")
            self.fill(draft, page, search, draft.recipient.lstrip("@"))
            page.wait_for_timeout(600)
            self.guard(draft.platform, page)
            links = visible(dialog.locator('a[href]'))
            candidates = {}
            for link in links[:30]:
                href = link.get_attribute("href") or ""
                if not re.fullmatch(r"/[A-Za-z0-9._]{1,30}/?", href):
                    continue
                username = href.strip("/")
                label = (link.inner_text().strip() or username)[:150]
                if draft.recipient.lstrip("@").casefold() not in (username + " " + label).casefold():
                    continue
                candidates[uuid4().hex] = {"label": label, "detail": "@" + username,
                                           "username": username, "locator": link.element_handle(), "href": href}
            draft.candidates = candidates
            exact = [item for item in candidates.values() if item["username"].casefold() == draft.recipient.lstrip("@").casefold()]
            if len(exact) == 1 and len(candidates) == 1:
                draft.selected = exact[0]
            elif candidates:
                draft.status, draft.note = "choose_recipient", "Select the exact Instagram account. No message has been typed."
                return
            else:
                raise DraftProblem("The account search did not expose a verifiable username. Select the conversation manually; Cortana will not guess.")
        selected = draft.selected
        if (not selected["locator"] or not selected["locator"].evaluate("(element) => element.isConnected")
                or not selected["locator"].is_visible() or selected["locator"].get_attribute("href") != selected["href"]):
            raise DraftProblem("Instagram search results changed. Prepare the draft again.")
        self.click(draft, page, selected["locator"])
        dialog = one(page.get_by_role("dialog"), "recipient search dialog")
        self.click(draft, page, one(dialog.get_by_role("button", name=re.compile(r"^(Chat|Next)$")), "open conversation button"))
        self.instagram_identity(page, selected["username"])
        body = self.instagram_body(page)
        if content(body):
            raise DraftProblem("This conversation has an unsent draft. It was preserved; clear or save it manually first.")
        self.fill(draft, page, body, draft.body)
        self.ready(draft, page)

    def verify(self, draft, page):
        self.guard(draft.platform, page)
        if draft.page is not None and draft.page is not page:
            raise DraftProblem("The original draft tab was closed. The message will not be recreated automatically.")
        if draft.platform == "gmail":
            dialog, subject, body = self.gmail_fields(page)
            self.gmail_recipient(dialog, draft.recipient)
            if subject.input_value() != draft.subject:
                raise DraftProblem("The email subject changed. Review the existing draft manually.")
        elif draft.platform == "whatsapp":
            self.whatsapp_identity(page, draft.selected["label"])
            body = self.whatsapp_body(page)
        else:
            self.instagram_identity(page, draft.selected["username"])
            body = self.instagram_body(page)
        if normalized(content(body)) != normalized(draft.body):
            raise DraftProblem("The draft text changed or is no longer present. It was preserved; Cortana will not recreate or send it.")
