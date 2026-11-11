#!/usr/bin/env python3
"""Agent Suite command line.

    python run.py demo                    safe demo - no setup needed
    python run.py doctor                  check the configuration
    python run.py auth google             authorise Gmail and Calendar
    python run.py serve                   start the approval dashboard
    python run.py run <agent>             run an agent once
    python run.py inbox                   poll Gmail and route replies
    python run.py watch                   register/renew the Gmail push watch
    python run.py approvals               list what is waiting on you
    python run.py approve <id> [--note]   approve from the terminal
    python run.py reject  <id> [--note]   reject from the terminal
    python run.py leads                   what the agents have found
    python run.py suppress <email>        never contact this address again
    python run.py graph <agent>           print the graph as mermaid
    python run.py test                    run the test suite
    python run.py schedule                run agents on a loop (daemon mode)

Nothing sends, quotes or applies without a decision from you.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import textwrap
import time

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from core import config  # noqa: E402
from core.log import configure, get_logger  # noqa: E402

log = get_logger("cli")

AGENTS = {
    "community": "Community discussion research and disclosed promotion drafts",
    "sponsorship": "Sponsorship outreach for the cricket channel",
    "video_client": "Video editing client acquisition",
    "fullstack_sales": "Full-stack development sales",
    "job_hunter": "Job discovery, fraud screening and resume tailoring",
    "saas_sales": "Taking your SaaS product to users, promoters and directories",
}

AGENT_MODULES = {name: f"agents.{name}.agent" for name in AGENTS}


def _store():
    from core.store import get_store
    return get_store()


def _banner(text: str) -> None:
    print("\n" + text + "\n" + "-" * min(72, len(text)))


# --------------------------------------------------------------------------
def cmd_doctor(args) -> int:
    from core.mailer import Mailer
    from core.oauth import GoogleOAuth
    store = _store()
    ok, warn, bad = [], [], []

    def check(label, condition, detail="", hard=True):
        (ok if condition else (bad if hard else warn)).append((label, detail))

    _banner("Agent Suite - configuration check")
    check("database reachable", True, store.url)
    provider = config.get("LLM_PROVIDER", "offline")
    check("LLM provider", provider != "offline",
          f"{provider} - set LLM_PROVIDER and a key for real drafting; "
          f"'offline' uses deterministic templates", hard=False)
    if provider == "anthropic":
        check("ANTHROPIC_API_KEY set", bool(config.get("ANTHROPIC_API_KEY")))
    if provider == "openai":
        base = config.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        if "localhost" in base or "127.0.0.1" in base:
            check("local model server", True, base)
        else:
            check("OPENAI_API_KEY set", bool(config.get("OPENAI_API_KEY")))
    if provider == "ollama":
        # The two ways this fails are both silent otherwise: Ollama not running,
        # and LLM_MODEL naming something that was never pulled.
        from core.llm import OllamaProvider
        prov = OllamaProvider()
        installed = prov.models()
        if not installed:
            check("Ollama reachable", False,
                  f"nothing answering at {prov.base} - start Ollama, then "
                  f"`ollama pull {prov.model}`")
        else:
            here = prov.model in installed or any(
                m.split(":")[0] == prov.model.split(":")[0] for m in installed)
            check("Ollama reachable", True,
                  f"{prov.base} - {len(installed)} model(s) installed")
            check(f"model {prov.model} installed", here,
                  "" if here else
                  f"`ollama pull {prov.model}`, or set LLM_MODEL to one of: "
                  f"{', '.join(installed[:6])}")
            if here:
                rate, err = prov.speed()
                if err:
                    check("model answers", False, err)
                else:
                    # Below ~15 tok/s the model is on the CPU. A pitch is
                    # roughly 450 tokens out plus the site text in, so 5 tok/s
                    # is four minutes of silence per brand.
                    mins = (450 / rate) / 60 if rate else 99
                    check("model is fast enough to wait for", rate >= 15,
                          f"{rate:.0f} tokens/sec - about {mins:.0f} min per "
                          f"brand, which is a CPU not a GPU. Either accept the "
                          f"wait, or `ollama pull qwen2.5:3b-instruct` and set "
                          f"LLM_MODEL to it" if rate < 15 else
                          f"{rate:.0f} tokens/sec - roughly {mins*60:.0f}s per "
                          f"brand", hard=False)
            check("context window big enough", prov.num_ctx >= 8192,
                  f"OLLAMA_NUM_CTX={prov.num_ctx} - below 8192 the brand's own "
                  f"site text gets cut off the prompt and the pitch goes "
                  f"generic", hard=False)

    check("SENDER_EMAIL set", bool(config.get("SENDER_EMAIL")))
    from core.mailer import PLACEHOLDER_POSTAL, _reachable_base
    postal = config.get("SENDER_POSTAL_ADDRESS", "").strip()
    check("SENDER_POSTAL_ADDRESS set",
          bool(postal) and postal.lower() not in PLACEHOLDER_POSTAL,
          f"{postal!r} is still the example value - put a real one in .env; it "
          f"is required by anti-spam law in most jurisdictions and it is "
          f"currently left out of the footer" if postal else
          "required by anti-spam law in most jurisdictions", hard=False)
    check("unsubscribe link is reachable", bool(_reachable_base()),
          f"PUBLIC_BASE_URL={config.get('PUBLIC_BASE_URL', '')} only works on "
          f"this machine, so emails ask the brand to reply 'unsubscribe' "
          f"instead - which is fine, and reads better than a dead link",
          hard=False)
    transport = config.get("MAIL_TRANSPORT", "smtp")
    if transport == "smtp":
        check("SMTP_HOST set", bool(config.get("SMTP_HOST")))
    else:
        try:
            GoogleOAuth(store).access_token()
            check("Gmail authorised", True)
        except Exception as exc:  # noqa: BLE001
            check("Gmail authorised", False, str(exc)[:120])

    check("DRY_RUN", config.dry_run(),
          "DRY_RUN is OFF - mail will really be sent" if not config.dry_run()
          else "on - nothing will actually be sent", hard=False)
    check("daily send cap", config.get_int("DAILY_SEND_CAP", 40) <= 50,
          f"{config.get_int('DAILY_SEND_CAP', 40)}/day - above ~50 per mailbox "
          f"risks your sender reputation", hard=False)
    check("DASHBOARD_TOKEN set", bool(config.get("DASHBOARD_TOKEN")),
          "without it, anyone who can reach the port can approve sends",
          hard=False)

    # -- replies -----------------------------------------------------------
    inbox_transport = (config.get("INBOX_TRANSPORT", "")
                       or ("imap" if config.get("MAIL_TRANSPORT", "smtp") == "smtp"
                           else "gmail")).lower()
    if inbox_transport == "imap":
        from core.imapbox import ImapBox
        box = ImapBox(store)
        if box.configured:
            status = box.check()
            check("replies can be read (IMAP)", status.startswith("connected"),
                  status, hard=False)
        else:
            check("replies can be read (IMAP)", False,
                  "set SMTP_USER and SMTP_PASSWORD (a Gmail App Password) and "
                  "replies will be picked up automatically", hard=False)

    # -- prospecting -------------------------------------------------------
    try:
        from agents.sponsorship.brain import Memory
        summary = Memory(store).summary()
        check("the agent's brain", True,
              f"{summary['decisions']} pieces of evidence"
              + (" - it has nothing to learn from yet"
                 if not summary["decisions"] else ""), hard=False)
        found = store.one("SELECT COUNT(*) AS n FROM prospects") or {"n": 0}
        check("brands found on the web so far", True,
              str(found.get("n") or 0),
              hard=False)
    except Exception as exc:  # noqa: BLE001
        check("brain readable", False, str(exc)[:120])

    # -- development clients -----------------------------------------------
    from agents.fullstack_sales.packages import load_card
    dev = load_card(refresh=True)
    packs = dev.get("packages") or []
    check("dev rate card", bool(packs) and bool(dev.get("usd")),
          f"{len(packs)} fixed-price packages, day rate "
          f"{dev.get('usd', {}).get('day_rate', '?')} USD / "
          f"{dev.get('inr', {}).get('day_rate', '?')} INR" if packs else
          "profiles/dev_rate_card.yaml has no packages - payment work will be "
          "priced by the day, which leaves most of the money behind")
    if packs:
        loose = [p for p in packs
                 if not (p.get("usd") or {}).get("floor")
                 or float(p["usd"]["floor"]) > float(p["usd"].get("ask", 0))]
        check("every package has a floor below its ask", not loose,
              ", ".join(str(p.get("id")) for p in loose[:4]) if loose else "")
    check("dev client sources",
          bool(config.get_list("DEV_CLIENT_SOURCES", [])),
          ", ".join(config.get_list("DEV_CLIENT_SOURCES",
                                    ["linkedin", "remoteok", "weworkremotely"])),
          hard=False)
    try:
        from agents.fullstack_sales.brain import DevMemory
        ds = DevMemory(store).summary()
        check("the dev agent's brain", True,
              f"{ds['decisions']} pieces of evidence"
              + (" - nothing to learn from yet" if not ds["decisions"] else ""),
              hard=False)
    except Exception as exc:  # noqa: BLE001
        check("dev brain readable", False, str(exc)[:120])

    # -- the product launch agent ------------------------------------------
    from agents.saas_sales import product as _prod
    _prod.load_product(refresh=True)
    if not config.get_bool("SAAS_ENABLED", False):
        check("product launch agent", True,
              "parked until the product is ready - built, tested and not "
              "running. Set SAAS_ENABLED=true when you want it", hard=False)
    ready, why = _prod.ready_to_sell()
    check("product profile", ready,
          f"stage `{_prod.stage()}` - waitlist and feedback only, no price, "
          f"no trial, no commission" if ready and _prod.stage() == "building"
          else (f"stage `{_prod.stage()}`" if ready else why), hard=False)
    if _prod.stage() == "live":
        check("pricing is filled in before anything is sold", _prod.has_pricing(),
              "product.yaml says `live` but has no pricing tiers, so every "
              "message that mentions a price will be blocked")
    try:
        from agents.saas_sales.brain import LaunchMemory
        ls = LaunchMemory(store).summary()
        check("the launch agent's brain", True,
              f"{ls['decisions']} pieces of evidence"
              + (" - nothing to learn from yet" if not ls["decisions"] else ""),
              hard=False)
    except Exception as exc:  # noqa: BLE001
        check("launch brain readable", False, str(exc)[:120])

    # -- hands -------------------------------------------------------------
    from core import tools as _tools
    import core.toolbelt as _belt          # noqa: F401  (registers them)
    on = config.get_bool("TOOL_USE_ENABLED", True)
    bindable = [n for n, t in _tools.all_tools().items() if t.safe]
    check("the agents have hands", on and bool(bindable),
          f"{len(bindable)} read-only tools the model can call itself: "
          f"{', '.join(sorted(bindable)[:6])}" if on and bindable
          else "TOOL_USE_ENABLED is off - the model can still think, but it "
               "cannot go and look anything up", hard=False)
    unsafe = [n for n, t in _tools.all_tools().items() if not t.safe]
    check("nothing that can act is bindable", not unsafe,
          ", ".join(unsafe[:4]) + " are registered but not read-only, so the "
          "model must never be handed them" if unsafe else
          "every registered tool is read-only; sending still goes through you")

    # -- what the agents have taught themselves ----------------------------
    try:
        from core.lessons import get_lessons
        taught = {a: len(get_lessons(a, store).all())
                  for a in ("sponsorship", "job_hunter", "video_client",
                            "fullstack_sales", "saas_sales")}
        total = sum(taught.values())
        check("rules learned from your decisions", True,
              ", ".join(f"{k.replace('_', ' ')}: {v}" for k, v in taught.items())
              + ("  - reject a draft and say why, or edit one before approving, "
                 "and it becomes a rule the agent follows from then on"
                 if not total else "  (/learned to read them)"), hard=False)
    except Exception as exc:  # noqa: BLE001
        check("lesson store readable", False, str(exc)[:120])
    provider_name = config.get("LLM_PROVIDER", "offline")
    thinking = provider_name not in ("offline", "none")
    # The detail line prints whether the check passes or fails, so it has to
    # read correctly both ways - it was explaining the offline downside on a
    # box that was configured perfectly well.
    check("the agents can think", thinking,
          f"{provider_name} - they read each target and write for it" if thinking
          else "with LLM_PROVIDER=offline every draft is a written template - "
               "the agents still run, and still rank, but they cannot read a "
               "target or learn what to say differently", hard=False)

    # -- freelance video clients -------------------------------------------
    from agents.video_client.quote import load_rates
    card = load_rates(refresh=True)
    have = bool((card.get("usd") or {}).get("tiers"))
    check("video rate card", have,
          f"{len((card.get('usd') or {}).get('tiers') or [])} USD tiers, "
          f"{len((card.get('inr') or {}).get('tiers') or [])} INR tiers"
          if have else "profiles/video_rates.yaml has no usd tiers - every "
                       "quote will say PLACEHOLDER")
    if have:
        floors = [t for t in card["usd"]["tiers"]
                  if not t.get("floor") or float(t["floor"]) > float(t.get("ask", 0))]
        check("every tier has a floor below its ask", not floors,
              ", ".join(str(t.get("id")) for t in floors[:4])
              + " - the floor is what stops a bad deal, and a missing one "
                "means the agent will accept anything" if floors else "")
    check("how you get paid is set", bool(config.get("PAYMENT_DETAILS")),
          "PAYMENT_DETAILS is empty, so every invoice says PLACEHOLDER where "
          "the bank or UPI details belong", hard=False)
    check("portfolio link", bool(config.get("PORTFOLIO_URL")),
          "PORTFOLIO_URL is empty - the pitch has nothing to point at, which "
          "is most of what a first email is for", hard=False)
    try:
        from agents.video_client.brain import DealMemory
        vs = DealMemory(store).summary()
        check("the client agent's brain", True,
              f"{vs['decisions']} pieces of evidence"
              + (" - nothing to learn from yet" if not vs["decisions"] else ""),
              hard=False)
    except Exception as exc:  # noqa: BLE001
        check("client brain readable", False, str(exc)[:120])

    # -- job hunting -------------------------------------------------------
    from agents.job_hunter import location as _loc
    sources = config.get_list("JOB_SOURCES", ["remotive"])
    check("job sources", bool(sources), ", ".join(sources), hard=False)
    check("job boards include the Indian ones",
          any(s in sources for s in ("linkedin", "naukri")),
          "add linkedin (and naukri) to JOB_SOURCES - greenhouse and lever only "
          "cover companies that use those tools, which is a small slice of the "
          "Indian market", hard=False)
    check("where you can work is set", bool(_loc.wanted_places()),
          f"{len(_loc.wanted_places())} places - without this a run tailors a "
          f"resume for every San Francisco posting it finds", hard=False)
    if "naukri" in sources:
        check("Naukri session cookie", bool(config.get("NAUKRI_COOKIE")),
              "NAUKRI_COOKIE is empty, so naukri contributes nothing - Naukri "
              "shows almost nothing to a logged-out visitor", hard=False)
    try:
        from agents.job_hunter.brain import JobMemory
        js = JobMemory(store).summary()
        check("the job hunter's brain", True,
              f"{js['decisions']} pieces of evidence"
              + (" - it has nothing to learn from yet" if not js["decisions"]
                 else ""), hard=False)
    except Exception as exc:  # noqa: BLE001
        check("job brain readable", False, str(exc)[:120])

    # -- sponsorship -------------------------------------------------------
    from core.search import SeedsProvider
    try:
        brands = SeedsProvider(config.get(
            "SPONSOR_FILE", str(config.profiles_dir() / "sponsors.yaml"))).load()
    except Exception as exc:  # noqa: BLE001
        brands = []
        check("sponsor list readable", False, str(exc)[:120])
    if brands:
        check("sponsor list", len(brands) >= 50,
              f"{len(brands)} brands - one reply in fifty is normal, so a short "
              f"list cannot work", hard=False)
        import agents.sponsorship.agent as _sp
        from agents.sponsorship.discover import salesman_reason
        banned = [b["name"] for b in brands
                  if _sp.blocked_reason(b) and not salesman_reason(
                      b.get("fit", ""), " ".join(str(h) for h in (b.get("hints") or [])))]
        check("no real-money gaming on the list", not banned,
              ", ".join(banned[:5]) + " - not legal to promote in India"
              if banned else "")
        # The other thing that must never creep back: brands whose only offer
        # is a cut of a sale.
        selling = [b["name"] for b in brands if salesman_reason(
            b.get("fit", ""), " ".join(str(h) for h in (b.get("hints") or [])))]
        check("nothing on the list is a commission deal", not selling,
              ", ".join(selling[:5]) + " - a cut per sale is a sales job, not a "
              "paid promotion" if selling else "")

    try:
        from agents.sponsorship import pitch as _pitch
        creator = _pitch.load_creator(refresh=True)
        facts = _pitch.audience_facts(creator)
        check("creator profile has your numbers", bool(facts),
              "; ".join(facts) if facts else
              "profiles/creator.yaml is blank, so sponsorship emails will make "
              "no audience claim at all - fill it in with real figures",
              hard=False)
        check("best work links", bool(_pitch.best_work_links(creator)),
              "add two video links to profiles/creator.yaml - they do more than "
              "any adjective in the pitch", hard=False)
    except Exception as exc:  # noqa: BLE001
        check("creator profile readable", False, str(exc)[:120])

    master = pathlib.Path(config.get("RESUME_MASTER_FILE",
                                     str(ROOT / "profiles" / "master_resume.yaml")))
    check("master resume present", master.exists(), str(master), hard=False)
    if master.exists():
        try:
            from agents.job_hunter.resume import load_master
            m = load_master(master)
            placeholders = "PLACEHOLDER" in json.dumps(m)
            check("master resume filled in", not placeholders,
                  "still contains PLACEHOLDER entries" if placeholders
                  else "no placeholders left", hard=False)
        except Exception as exc:  # noqa: BLE001
            check("master resume parses", False, str(exc)[:160])

    # Software and video are separate careers; a profile must not carry the
    # other one's material.
    from agents.job_hunter.resume import load_master, track_violations
    for prof in ("master_resume.yaml", "master_resume_video.yaml"):
        path = ROOT / "profiles" / prof
        if not path.exists():
            continue
        try:
            leaked = track_violations(load_master(path))
        except Exception:  # noqa: BLE001
            continue
        check(f"{prof} stays in its own track", not leaked,
              ("mentions " + ", ".join(leaked[:6]) + " - that belongs in the "
               "other profile") if leaked else "no cross-over", hard=False)

    seeds = pathlib.Path(config.get("SEEDS_FILE",
                                    str(ROOT / "profiles" / "targets.yaml")))
    check("target list present", seeds.exists(), str(seeds), hard=False)

    mailer = Mailer(store)
    rate = mailer.bounce_rate()
    check("bounce rate under 2%", rate < 0.02, f"{rate:.1%}", hard=False)
    check("suppression list", True, f"{len(mailer.suppression.all())} addresses")

    for label, detail in ok:
        print(f"  ok    {label}" + (f"  ({detail})" if detail else ""))
    for label, detail in warn:
        print(f"  warn  {label}" + (f"  - {detail}" if detail else ""))
    for label, detail in bad:
        print(f"  FAIL  {label}" + (f"  - {detail}" if detail else ""))
    print()
    if bad:
        print(f"{len(bad)} problem(s) must be fixed before this will run for real.")
        return 1
    print("Configuration looks usable." + (" Still in DRY_RUN."
                                           if config.dry_run() else ""))
    return 0


def cmd_auth(args) -> int:
    if args.provider != "google":
        print(f"unknown provider {args.provider!r}")
        return 1
    from core.oauth import CALENDAR_SCOPES, GMAIL_SCOPES, GoogleOAuth
    oauth = GoogleOAuth(_store(), scopes=GMAIL_SCOPES + CALENDAR_SCOPES)
    oauth.run_installed_flow(port=args.port, open_browser=not args.no_browser)
    from core.gmail import GmailClient
    print("Signed in as:", GmailClient(_store()).profile().get("emailAddress"))
    return 0


def cmd_serve(args) -> int:
    import os
    from server.app import serve
    if getattr(args, "demo", False):
        # Set before anything reads it, so every page this process renders is
        # already redacted. There is no way to turn it back on mid-session by
        # accident, which is the point.
        os.environ["DEMO_MODE"] = "true"
    store = _store()

    def on_push(payload):
        return _process_inbox(store, push=payload)

    srv = serve(host=args.host, port=args.port, store=store, on_gmail_push=on_push)
    url = (f"http://{args.host or config.get('DASHBOARD_HOST', '127.0.0.1')}"
           f":{args.port or config.get_int('DASHBOARD_PORT', 8080)}"
           + (f"/?token={config.get('DASHBOARD_TOKEN')}"
              if config.get("DASHBOARD_TOKEN") else "/"))
    _banner("Agent Suite console")
    print(f"Open this in your browser:\n\n    {url}\n")
    print("Left side: your agents, and how many cards each is holding.")
    print("Right side: that agent's work. Nothing is sent until you approve it.")
    if getattr(args, "demo", False):
        print("\nDemo mode: contact details hidden, nothing can be sent or run.")
    print("\nCtrl-C to stop.\n")
    if getattr(args, "open", False):
        import webbrowser
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping")
    return 0


def cmd_run(args) -> int:
    store = _store()
    name = args.agent
    if name not in AGENTS:
        print(f"unknown agent {name!r}. choose from: {', '.join(AGENTS)}")
        return 1
    _banner(f"Running {name}")
    if name == "job_hunter":
        import agents.job_hunter.agent as jh
        result = jh.make(store=store).run(
            queries=args.query or None, thread_id=args.thread)
    else:
        module = AGENT_MODULES[name]
        mod = __import__(module, fromlist=["make"])
        result = mod.make(store=store).run(thread_id=args.thread)

    print(f"\nstatus: {result.status}")
    if result.interrupted:
        print(f"\nPaused for your decision. Approval id: {result.approval_id}")
        print(f"Review it at the dashboard, or:  python run.py approve "
              f"{result.approval_id}")
    elif result.complete:
        print("summary:", json.dumps(result.state.get("summary", {}), indent=2))
    elif result.error:
        print("error:", result.error)
        return 1
    return 0


def _process_inbox(store, push=None) -> int:
    from core.inbox import process
    return process(store, push=push)


def cmd_inbox(args) -> int:
    store = _store()
    _banner("Checking the inbox")
    n = _process_inbox(store)
    print(f"handled {n} message(s)")
    pending = len(__import__("core.hitl", fromlist=["ApprovalQueue"])
                  .ApprovalQueue(store).pending())
    if pending:
        print(f"{pending} item(s) now waiting for your decision.")
    return 0


def cmd_watch(args) -> int:
    from core.gmail import GmailClient
    topic = args.topic or config.require("PUBSUB_TOPIC")
    gm = GmailClient(_store())
    renewed = gm.renew_watch_if_needed(topic, within_hours=args.within)
    left = gm.watch_expires_in()
    print(("registered a new watch" if renewed else "existing watch is still good")
          + (f"; expires in {left/3600:.1f}h" if left else ""))
    return 0


def cmd_approvals(args) -> int:
    from core.hitl import ApprovalQueue
    q = ApprovalQueue(_store())
    rows = q.pending()
    if not rows:
        print("Nothing waiting on you.")
        return 0
    _banner(f"{len(rows)} item(s) waiting")
    for a in rows:
        p = a["payload"]
        print(f"\n  {a['id']}  [{a['kind']}]  {a['agent']}")
        print(f"  {a['title']}")
        if p.get("subject"):
            print(f"    subject: {p['subject']}")
        if p.get("quote"):
            print(f"    total:   {p['quote'].get('currency')} "
                  f"{p['quote'].get('total', 0):,.0f}")
        if p.get("resume_path"):
            print(f"    resume:  {p['resume_path']}")
        if p.get("body"):
            print(textwrap.indent(textwrap.fill(p["body"][:300], 72), "    | "))
    print(f"\n  approve with:  python run.py approve <id>")
    return 0


def _decide(approval_id: str, approve: bool, note: str) -> int:
    from core.hitl import ApprovalQueue
    from core.registry import resume_thread
    store = _store()
    q = ApprovalQueue(store)
    row = q.get(approval_id)
    if row is None:
        print(f"no such approval: {approval_id}")
        return 1
    if row["status"] != "pending":
        print(f"already {row['status']}")
        return 1
    decision = (q.approve(approval_id, note=note) if approve
                else q.reject(approval_id, note=note))
    print(("approved" if approve else "rejected") + f": {row['title']}")
    result = resume_thread(row["thread_id"], decision.to_json(), store)
    print("run status:", result.status)
    if result.interrupted:
        print(f"next approval waiting: {result.approval_id}")
    return 0


def cmd_approve(args) -> int:
    return _decide(args.id, True, args.note or "")


def cmd_reject(args) -> int:
    return _decide(args.id, False, args.note or "")


def cmd_leads(args) -> int:
    store = _store()
    rows = store.query(
        "SELECT agent, status, COUNT(*) AS n FROM leads GROUP BY agent, status "
        "ORDER BY agent, status")
    _banner("Leads")
    for r in rows:
        print(f"  {r['agent']:<18} {r['status']:<18} {r['n']:>4}")
    if args.detail:
        print()
        for r in store.query(
                "SELECT agent, company, email, phone, status, score, role "
                "FROM leads ORDER BY updated_at DESC LIMIT ?", (args.detail,)):
            print(f"  {r['agent']:<16} {(r['company'] or r['role'])[:32]:<34} "
                  f"{(r['email'] or r['phone'] or '-'):<32} {r['status']}")
    return 0


def cmd_suppress(args) -> int:
    from core.mailer import SuppressionList
    s = SuppressionList(_store())
    if args.remove:
        s.remove(args.email)
        print(f"{args.email} removed from the suppression list")
    else:
        s.add(args.email, reason=args.reason or "manual")
        print(f"{args.email} will never be contacted again")
    return 0


def cmd_graph(args) -> int:
    from core.registry import get_graph, names
    if args.agent not in names():
        print(f"unknown graph. available: {', '.join(names())}")
        return 1
    print(get_graph(args.agent, _store()).to_mermaid())
    return 0


def cmd_test(args) -> int:
    from scripts.run_tests import main as run_tests
    return run_tests(["--pattern", args.pattern])


def cmd_telegram(args) -> int:
    """Run the Telegram bot: control all four agents from your phone."""
    from server.bot import Bot, main as bot_main
    if args.setup_only:
        from core.telegram import Telegram
        bot = Bot(store=_store(), telegram=Telegram())
        if not bot.chat_id:
            print("Not bound to a group yet. Start the bot with "
                  "`python run.py telegram` and send /start in your group.")
            return 1
        print(bot.setup(bot.chat_id))
        return 0
    return bot_main()


DEMO_AGENTS = {
    "jobs": "job_hunter",
    "sponsorship": "sponsorship",
    "video": "video_client",
    "dev": "fullstack_sales",
}


def _demo_env() -> None:
    """Hard-wire everything to safe, offline, fixture-backed settings."""
    import logging
    import os
    os.environ.update({
        "DRY_RUN": "true", "DRY_RUN_PRINT": "false", "LLM_PROVIDER": "offline",
        "JOB_SOURCES": "fixture",
        "JOB_FIXTURE_FILE": str(ROOT / "tests" / "fixtures" / "jobs.json"),
        "JOB_MAX_AGE_DAYS": "3650", "NOTIFY_CHANNELS": "store",
        "SEARCH_PROVIDER": "seeds",
        "SEEDS_FILE": str(ROOT / "tests" / "fixtures" / "targets.yaml"),
        # The sponsorship agent's real list points at real companies. The demo
        # must never touch those, so it is redirected at the fixture sites
        # served from this machine.
        "SPONSOR_FILE": str(ROOT / "tests" / "fixtures" / "sponsors.yaml"),
        "CREATOR_PROFILE": str(ROOT / "tests" / "fixtures" / "creator.yaml"),
        "CONTACT_GUESS_ENABLED": "false",
        # The demo must never touch the internet. Without this the sponsorship
        # agent decides a web sweep is due (it has no record of one) and goes
        # off crawling live sites instead of the fixtures.
        "DISCOVER_ENABLED": "false",
        "DB_URL": f"sqlite:///{ROOT / 'data' / 'demo.db'}",
        "RESUME_OUTPUT_DIR": str(ROOT / "data" / "resumes"),
        "SENDER_EMAIL": "you@example.com", "SENDER_NAME": "Vineet Kumar Das",
        "SENDER_POSTAL_ADDRESS": "Badlapur, Maharashtra, India",
        "OPERATOR_NAME": "Vineet", "OPERATOR_EMAIL": "you@example.com",
        "YOUTUBE_CHANNEL_URL": "https://youtube.com/@yourchannel",
        "PORTFOLIO_URL": "https://drive.google.com/your-portfolio",
        "CRAWL_MIN_INTERVAL": "0", "UNSUBSCRIBE_SECRET": "demo-secret",
        "PUBLIC_BASE_URL": "http://localhost:8080",
        "LOG_LEVEL": "ERROR",
    })
    logging.getLogger().setLevel(logging.ERROR)


def _demo_reset() -> None:
    import shutil
    for suffix in ("", "-wal", "-shm"):
        f = pathlib.Path(str(ROOT / "data" / "demo.db") + suffix)
        if f.exists():
            f.unlink()
    shutil.rmtree(ROOT / "data" / "resumes", ignore_errors=True)
    import core.store as store_mod
    store_mod._default = None


def _demo_jobs(store, queue, pause: bool) -> dict:
    import agents.job_hunter.agent as jh

    _banner("JOBS AGENT - nothing is applied to")
    print("Reading 7 sample job postings. Two are worth your time; the rest are\n"
          "either the wrong kind of work, too senior, or outright scams.\n")

    app = jh.make(store=store).build()
    result = app.invoke({"_thread_id": "demo-jobs"}, thread_id="demo-jobs")

    shown, gate = [], 0
    while result.interrupted and gate < 15:
        gate += 1
        row = queue.get(result.approval_id)
        p = row["payload"]
        shown.append(p)
        if gate == 1:
            print("A real job it wants to apply to:\n")
            print(f"    {p['title']}  at  {p['company']}")
            print(f"    location            : {p['location'] or 'not stated'}")
            print(f"    salary              : {p['salary'] or 'not stated'}")
            print(f"    your skills match   : {p['keyword_coverage']:.0%}")
            print(f"    fraud check         : {p['screen']['verdict']}"
                  f"  ({p['screen']['reason'][:50]})")
            print(f"    invented facts      : "
                  f"{p['stripped_claims'] or 'none - nothing was made up'}")
            print(f"    resume it built     : "
                  f"{pathlib.Path(p['resume_path']).name}")
            print(f"    where you'd apply   : {p['apply_url']}\n")
            if pause:
                print("Stopping here so YOU can decide.\n")
                print("  1. run:  python run.py serve")
                print("  2. open the link it prints, in your browser")
                print("  3. press Approve or Reject and watch it continue\n")
                return {"paused": True}
            print("Pretending you pressed APPROVE, and moving on...\n")
            decision = queue.approve(result.approval_id, note="demo")
        else:
            decision = queue.reject(result.approval_id, note="demo: passed on it")
        result = app.resume("demo-jobs", decision.to_json())

    rejected = result.state.get("rejected", [])
    off_target = result.state.get("off_target") or []
    if off_target:
        print(f"Not your kind of job, so never shown to you ({len(off_target)}):\n")
        for o in off_target:
            print(f"    FILTERED {o['title']}  at  {o['company']}")
            print(f"             why: {o['reason'][:88]}\n")

    print(f"Looked like a real job but was fake ({len(rejected)}):\n")
    for r in rejected:
        print(f"    BLOCKED  {r['title']}  at  {r['company']}")
        print(f"             why: {r['reason'][:88]}\n")

    summary = result.state.get("summary") or {}
    pdfs = sorted((ROOT / "data" / "resumes").glob("*.pdf"))
    print(f"  job posts read     : {summary.get('found', 0)}")
    print(f"  wrong kind of job  : {len(off_target)}")
    print(f"  fakes blocked      : {summary.get('rejected', 0)}")
    print(f"  real jobs shown    : {len(shown)}")
    print(f"  resumes built      : {len(pdfs)}")
    print(f"  applications marked: {summary.get('applied', 0)}")
    print(f"  emails sent        : 0   (DRY RUN, always)")
    if pdfs:
        print("\n  Resumes it wrote, one per job:")
        for f in pdfs:
            print(f"    {f}")
    return {"resumes": len(pdfs), "blocked": len(rejected)}


DEMO_BLURB = {
    "sponsorship": ("SPONSORSHIP AGENT - no email is sent",
                    "Looking for brands to sponsor your cricket channel."),
    "video_client": ("VIDEO CLIENT AGENT - no email is sent",
                     "Looking for creators who need a video editor."),
    "fullstack_sales": ("DEV SALES AGENT - no email is sent",
                        "Looking for businesses that need a website built."),
}


def _demo_outreach(name: str, store, queue, pause: bool) -> dict:
    """Run an outreach agent against local stand-in websites.

    The sample prospect sites are served from your own machine on made-up
    domains, so this reaches nothing on the internet and emails nobody.
    """
    from tests.fakes.servers import FakeWebServer

    title, blurb = DEMO_BLURB[name]
    module = {"sponsorship": "agents.sponsorship.agent",
              "video_client": "agents.video_client.agent",
              "fullstack_sales": "agents.fullstack_sales.agent"}[name]

    _banner(title)
    print(f"{blurb}\n")

    web = FakeWebServer().start()
    try:
        mod = __import__(module, fromlist=["make"])
        app = mod.make(store=store).build()
        thread = f"demo-{name}"
        result = app.invoke({"_thread_id": thread}, thread_id=thread)

        drafts, gate = [], 0
        while result.interrupted and gate < 10:
            gate += 1
            row = queue.get(result.approval_id)
            p = row["payload"]
            drafts.append(p)
            if gate == 1:
                route = {"email": "An email it wants to send",
                         "whatsapp": "A WhatsApp message it has written for you",
                         "phone": "A message for a number it found",
                         "form": "A message to paste into their enquiry form",
                         "social": "A message to send as a DM",
                         }.get(p.get("channel", "email"), "A message it drafted")
                print(f"{route}:\n")
                print(f"    to        : {p.get('to', 'unknown')}")
                print(f"    company   : {p.get('company', '')}")
                if p.get("deal_type"):
                    print(f"    asking for: {p['deal_type']}")
                print(f"    subject   : {p.get('subject', '')}\n")
                body = str(p.get("body", "")).strip().splitlines()
                for line in body[:14]:
                    print(f"    | {line}")
                if len(body) > 14:
                    print(f"    | ... {len(body) - 14} more lines")
                print()
                if p.get("whatsapp_text"):
                    print("The same pitch, written for WhatsApp:\n")
                    for line in str(p["whatsapp_text"]).strip().splitlines():
                        print(f"    | {line}")
                    print()
                if pause:
                    print("Stopping here so YOU can decide.\n")
                    print("  1. run:  python run.py serve")
                    print("  2. open the link it prints, in your browser")
                    print("  3. press Approve or Reject\n")
                    return {"paused": True}
                print("Pretending you pressed APPROVE...\n")
                decision = queue.approve(result.approval_id, note="demo")
            elif gate == 2:
                # Approve a second one as well. The interesting case is a brand
                # that publishes no address, which the agent cannot send to
                # itself - a demo that never reaches that path shows half the
                # agent.
                decision = queue.approve(result.approval_id, note="demo")
            else:
                decision = queue.reject(result.approval_id, note="demo")
            result = app.resume(thread, decision.to_json())

        summary = result.state.get("summary") or {}
        skipped = result.state.get("skipped", [])
        # "operator rejected" entries are this demo pressing Reject on its own
        # behalf. Showing them as reasons the agent passed would be misleading.
        genuine = [sk for sk in skipped
                   if "operator rejected" not in str(
                       sk.get("reason", "") if isinstance(sk, dict) else sk)]
        print(f"  prospects looked at: "
              f"{summary.get('considered', len(drafts) + len(skipped))}")
        print(f"  emails drafted     : {len(drafts)}")
        print(f"  agent passed over  : {len(genuine)}")
        for sk in genuine[:4]:
            why = sk.get("reason", "") if isinstance(sk, dict) else str(sk)
            who = (sk.get("company") or sk.get("domain") or "one prospect") \
                if isinstance(sk, dict) else "one prospect"
            print(f"      {who}: {why[:72]}")
        handoffs = (result.state or {}).get("handoff") or []
        if handoffs:
            print(f"  no address, so ready for you to send by hand: "
                  f"{len(handoffs)}")
            for h in handoffs[:3]:
                print(f"      {h.get('company', '')}: {h.get('channel', '')} "
                      f"{h.get('route', '')}")
        print(f"  emails sent        : 0   (DRY RUN, always)")
        return {"drafted": len(drafts)}
    finally:
        web.stop()


def cmd_demo(args) -> int:
    """A safe, zero-configuration demonstration of every agent.

    Bundled sample data, no API key, nothing reaching the internet, hard
    DRY_RUN. With --pause it stops at the first approval so you can decide it
    yourself instead of watching a pretend decision.
    """
    _demo_env()
    _demo_reset()

    from core.hitl import ApprovalQueue
    from core.store import get_store
    store = get_store()
    queue = ApprovalQueue(store)

    which = (args.agent or "all").lower()
    if which != "all" and which not in DEMO_AGENTS:
        print(f"unknown agent {which!r}. choose from: all, "
              f"{', '.join(DEMO_AGENTS)}")
        return 1
    names = list(DEMO_AGENTS) if which == "all" else [which]

    paused = False
    for short in names:
        agent = DEMO_AGENTS[short]
        outcome = (_demo_jobs(store, queue, args.pause) if agent == "job_hunter"
                   else _demo_outreach(agent, store, queue, args.pause))
        print()
        if outcome.get("paused"):
            paused = True
            break

    if paused:
        return 0

    _banner("DONE - " + ("all four agents" if len(names) > 1
                         else f"the {names[0]} agent"))
    print("  Nothing left your machine. No email was sent, nothing was applied to.\n")
    print("  Run just one of them:")
    for short in DEMO_AGENTS:
        print(f"    python run.py demo --agent {short}")
    print("\n  Decide an approval yourself instead of watching a pretend one:")
    print("    python run.py demo --pause")
    print("\n  Run them for real, from your phone:")
    print("    python run.py telegram\n")
    return 0


def cmd_sponsors(args) -> int:
    """Build a contact sheet for the whole sponsor list.

    This is the reference document: every brand, the route we found to them,
    and the evidence for it, in a file you can open in Excel and work down by
    hand. The agent uses the same data - this just lets you see all of it at
    once instead of one approval at a time.
    """
    import concurrent.futures as cf
    import csv

    from agents.sponsorship import agent as sponsor
    from core.crawler import Crawler
    from core.search import SeedsProvider

    brands = SeedsProvider(sponsor.build_config().seed_file).load()
    if args.segment:
        want = args.segment.lower()
        brands = [b for b in brands if want in b.get("segment", "").lower()]
    if args.limit:
        brands = brands[: args.limit]

    excluded = [(b, sponsor.blocked_reason(b)) for b in brands]
    brands = [b for b, why in excluded if not why]
    for b, why in excluded:
        if why:
            print(f"  excluded  {b.get('name')}: {why}")

    print(f"Reading {len(brands)} sites. This takes a few minutes.\n")

    def one(b):
        try:
            prof = Crawler(max_pages=6, timeout=14).profile_site(
                b["url"], hints=b.get("hints"))
            return b, prof, ""
        except Exception as exc:  # noqa: BLE001
            return b, None, f"{type(exc).__name__}: {exc}"[:120]

    rows = []
    with cf.ThreadPoolExecutor(max(1, args.workers)) as pool:
        for i, (b, prof, err) in enumerate(pool.map(one, brands), 1):
            best = (prof.contacts[0] if prof and prof.contacts else None)
            emails = [c.email for c in (prof.contacts if prof else [])
                      if c.email and not c.guessed][:3]
            phones = [c.phone for c in (prof.contacts if prof else []) if c.phone][:2]
            rows.append({
                "name": b.get("name", ""),
                "segment": b.get("segment", ""),
                "tier": b.get("tier", ""),
                "website": b.get("url", ""),
                "emails": " | ".join(emails),
                "phones": " | ".join(phones),
                "best_route": best.channel if best else "none",
                "best_contact": best.label if best else "",
                "guessed": "yes" if (best and best.guessed) else "no",
                "contact_form": (prof.contact_form_url if prof else ""),
                "instagram": (prof.socials.get("instagram", "") if prof else ""),
                "linkedin": (prof.socials.get("linkedin", "") if prof else ""),
                "why_they_fit": b.get("fit", ""),
                "evidence": best.evidence if best else err or "site unreadable",
            })
            status = "ok" if emails else ("phone" if phones else "-")
            print(f"  {i:>3}/{len(brands)}  {b.get('name','')[:28]:<28} {status}")

    out = pathlib.Path(args.out or (config.data_dir() / "sponsor_contacts.csv"))
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    with_email = sum(1 for r in rows if r["emails"])
    with_phone = sum(1 for r in rows if r["phones"] and not r["emails"])
    reachable = sum(1 for r in rows if r["best_route"] != "none")
    print(f"\n{len(rows)} brands")
    print(f"  {with_email} with a published email address")
    print(f"  {with_phone} more with a phone or WhatsApp number")
    print(f"  {reachable} reachable in total")
    print(f"\nWritten to {out}")
    return 0


def cmd_discover(args) -> int:
    """Run the sponsorship agent with its web sweep forced on."""
    import agents.sponsorship.agent as sponsor
    store = _store()
    _banner("Looking for sponsors that are not on your list yet")
    agent = sponsor.make(store=store)
    only = [s.strip() for s in (args.sources or "").split(",") if s.strip()]
    result = agent.build().invoke(
        {"_thread_id": args.thread, "discover": True,
         "only_sources": only or None},
        thread_id=args.thread)

    state = result.state or {}
    print()
    for key, label in (("swept", "candidates seen"),
                       ("new_domains", "not already on your list"),
                       ("verified", "real, Indian and worth a look"),
                       ("added", "added to the list"),
                       ("sent", "pitches sent")):
        print(f"  {label:<34} {(state.get('stats') or {}).get(key, 0)}")
    dropped = state.get("skipped") or []
    if dropped:
        print(f"\n  Passed over ({len(dropped)}):")
        for d in dropped[:10]:
            print(f"    {d.get('name', '')[:30]:<30} {d.get('reason', '')[:60]}")
    if result.interrupted:
        print(f"\n  Waiting on your decision. Approve in Telegram, or:")
        print(f"    python run.py serve")
    return 0


def cmd_apply(args) -> int:
    from agents.job_hunter.application import ApplicationAgent
    result = ApplicationAgent(store=_store()).run(args.url, str(pathlib.Path(args.resume).resolve()))
    print("Application:", result.status)
    print("Review the observed fields in the console before submission.")
    return 0 if not result.error else 1


def cmd_book(args) -> int:
    from agents.job_hunter.booking import BookingAgent
    result = BookingAgent(store=_store()).run(args.summary, args.start, args.end, args.attendee)
    print("Booking:", result.status, "- review in the console")
    return 0 if not result.error else 1


def cmd_schedule(args) -> int:
    """Simple built-in loop, for when you do not want cron."""
    store = _store()
    inbox_every = config.get_int("INBOX_POLL_SECONDS", 300)
    outreach_every = config.get_int("OUTREACH_INTERVAL_SECONDS", 86400)
    # The list needs refreshing far less often than it needs working. Once a
    # week is enough to catch new brands while they are still new.
    discover_every = config.get_int("DISCOVER_INTERVAL_SECONDS", 7 * 86400)
    last_outreach = 0.0
    _banner("Scheduler running - Ctrl-C to stop")
    print(f"  inbox check every {inbox_every}s; outreach every "
          f"{outreach_every/3600:.1f}h; new-sponsor sweep every "
          f"{discover_every/86400:.1f} days")
    try:
        while True:
            try:
                _process_inbox(store)
                from core.followups import queue_due
                queue_due(store)
            except Exception as exc:  # noqa: BLE001
                log.error(f"inbox poll failed: {exc}")
            if time.time() - last_outreach > outreach_every:
                for name in config.get_list("SCHEDULED_AGENTS", []):
                    try:
                        pending = store.one("SELECT id FROM approvals WHERE agent=? AND status=? LIMIT 1",
                                            (name, "pending"))
                        if pending:
                            continue
                        mod = AGENT_MODULES[name]
                        __import__(mod, fromlist=["make"]).make(store=store).run()
                    except Exception as exc:  # noqa: BLE001
                        log.error(f"scheduled run of {name} failed: {exc}")
                last_outreach = time.time()

            # The sponsorship agent decides for itself whether a sweep is
            # due, so there is nothing separate to schedule here.
            topic = config.get("PUBSUB_TOPIC")
            if topic:
                try:
                    from core.gmail import GmailClient
                    GmailClient(store).renew_watch_if_needed(topic)
                except Exception as exc:  # noqa: BLE001
                    log.error(f"watch renewal failed: {exc}")
            time.sleep(inbox_every)
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


# --------------------------------------------------------------------------
def cmd_workflow(args) -> int:
    from core.workflow_service import WorkflowService
    service = WorkflowService(_store())
    if args.action == 'list':
        result = service.ledger.list()
    elif args.action == 'create':
        if not args.file:
            raise ValueError('create needs --file containing a task request')
        request = json.loads(pathlib.Path(args.file).read_text(encoding='utf-8'))
        task = service.create(**request)
        result = service.prepare(task['task_id'])
    elif args.action == 'show':
        result = service.ledger.get(args.task)
    elif args.action in ('pause', 'resume', 'cancel'):
        result = service.ledger.control(args.task, args.action)
    elif args.action == 'prepare':
        result = service.prepare(args.task)
    elif args.action == 'dispatch':
        result = service.dispatch(args.task)
    else:
        result = service.decide(args.task, args.action == 'approve')
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def main(argv=None) -> int:
    configure()
    p = argparse.ArgumentParser(
        prog="run.py", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    wf = sub.add_parser('workflow', help='source-backed tasks in the existing Suite')
    wf.add_argument('action', choices=('list', 'create', 'show', 'prepare', 'approve', 'reject', 'pause', 'resume', 'cancel', 'dispatch'))
    wf.add_argument('--file', help='JSON request file for create')
    wf.add_argument('--task', help='exact task ID for other actions')
    wf.set_defaults(fn=cmd_workflow)

    dm = sub.add_parser("demo", help="safe zero-setup demonstration")
    dm.add_argument("--pause", action="store_true",
                    help="stop at the first approval so you can decide it")
    dm.add_argument("--agent", default="all",
                    help="all (default), jobs, sponsorship, video or dev")
    dm.set_defaults(fn=cmd_demo)

    tgp = sub.add_parser("telegram",
                         help="run the Telegram bot (control everything from your phone)")
    tgp.add_argument("--setup-only", action="store_true",
                     help="re-create any missing topics in the bound group and exit")
    tgp.set_defaults(fn=cmd_telegram)

    sub.add_parser("doctor", help="check the configuration").set_defaults(fn=cmd_doctor)

    a = sub.add_parser("auth", help="authorise Google")
    a.add_argument("provider", nargs="?", default="google")
    a.add_argument("--port", type=int, default=8765)
    a.add_argument("--no-browser", action="store_true")
    a.set_defaults(fn=cmd_auth)

    s = sub.add_parser("serve", help="start the console in your browser")
    s.add_argument("--host")
    s.add_argument("--port", type=int)
    s.add_argument("--demo", action="store_true",
                   help="read-only, with contact details hidden - for showing "
                        "it to somebody")
    s.add_argument("--open", action="store_true",
                   help="open it in your browser once it is up")
    s.set_defaults(fn=cmd_serve)

    r = sub.add_parser("run", help="run one agent")
    r.add_argument("agent", choices=sorted(AGENTS))
    r.add_argument("--thread", help="resume or name a specific run")
    r.add_argument("--query", action="append", help="override search queries")
    r.set_defaults(fn=cmd_run)

    application = sub.add_parser("apply", help="inspect and review an application form")
    application.add_argument("url")
    application.add_argument("--resume", required=True)
    application.set_defaults(fn=cmd_apply)
    booking = sub.add_parser("book", help="review and book a specific interview slot")
    booking.add_argument("--summary", required=True)
    booking.add_argument("--start", required=True, help="ISO datetime with timezone offset")
    booking.add_argument("--end", required=True)
    booking.add_argument("--attendee", action="append", required=True)
    booking.set_defaults(fn=cmd_book)

    sub.add_parser("inbox", help="poll Gmail and route replies").set_defaults(
        fn=cmd_inbox)

    w = sub.add_parser("watch", help="register or renew the Gmail push watch")
    w.add_argument("--topic")
    w.add_argument("--within", type=float, default=36.0)
    w.set_defaults(fn=cmd_watch)

    sub.add_parser("approvals", help="list what is waiting").set_defaults(
        fn=cmd_approvals)

    ap = sub.add_parser("approve")
    ap.add_argument("id")
    ap.add_argument("--note")
    ap.set_defaults(fn=cmd_approve)

    rj = sub.add_parser("reject")
    rj.add_argument("id")
    rj.add_argument("--note")
    rj.set_defaults(fn=cmd_reject)

    ld = sub.add_parser("leads")
    ld.add_argument("--detail", type=int, nargs="?", const=25, default=0)
    ld.set_defaults(fn=cmd_leads)

    sp = sub.add_parser("suppress", help="never contact an address again")
    sp.add_argument("email")
    sp.add_argument("--reason")
    sp.add_argument("--remove", action="store_true")
    sp.set_defaults(fn=cmd_suppress)

    gr = sub.add_parser("graph", help="print a graph as mermaid")
    gr.add_argument("agent")
    gr.set_defaults(fn=cmd_graph)

    t = sub.add_parser("test", help="run the test suite")
    t.add_argument("--pattern", default="test_*.py")
    t.add_argument("-v", "--verbose", action="store_true")
    t.set_defaults(fn=cmd_test)

    sp2 = sub.add_parser("sponsors",
                         help="build a contact sheet for the sponsor list")
    sp2.add_argument("--segment", default="",
                     help="only one kind, e.g. agency, nutrition, cricket_gear")
    sp2.add_argument("--limit", type=int, default=0, help="stop after N brands")
    sp2.add_argument("--workers", type=int, default=8)
    sp2.add_argument("--out", default="", help="where to write the CSV")
    sp2.set_defaults(fn=cmd_sponsors)

    dc = sub.add_parser("discover",
                        help="search the web for sponsors not on your list yet")
    dc.add_argument("--sources", default="",
                    help="comma separated: cuelinks, admitad, youtube, "
                         "trade_press, web_search")
    dc.add_argument("--thread", default="discover")
    dc.set_defaults(fn=cmd_discover)

    sub.add_parser("schedule", help="run on a loop").set_defaults(fn=cmd_schedule)

    args = p.parse_args(argv)
    try:
        return args.fn(args)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # noqa: BLE001
        log.exception("command failed")
        print(f"\nerror: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
