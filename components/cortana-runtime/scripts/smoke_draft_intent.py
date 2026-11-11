"""Exercise local model draft extraction without opening accounts or sending."""
import asyncio
import json
import re
import sys
import time
import unicodedata
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "agent"), str(ROOT)]
from core import tasks
from core.tools_loader import load_all_tools
from routers import chat

CASES = [
    ("Draft a WhatsApp message to Alex. The exact message is: I will arrive at 7.",
     "whatsapp", "Alex", "I will arrive at 7."),
    ("Instagram par @alex_demo ko ye exact message likho: Kal milte hain at 7.",
     "instagram", "@alex_demo", "Kal milte hain at 7."),
    ("Gmail में alex@example.com को ईमेल लिखो। Subject: Meeting. "
     "संदेश का सही पाठ: कल शाम सात बजे मिलते हैं।",
     "gmail", "alex@example.com", "कल शाम सात बजे मिलते हैं।"),
]


async def main():
    load_all_tools()
    results = []
    for message, platform, recipient, body in CASES:
        calls = []

        def draft_only(name, args, **_kwargs):
            if name != "prepare_message_draft":
                raise AssertionError(f"Unexpected tool: {name}")
            calls.append(args)
            return {
                "draft_id": "local-model-fixture",
                "platform": args.get("platform"), "status": "draft_ready",
                "recipient": args.get("recipient"),
                "preview": {"body": args.get("body"), "subject": args.get("subject", "")},
                "note": "Controlled test only. No account was opened or message typed.",
            }

        request_id = str(uuid4())
        token = tasks.begin(request_id, communication_allowed=True)
        started = time.monotonic()
        try:
            with patch.object(chat, "dispatch", draft_only), \
                    patch.object(chat.db, "get_recent_messages", return_value=[]), \
                    patch.object(chat.db, "all_facts", return_value=[]):
                response = await chat._perform(chat.ChatRequest(message=message, request_id=request_id))
        finally:
            tasks.finish(request_id, token)
        if len(calls) != 1:
            raise AssertionError(f"Expected one draft tool call, got {calls!r}: {response.reply}")
        actual = calls[0]
        assert actual.get("platform") == platform, actual
        assert actual.get("recipient", "").lstrip("@") == recipient.lstrip("@"), actual
        if platform == "gmail":
            assert actual.get("subject") == "Meeting", actual
            outgoing = actual.get("body", "")
            assert outgoing and all(not c.isalpha() or "LATIN" in unicodedata.name(c, "")
                                    for c in outgoing), actual
            assert re.search(r"\b(?:meet|meeting)\b", outgoing, re.I), actual
            assert "tomorrow" in outgoing.lower(), actual
            assert re.search(r"\b(?:evening|p\.?m\.?)\b", outgoing, re.I), actual
            assert re.search(r"\b(?:7|seven)\b", outgoing, re.I), actual
        else:
            assert actual.get("body") == body, actual
        assert response.pending_draft and response.pending_confirmation is None
        results.append({"platform": platform,
                        "outgoing_body": actual["body"],
                        "language_policy": "English translation" if platform == "gmail" else "English or Roman Hinglish, exact text",
                        "seconds": round(time.monotonic() - started, 2)})
    report = {"status": "passed", "accounts_accessed": False, "messages_sent": False, "results": results}
    destination = ROOT / "tmp" / "draft-intent-smoke.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
