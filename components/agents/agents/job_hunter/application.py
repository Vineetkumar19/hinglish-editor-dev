"""Observed form fields -> factual answers -> explicit review -> submission."""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path

from core import config
from core.browser import ApplicationBrowser
from core.graph import END, StateGraph
from core.hitl import require_approval
from core.store import get_store
from core.yamlite import load_yaml
from .resume import load_master


def normalise(text):
    return re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip()


def plan_answers(inspection, master, answers, resume_path):
    contact = master.get("contact") or {}
    name = master.get("name") or ""
    known = {"first name": name.split(" ")[0], "last name": name.split(" ")[-1],
             "full name": name, "name": name, "email": contact.get("email"),
             "email address": contact.get("email"), "phone": contact.get("phone"),
             "phone number": contact.get("phone"), "location": contact.get("location"),
             "linkedin": contact.get("linkedin"), "linkedin profile": contact.get("linkedin"),
             "github": contact.get("github"), "website": contact.get("website"),
             "portfolio": contact.get("website")}
    known.update({normalise(k): v for k, v in answers.items() if v not in (None, "")})
    fields, missing = [], []
    for field in inspection.get("fields") or []:
        field = dict(field)
        field.pop("answer", None)
        label = normalise(field.get("label", "")).removesuffix(" required").strip()
        value = known.get(label)
        if field["type"] == "file" and re.search(r"resume|cv", label):
            value = str(resume_path)
        if value not in (None, ""):
            if field["type"] == "number":
                try:
                    float(value)
                except (ValueError, TypeError):
                    value = None
            if field.get("options") and str(value) not in [o["label"] for o in field["options"]]:
                value = None
            if value is not None:
                field["answer"] = value
        if field.get("required") and "answer" not in field:
            missing.append(field.get("label") or field.get("name") or str(field["index"]))
        fields.append(field)
    return {**inspection, "fields": fields, "missing": missing}


class ApplicationAgent:
    def __init__(self, store=None, browser=None):
        self.store = store or get_store()
        self.browser = browser or ApplicationBrowser()

    def n_inspect(self, state):
        path = Path(state["resume_path"])
        if not path.is_file():
            raise FileNotFoundError(f"Resume is missing: {path}")
        answers_path = Path(config.get("APPLICATION_ANSWERS_FILE",
                            str(config.profiles_dir() / "application_answers.yaml")))
        answers = load_yaml(answers_path.read_text(encoding="utf-8")) if answers_path.exists() else {}
        inspection = self.browser.inspect(state["url"])
        plan = plan_answers(inspection, state.get("master") or load_master(), answers or {}, str(path))
        return {"plan": plan, "answers": answers or {}}

    def n_review(self, state):
        plan = state["plan"]
        decision = require_approval(agent="job_hunter", thread_id=state["_thread_id"],
            kind="submit_application", title=f"Review application form: {state['url']}",
            payload={"apply_url": state["url"], "resume_path": state["resume_path"],
                     "body": json.dumps(plan["fields"], indent=2),
                     "answers": state.get("answers", {}), "missing_fields": plan["missing"],
                     "blocked": plan.get("blocked", ""),
                     "editable": ["answers"],
                     "note": "Approval permits submitting this observed form with the listed answers."},
            store=self.store)
        answers = {**state.get("answers", {}), **(decision.edits.get("answers") or {})}
        return {"decision": decision.to_json(), "answers": answers,
                "plan": plan_answers(plan, state.get("master") or load_master(), answers, state["resume_path"])}

    def n_submit(self, state):
        plan = state["plan"]
        if plan.get("blocked") or plan["missing"]:
            if state.get("lead_id"):
                from core.store import now
                self.store.run("UPDATE leads SET status=?,updated_at=? WHERE id=?",
                               ("needs_human", now(), state["lead_id"]))
            return {"result": {"outcome": "needs_human", "missing": plan["missing"],
                               "reason": plan.get("blocked", "")}}
        key = hashlib.sha256(state["url"].encode()).hexdigest()
        previous = self.store.kv_get("application_attempt", key)
        if previous and not config.dry_run():
            return {"result": previous}
        def before_submit():
            self.store.kv_set("application_attempt", key,
                              {"outcome": "submission_unconfirmed", "ts": time.time()})
        result = self.browser.submit(plan, state["resume_path"],
                                     dry_run=config.dry_run(), before_submit=before_submit)
        if result["outcome"] not in ("preview", "form_changed", "needs_human"):
            self.store.kv_set("application_attempt", key, result)
        if result["outcome"] == "form_changed":
            plan = plan_answers(result["inspection"], state.get("master") or load_master(),
                                state.get("answers", {}), state["resume_path"])
        else:
            self.store.event("application_result", "job_hunter", state["_thread_id"], **result)
            if state.get("lead_id"):
                status = {"submitted": "applied", "submission_unconfirmed": "submission_unconfirmed",
                          "preview": "dry_run"}.get(result["outcome"], "needs_human")
                from core.store import now
                self.store.run("UPDATE leads SET status=?,updated_at=? WHERE id=?",
                               (status, now(), state["lead_id"]))
        return {"result": result, "plan": plan}

    def build(self):
        graph = StateGraph()
        graph.add_node("inspect", self.n_inspect)
        graph.add_node("review", self.n_review)
        graph.add_node("submit", self.n_submit)
        graph.set_entry_point("inspect")
        graph.add_edge("inspect", "review")
        graph.add_conditional_edges("review", lambda s: "yes" if s["decision"]["status"] in
                                    ("approved", "edited") else "no", {"yes": "submit", "no": END})
        graph.add_conditional_edges("submit", lambda s: "changed" if s["result"]["outcome"] ==
                                    "form_changed" else "end", {"changed": "review", "end": END})
        return graph.compile(store=self.store, name="job_hunter_application", recursion_limit=15)

    def run(self, url, resume_path, thread_id=None, lead_id="", master=None):
        tid = thread_id or f"application-{time.time_ns()}"
        return self.build().invoke({"url": url, "resume_path": resume_path,
                                   "_thread_id": tid, "lead_id": lead_id,
                                   "master": master}, thread_id=tid)


def make(store=None, **kwargs):
    return ApplicationAgent(store=store, **kwargs)
