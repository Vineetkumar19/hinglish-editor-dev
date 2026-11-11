"""The tools themselves.

Every one of these is read-only, and that is checked rather than trusted: none
of them sends, spends, writes to his files, or changes state the next run can
see. Looking something up is the whole permitted category.

What each one is FOR matters more than what it does. A model with a web search
will use it on every draft whether or not it helps, so each description says
plainly when to reach for it and when not to - a tool described as "search the
web" gets called constantly, one described as "only when the posting does not
say what the company does" gets called when it is needed.
"""
from __future__ import annotations

import json

from core import config
from core.log import get_logger
from core.tools import Tool, register

log = get_logger("toolbelt")


# --------------------------------------------------------------------------
# looking things up on the internet
# --------------------------------------------------------------------------
def _search_web(query: str, limit: int = 5) -> str:
    """Whatever search provider is configured, as plain text."""
    from core.search import get_search
    try:
        hits = get_search().search(query, limit=int(limit))
    except Exception as exc:  # noqa: BLE001
        return f"search failed: {exc}"
    if not hits:
        return "no results"
    out = []
    for h in hits[: int(limit)]:
        title = getattr(h, "title", "") or ""
        url = getattr(h, "url", "") or ""
        snippet = (getattr(h, "snippet", "") or "")[:200]
        out.append(f"- {title}\n  {url}\n  {snippet}")
    return "\n".join(out)


register(Tool(
    name="search_web",
    description=(
        "Search the web and get back titles, URLs and snippets. Use this ONLY "
        "when you need a fact you were not given and cannot infer - for "
        "example what a company actually sells when their posting does not "
        "say. Do not use it to research things you already have in front of "
        "you, and do not use it more than twice."),
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string",
                      "description": "What to search for, as you would type it"},
            "limit": {"type": "integer",
                      "description": "How many results, 1 to 8. Default 5."},
        },
        "required": ["query"],
    },
    run=_search_web, safe=True, cost_hint=3.0))


def _read_page(url: str) -> str:
    """One page, as readable text. Honours robots.txt via the crawler."""
    if not str(url).startswith(("http://", "https://")):
        return "url must start with http:// or https://"
    from core.crawler import Crawler
    try:
        page = Crawler().fetch(url)
    except Exception as exc:  # noqa: BLE001
        return f"could not read {url}: {exc}"
    if not getattr(page, "ok", False):
        return f"{url} refused to load"
    text = (getattr(page, "text", "") or "").strip()
    return text[:4000] if text else f"{url} loaded but had no readable text"


register(Tool(
    name="read_page",
    description=(
        "Fetch one web page and read its text. Use this when you have a URL "
        "and the thing you need is on it - a pricing page, an about page, a "
        "job posting you were only given the link to. One or two pages at "
        "most; it is slow."),
    parameters={
        "type": "object",
        "properties": {"url": {"type": "string",
                               "description": "Full URL including https://"}},
        "required": ["url"],
    },
    run=_read_page, safe=True, cost_hint=5.0))


# --------------------------------------------------------------------------
# looking things up in his own files
# --------------------------------------------------------------------------
def _my_numbers() -> str:
    """The channel figures the sponsorship pitch is allowed to state."""
    from agents.sponsorship import pitch as pitch_mod
    creator = pitch_mod.load_creator()
    facts = pitch_mod.audience_facts(creator)
    if not facts:
        return ("No audience numbers are filled in. Do not state any figure "
                "at all.")
    return ("These are the only channel figures you may state:\n"
            + "\n".join(f"- {f}" for f in facts))


register(Tool(
    name="my_numbers",
    description=(
        "The creator's real audience figures - subscribers, followers, "
        "averages. Call this before writing any sentence that mentions how "
        "big the channel is. Never state a number that does not come back "
        "from here."),
    parameters={"type": "object", "properties": {}},
    run=_my_numbers, safe=True, cost_hint=0.1))


def _rate_card(kind: str = "video", currency: str = "usd") -> str:
    """What he charges, from the real card. Never a guess."""
    kind = (kind or "video").lower()
    currency = (currency or "usd").lower()
    from core.work_policy import project_floor
    minimum = project_floor(currency)
    try:
        if kind.startswith("dev"):
            from agents.fullstack_sales.packages import load_card
            card = load_card()
            block = card.get(currency) or {}
            lines = [f"Day rate: {block.get('day_rate')} "
                     f"{block.get('currency', currency.upper())} "
                     f"(floor {block.get('day_rate_floor')})"]
            for p in (card.get("packages") or []):
                money = p.get(currency) or p.get("usd") or {}
                floor = max(float(money.get('floor') or 0), minimum)
                ask = max(float(money.get('ask') or 0), floor)
                lines.append(f"- {p.get('label')}: ask {ask:g}, "
                             f"floor {floor:g}, "
                             f"{p.get('turnaround', '')}")
            return "\n".join(lines)
        from agents.video_client.quote import load_rates
        card = (load_rates().get(currency) or {})
        lines = []
        for t in (card.get("tiers") or []):
            floor = max(float(t.get('floor') or 0), minimum)
            ask = max(float(t.get('ask') or 0), floor)
            lines.append(f"- {t.get('name')}: ask {ask:g}, "
                         f"floor {floor:g}, {t.get('unit', '')}")
        return "\n".join(lines) or "no tiers configured"
    except Exception as exc:  # noqa: BLE001
        return f"could not read the rate card: {exc}"


