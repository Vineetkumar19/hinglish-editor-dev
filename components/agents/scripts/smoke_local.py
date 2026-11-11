"""Run real local inference through all five workflows against isolated fixtures.

No real recipients, external websites, production database or credentials.
"""
from pathlib import Path
import importlib
import argparse
import json
import os
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
tempfile.tempdir = str(ROOT / "tmp" / "tests")
from scripts.run_tests import local_only
from tests.base import SuiteCase
from tests.fakes.servers import FakeWebServer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", action="append", choices=("community", "sponsorship", "video_client", "fullstack_sales", "job_hunter"))
    parser.add_argument("--model", default="storylens-meaning:14b")
    args = parser.parse_args()
    case = SuiteCase()
    case.setUp()
    os.environ.update({"LLM_PROVIDER": "ollama", "LLM_MODEL": args.model,
        "OLLAMA_BASE_URL": "http://127.0.0.1:11434", "OLLAMA_NUM_CTX": "8192",
        "OLLAMA_NUM_GPU": "99", "OLLAMA_THINK": "false", "OLLAMA_NUM_BATCH": "256",
        "LLM_FALLBACK_OFFLINE": "false", "TOOL_USE_ENABLED": "false",
        "SPONSORSHIP_MAX_LEADS": "1", "VIDEO_CLIENT_MAX_LEADS": "1",
        "FULLSTACK_MAX_LEADS": "1", "JOB_MAX_PER_RUN": "1", "JOB_AUTO_APPLICATIONS": "false"})
    sys.addaudithook(local_only)
    web = FakeWebServer().start()
    report = {"model": os.environ["LLM_MODEL"], "external_networking": "blocked except loopback",
              "dry_run": True, "workflows": []}
    try:
        from core.llm import LLM
        for name in (args.agent or ("community", "sponsorship", "video_client", "fullstack_sales", "job_hunter")):
            print("Checking", name, flush=True)
            start = time.monotonic()
            llm = LLM("ollama", store=case.store)
            module = importlib.import_module(f"agents.{name}.agent")
            agent = module.make(store=case.store, llm=llm)
            tid = "local-smoke-" + name
            initial = {"_thread_id": tid}
            if name == "community":
                initial["contexts"] = [{"title": "Cricket analysis", "url": "https://example.com/discussion",
                    "description": "How should I judge a batter's risk when chasing 180?",
                    "platform": "forum", "promotion_allowed": False}]
            if name == "job_hunter":
                job = json.loads((ROOT / "tests" / "fixtures" / "jobs.json").read_text())[0]
                job.update({"salary_min": 600000, "salary_max": 1200000,
                            "url": "https://careers.zerodha.com/backend-engineer",
                            "apply_url": "https://careers.zerodha.com/backend-engineer/apply",
                            "contact_email": ""})
                initial["queue"] = [job]
            approvals = []
            def decide(row):
                approvals.append({"kind": row["kind"], "title": row["title"], "payload": row["payload"]})
                return "approve"
            result = case.drive(agent.build(), tid, decide, initial=initial)
            record = {"agent": name, "status": result.status, "error": result.error,
                "seconds": round(time.monotonic()-start, 2), "approvals": len(approvals),
                "model_calls": llm.usage.calls, "stats": result.state.get("summary") or result.state.get("stats"),
                "drafts": approvals}
            record["rejected"] = result.state.get("rejected", [])
            record["passed"] = result.complete and not result.error and bool(approvals) and llm.usage.calls > 0
            report["workflows"].append(record)
            print(name, result.status, f"calls={llm.usage.calls}", f"approvals={len(approvals)}", flush=True)
        report["all_passed"] = all(r["passed"] for r in report["workflows"])
    finally:
        web.stop()
        path = ROOT / "data" / "local-model-validation.json"
        path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        case.tearDown()
    print("Report:", path, flush=True)
    return 0 if report.get("all_passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
