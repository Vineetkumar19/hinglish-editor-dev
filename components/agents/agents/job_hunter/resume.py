"""Dynamic resume tailoring - the RenderCV role, without RenderCV.

Design constraint: the model must not be able to invent experience. So it is
never asked to write a resume. It is asked to *select and order* material that
already exists in your master profile, and to lightly rephrase bullets it
selects. Everything it returns is then checked against the master:

  * every experience, project and education entry must exist by id
  * every skill must already be in your skills list
  * every rephrased bullet is scanned for numbers, company names, technologies
    and acronyms that do not appear anywhere in the master profile

Anything that fails is dropped and logged, and if too much is dropped the
tailoring is abandoned in favour of the untailored master. A resume that quietly
invents a job is worse than one that is merely generic.
"""
from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass, field

from core import config
from core.log import get_logger
from core.pdf import PDF
from core.schema import ValidationError, validate
from core.yamlite import dump_yaml, load_yaml

log = get_logger("resume")

MASTER_SCHEMA = {
    "type": "object",
    "required": ["name", "contact", "experience"],
    "properties": {
        "track": {"type": "string", "default": "software"},
        "name": {"type": "string", "min_length": 2},
        "headline": {"type": "string", "default": ""},
        "summary": {"type": "string", "default": ""},
        "contact": {
            "type": "object",
            "properties": {
                "email": {"type": "string", "default": ""},
                "phone": {"type": "string", "default": ""},
                "location": {"type": "string", "default": ""},
                "linkedin": {"type": "string", "default": ""},
                "github": {"type": "string", "default": ""},
                "website": {"type": "string", "default": ""},
            },
        },
        "skills": {"type": "object", "default": {}},
        "experience": {
            "type": "array", "min_items": 1,
            "items": {
                "type": "object",
                "required": ["id", "title", "company"],
                "properties": {
                    "id": {"type": "string"},
                    "title": {"type": "string"},
                    "company": {"type": "string"},
                    "location": {"type": "string", "default": ""},
                    "start": {"type": "string", "default": ""},
                    "end": {"type": "string", "default": ""},
                    "bullets": {"type": "array", "items": {"type": "string"},
                                "default": []},
                    "tech": {"type": "array", "items": {"type": "string"},
                             "default": []},
                },
            },
        },
        "projects": {"type": "array", "default": [], "items": {"type": "object"}},
        "education": {"type": "array", "default": [], "items": {"type": "object"}},
        "certifications": {"type": "array", "default": [],
                           "items": {"type": "string"}},
        "leadership": {"type": "array", "default": [],
                       "items": {"type": "string"}},
    },
}


# --------------------------------------------------------------------------
# track separation
# --------------------------------------------------------------------------
# A software resume must never carry video editing material, and a video
# editing resume must never carry backend engineering material. They are
# different careers and mixing them weakens both. Each master profile declares
# its track, and these vocabularies are how we catch a leak.
#
# Only unambiguous terms belong here. Words that legitimately appear in both
# worlds - "design system", "Figma", "editing" - are deliberately absent.
TRACK_VOCAB = {
    "video": [
        "premiere pro", "after effects", "davinci resolve", "motion graphics",
        "colour grading", "color grading", "colour grade", "color grade",
        "sound design", "kinetic typography", "lower thirds", "telestration",
        "video editor", "video editing", "thumbnail design", "subtitling",
        "multicam", "colour matched", "color matched",
    ],
    "software": [
        "spring boot", "spring security", "rest api", "jwt", "mysql", "mongodb",
        "postgresql", "sqlite", "express.js", "node.js", "docker", "kubernetes",
        "hibernate", "backend service", "schema design", "unit testing",
        "python", "java", "javascript", "react", "sql",
    ],
}


def track_violations(master: dict) -> list[str]:
    """Terms from the OTHER track found in this master profile.

    Returns the offending terms, empty when the profile is clean. Used by
    `run.py doctor` and by the test suite - a leak here is what produces a
    backend resume that talks about colour grading.
    """
    track = (master.get("track") or "software").strip().lower()
    other = "video" if track == "software" else "software"
    corpus = master_corpus(master).lower()
    found = []
    for term in TRACK_VOCAB.get(other, []):
        pattern = (r"\b" + re.escape(term) + r"\b") if " " not in term \
            else re.escape(term)
        if re.search(pattern, corpus):
            found.append(term)
    return found

