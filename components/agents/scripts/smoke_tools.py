"""Verify real local model tool calling against the operator's local rate card."""
from pathlib import Path
import json
import os
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
tempfile.tempdir = str(ROOT / "tmp" / "tests")
from scripts.run_tests import local_only
from tests.base import SuiteCase


def main():
    case = SuiteCase()
    case.setUp()
    os.environ.update({"LLM_PROVIDER": "ollama", "LLM_MODEL": "storylens-meaning:14b",
        "OLLAMA_BASE_URL": "http://127.0.0.1:11434", "OLLAMA_THINK": "false",
        "OLLAMA_NUM_GPU": "99", "OLLAMA_NUM_CTX": "8192", "LLM_FALLBACK_OFFLINE": "false"})
    sys.addaudithook(local_only)
    try:
        import core.toolbelt
        from core.llm import LLM
        answer, calls = LLM("ollama", store=case.store).with_tools(
            "Call rate_card with kind=video and currency=inr. Then tell me the asking price "
            "and minimum for the short-form tier. You must read the tool result before answering.",
            ["rate_card"], temperature=0, max_tokens=350, max_calls=1)
        used = bool(calls.calls)
        passed = used and "10000" in answer.replace(",", "")
        report = {"model": os.environ["LLM_MODEL"], "passed": passed, "answer": answer,
                  "tool_calls": calls.to_json(), "external_networking": "blocked"}
        (ROOT / "data" / "local-tools-validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Tool calls: {len(calls.calls)}; effective project floor reproduced: {passed}")
        return 0 if passed else 1
    finally:
        case.tearDown()


if __name__ == "__main__":
    raise SystemExit(main())
