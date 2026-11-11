"""Bounded timing evidence without audio, prompt text, or credentials."""
import json
import threading
import time
from collections import deque
from core.config import ROOT_DIR

_events = deque(maxlen=100)
_lock = threading.Lock()


def record(stage, **measurements):
    with _lock:
        _events.append({'at':time.time(), 'stage':stage, **measurements})
        try:
            target = ROOT_DIR/'tmp/voice-latency.json'
            target.parent.mkdir(exist_ok=True)
            temporary = target.with_suffix('.tmp')
            temporary.write_text(json.dumps(list(_events), indent=2), encoding='utf-8')
            temporary.replace(target)
        except OSError:
            pass  # Measurement failure must never block the owner's command.