register(Tool(
    name="rate_card",
    description=(
        "What he actually charges. `kind` is 'video' or 'dev', `currency` is "
        "'usd' or 'inr'. Every price you write must come from here. If this "
        "returns nothing, write PLACEHOLDER rather than a number."),
    parameters={
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": ["video", "dev"]},
            "currency": {"type": "string", "enum": ["usd", "inr"]},
        },
        "required": ["kind"],
    },
    run=_rate_card, safe=True, cost_hint=0.1))


def _what_i_learned(agent: str, about: str = "") -> str:
    """The rules he has taught this agent by rejecting or rewriting drafts."""
    from core.lessons import get_lessons
    try:
        rows = get_lessons(agent).relevant(about or "", limit=10)
    except Exception as exc:  # noqa: BLE001
        return f"could not read the lessons: {exc}"
    if not rows:
        return "nothing learned yet"
    return "\n".join(f"- {r['rule']}" for r in rows)


register(Tool(
    name="what_i_learned",
    description=(
        "The standing rules this agent has been given by having drafts "
        "rejected or rewritten. Call this if you are unsure whether "
        "something you are about to write has been objected to before."),
    parameters={
        "type": "object",
        "properties": {
            "agent": {"type": "string",
                      "description": "sponsorship, video_client, "
                                     "fullstack_sales, job_hunter or saas_sales"},
            "about": {"type": "string",
                      "description": "Optional topic to narrow it to"},
        },
        "required": ["agent"],
    },
    run=_what_i_learned, safe=True, cost_hint=0.1))


def _check_claims(text: str) -> str:
    """Whether a draft claims something the product cannot back yet."""
    from agents.saas_sales.product import check_claims, stage
    problems = check_claims(text or "")
    if not problems:
        return f"clean - nothing here overclaims at stage `{stage()}`"
    return ("These would be blocked:\n"
            + "\n".join(f"- {p}" for p in problems))


register(Tool(
    name="check_claims",
    description=(
        "Check a sentence or a whole draft against what the product can "
        "actually back today. Use it on anything you are unsure about BEFORE "
        "you finish writing - it is faster than being rejected."),
    parameters={
        "type": "object",
        "properties": {"text": {"type": "string",
                                "description": "The text to check"}},
        "required": ["text"],
    },
    run=_check_claims, safe=True, cost_hint=0.1))


def _already_contacted(domain: str) -> str:
    """Whether this target has been written to before."""
    from core.store import get_store
    store = get_store()
    try:
        rows = store.query(
            "SELECT agent, company, status, created_at FROM leads "
            "WHERE company LIKE ? OR domain LIKE ? ORDER BY created_at DESC "
            "LIMIT 5", (f"%{domain}%", f"%{domain}%"))
    except Exception as exc:  # noqa: BLE001
        return f"could not check: {exc}"
    if not rows:
        return "never contacted"
    return "\n".join(f"- {r['agent']}: {r['company']} ({r['status']})"
                     for r in rows)


register(Tool(
    name="already_contacted",
    description=(
        "Whether this company or person has been written to before, and what "
        "happened. Worth checking before an opening line that assumes it is "
        "the first contact."),
    parameters={
        "type": "object",
        "properties": {"domain": {"type": "string",
                                  "description": "Company name or domain"}},
        "required": ["domain"],
    },
    run=_already_contacted, safe=True, cost_hint=0.2))


# --------------------------------------------------------------------------
# which agent gets which hands
# --------------------------------------------------------------------------
# Deliberately narrow. Every extra tool is a thing the model will try on a
# draft that did not need it, and on a local model each attempt is real time.
BELTS = {
    "sponsorship": ["my_numbers", "read_page", "what_i_learned",
                    "already_contacted"],
    "video_client": ["rate_card", "read_page", "what_i_learned",
                     "already_contacted"],
    "fullstack_sales": ["rate_card", "read_page", "search_web",
                        "what_i_learned", "already_contacted"],
    "job_hunter": ["read_page", "search_web", "what_i_learned"],
    "saas_sales": ["check_claims", "read_page", "what_i_learned",
                   "already_contacted"],
}


def belt_for(agent: str) -> list[str]:
    return list(BELTS.get(agent, []))


def describe_belt(agent: str) -> str:
    from core.tools import all_tools
    known = all_tools()
    return json.dumps([{"name": n, "description": known[n].description}
                       for n in belt_for(agent) if n in known], indent=1)
