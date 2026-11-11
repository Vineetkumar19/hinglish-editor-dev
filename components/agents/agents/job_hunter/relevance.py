"""Is this job actually worth looking at?

The fraud filter answers "is this posting real". This answers a different and
equally important question: "is this posting *for me*". Without it a search for
"engineer" on any public board returns Inside Sales Contractor, Tier III
Service Desk Engineer and Freelance Writer, because board search endpoints
match loosely and rank by recency, not by fit.

Three independent gates, each of which can reject on its own:

  1. ROLE     - does the title belong to one of the role families you want
  2. SENIORITY- does the title demand more seniority than you have
  3. EXPERIENCE - does the description demand more years than you have

and two extractors that pull out what you actually want to read before
deciding: the skills it asks for, and the years it asks for.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from core import config

# ---------------------------------------------------------------------------
# role families
# ---------------------------------------------------------------------------
# Each family is (name, strong terms, supporting terms). A title matches when
# it contains a strong term, or two supporting terms. Keep these in title
# vocabulary - this is matched against the job TITLE, not the description.
ROLE_FAMILIES: dict[str, dict] = {
    "software": {
        "strong": ["software engineer", "software developer", "sde",
                   "backend engineer", "back end engineer", "backend developer",
                   "frontend engineer", "front end engineer", "frontend developer",
                   "full stack", "fullstack", "full-stack", "web developer",
                   "application developer", "platform engineer", "api engineer",
                   "product engineer", "systems engineer", "member of technical staff"],
        "support": ["engineer", "developer", "programmer", "software", "swe"],
    },
    "java": {
        "strong": ["java developer", "java engineer", "spring boot",
                   "java full stack", "j2ee"],
        "support": ["java", "spring", "developer", "engineer"],
    },
    "python": {
        "strong": ["python engineer", "python developer", "django developer",
                   "fastapi"],
        "support": ["python", "django", "flask", "engineer", "developer"],
    },
    "ai_ml": {
        "strong": ["machine learning engineer", "ml engineer", "ai engineer",
                   "applied scientist", "research engineer", "deep learning",
                   "nlp engineer", "computer vision engineer", "mlops"],
        "support": ["machine learning", "artificial intelligence", "ai", "ml",
                    "llm", "genai", "engineer"],
    },
    "agentic_ai": {
        "strong": ["ai agent", "agentic", "agent engineer", "llm engineer",
                   "generative ai engineer", "genai engineer", "ai automation",
                   "prompt engineer", "ai application engineer",
                   "ai software engineer", "ai developer"],
        "support": ["agent", "llm", "genai", "generative", "automation", "ai"],
    },
    "forward_deployed": {
        "strong": ["forward deployed", "forward-deployed", "fde",
                   "solutions engineer", "solution engineer",
                   "implementation engineer", "deployment engineer",
                   "field engineer", "customer engineer", "delivery engineer"],
        "support": ["solutions", "deployment", "implementation", "engineer"],
    },
    "data_engineering": {
        "strong": ["data engineer", "analytics engineer", "etl developer",
                   "big data engineer", "data platform", "data infrastructure",
                   "pipeline engineer"],
        "support": ["data", "etl", "pipeline", "spark", "warehouse", "engineer"],
    },
    "data_analysis": {
        "strong": ["data analyst", "business analyst", "analytics analyst",
                   "bi analyst", "business intelligence", "reporting analyst",
                   "data scientist"],
        "support": ["analyst", "analytics", "data", "sql", "bi"],
    },
    "devops": {
        "strong": ["devops engineer", "site reliability", "sre",
                   "cloud engineer", "infrastructure engineer",
                   "platform reliability"],
        "support": ["devops", "kubernetes", "cloud", "infrastructure", "engineer"],
    },
}

DEFAULT_FAMILIES = list(ROLE_FAMILIES)

# Titles that are emphatically not software work, however the board tagged
# them. Checked first, because "Sales Engineer" contains "engineer".
HARD_EXCLUDE = [
    "sales", "account executive", "account manager", "business development",
    "recruiter", "recruiting", "talent acquisition", "human resources",
    "hr ", "marketing", "seo", "copywriter", "content writer", "freelance writer",
    "social media", "customer support", "customer service", "support specialist",
    "service desk", "help desk", "helpdesk", "desktop support", "technician",
    "teacher", "tutor", "instructor", "nurse", "driver", "warehouse",
    "accountant", "bookkeeper", "paralegal", "insurance", "real estate agent",
    "data entry", "virtual assistant", "telecaller", "bpo", "call center",
    "call centre", "field sales", "territory", "graphic designer",
    "video editor", "photographer", "translator", "transcription",
    # Ad-operations and campaign roles carry "analyst" and get picked up by the
    # data_analysis family. A live run surfaced "Account Specialist (Bing Ads
    # Analyst)" as a match for a backend engineer.
    "account specialist", "ads analyst", "ad operations", "adops",
    "campaign", "media buyer", "merchandiser", "category manager",
    "procurement", "supply chain", "logistics executive", "operations executive",
]

# Seniority the title implies. A fresher applying to "Staff Engineer" is noise
# for them and noise for you.
SENIORITY = [
    (["intern", "internship", "trainee", "apprentice"], 0),
    (["graduate", "new grad", "fresher", "entry level", "entry-level",
      "junior", "associate", "jr "], 0),
    (["senior", "sr ", "sr."], 4),
    (["staff", "lead ", "tech lead", "team lead"], 6),
    (["principal", "architect", "head of", "manager", "director",
      "vp ", "vice president", "chief"], 8),
]

# ---------------------------------------------------------------------------
# skills
# ---------------------------------------------------------------------------
SKILL_VOCAB = [
    # languages
    "Java", "Python", "JavaScript", "TypeScript", "Go", "Golang", "Rust", "C++",
    "C#", "Ruby", "PHP", "Scala", "Kotlin", "Swift", "SQL", "R",
    # backend / frameworks
    "Spring Boot", "Spring", "Hibernate", "JPA", "Django", "Flask", "FastAPI",
    "Node.js", "Express", "NestJS", ".NET", "Rails", "GraphQL", "REST API",
    "gRPC", "Microservices", "Kafka", "RabbitMQ", "Celery",
    # frontend
    "React", "Next.js", "Angular", "Vue", "Svelte", "Tailwind", "Redux",
    "HTML", "CSS", "Bootstrap",
    # data
    "PostgreSQL", "MySQL", "MongoDB", "Redis", "Cassandra", "DynamoDB",
    "Elasticsearch", "Snowflake", "BigQuery", "Redshift", "Databricks",
    "Spark", "Hadoop", "Airflow", "dbt", "ETL", "Data Warehouse", "Kinesis",
    "Power BI", "Tableau", "Looker", "Excel", "Pandas", "NumPy",
    # ai
    "Machine Learning", "Deep Learning", "PyTorch", "TensorFlow", "scikit-learn",
    "LLM", "RAG", "LangChain", "LangGraph", "Hugging Face", "Transformers",
    "NLP", "Computer Vision", "OpenAI", "Prompt Engineering", "Vector Database",
    "Pinecone", "Embeddings", "Fine-tuning", "MLOps", "MLflow",
    # infra
    "AWS", "Azure", "GCP", "Docker", "Kubernetes", "Terraform", "Jenkins",
    "CI/CD", "GitHub Actions", "Linux", "Git", "Nginx", "Serverless", "Lambda",
    # practice
    "Agile", "Scrum", "TDD", "Unit Testing", "System Design", "Data Structures",
    "Algorithms", "OOP", "Design Patterns",
]

_SKILL_PATTERNS = [
    (s, re.compile(r"(?<![A-Za-z0-9])" + re.escape(s).replace(r"\ ", r"[\s\-]")
                   + r"(?![A-Za-z0-9])", re.I))
    for s in SKILL_VOCAB
]

# ---------------------------------------------------------------------------
# experience
# ---------------------------------------------------------------------------
_YEAR_WORD = r"(?:years?|yrs?)"
_EXP_PATTERNS = [
    # "3-5 years", "3 to 5 years"  -> lower bound
    re.compile(r"(\d{1,2})\s*(?:-|–|—|to)\s*\d{1,2}\+?\s*" + _YEAR_WORD, re.I),
    # "minimum 3 years", "at least 3 years", "3+ years", "3 years of"
    re.compile(r"(?:minimum|at least|min\.?|over)\s*(?:of\s*)?(\d{1,2})\+?\s*"
               + _YEAR_WORD, re.I),
    re.compile(r"(\d{1,2})\s*\+\s*" + _YEAR_WORD, re.I),
    re.compile(r"(\d{1,2})\s*" + _YEAR_WORD + r"(?:\s*(?:of|in|with|\+))", re.I),
]

FRESHER_SIGNALS = [
    "fresher", "freshers", "new grad", "new graduate", "recent graduate",
    "entry level", "entry-level", "no prior experience", "no experience required",
    "0-1 year", "0-2 year", "campus hire", "graduate program", "graduate trainee",
    "early career", "0 to 1 year", "internship",
]


@dataclass
class Match:
    relevant: bool = False
    family: str = ""
    score: float = 0.0
    reason: str = ""
    skills: list[str] = field(default_factory=list)
    min_years: int | None = None
    seniority: int = 0
    fresher_friendly: bool = False

    def to_json(self) -> dict:
        return {"relevant": self.relevant, "family": self.family,
                "score": round(self.score, 3), "reason": self.reason,
                "skills": self.skills, "min_years": self.min_years,
                "seniority": self.seniority,
                "fresher_friendly": self.fresher_friendly}


def wanted_families() -> list[str]:
    names = config.get_list("JOB_ROLE_FAMILIES", DEFAULT_FAMILIES)
    return [n for n in names if n in ROLE_FAMILIES] or DEFAULT_FAMILIES


def max_experience_years() -> int:
    """Your current experience. Jobs asking for more than this are dropped."""
    try:
        return max(0, int(config.get("JOB_EXPERIENCE_YEARS", "0")))
    except (TypeError, ValueError):
        return 0


def experience_slack() -> int:
    """How far above your level to still allow through.

    A posting asking for "2+ years" is worth seeing when you have 0 - plenty
    of them interview freshers who are strong. Asking for 8 is not.
    """
    try:
        return max(0, int(config.get("JOB_EXPERIENCE_SLACK", "2")))
    except (TypeError, ValueError):
        return 2


def extract_skills(text: str, limit: int = 14) -> list[str]:
    """Skills the posting actually names, in the order they are mentioned."""
    found: list[tuple[int, str]] = []
    for name, pattern in _SKILL_PATTERNS:
        m = pattern.search(text or "")
        if m:
            found.append((m.start(), name))
    found.sort()
    out: list[str] = []
    for _, name in found:
        # "Spring Boot" already implies "Spring"; do not print both
        if any(name != other and name in other for _, other in found):
            continue
        if name not in out:
            out.append(name)
    return out[:limit]


def required_years(text: str) -> int | None:
    """Lowest number of years the posting demands, or None if it never says."""
    blob = (text or "")[:6000]
    low = blob.lower()
    if any(sig in low for sig in FRESHER_SIGNALS):
        return 0
    hits = []
    for pattern in _EXP_PATTERNS:
        for m in pattern.finditer(blob):
            try:
                value = int(m.group(1))
            except (TypeError, ValueError):
                continue
            # 15+ years is almost always "15 years in business", not a demand
            if 0 <= value <= 14:
                hits.append(value)
    return min(hits) if hits else None


def title_seniority(title: str) -> int:
    t = f" {(title or '').lower()} "
    for terms, level in SENIORITY:
        if any(term in t for term in terms):
            return level
    return 1  # unmarked titles are mid-ish but open to anyone


def _family_for(title: str) -> tuple[str, float]:
    """Pick the family whose vocabulary fits the title most specifically.

    Several families can legitimately match one title - "Java Full Stack
    Developer" is both software and java, "Generative AI Engineer" is both
    ai_ml and agentic_ai. The longest matching keyword wins, because the
    longer phrase is the more specific claim: "java full stack" says more
    than "full stack", and "generative ai engineer" more than "ai engineer".
    """
    t = (title or "").lower()
    best, best_score, best_specificity = "", 0.0, 0
    for name in wanted_families():
        spec = ROLE_FAMILIES[name]
        matched = [k for k in spec["strong"] if k in t]
        support = sum(1 for k in spec["support"] if k in t)
        if matched:
            score = 1.0 + 0.1 * len(matched)
            specificity = max(len(k) for k in matched)
        elif support >= 2:
            score = 0.6 + 0.05 * support
            specificity = 0
        else:
            continue
        if (specificity, score) > (best_specificity, best_score):
            best, best_score, best_specificity = name, score, specificity
    return best, best_score


def classify(job, *, max_years: int | None = None) -> Match:
    """Decide whether this posting is worth your attention, and why."""
    title = getattr(job, "title", "") or ""
    description = getattr(job, "description", "") or ""
    low_title = f" {title.lower()} "
    ceiling = (max_experience_years() if max_years is None else max_years) \
        + experience_slack()

    skills = extract_skills(f"{title}\n{description}")
    years = required_years(description)
    seniority = title_seniority(title)
    fresher = years == 0 or any(s in description.lower() for s in FRESHER_SIGNALS)

    base = Match(skills=skills, min_years=years, seniority=seniority,
                 fresher_friendly=fresher)

    hit = next((bad for bad in HARD_EXCLUDE if bad in low_title), "")
    if hit:
        base.reason = f"not a software role - the title says {hit.strip()!r}"
        return base

    family, score = _family_for(title)
    if not family:
        base.reason = ("the title does not match any role you asked for "
                       f"({', '.join(wanted_families())})")
        return base
    base.family, base.score = family, score

    if seniority > ceiling:
        base.reason = (f"asks for about {seniority} years of seniority; you have "
                       f"{ceiling - experience_slack()}")
        return base

    if years is not None and years > ceiling:
        base.reason = (f"asks for {years}+ years; you have "
                       f"{ceiling - experience_slack()}")
        return base

    base.relevant = True
    bits = [f"matches {family.replace('_', ' ')}"]
    if years is not None:
        bits.append("open to freshers" if years == 0 else f"wants {years}+ years")
    if skills:
        bits.append(f"{len(skills)} skills you can check against")
    base.reason = "; ".join(bits)
    # freshers-welcome postings rank above ones that merely tolerate you
    base.score = score + (0.5 if years == 0 else 0.0) + min(len(skills), 10) * 0.01
    return base


def sort_key(match: Match):
    return (-match.score, match.min_years if match.min_years is not None else 99)
