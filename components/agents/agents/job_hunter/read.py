"""The model's read of a job posting.

The scam filter answers "is this real" and the resume tailor answers "which of
his bullets match". Neither answers the question he actually has when a card
arrives on his phone: what does this job really want, and where does he fall
short of it.

That read goes on the card above the decision. A model that has just written
down the gap is also a model that tailors better, which is why this runs before
the tailoring step rather than after.
"""
from __future__ import annotations

import textwrap

from core.lessons import get_lessons
from core.llm import LLMError
from core.log import get_logger

log = get_logger("jobs.read")

READ_SCHEMA = {
    "type": "object",
    "required": ["reads_as", "strongest_match", "biggest_gap", "worth_applying"],
    "properties": {
        "reads_as": {"type": "string", "min_length": 15, "max_length": 400},
        "strongest_match": {"type": "string", "max_length": 220, "default": ""},
        "biggest_gap": {"type": "string", "max_length": 220, "default": ""},
        "worth_applying": {"type": "boolean", "default": True},
        "why_not": {"type": "string", "max_length": 220, "default": ""},
    },
}


def _fill(text: str) -> str:
    lines = [ln[8:] if ln.startswith(" " * 8) else ln
             for ln in text.strip("\n").splitlines()]
    return "\n".join(lines).strip()


def build_prompt(job: dict, resume: dict) -> str:
    skills = resume.get("skills") or {}
    flat = []
    for group in ("languages", "backend", "databases", "frontend", "tools"):
        flat.extend(str(x) for x in (skills.get(group) or [])[:6])
    years = resume.get("years_experience") or "under a year in a paid role"

    return _fill(f"""
        Read this job posting and say what it actually wants. You are reading on
        behalf of one specific engineer, described below. Be honest about the
        gap - a card that oversells a job wastes his evening.

        THE POSTING
        Title: {job.get('title', '')}
        Company: {job.get('company', '')}
        Location: {job.get('location', 'not stated')}
        ---
        {(job.get('description') or '')[:6000]}
        ---

        THE ENGINEER
        - {resume.get('headline', 'Software Engineer')}
        - Experience: {years}
        - Works with: {', '.join(flat[:22])}
        - Currently: {(resume.get('experience') or [{}])[0].get('title', '')} at
          {(resume.get('experience') or [{}])[0].get('company', '')}

        Answer four things.
        1. "reads_as": in one or two sentences, what the team actually does and
           what this role does inside it. From their words, not from the title.
        2. "strongest_match": the single strongest overlap between what they
           ask for and what he has. Name it specifically.
        3. "biggest_gap": the thing they ask for that he most clearly does not
           have. If there is genuinely none, say so - do not invent one.
        4. "worth_applying": false only when the gap is disqualifying - a
           security clearance, a language he does not speak, ten years of
           experience, a country he cannot work in. A stack he has not used is
           not disqualifying. If false, put one line in "why_not".

        Do not flatter, do not sell, and do not repeat the job title back.
    """)


def read_job(llm, job: dict, resume: dict, store=None) -> dict:
    """The read, or a safe empty one when there is no model."""
    if llm is None or llm.is_offline:
        return {}
    prompt = build_prompt(job, resume)
    learned = get_lessons("job_hunter", store).prompt_block(
        context=f"{job.get('title','')} {job.get('company','')}", scope="screen")
    if learned:
        prompt = f"{prompt}\n\n{learned}"
    try:
        return llm.structured(
            prompt, READ_SCHEMA, task="read_job",
            system="You read job postings for one engineer and report what you "
                   "see. You are blunt about gaps and you never flatter.",
            temperature=0.2, max_tokens=500)
    except (LLMError, Exception) as exc:  # noqa: BLE001
        if getattr(llm, "provider_name", None) == "chatgpt":
            raise
        log.warn(f"could not read the posting: {exc}")
        return {}
