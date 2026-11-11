"""Atomic local checkpoints, including transient Windows sharing locks."""
import json
import time
import uuid
from pathlib import Path


def write(path, data):
    path = Path(path)
    partial = path.with_name(path.name + '.' + uuid.uuid4().hex + '.partial')
    try:
        partial.write_text(json.dumps(data, ensure_ascii=False, indent=2), 'utf-8')
        for attempt in range(8):
            try:
                partial.replace(path)
                return
            except PermissionError:
                if attempt == 7:
                    raise
                time.sleep(min(.025 * 2 ** attempt, .4))
    finally:
        try:
            partial.unlink(missing_ok=True)
        except OSError:
            pass
