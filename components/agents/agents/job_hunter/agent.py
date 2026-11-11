"""Job discovery, factual resume tailoring and reviewed applications.

Screen -> tailor -> render -> job review -> observed-form review -> submit.
Browser submission uses supplied facts and separately reviewed answers; missing
facts, changed forms and unsupported portals pause for human completion.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import re
import textwrap
import time

from agents.job_hunter import (discovery, location,
                               read as read_mod, relevance,
                               resume as resume_mod, scam_filter)
from agents.job_hunter.brain import JobMemory
from agents.job_hunter.discovery import Job
from core import config
from core.calendar import CalendarClient
from core.graph import END, StateGraph, append, merge_dict
from core.hitl import require_approval
from core.llm import LLM, get_llm, offline_handler
from core.log import get_logger
from core.mailer import Mailer, OutgoingMessage, SendBlocked
from core.notify import get_notifier
from core.store import get_store, new_id, now

log = get_logger("job_hunter")

AGENT = "job_hunter"


def output_dir() -> pathlib.Path:
    d = pathlib.Path(config.get("RESUME_OUTPUT_DIR",
                                str(config.data_dir() / "resumes")))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _fmt_salary(job: dict) -> str:
    """A salary line a person can read. Boards leave this empty more often
    than not, and "0-0" is worse than saying so."""
    lo = float(job.get("salary_min") or 0)
    hi = float(job.get("salary_max") or 0)
    cur = (job.get("salary_currency") or "").strip()
    if not lo and not hi:
        return "not stated"
    if lo and hi and lo != hi:
        return f"{cur} {lo:,.0f} - {hi:,.0f}".strip()
    return f"{cur} {(lo or hi):,.0f}".strip()


def _fmt_experience(job: dict) -> str:
    match = job.get("match") or {}
    years = match.get("min_years")
    if years == 0:
        return "open to freshers"
    if years is None:
        return "not stated"
    return f"{years}+ years"


class JobHunter:
    def __init__(self, store=None, llm: LLM | None = None, notifier=None,
                 calendar=None, mailer=None):
        self.store = store or get_store()
        self.llm = llm or get_llm(self.store)
        self.notifier = notifier or get_notifier(self.store)
        self.calendar = calendar
        if self.calendar is None:
            from core.oauth import GoogleOAuth
            if GoogleOAuth(self.store).load():
                self.calendar = CalendarClient(self.store)
        self.mailer = mailer or Mailer(self.store)

    # ---------------------------------------------------------------- nodes --
    @property
    def brain(self) -> JobMemory:
        if getattr(self, "_brain", None) is None:
            self._brain = JobMemory(self.store)
        return self._brain

    def n_aggregate(self, s: dict) -> dict:
        if s.get("queue"):
            return {}
        queries = s.get("queries") or config.get_list(
            "JOB_QUERIES", ["Software Engineer", "Backend Engineer",
                            "Full Stack Developer"])
        jobs = discovery.aggregate(queries, sources=s.get("sources"))
        fresh, dupes, off_target = [], 0, []
        max_age = config.get_int("JOB_MAX_AGE_DAYS", 30) * 86400
        for j in jobs:
            if j.posted_at and (time.time() - j.posted_at) > max_age:
                continue
            # Is this job even for me? Boards match loosely and rank by
            # recency, so without this an "engineer" search returns sales
            # contractors and service desk roles.
            match = relevance.classify(j)
            if not match.relevant:
                if len(off_target) < 12:
                    off_target.append({"title": j.title, "company": j.company,
                                       "reason": match.reason})
                continue
            # And is it somewhere he can take it? This has to happen here,
            # before tailoring: a resume tailored by a local model costs
            # minutes, and spending them on a San Francisco posting he was
            # never going to take is the most expensive mistake in the run.
            here, why = location.acceptable(j)
            if not here:
                if len(off_target) < 12:
                    off_target.append({"title": j.title, "company": j.company,
                                       "reason": why})
                continue
            if not self.store.mark_seen(f"{AGENT}:job", j.key()):
                dupes += 1
                continue
            record = j.to_json()
            record["match"] = match.to_json()
            record["location_note"] = why
            record["_sort"] = relevance.sort_key(match)
            fresh.append(record)
        # best fit first, so the first thing you are asked about is the best
        # thing found - you may never reach the bottom of the queue
        # The static match score orders by how well the posting fits the
        # resume. The brain orders by what he has actually said yes to. Both
        # matter, so the learned score breaks ties inside a fit band rather
        # than overriding fit entirely - with no history it changes nothing.
        for r in fresh:
            r["brain_score"] = round(self.brain.score_job(r)[0], 4)
        fresh.sort(key=lambda r: (r.pop("_sort"), -r["brain_score"]))
        limit = config.get_int("JOB_MAX_PER_RUN", 25)
        return {"queue": fresh[:limit], "queries": queries,
                "off_target": off_target,
                "stats": {"found": len(jobs), "already_seen": dupes,
                          "off_target": len(jobs) - len(fresh) - dupes,
                          "queued": len(fresh[:limit])},
                "log": f"aggregated {len(jobs)}, {len(fresh)} on target"}

    def n_next_job(self, s: dict) -> dict:
        q = list(s.get("queue") or [])
        if not q:
            return {"job": None}
        return {"job": q.pop(0), "queue": q, "screen": None, "tailored": None}

    def n_screen(self, s: dict) -> dict:
        from core.work_policy import budget_check
        budget = budget_check(s["job"])
        if budget["reject"]:
            return {"screen": {"verdict": "reject", "score": 0, "flags": ["below_pay_floor"],
                    "stage": "preferences", "reason": budget["reason"]}}
        job = Job(**{k: v for k, v in s["job"].items()
                 if k in Job.__dataclass_fields__ and k != "raw"})
        result = scam_filter.screen(self.llm, job)
        return {"screen": {"verdict": result.verdict, "score": result.score,
                           "flags": result.flags, "stage": result.stage,
                           "reason": result.reason},
                "log": f"screen {job.company}: {result.verdict}"}

    def r_after_screen(self, s: dict) -> str:
        return "reject" if s["screen"]["verdict"] == "reject" else "tailor"

    def n_reject(self, s: dict) -> dict:
        job, sc = s["job"], s["screen"]
        self.store.upsert("leads", ("id",), {
            "id": new_id("jb"), "agent": AGENT, "company": job["company"],
            "domain": "", "person": "", "role": job["title"],
            "email": job.get("contact_email", ""), "phone": "",
            "source_url": job.get("url", ""), "score": sc["score"],
            "status": "rejected_budget" if sc["stage"] == "preferences" else "rejected_fraud", "thread_id": s["_thread_id"],
            "data_json": json.dumps({"job": job, "screen": sc}),
            "created_at": now(), "updated_at": now()})
        log.info("job discarded as likely fraudulent", company=job["company"],
                 title=job["title"][:50])
        self.brain.record_job(job, "passed" if sc["stage"] == "preferences" else "fraud", note=sc.get("reason", ""))
        return {"rejected": [{"company": job["company"], "title": job["title"],
                              "reason": sc["reason"], "flags": sc["flags"]}],
                "stats": {"rejected": 1},
                "log": f"REJECTED {job['company']}: {sc['reason'][:80]}"}

    def n_tailor(self, s: dict) -> dict:
        job = Job(**{k: v for k, v in s["job"].items()
                 if k in Job.__dataclass_fields__ and k != "raw"})
        master = resume_mod.load_master()
        # Read the posting before tailoring to it. A model that has just written
        # down the gap tailors better than one that goes straight to matching
        # keywords, and the read is what goes on the card above the decision.
        read = read_mod.read_job(self.llm, s["job"], master, store=self.store)
        result = resume_mod.tailor(master, job, llm=self.llm)
        if result.novel:
            log.warn("stripped unsupported claims from the tailored resume",
                     terms=result.novel[:8])
        return {"read": read,
                "tailored": {"data": result.data, "dropped": result.dropped,
                             "novel": result.novel,
                             "coverage": result.keyword_coverage},
                "log": f"tailored for {job.company} "
                       f"(keyword coverage {result.keyword_coverage:.0%})"}

    def n_render(self, s: dict) -> dict:
        job = s["job"]
        slug = re.sub(r"[^A-Za-z0-9]+", "-",
                      f"{job['company']}-{job['title']}").strip("-")[:60].lower()
        name = re.sub(r"[^A-Za-z0-9]+", "-",
                      s["tailored"]["data"].get("name", "resume")).strip("-")
        path = output_dir() / f"{name}-{slug}.pdf"
        resume_mod.render_pdf(s["tailored"]["data"], str(path))
        size = path.stat().st_size
        log.info("resume rendered", path=str(path), bytes=size)
        return {"resume_path": str(path), "resume_bytes": size,
                "log": f"rendered {path.name}"}

    def n_review(self, s: dict) -> dict:
        job, t = s["job"], s["tailored"]
        sc = s["screen"]
        decision = require_approval(
            agent=AGENT, thread_id=s["_thread_id"], kind="apply_to_job",
            title=f"Apply: {job['title']} at {job['company']}",
            payload={
                "company": job["company"], "title": job["title"],
                "location": job.get("location", ""),
                "remote": job.get("remote", False),
                "location_note": job.get("location_note", ""),
                "salary": _fmt_salary(job),
                "apply_url": job.get("apply_url") or job.get("url", ""),
                "source": job.get("source", ""),
                "screen": sc,
                "skills": (job.get("match") or {}).get("skills", []),
                "experience": _fmt_experience(job),
                "role_family": (job.get("match") or {}).get("family", ""),
                "why_it_matched": (job.get("match") or {}).get("reason", ""),
                "keyword_coverage": t["coverage"],
                "reads_as": (s.get("read") or {}).get("reads_as", ""),
                "strongest_match": (s.get("read") or {}).get("strongest_match", ""),
                "biggest_gap": (s.get("read") or {}).get("biggest_gap", ""),
                "worth_applying": (s.get("read") or {}).get("worth_applying", True),
                "why_not": (s.get("read") or {}).get("why_not", ""),
                "stripped_claims": t["novel"],
                "tailoring_notes": t["dropped"],
                "resume_path": s["resume_path"],
                "description_excerpt": (job.get("description") or "")[:1200],
                "actions": ["approve = prepare application for review", "reject = discard"],
            },
            store=self.store)
        try:
            from core.reflect import learn_from_decision
            # The payload has no "body", so the rule is learned from his note -
            # which for a job is the useful part anyway: "too senior", "wrong
            # stack", "I will not relocate there".
            learn_from_decision(AGENT, decision,
                                {"body": (job.get("description") or "")[:1500]},
                                store=self.store, llm=self.llm, scope="screen")
        except Exception as exc:  # noqa: BLE001
            log.debug(f"could not learn from that decision: {exc}")
        return {"decision": decision.to_json(),
                "log": f"review decision: {decision.status}"}

    def r_after_review(self, s: dict) -> str:
        d = s.get("decision") or {}
        return "applied" if d.get("status") in ("approved", "edited") else "passed"

    def n_applied(self, s: dict) -> dict:
        job = s["job"]
        from core.store import hash_key
        lead_id = "jb_" + hash_key(s["_thread_id"], job.get("id") or job.get("url"))[:24]
        self.store.upsert("leads", ("id",), {
            "id": lead_id, "agent": AGENT, "company": job["company"], "domain": "",
            "person": "", "role": job["title"],
            "email": job.get("contact_email", ""), "phone": "",
            "source_url": job.get("apply_url") or job.get("url", ""),
            "score": s["tailored"]["coverage"], "status": "ready_to_apply",
            "thread_id": s["_thread_id"],
            "data_json": json.dumps({"job": job, "resume": s["resume_path"],
                                     "screen": s["screen"]}),
            "created_at": now(), "updated_at": now()})
        self.store.event("application_prepared", AGENT, s["_thread_id"],
                         company=job["company"], title=job["title"],
                         resume=s["resume_path"])
        self.brain.record_job({**job, "keyword_coverage": s["tailored"]["coverage"]},
                              "approved")
        if config.get_bool("JOB_AUTO_APPLICATIONS", False):
            from .application import ApplicationAgent
            ApplicationAgent(store=self.store).run(
                job.get("apply_url") or job.get("url"), s["resume_path"],
                thread_id="apply-" + lead_id, lead_id=lead_id,
                master=s["tailored"]["data"])
        return {"applied": [{"company": job["company"], "title": job["title"],
                             "url": job.get("apply_url") or job.get("url"),
                             "resume": s["resume_path"], "lead_id": lead_id}],
                "stats": {"prepared": 1},
                "log": f"application prepared: {job['company']}"}

    def n_passed(self, s: dict) -> dict:
        job = s["job"]
        # A pass is the more common answer, so it is where most of the learning
        # comes from. Without recording it the brain only ever sees wins.
        self.brain.record_job(job, "passed",
                              note=(s.get("decision") or {}).get("note", ""))
        return {"passed": [{"company": job["company"], "title": job["title"],
                            "note": (s.get("decision") or {}).get("note", "")}],
                "stats": {"passed": 1}, "log": f"passed on {job['company']}"}

    def r_more(self, s: dict) -> str:
        return "next" if s.get("queue") else "done"

    def n_done(self, s: dict) -> dict:
        stats = s.get("stats") or {}
        applied = s.get("applied") or []
        if applied:
            lines = "\n".join(f"- {a['title']} at {a['company']}\n  {a['url']}"
                              for a in applied[:10])
            self.notifier.send(
                f"{len(applied)} application(s) ready",
                f"Tailored resumes are built and waiting:\n\n{lines}",
                priority="normal", tags=("briefcase",))
        log.info("job hunt finished", **stats)
        return {"summary": stats}

    # ---------------------------------------------------------------- graph --
    def build(self, recursion_limit: int = 400):
        g = StateGraph(reducers={"log": append, "applied": append,
                                 "rejected": append, "passed": append,
                                 "stats": _sum_stats})
        g.add_node("aggregate", self.n_aggregate, retries=1, backoff=3)
        g.add_node("next_job", self.n_next_job)
        g.add_node("screen", self.n_screen)
        g.add_node("reject", self.n_reject)
        g.add_node("tailor", self.n_tailor, retries=1)
        g.add_node("render", self.n_render, retries=1)
        g.add_node("review", self.n_review)
        g.add_node("applied", self.n_applied)
        g.add_node("passed", self.n_passed)
        g.add_node("done", self.n_done)

        g.set_entry_point("aggregate")
        g.add_conditional_edges("aggregate",
                                lambda s: "next" if s.get("queue") else "done",
                                {"next": "next_job", "done": "done"})
        g.add_conditional_edges("next_job",
                                lambda s: "go" if s.get("job") else "done",
                                {"go": "screen", "done": "done"})
        g.add_conditional_edges("screen", self.r_after_screen,
                                {"reject": "reject", "tailor": "tailor"})
        g.add_conditional_edges("reject", self.r_more,
                                {"next": "next_job", "done": "done"})
        g.add_edge("tailor", "render")
        g.add_edge("render", "review")
        g.add_conditional_edges("review", self.r_after_review,
                                {"applied": "applied", "passed": "passed"})
        g.add_conditional_edges("applied", self.r_more,
                                {"next": "next_job", "done": "done"})
        g.add_conditional_edges("passed", self.r_more,
                                {"next": "next_job", "done": "done"})
        g.add_edge("done", END)
        return g.compile(store=self.store, name=AGENT,
                         recursion_limit=recursion_limit)

    def run(self, queries=None, sources=None, thread_id: str | None = None, **kw):
        tid = thread_id or f"{AGENT}-{time.strftime('%Y%m%d-%H%M%S')}"
        return self.build().invoke(
            {"_thread_id": tid, "queries": queries, "sources": sources},
            thread_id=tid, **kw)


def _sum_stats(old, new):
    out = dict(old or {})
    for k, v in (new or {}).items():
        out[k] = out.get(k, 0) + v if isinstance(v, (int, float)) else v
    return out


# ==========================================================================
# interview scheduling
# ==========================================================================
INTERVIEW_RE = re.compile(
    r"\b(interview|availability|available|schedule a (call|chat)|"
    r"book a (time|slot)|hop on a call|next round|screening call|"
    r"technical round|when (are|would) you)\b", re.I)


def looks_like_interview_request(text: str) -> bool:
    return bool(INTERVIEW_RE.search(text or ""))


@offline_handler("interview_reply")
def _offline_interview_reply(ctx: dict) -> dict:
    slots = ctx.get("slots") or []
    name = (ctx.get("recruiter_name") or "").split(" ")[0]
    greet = f"Hi {name}," if name and name.isalpha() else "Hi there,"
    tz = config.get("TIMEZONE", "Asia/Kolkata")
    listed = "\n".join(f"  - {s}" for s in slots) or "  - PLACEHOLDER: no free slots found"
    body = (f"{greet}\n\nThanks for getting back to me - happy to talk.\n\n"
            f"These times are open in my calendar ({tz}):\n\n{listed}\n\n"
            f"If none of those work, send a couple that suit you and I'll make "
            f"one of them work.\n\n{config.get('OPERATOR_NAME', 'Vineet')}")
    return {"body": body, "subject": "", "needs_human": not slots,
            "next_step": "Awaiting their choice of slot"}


class InterviewScheduler:
    """Detects an interview request, proposes real free slots, books on confirm."""

    def __init__(self, store=None, llm=None, calendar=None, mailer=None,
                 notifier=None):
        self.store = store or get_store()
        self.llm = llm or get_llm(self.store)
        self.calendar = calendar
        self.mailer = mailer or Mailer(self.store)
        self.notifier = notifier or get_notifier(self.store)
        if self.calendar is None:
            from core.oauth import GoogleOAuth
            if GoogleOAuth(self.store).load():
                self.calendar = CalendarClient(self.store)

    def n_detect(self, s: dict) -> dict:
        msg = s["message"]
        is_interview = looks_like_interview_request(
            (msg.get("subject", "") + " " + (msg.get("reply_text") or "")))
        return {"is_interview": is_interview,
                "log": f"interview request: {is_interview}"}

    def r_detect(self, s: dict) -> str:
        return "schedule" if s.get("is_interview") else "ignore"

    def n_ignore(self, s: dict) -> dict:
        return {"outcome": "not_an_interview_request"}

    def n_slots(self, s: dict) -> dict:
        if self.calendar is None:
            return {"slots": [], "outcome_note": "no calendar configured",
                    "log": "calendar not configured - cannot propose times"}
        found = self.calendar.find_slots(
            days_ahead=config.get_int("SCHEDULE_DAYS_AHEAD", 7),
            duration_min=config.get_int("INTERVIEW_MINUTES", 45),
            max_slots=config.get_int("SCHEDULE_MAX_SLOTS", 4))
        tz = config.get("TIMEZONE", "Asia/Kolkata")
        return {"slots": [sl.human(tz) for sl in found],
                "slot_iso": [[sl.start.isoformat(), sl.end.isoformat()]
                             for sl in found],
                "log": f"found {len(found)} free slots"}

    def n_draft(self, s: dict) -> dict:
        msg = s["message"]
        if not s.get("slots"):
            return {"draft": {"body": "Hi,\n\nThanks for the interview invitation. "
                    "Please share a couple of preferred times and your timezone so I can "
                    "confirm availability.\n\n" + config.get("OPERATOR_NAME", "Vineet"),
                    "subject": "", "needs_human": True,
                    "next_step": "Confirm availability before booking"}}
        draft = self.llm.structured(
            "Reply to this interview request offering the available times "
            "listed. Do not offer any time that is not listed. Keep it to four "
            "sentences.\n\n"
            f"Available: {s.get('slots')}\n\n"
            f"Their message:\n---\n{(msg.get('reply_text') or '')[:2000]}\n---",
            {"type": "object", "required": ["body"],
             "properties": {"body": {"type": "string", "min_length": 40,
                                     "max_length": 1500},
                            "subject": {"type": "string", "default": ""},
                            "needs_human": {"type": "boolean", "default": False},
                            "next_step": {"type": "string", "default": ""}}},
            task="interview_reply",
            context={"slots": s.get("slots"),
                     "recruiter_name": msg.get("from_name", ""), "message": msg},
            temperature=0.2)
        return {"draft": draft}

    def n_approve(self, s: dict) -> dict:
        msg = s["message"]
        d = require_approval(
            agent=AGENT, thread_id=s["_thread_id"], kind="interview_reply",
            title=f"Interview times to {msg.get('from_addr')}",
            payload={"to": msg.get("from_addr"),
                     "subject": s["draft"].get("subject")
                     or f"Re: {msg.get('subject','')}",
                     "body": s["draft"]["body"], "slots": s.get("slots", []),
                     "their_message": (msg.get("reply_text") or "")[:1200]},
            store=self.store)
        if not d.approved:
            return {"decision": d.to_json(), "outcome": "declined_to_reply"}
        return {"decision": d.to_json(),
                "final": d.apply_to({"subject": s["draft"].get("subject")
                                     or f"Re: {msg.get('subject','')}",
                                     "body": s["draft"]["body"]})}

    def r_after_approve(self, s: dict) -> str:
        d = s.get("decision") or {}
        return "send" if d.get("status") in ("approved", "edited") else "end"

    def n_send(self, s: dict) -> dict:
        msg = s["message"]
        out = OutgoingMessage(
            to=msg.get("from_addr", ""), subject=s["final"]["subject"],
            body=s["final"]["body"], in_reply_to=msg.get("rfc_message_id", ""),
            references=msg.get("references", ""),
            gmail_thread_id=msg.get("thread_id", ""), tag=AGENT,
            idempotency_key=f"{s['_thread_id']}:interview-times",
            include_footer=False)
        try:
            res = self.mailer.send(out, enforce_cap=False)
        except SendBlocked as exc:
            return {"outcome": f"blocked: {exc}"}
        self.mailer.record(s["_thread_id"], AGENT, "out", out, res)
        if not res.get("dry_run") and s.get("slot_iso"):
            self.store.kv_set("interview_offers", msg.get("from_addr", "").lower(), {
                "slots": s["slots"], "slot_iso": s["slot_iso"],
                "summary": msg.get("subject") or "Interview", "thread_id": s["_thread_id"]})
        self.notifier.send("Interview times sent",
                           f"Proposed {len(s.get('slots', []))} slots to "
                           f"{msg.get('from_addr')}.", priority="normal")
        return {"outcome": "times_proposed"}

    def build(self):
        g = StateGraph(reducers={"log": append})
        g.add_node("detect", self.n_detect)
        g.add_node("ignore", self.n_ignore)
        g.add_node("slots", self.n_slots, retries=1)
        g.add_node("draft", self.n_draft, retries=1)
        g.add_node("approve", self.n_approve)
        g.add_node("send", self.n_send)
        g.set_entry_point("detect")
        g.add_conditional_edges("detect", self.r_detect,
                                {"schedule": "slots", "ignore": "ignore"})
        g.add_edge("ignore", END)
        g.add_edge("slots", "draft")
        g.add_edge("draft", "approve")
        g.add_conditional_edges("approve", self.r_after_approve,
                                {"send": "send", "end": END})
        g.add_edge("send", END)
        return g.compile(store=self.store, name=f"{AGENT}_interview")

    def handle(self, message: dict, thread_id: str | None = None, **kw):
        tid = thread_id or f"{AGENT}-iv-{message.get('id') or new_id()}"
        return self.build().invoke({"message": message, "_thread_id": tid},
                                   thread_id=tid, **kw)

    def confirm_slot(self, *, summary: str, start_iso: str, end_iso: str,
                     attendees: list[str], description: str = "") -> dict:
        """Called once they pick a time. Creates the calendar event."""
        if self.calendar is None:
            raise RuntimeError("no calendar client configured")
        return self.calendar.create_event(
            summary=summary, start=dt.datetime.fromisoformat(start_iso),
            end=dt.datetime.fromisoformat(end_iso), attendees=attendees,
            description=description, add_meet=True)


def make(store=None, **kw) -> JobHunter:
    return JobHunter(store=store, **kw)


def make_scheduler(store=None, **kw) -> InterviewScheduler:
    return InterviewScheduler(store=store, **kw)