TAILOR_SCHEMA = {
    "type": "object",
    "required": ["summary", "experience_ids", "skill_order"],
    "properties": {
        "summary": {"type": "string", "max_length": 600, "default": ""},
        "experience_ids": {"type": "array", "items": {"type": "string"},
                           "max_items": 12},
        "project_ids": {"type": "array", "items": {"type": "string"},
                        "max_items": 8, "default": []},
        "skill_order": {"type": "array", "items": {"type": "string"},
                        "max_items": 40},
        "bullet_rewrites": {
            "type": "array", "max_items": 24, "default": [],
            "items": {"type": "object",
                      "properties": {
                          "experience_id": {"type": "string"},
                          "index": {"type": "integer", "minimum": 0},
                          "text": {"type": "string", "max_length": 300}}},
        },
        "dropped_reason": {"type": "string", "default": ""},
    },
}


# --------------------------------------------------------------------------
# master profile
# --------------------------------------------------------------------------
def master_path() -> pathlib.Path:
    return pathlib.Path(config.get("RESUME_MASTER_FILE",
                                   str(config.ROOT / "profiles" / "master_resume.yaml")))


def load_master(path=None) -> dict:
    p = pathlib.Path(path) if path else master_path()
    if not p.exists():
        raise FileNotFoundError(
            f"master resume not found at {p}. Copy profiles/master_resume.yaml "
            f"and fill it in - this is the single source of truth the agent is "
            f"allowed to draw on.")
    data = load_yaml(p.read_text(encoding="utf-8"))
    try:
        master = validate(data, MASTER_SCHEMA)
    except ValidationError as exc:
        hint = ""
        if "expected string, got dict" in str(exc):
            hint = ("\n\nHint: a list item containing ': ' is parsed as a "
                    "key/value pair in YAML. Wrap such a line in double quotes, "
                    'e.g.  - "Handle the pipeline: edit, grade, mix"')
        raise ValueError(f"{p} is not a valid master resume: {exc}{hint}") from exc
    leaked = track_violations(master)
    if leaked:
        other = "video" if (master.get("track") or "software") == "software" \
            else "software"
        log.warn(f"{p.name} is the '{master.get('track')}' profile but mentions "
                 f"{other} material: {', '.join(leaked)}. These are different "
                 f"careers - move that material to the other profile.")
    return master


# --------------------------------------------------------------------------
# hallucination guard
# --------------------------------------------------------------------------
_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9+#.\-]{1,}")
_NUMBER = re.compile(r"\b\d[\d,.]*%?\b")
_STOP = set("""a an and are as at be by for from has have in into is it its of on or
that the to was were will with we our you your they their i my me this these those
which who whom while when where how what why all any both each few more most other
some such no nor not only own same so than too very can just also over under after
before between during about across through""".split())


def master_corpus(master: dict) -> str:
    parts = [master.get("summary", ""), master.get("headline", "")]
    for group in (master.get("skills") or {}).values():
        parts.extend(group if isinstance(group, list) else [str(group)])
    for e in master.get("experience", []):
        parts += [e.get("title", ""), e.get("company", ""), e.get("location", "")]
        parts += e.get("bullets", []) or []
        parts += e.get("tech", []) or []
    for p in master.get("projects", []):
        parts += [str(p.get("name", "")), str(p.get("description", ""))]
        parts += p.get("tech", []) or []
        parts += p.get("bullets", []) or []
    for ed in master.get("education", []):
        parts += [str(v) for v in ed.values()]
    parts += master.get("certifications", []) or []
    return "\n".join(str(p) for p in parts)


