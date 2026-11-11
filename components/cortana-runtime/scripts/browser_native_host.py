"""Chromium native messaging entrypoint; no shell, no generic command execution."""
import json
import os
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'agent'), str(ROOT)]


def main():
    # Chromium's length-prefixed protocol must never pass through Windows
    # newline translation (the four-byte length may itself contain 0x0A).
    if os.name == 'nt':
        import msvcrt
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    manifest = json.loads((ROOT / 'browser-extension' / 'native-host.json').read_text(encoding='utf-8'))
    if len(sys.argv) < 2 or sys.argv[1] not in manifest['allowed_origins']:
        return 2
    from core.browser_bridge import exchange
    while True:
        size = sys.stdin.buffer.read(4)
        if not size:
            return 0
        if len(size) != 4:
            return 2
        length = struct.unpack('<I', size)[0]
        if not 0 < length <= 256000:
            return 2
        raw = sys.stdin.buffer.read(length)
        if len(raw) != length:
            return 2
        try:
            response = exchange(json.loads(raw))
        except Exception:
            response = {'commands': [], 'error': 'Native bridge rejected the request.'}
        output = json.dumps(response).encode('utf-8')
        sys.stdout.buffer.write(struct.pack('<I', len(output)) + output)
        sys.stdout.buffer.flush()


if __name__ == '__main__':
    raise SystemExit(main())
