"""Measure installed Ollama models on the actual machine; never sends mail."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
import urllib.request


def call(base, path, payload):
    request = urllib.request.Request(base + path, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=240) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("models", nargs="+", help="Installed model names")
    parser.add_argument("--base", default="http://127.0.0.1:11434")
    args = parser.parse_args()
    rows = []
    schema = {"type": "object", "properties": {
        "intent": {"type": "string", "enum": ["interested", "unsubscribe", "other"]},
        "subject": {"type": "string"}, "body": {"type": "string"}},
        "required": ["intent", "subject", "body"], "additionalProperties": False}
    prompt = ("Return JSON. A creator replies: 'Interested. Please send relevant "
              "editing samples.' Classify intent and draft a reply under 90 words. "
              "The only portfolio is https://example.com/work. Do not invent rates, "
              "availability, or experience. Ask the usual length and video volume.")
    for model in args.models:
        start = time.monotonic()
        try:
            data = call(args.base, "/api/chat", {
                "model": model, "stream": False, "think": False, "keep_alive": "0",
                "format": schema, "messages": [{"role": "user", "content": prompt}],
                "options": {"num_ctx": 8192, "num_predict": 256,
                            "temperature": 0, "num_batch": 256, "num_gpu": 99}})
            content = data.get("message", {}).get("content", "")
            answer = json.loads(content)
            seconds = data.get("eval_duration", 0) / 1e9
            row = {"model": model, "wall_seconds": round(time.monotonic() - start, 2),
                   "tokens_per_second": round(data.get("eval_count", 0) / seconds, 2)
                   if seconds else 0, "valid_json": True,
                   "correct_intent": answer.get("intent") == "interested",
                   "uses_supplied_portfolio": "https://example.com/work" in answer.get("body", ""),
                   "answer": answer}
        except Exception as exc:
            row = {"model": model, "error": str(exc),
                   "wall_seconds": round(time.monotonic() - start, 2)}
        rows.append(row)
        print(json.dumps(row), flush=True)
    out = Path(__file__).resolve().parent.parent / "data" / "model-benchmark.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