def novel_claims(text: str, corpus: str) -> list[str]:
    """Tokens and figures in `text` with no support anywhere in the master."""
    low_corpus = corpus.lower()
    corpus_tokens = {t.lower() for t in _TOKEN.findall(corpus)}
    corpus_numbers = set(_NUMBER.findall(corpus))
    novel = []
    for tok in _TOKEN.findall(text or ""):
        low = tok.lower()
        if low in _STOP or len(low) < 3:
            continue
        if low in corpus_tokens:
            continue
        # allow plural/possessive and simple inflections of a supported token
        stem = re.sub(r"(ing|ed|es|s|'s)$", "", low)
        if stem and (stem in corpus_tokens or any(c.startswith(stem)
                                                  for c in corpus_tokens)):
            continue
        novel.append(tok)
    for num in _NUMBER.findall(text or ""):
        if num not in corpus_numbers and num.strip("0.,%") != "":
            novel.append(num)
    return sorted(set(novel))


@dataclass
class TailorResult:
    data: dict = field(default_factory=dict)
    dropped: list = field(default_factory=list)
    novel: list = field(default_factory=list)
    tailored: bool = False
    keyword_coverage: float = 0.0

    @property
    def clean(self) -> bool:
        return not self.novel


# --------------------------------------------------------------------------
# keyword extraction from a job description
# --------------------------------------------------------------------------
def job_keywords(description: str, title: str = "", limit: int = 30) -> list[str]:
    text = f"{title}\n{description}"
    counts: dict[str, int] = {}
    for tok in _TOKEN.findall(text):
        low = tok.lower()
        if low in _STOP or len(low) < 3:
            continue
        counts[low] = counts.get(low, 0) + 1
    # phrases like "next.js", "ci/cd" survive tokenisation already
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [k for k, _ in ranked[:limit]]


def coverage(master: dict, keywords: list[str]) -> float:
    corpus = master_corpus(master).lower()
    if not keywords:
        return 0.0
    hit = sum(1 for k in keywords if k in corpus)
    return round(hit / len(keywords), 3)


# --------------------------------------------------------------------------
# tailoring
# --------------------------------------------------------------------------
def _offline_tailor(master: dict, job) -> dict:
    """Deterministic tailoring: rank real entries by keyword overlap.

    No rewriting at all, so it is incapable of inventing anything.
    """
    keywords = set(job_keywords(job.description, job.title, limit=40))

    def score(entry: dict) -> int:
        blob = " ".join(str(v) for v in entry.values()
                        if isinstance(v, (str, int, float)))
        blob += " " + " ".join(entry.get("bullets", []) or [])
        blob += " " + " ".join(entry.get("tech", []) or [])
        toks = {t.lower() for t in _TOKEN.findall(blob)}
        return len(toks & keywords)

    exp = sorted(master.get("experience", []), key=lambda e: -score(e))
    # Relevance first; `featured: true` only breaks ties. A project you marked
    # as a favourite should not outrank one that actually matches the job.
    projects = sorted(master.get("projects", []),
                      key=lambda p: (-score(p), 0 if p.get("featured") else 1))
    skills_flat = []
    for group in (master.get("skills") or {}).values():
        skills_flat.extend(group if isinstance(group, list) else [str(group)])
    skills = sorted(set(skills_flat),
                    key=lambda s: (-(s.lower() in keywords), skills_flat.index(s)))
    return {
        "summary": master.get("summary", ""),
        "experience_ids": [e["id"] for e in exp],
        "project_ids": [str(p.get("id", p.get("name", "")))
                        for p in projects[:max_projects()]],
        "skill_order": skills[:40],
        "bullet_rewrites": [],
        "dropped_reason": "",
    }


