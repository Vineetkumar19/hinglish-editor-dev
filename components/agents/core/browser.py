"""Optional Playwright support for public pages and reviewed application forms.

Uses an ordinary installed Chrome/Edge browser. Login and verification walls
are returned for human action. No fingerprint patches or CAPTCHA services.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import re
import threading
from pathlib import Path

from . import config

_BROWSER_LOCK = threading.RLock()

FIELDS_JS = """() => Array.from(document.querySelectorAll('input,textarea,select'))
 .map((e,index)=>({index, id:e.id, name:e.name, type:e.type||e.tagName.toLowerCase(),
 label:(Array.from(e.labels||[]).map(l=>l.innerText).join(' ')||e.getAttribute('aria-label')||e.placeholder||e.name||e.id).trim(),
 required:e.required||e.getAttribute('aria-required')==='true',
 visible:!!(e.offsetWidth||e.offsetHeight||e.getClientRects().length),
 options:e.tagName==='SELECT'?Array.from(e.options).map(o=>({label:o.text,value:o.value})):[]}))"""


@contextlib.contextmanager
def browser_page(url):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Browser support is not installed. Run setup.ps1 or "
                           "pip install -r requirements-browser.txt in Python 3.12.") from exc
    with _BROWSER_LOCK, sync_playwright() as api:
        folder = config.data_dir() / "browser"
        folder.mkdir(parents=True, exist_ok=True)
        browser = api.chromium.launch_persistent_context(
            str(folder), channel=config.get("BROWSER_CHANNEL", "chrome"),
            headless=config.get_bool("BROWSER_HEADLESS", True),
            viewport={"width": 1280, "height": 900}, accept_downloads=False)
        try:
            page = browser.pages[0] if browser.pages else browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(800)
            yield page
        finally:
            browser.close()


def page_html(url: str) -> str:
    with browser_page(url) as page:
        return page.content()


def fingerprint(fields):
    value = [{k: f.get(k) for k in ("frame", "index", "id", "name", "type", "label", "required", "options")}
             for f in fields]
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def inspect_page(page):
    text = page.locator("body").inner_text(timeout=10000)[:16000]
    if page.locator("input[type=password]").count() or re.search(
            r"verify (?:that )?you are human|complete the captcha|security verification", text, re.I):
        return {"fields": [], "blocked": "Login or human verification required", "url": page.url}
    fields = []
    for frame_index, frame in enumerate(page.frames):
        for field in frame.evaluate(FIELDS_JS):
            if field["visible"] and field["type"] not in ("hidden", "submit", "button", "reset", "search"):
                fields.append({**field, "frame": frame_index})
    return {"fields": fields, "fingerprint": fingerprint(fields), "url": page.url,
            "page_excerpt": text[:1500], "blocked": "" if fields else "No application form found"}


class ApplicationBrowser:
    def inspect(self, url):
        with browser_page(url) as page:
            return inspect_page(page)

    def submit(self, plan, resume_path, *, dry_run=False, before_submit=None):
        if dry_run:
            return {"outcome": "preview", "reason": "Dry run: no fields uploaded or submitted"}
        with browser_page(plan["url"]) as page:
            current = inspect_page(page)
            if current.get("blocked") or current.get("fingerprint") != plan["fingerprint"]:
                return {"outcome": "form_changed", "inspection": current}
            for field in plan["fields"]:
                if "answer" not in field:
                    continue
                locator = page.frames[field["frame"]].locator("input,textarea,select").nth(field["index"])
                if field["type"] == "file":
                    locator.set_input_files(resume_path)
                elif field["type"] in ("checkbox", "radio"):
                    locator.set_checked(str(field["answer"]).lower() in ("true", "yes", "1"))
                elif field.get("options"):
                    locator.select_option(label=str(field["answer"]))
                else:
                    locator.fill(str(field["answer"]))
            screenshot = config.data_dir() / "applications" / (plan["fingerprint"][:16] + ".png")
            screenshot.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(screenshot), full_page=True)
            submit = page.get_by_role("button", name=re.compile(r"^(submit(?: application)?|apply(?: now)?)$", re.I))
            if submit.count() != 1:
                return {"outcome": "needs_human", "reason": "No unique final submit button", "screenshot": str(screenshot)}
            if before_submit:
                before_submit()
            submit.click(timeout=15000)
            page.wait_for_timeout(1500)
            body = page.locator("body").inner_text()[:12000]
            confirmed = bool(re.search(r"application (?:has been |was )?(?:received|submitted)|"
                                       r"thank you for applying|thanks for applying", body, re.I))
            return {"outcome": "submitted" if confirmed else "submission_unconfirmed",
                    "url": page.url, "screenshot": str(screenshot),
                    "confirmation": body[:1200]}
