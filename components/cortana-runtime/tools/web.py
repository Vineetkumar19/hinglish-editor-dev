"""open_website — launch the browser at a URL, or run a search on a
known site, optionally in an incognito window.

Scope, stated plainly: this *drives the browser's launch*, it does not
drive the page. "Open Chrome, go to Wikipedia and search Red Fort
history" works, because that resolves to a single Wikipedia search URL
that Chrome is launched at. What this cannot do is then read the results,
click the third link, and summarize it — controlling a live page requires
a headless-browser automation layer (Playwright), which is the Phase 10
item on the roadmap and a much heavier dependency.

Only http/https URLs are allowed, so this can't be turned into a way to
launch local executables or file:// paths.
"""

import platform
import subprocess
import urllib.parse
from pathlib import Path

from core.tool_registry import tool
from core.permissions import RiskLevel
from core.processes import public_environment, shell_open

# Search-URL templates for the sites worth having by name. "{q}" is
# replaced with the URL-encoded query.
SEARCH_SITES = {
    "google": "https://www.google.com/search?q={q}",
    "wikipedia": "https://en.wikipedia.org/w/index.php?search={q}",
    "youtube": "https://www.youtube.com/results?search_query={q}",
    "maps": "https://www.google.com/maps/search/{q}",
    "images": "https://www.google.com/search?tbm=isch&q={q}",
    "news": "https://news.google.com/search?q={q}",
    "github": "https://github.com/search?q={q}",
    "stackoverflow": "https://stackoverflow.com/search?q={q}",
    "amazon": "https://www.amazon.in/s?k={q}",
    "flipkart": "https://www.flipkart.com/search?q={q}",
    "gmail": "https://mail.google.com/mail/u/0/#search/{q}",
    "drive": "https://drive.google.com/drive/search?q={q}",
    "chatgpt": "https://chatgpt.com/?q={q}",
    "claude": "https://claude.ai/new?q={q}",
}

# Plain homepages, used when there's no query to search for.
SITE_HOMES = {
    "google": "https://www.google.com",
    "wikipedia": "https://en.wikipedia.org",
    "youtube": "https://www.youtube.com",
    "maps": "https://www.google.com/maps",
    "news": "https://news.google.com",
    "github": "https://github.com",
    "stackoverflow": "https://stackoverflow.com",
    "amazon": "https://www.amazon.in",
    "flipkart": "https://www.flipkart.com",
    "gmail": "https://mail.google.com",
    "drive": "https://drive.google.com",
    "chatgpt": "https://chatgpt.com",
    "claude": "https://claude.ai",
    "whatsapp": "https://web.whatsapp.com",
    "linkedin": "https://www.linkedin.com",
    "instagram": "https://www.instagram.com",
    "netflix": "https://www.netflix.com",
    "spotify": "https://open.spotify.com",
}

DEFAULT_SEARCH = "google"


def close_website(site: str) -> dict:
    from core.desktop_drafts import draft_request
    host = urllib.parse.urlsplit(_build_url(site, '', '')).hostname
    return draft_request('close_site', {'host': host})


tool(name='close_website', description='Close one currently selected Chrome tab with the requested exact website host. Refuse ambiguous windows; never close other tabs or dismiss Save prompts.',
     risk=RiskLevel.LOW, parameters={'type': 'object', 'properties': {'site': {'type': 'string'}}, 'required': ['site']})(close_website)


class UnsafeUrl(Exception):
    pass


