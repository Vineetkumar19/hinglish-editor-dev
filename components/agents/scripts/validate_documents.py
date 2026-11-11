"""Generate clearly labeled local samples for visual document QA; never sends."""
from pathlib import Path
import json
import os
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.update({"DRY_RUN": "true", "LLM_PROVIDER": "offline", "NOTIFY_CHANNELS": "store",
                   "VIDEO_DOC_DIR": str(ROOT / "data" / "validation")})
from core import config
config._LOADED = True


def main():
    from agents.video_client import docs
    from agents.video_client.quote import build_quote
    from agents.job_hunter import resume
    from agents.job_hunter.discovery import Job
    from core.llm import LLM
    folder = ROOT / "data" / "validation"
    folder.mkdir(parents=True, exist_ok=True)
    quote = build_quote("India long-form editing")
    gig = {"company": "VALIDATION SAMPLE", "title": "Sample editing project"}
    files = {"proposal": docs.proposal(gig, quote, amount=quote.floor + 123),
             "invoice": docs.invoice(gig, quote, amount=quote.floor + 123,
                 payment_details="VALIDATION SAMPLE ONLY - payment details supplied after deal acceptance")}
    tailored = resume.tailor(resume.load_master(), Job(title="Backend Engineer",
        description="Java Spring Boot REST APIs MySQL React unit testing"), llm=LLM("offline"))
    files["resume"] = str(folder / "resume-sample.pdf")
    resume.render_pdf(tailored.data, files["resume"])
    (folder / "documents.json").write_text(json.dumps(files, indent=2), encoding="utf-8")
    print(json.dumps(files))


if __name__ == "__main__":
    main()
