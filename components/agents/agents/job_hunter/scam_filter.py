"""Two-stage fraud screening for job postings.

Stage 1 is a heuristic pre-screen over indicators that are close to conclusive:
a request for money, a recruiter using a free email domain, interviews conducted
entirely on WhatsApp or Telegram, a salary wildly out of line with the role. It
is deliberately tuned for near-zero false positives on genuine listings, because
the cost of wrongly binning a real job is high and the cost of a second look is
low.

Stage 2 hands anything that survives to an LLM for consistency analysis - ten
years of experience demanded at intern pay, a company name that does not match
the recruiter's domain, a description too generic to describe any actual job.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from core.llm import LLM, offline_handler
from core.log import get_logger

log = get_logger("scam_filter")

FREE_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "yahoo.co.in", "hotmail.com", "outlook.com",
    "rediffmail.com", "protonmail.com", "aol.com", "mail.com", "gmx.com",
    "yandex.com", "icloud.com", "zoho.com",
}

# (weight, label, pattern). Weight >= 1.0 alone is enough to reject.
RULES: list[tuple[float, str, str]] = [
    (1.0, "asks for money",
     r"\b(registration|processing|security|training|placement|application)\s+"
     r"(fee|charge|deposit|amount)\b|\bpay\s+(a\s+)?(fee|deposit|rs\.?\s*\d)"),
    (1.0, "asks for bank or card details upfront",
     r"\b(bank account (details|number)|card number|cvv|upi pin|otp)\b"),
    (1.0, "cheque or package reshipping scam",
     r"\b(cash(ing)? (a )?che(que|ck)|reship|receive and forward packages|"
     r"money (mule|transfer agent))\b"),
    (0.8, "interviews conducted only on WhatsApp or Telegram",
     r"\b(interview|hiring process|onboarding|selection).{0,40}"
     r"(whatsapp|telegram|signal)\b|"
     r"\b(whatsapp|telegram)\s*(chat|us|me|number).{0,30}\b(interview|apply)\b"),
    (0.7, "asks for identity documents before any interview",
     r"\b(send|share|submit).{0,30}(aadhaar|aadhar|pan card|passport|"
     r"ssn|social security)\b"),
    (0.6, "unrealistic earnings claim",
     r"\b(earn|income|salary).{0,25}(per day|daily|a day)\b|"
     r"\b(guaranteed|assured)\s+(job|placement|income|earning)\b|"
     r"\bwork from home.{0,20}(no experience|anyone can)\b"),
    (0.5, "pressure tactics",
     r"\b(limited (seats|vacancies|positions)|immediate joining bonus|"
     r"apply within 24 hours|only \d+ (seats|slots) left)\b"),
    (0.4, "no company identified",
     r"\b(reputed|leading|mnc) (company|client|organisation|organization)\b"
     r"(?!.{0,60}\b[A-Z][a-z]+\b)"),
    (0.3, "personal contact instead of a careers process",
     r"\b(contact|call|whatsapp)\s*(me|us)?\s*(on|at)?\s*"
     r"(\+?91[\s-]?)?[6-9]\d{9}\b"),
]

CLEAN_SIGNALS = [
    (r"\b(equal opportunity|eoe|we are an equal)\b", 0.15),
    (r"\b(benefits|health insurance|provident fund|pf|gratuity|esop)\b", 0.10),
    (r"\b(hybrid|on-?site|remote)\b.{0,40}\b(bengaluru|bangalore|mumbai|pune|"
     r"hyderabad|delhi|noida|gurgaon|chennai)\b", 0.08),
    (r"\bapply (through|via) (our )?(careers|website|portal)\b", 0.08),
]


@dataclass
class ScreenResult:
    verdict: str = "pass"           # pass | suspicious | reject
    score: float = 0.0              # 0 clean .. 1 certainly fraudulent
    flags: list = field(default_factory=list)
    stage: str = "heuristic"
    reason: str = ""

    @property
    def rejected(self) -> bool:
        return self.verdict == "reject"


def heuristic_screen(job) -> ScreenResult:
    text = f"{job.title}\n{job.company}\n{job.description}"
    low = text.lower()
    score, flags = 0.0, []

    for weight, label, pattern in RULES:
        if re.search(pattern, low, re.I | re.S):
            score += weight
            flags.append(label)

    # A recruiter on a free email domain for a named company is a classic tell.
    email = (job.contact_email or "").lower()
    if email:
        domain = email.split("@")[-1]
        if domain in FREE_EMAIL_DOMAINS and job.company:
            score += 0.6
            flags.append(f"recruiter uses a free email domain ({domain})")
        elif job.company and domain:
            slug = re.sub(r"[^a-z0-9]", "", job.company.lower())
            dslug = re.sub(r"[^a-z0-9]", "", domain.split(".")[0])
            if slug and dslug and slug[:6] not in dslug and dslug[:6] not in slug:
                score += 0.25
                flags.append(f"recruiter domain {domain} does not match "
                             f"the stated company")

    if len(job.description.split()) < 35:
        score += 0.3
        flags.append("description too short to describe a real role")

    for pattern, credit in CLEAN_SIGNALS:
        if re.search(pattern, low, re.I):
            score = max(0.0, score - credit)

    score = min(1.0, score)
    if score >= 1.0:
        verdict = "reject"
    elif score >= 0.5:
        verdict = "suspicious"
    else:
        verdict = "pass"
    return ScreenResult(verdict=verdict, score=round(score, 2), flags=flags,
                        stage="heuristic",
                        reason="; ".join(flags) if flags else "no fraud indicators")


CONSISTENCY_SCHEMA = {
    "type": "object",
    "required": ["verdict", "confidence"],
    "properties": {
        "verdict": {"type": "string", "enum": ["genuine", "suspicious", "fraudulent"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.5},
        "inconsistencies": {"type": "array", "items": {"type": "string"},
                            "max_items": 6, "default": []},
        "reason": {"type": "string", "max_length": 400, "default": ""},
    },
}

SENIORITY_YEARS = [
    (r"\b(10|1[0-9]|2[0-9])\+?\s*(years|yrs)\b", 10),
    (r"\b([5-9])\+?\s*(years|yrs)\b", 5),
    (r"\b([1-4])\+?\s*(years|yrs)\b", 1),
]
JUNIOR_TITLES = r"\b(intern|internship|trainee|fresher|junior|entry.?level|graduate)\b"


@offline_handler("job_consistency")
def _offline_consistency(ctx: dict) -> dict:
    """Deterministic consistency checks - the same logic an LLM is asked for."""
    job = ctx.get("job")
    title = (getattr(job, "title", "") or "").lower()
    desc = (getattr(job, "description", "") or "").lower()
    blob = title + "\n" + desc
    issues = []

    years = 0
    for pattern, value in SENIORITY_YEARS:
        if re.search(pattern, blob):
            years = max(years, value)
    junior = bool(re.search(JUNIOR_TITLES, title))
    if junior and years >= 5:
        issues.append(f"advertised as entry level but demands {years}+ years")

    smin = getattr(job, "salary_min", 0) or 0
    cur = (getattr(job, "salary_currency", "") or "").upper()
    if smin:
        # crude annualised floor checks, per currency
        floor = {"INR": 300000, "USD": 30000}.get(cur, 0)
        if floor and years >= 8 and smin < floor:
            issues.append(f"senior requirements at {cur} {smin:,.0f}, far below "
                          f"market for the experience demanded")
        ceiling = {"INR": 10_000_000, "USD": 400_000}.get(cur, 0)
        if ceiling and junior and smin > ceiling * 0.4:
            issues.append("entry-level role offering an implausibly high salary")

    # Lexical density check. A real posting names technologies, teams and
    # responsibilities; a fake one recycles the same dozen filler words. The
    # threshold is set low on purpose: wrongly binning a genuine role costs the
    # candidate an opportunity, while a borderline one only costs a second look.
    vocabulary = set(re.findall(r"[a-z]{4,}", desc))
    if desc and len(vocabulary) < 20:
        issues.append("description is generic - no specific technology, team or "
                      "product named")

    if issues:
        verdict = "fraudulent" if len(issues) >= 2 else "suspicious"
        return {"verdict": verdict, "confidence": 0.7,
                "inconsistencies": issues, "reason": "; ".join(issues)}
    return {"verdict": "genuine", "confidence": 0.6, "inconsistencies": [],
            "reason": "requirements, seniority and compensation are consistent"}


def semantic_screen(llm: LLM, job) -> ScreenResult:
    prompt = (
        "Assess this job posting for internal consistency and signs of fraud.\n"
        "Look for: experience demanded versus seniority and pay; a company name "
        "that does not match the recruiter's domain; a description too generic to "
        "describe a real role; anything asking the applicant for money or "
        "documents.\n\n"
        f"Title: {job.title}\nCompany: {job.company}\nLocation: {job.location}\n"
        f"Salary: {job.salary_currency} {job.salary_min:,.0f}-{job.salary_max:,.0f}\n"
        f"Contact: {job.contact_email}\n\n---\n{job.description[:6000]}\n---")
    try:
        out = llm.structured(prompt, CONSISTENCY_SCHEMA, task="job_consistency",
                             context={"job": job},
                             system="You screen job postings for fraud. Be "
                                    "specific about what is inconsistent.",
                             temperature=0.0)
    except Exception as exc:  # noqa: BLE001
        if getattr(llm, "provider_name", None) == "chatgpt":
            raise
        log.warn(f"semantic screen failed, treating as pass: {exc}")
        return ScreenResult("pass", 0.0, [], "semantic", f"screen unavailable: {exc}")
    mapping = {"genuine": "pass", "suspicious": "suspicious", "fraudulent": "reject"}
    return ScreenResult(verdict=mapping.get(out["verdict"], "suspicious"),
                        score=round(out.get("confidence", 0.5)
                                    if out["verdict"] != "genuine" else 0.0, 2),
                        flags=out.get("inconsistencies", []),
                        stage="semantic", reason=out.get("reason", ""))


def screen(llm: LLM, job) -> ScreenResult:
    """Full two-stage screen. A heuristic rejection short-circuits."""
    first = heuristic_screen(job)
    if first.verdict == "reject":
        log.info("job rejected by heuristics", company=job.company,
                 title=job.title[:50], reason=first.reason[:120])
        return first
    second = semantic_screen(llm, job)
    if second.verdict == "reject":
        return second
    if first.verdict == "suspicious" or second.verdict == "suspicious":
        combined = ScreenResult(
            "suspicious", max(first.score, second.score),
            first.flags + second.flags, "combined",
            "; ".join(x for x in (first.reason, second.reason) if x))
        # Two independent suspicions is a rejection.
        if first.verdict == "suspicious" and second.verdict == "suspicious":
            combined.verdict = "reject"
        return combined
    return ScreenResult("pass", 0.0, [], "combined", "passed both screens")