def tailor(master: dict, job, llm=None) -> TailorResult:
    keywords = job_keywords(job.description, job.title)
    cov = coverage(master, keywords)

    if llm is None or getattr(llm, "is_offline", False):
        picked = _offline_tailor(master, job)
        return _assemble(master, picked, cov, novel=[], dropped=[], tailored=True)

    valid_ids = [e["id"] for e in master.get("experience", [])]
    skills_flat = []
    for group in (master.get("skills") or {}).values():
        skills_flat.extend(group if isinstance(group, list) else [str(group)])

    prompt = (
        "Tailor this candidate's existing resume material to the job below.\n\n"
        "You may ONLY select and reorder what already exists. You may lightly "
        "rephrase a bullet to use the job's vocabulary, but you must not add any "
        "fact, number, employer, technology or achievement that is not already "
        "present. If the candidate does not have relevant experience, return "
        "fewer items rather than inventing any.\n\n"
        f"Valid experience ids: {valid_ids}\n"
        f"Valid skills: {skills_flat}\n\n"
        f"=== JOB ===\nTitle: {job.title}\nCompany: {job.company}\n"
        f"{job.description[:5000]}\n\n"
        f"=== CANDIDATE MASTER PROFILE ===\n{dump_yaml(master)[:9000]}")
    try:
        picked = llm.structured(prompt, TAILOR_SCHEMA, task="tailor_resume",
                                context={"master": master, "job": job},
                                system="You tailor resumes by selection, never by "
                                       "invention.",
                                temperature=0.1, max_tokens=2000)
    except Exception as exc:  # noqa: BLE001
        if getattr(llm, "provider_name", None) == "chatgpt":
            raise
        log.warn(f"LLM tailoring failed, falling back to keyword ranking: {exc}")
        picked = _offline_tailor(master, job)
        return _assemble(master, picked, cov, [], [], tailored=True)

    corpus = master_corpus(master)
    dropped, novel_all = [], []

    picked["experience_ids"] = [i for i in picked.get("experience_ids", [])
                                if i in valid_ids] or valid_ids
    unknown = [i for i in picked.get("experience_ids", []) if i not in valid_ids]
    dropped += [f"unknown experience id {i}" for i in unknown]

    allowed_skills = {s.lower(): s for s in skills_flat}
    kept_skills = []
    for s in picked.get("skill_order", []):
        if s.lower() in allowed_skills:
            kept_skills.append(allowed_skills[s.lower()])
        else:
            dropped.append(f"invented skill {s!r}")
    picked["skill_order"] = kept_skills or skills_flat

    summary_novel = novel_claims(picked.get("summary", ""), corpus)
    if summary_novel:
        dropped.append(f"summary contained unsupported terms {summary_novel}")
        novel_all += summary_novel
        picked["summary"] = master.get("summary", "")

    kept_rewrites = []
    for rw in picked.get("bullet_rewrites", []) or []:
        n = novel_claims(rw.get("text", ""), corpus)
        if n:
            dropped.append(f"bullet rewrite added unsupported terms {n}")
            novel_all += n
            continue
        kept_rewrites.append(rw)
    picked["bullet_rewrites"] = kept_rewrites

    if len(dropped) > 6:
        log.warn("too much invented content - falling back to untailored master",
                 dropped=len(dropped))
        picked = _offline_tailor(master, job)
        dropped.append("ABANDONED LLM TAILORING - fell back to keyword ranking")

    return _assemble(master, picked, cov, novel_all, dropped, tailored=True)


def max_projects() -> int:
    """How many projects land on the resume. Three fits one page comfortably."""
    try:
        return max(1, int(config.get("RESUME_MAX_PROJECTS", "3")))
    except (TypeError, ValueError):
        return 3


def featured_projects(master: dict, limit: int | None = None) -> list:
    """The fallback project set when nothing has been ranked against a job."""
    ordered = sorted(master.get("projects", []),
                     key=lambda p: 0 if p.get("featured") else 1)
    return ordered[:limit or max_projects()]


