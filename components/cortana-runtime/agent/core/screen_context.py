"""Short-lived screenshots in RAM. No screen history or automatic cloud upload."""
import base64
import io
import secrets
import threading
import time
from dataclasses import dataclass

from PIL import Image

MAX_AGE_SECONDS = 300
_lock = threading.Lock()


@dataclass
class Capture:
    png: bytes
    width: int
    height: int
    created: float


_captures: dict[str, Capture] = {}


def _expire():
    now = time.monotonic()
    for key, item in list(_captures.items()):
        if now - item.created > MAX_AGE_SECONDS:
            _captures.pop(key, None)


def capture() -> dict:
    import mss
    import mss.tools
    with mss.mss() as sct:
        # Active monitor can be selected in a later milestone. Capture the
        # primary screen now; all-monitor panoramas make small text unreadable.
        shot = sct.grab(sct.monitors[1])
        png = mss.tools.to_png(shot.rgb, shot.size)
    item = Capture(png, shot.width, shot.height, time.monotonic())
    key = secrets.token_urlsafe(24)
    with _lock:
        _expire()
        while len(_captures) >= 3:
            _captures.pop(next(iter(_captures)))
        _captures[key] = item
    expiry = threading.Timer(MAX_AGE_SECONDS, discard, args=(key,))
    expiry.daemon = True
    expiry.start()
    return {
        "screenshot_id": key, "width": item.width, "height": item.height,
        "expires_in_seconds": MAX_AGE_SECONDS, "storage": "memory", "monitor": "primary",
    }


def consume(key: str) -> Capture:
    with _lock:
        _expire()
        item = _captures.pop(key, None)
    if item is None:
        raise ValueError("Screen capture expired or was already used. Capture the screen again.")
    return item


def discard(key: str):
    with _lock:
        _captures.pop(key, None)


def encode(item: Capture) -> str:
    with Image.open(io.BytesIO(item.png)) as im:
        # Preserve enough pixels for code and UI text; bound request size.
        im.thumbnail((1920, 1440), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        im.save(out, format="PNG")
    return base64.b64encode(out.getvalue()).decode("ascii")