def _normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        raise UnsafeUrl("No URL given.")
    if any(ord(char) < 32 for char in url) or "\\" in url:
        raise UnsafeUrl("Control characters and backslashes are not valid web links.")

    # Reject any explicit non-web scheme *before* prefixing. Without this
    # check, "file:///C:/Windows/System32/cmd.exe" got silently rewritten to
    # "https://file:///C:/..." and sailed past the scheme test below, because
    # by then the scheme really was https.
    scheme_sep = url.find(":")
    if scheme_sep > 0:
        maybe_scheme = url[:scheme_sep].lower()
        if maybe_scheme.isalpha() and maybe_scheme not in ("http", "https"):
            raise UnsafeUrl(f"Only http and https links can be opened, not '{maybe_scheme}:'.")

    if not url.lower().startswith(("http://", "https://")):
        # Bare domain like "wikipedia.org" -> https.
        url = "https://" + url.lstrip("/")

    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UnsafeUrl(f"Only http/https links can be opened, got '{parsed.scheme}'.")
    if not parsed.hostname or "." not in parsed.hostname or parsed.username or parsed.password:
        raise UnsafeUrl(f"'{url}' is not a valid web address.")
    return url


def _build_url(site: str, query: str, url: str) -> str:
    if url:
        return _normalize_url(url)

    site_key = (site or "").strip().lower()
    q = (query or "").strip()

    if site_key == "gmail":
        from core.communication_targets import website
        return website("gmail") + ("#search/" + urllib.parse.quote_plus(q) if q else "")

    if q:
        template = SEARCH_SITES.get(site_key) or SEARCH_SITES[DEFAULT_SEARCH]
        return template.format(q=urllib.parse.quote_plus(q))

    if site_key in SITE_HOMES:
        return SITE_HOMES[site_key]
    if site_key:
        return _normalize_url(site_key)

    raise UnsafeUrl("Nothing to open — give a url, a site name, or a search query.")


def open_website(site: str = "", query: str = "", url: str = "", incognito: bool = False) -> dict:
    target = _build_url(site, query, url)

    if platform.system() != "Windows":
        return {
            "opened": False,
            "url": target,
            "incognito": incognito,
            "note": "Not running on Windows — skipped actual launch (sandbox verification only).",
        }

    from core.app_config import approved_apps
    chrome = approved_apps().get("chrome")
    executable = chrome[0] if isinstance(chrome, list) and chrome else ""
    if executable and Path(executable).is_file():
        from core.communication_targets import chrome_profile_args
        args = [executable, *chrome_profile_args()]
        if incognito:
            args.append("--incognito")
        args.append(target)
        subprocess.Popen(args, shell=False, env=public_environment())
        browser = "chrome"
    else:
        if incognito:
            raise UnsafeUrl("Private browsing requires Chrome at its configured path.")
        shell_open(target)
        browser = "default browser"

    return {"opened": True, "url": target, "browser": browser, "incognito": incognito,
            "verification": "Browser launch accepted; page loading is not yet verified"}


def _website_preview(site: str = "", query: str = "", url: str = "", incognito: bool = False) -> str:
    return (
        "Open this exact address in your browser:\n" + _build_url(site, query, url)
        + ("\nPrivate Chrome window." if incognito else "")
        + "\nThe address and any query text will be sent to that website."
    )


tool(
    name="open_website",
    description=(
        "Open a website or run a web search in Chrome, optionally in an incognito "
        "window. Give either a full 'url', or a 'site' name "
        "(google, wikipedia, youtube, maps, github, amazon, chatgpt, claude, "
        "gmail, whatsapp, linkedin, ...) with an optional 'query' to search for "
        "on that site. Example: site='wikipedia', query='Red Fort history'. "
        "Set incognito=true for a private window."
    ),
    risk=RiskLevel.HIGH,
    parameters={
        "type": "object",
        "properties": {
            "site": {
                "type": "string",
                "description": "Site name to open or search, e.g. 'wikipedia', 'youtube', 'google'.",
            },
            "query": {
                "type": "string",
                "description": "What to search for on that site. Omit to just open the homepage.",
            },
            "url": {
                "type": "string",
                "description": "A full http(s) URL. Use instead of site/query when you have an exact address.",
            },
            "incognito": {
                "type": "boolean",
                "description": "Open in a private/incognito Chrome window.",
            },
        },
        "required": [],
    },
    preview=_website_preview,
)(open_website)
