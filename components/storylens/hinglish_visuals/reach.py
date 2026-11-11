"""Public, read-only Agent Reach web channel; no account/session import or installer side effects."""
import importlib
from pathlib import Path
import sys


def channel(root):
    runtime = Path(root) / 'tools' / 'agent-reach-runtime'
    if runtime.is_dir() and str(runtime) not in sys.path:
        sys.path.insert(0, str(runtime))
    return importlib.import_module('agent_reach.channels.web').WebChannel()


def search(root, query, limit=5):
    return channel(root)._exa_search(query=query, limit=limit, timeout=25)


def read(root, url):
    return channel(root).read(url, timeout=25)[:40000]
