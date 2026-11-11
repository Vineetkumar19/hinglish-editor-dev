"""Start the authenticated Storylens console, with no inbox or scheduler."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be in the range 1–65535")
    if not os.environ.get("DASHBOARD_TOKEN", "").strip():
        parser.error("DASHBOARD_TOKEN must be supplied by the Storylens launcher")

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    os.environ.update({
        "SUITE_STORYLENS_INTEGRATED": "true",
        "LLM_PROVIDER": "chatgpt",
        "LLM_FALLBACK_OFFLINE": "false",
        "SUITE_CHATGPT_MODEL": "gpt-6.1-sol",
        "SUITE_CHATGPT_REASONING_EFFORT": "medium",
        "NOTIFY_CHANNELS": "store",
        "SEARCH_PROVIDER": "chatgpt_web",
        "SAAS_ENABLED": "false",
    })
    from server.app import serve

    with serve(host="127.0.0.1", port=args.port) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