def _assemble(master: dict, picked: dict, cov: float, novel: list,
              dropped: list, tailored: bool) -> TailorResult:
    by_id = {e["id"]: e for e in master.get("experience", [])}
    rewrites: dict[tuple[str, int], str] = {
        (rw.get("experience_id"), int(rw.get("index", 0))): rw.get("text", "")
        for rw in (picked.get("bullet_rewrites") or [])}

    # Jobs are listed newest first, never by relevance. A recruiter reads the
    # top entry as "where they are now", so re-ordering by keyword score would
    # make an old internship look like the current role. The master file is
    # authored newest-first, so master order IS chronological order; whatever
    # the ranker or the model returns, we restore it here.
    order = {e["id"]: i for i, e in enumerate(master.get("experience", []))}
    experience = []
    for eid in sorted(set(picked.get("experience_ids", [])),
                      key=lambda i: order.get(i, len(order))):
        src = by_id.get(eid)
        if not src:
            continue
        entry = dict(src)
        entry["bullets"] = [rewrites.get((eid, i), b)
                            for i, b in enumerate(src.get("bullets", []) or [])]
        experience.append(entry)

    projects_by = {str(p.get("id", p.get("name", ""))): p
                   for p in master.get("projects", [])}
    projects = [projects_by[i] for i in picked.get("project_ids", [])
                if i in projects_by]

    data = {
        "name": master["name"],
        "headline": master.get("headline", ""),
        "summary": picked.get("summary") or master.get("summary", ""),
        "contact": master.get("contact", {}),
        "skills": picked.get("skill_order", []),
        "experience": experience,
        "projects": projects[:max_projects()] or featured_projects(master),
        "education": master.get("education", []),
        "certifications": master.get("certifications", []),
        "leadership": master.get("leadership", []),
    }
    return TailorResult(data=data, dropped=dropped, novel=sorted(set(novel)),
                        tailored=tailored, keyword_coverage=cov)


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------
def render_pdf(data: dict, path: str, *, accent_rule: bool = True) -> str:
    doc = PDF(margin=50, font="Helvetica", size_pt=9.6, leading=1.3)
    contact = data.get("contact", {}) or {}
    bits = [contact.get(k, "") for k in ("location", "email", "phone")]
    subtitle = "  |  ".join([b for b in bits if b])
    doc.title(data.get("name", ""), data.get("headline", ""))
    if subtitle:
        doc.text(subtitle, size=9, gray=0.3)
    links = [v for k, v in contact.items()
             if k in ("linkedin", "github", "website") and v]
    if links:
        doc.text("  |  ".join(links), size=9, gray=0.25)
    doc.space(2)
    if accent_rule:
        doc.hrule(gray=0.55, thickness=1.0)

    if data.get("summary"):
        doc.heading("Summary", rule=False, space_before=8, space_after=1)
        doc.text(data["summary"], size=9.6)

    if data.get("skills"):
        doc.heading("Skills", rule=False, space_before=8, space_after=1)
        doc.text(", ".join(data["skills"]), size=9.6)

    if data.get("experience"):
        doc.heading("Experience", space_before=10)
        for e in data["experience"]:
            when = " - ".join(x for x in (e.get("start", ""), e.get("end", "")) if x)
            doc.row(f"{e.get('title','')}, {e.get('company','')}", when,
                    bold_left=True, size=10)
            if e.get("location"):
                doc.text(e["location"], size=8.6, gray=0.4)
            for b in e.get("bullets", []) or []:
                doc.bullet(b, size=9.4)
            if e.get("tech"):
                doc.text("Tech: " + ", ".join(e["tech"]), size=8.8, gray=0.35,
                         indent=10)
            doc.space(4)

    if data.get("projects"):
        doc.heading("Projects", space_before=8)
        for p in data["projects"]:
            doc.row(str(p.get("name", "")), str(p.get("when", "")), bold_left=True,
                    size=10)
            if p.get("description"):
                doc.text(str(p["description"]), size=9.4, indent=10)
            for b in p.get("bullets", []) or []:
                doc.bullet(b, size=9.4)
            if p.get("link"):
                doc.text(str(p["link"]), size=8.8, gray=0.3, indent=10)
            if p.get("tech"):
                doc.text("Tech: " + ", ".join(p["tech"]), size=8.8, gray=0.35,
                         indent=10)
            doc.space(3)

    if data.get("education"):
        doc.heading("Education", space_before=8)
        for ed in data["education"]:
            doc.row(f"{ed.get('degree','')}, {ed.get('institution','')}",
                    str(ed.get("year", "")), bold_left=True, size=10)
            if ed.get("detail"):
                doc.text(str(ed["detail"]), size=9, gray=0.35, indent=10)

    if data.get("certifications"):
        doc.heading("Certifications", space_before=8)
        for c in data["certifications"]:
            doc.bullet(str(c), size=9.4)

    if data.get("leadership"):
        doc.heading("Leadership", space_before=8)
        for item in data["leadership"]:
            doc.bullet(str(item), size=9.4)

    return doc.save(path)
