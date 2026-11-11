"""Where a pop-up card goes: never over the speaker's face.

The face is measured during the pop-up itself (Smart Zoom's local YuNet detector, Haar fallback), mapped
from the source frame onto the sequence canvas, grown to cover hair/raised hands, and the card takes the
first free spot: top centre, top corners, then lower corners (vertical); top right/left, then middle
right/left (horizontal)."""
import numpy as np

from hinglish_broll.library import read_frames


def face_box(locator, path, t0, t1, samples=3):
    """Median largest-face box (x0, y0, x1, y1) as fractions of the upright source frame, or None."""
    times = [t0 + (t1 - t0) * (k + .5) / samples for k in range(samples)]
    boxes = []
    try:
        frames = read_frames(path, times, size=640)
    except Exception:
        return None
    cv2 = locator.cv2
    for _, image in frames:
        bgr = np.ascontiguousarray(np.array(image.convert('RGB'))[:, :, ::-1])
        h, w = bgr.shape[:2]
        if locator.yunet is not None:
            locator.yunet.setInputSize((w, h))
            _, faces = locator.yunet.detect(bgr)
            found = [] if faces is None else [f[:4] for f in faces]
        else:
            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            found = list(locator.haar.detectMultiScale(gray, 1.1, 5, minSize=(w // 14, w // 14)))
        if len(found):
            x, y, bw, bh = max(found, key=lambda b: b[2] * b[3])
            boxes.append((x / w, y / h, (x + bw) / w, (y + bh) / h))
    if not boxes:
        return None
    return tuple(float(np.median([b[i] for b in boxes])) for i in range(4))


def to_canvas(box, source_size, canvas_size):
    """Source-fraction box -> canvas pixels, assuming the clip is fitted and centred (the XML default)."""
    sw, sh = source_size
    cw, ch = canvas_size
    scale = min(cw / sw, ch / sh)
    ox, oy = (cw - sw * scale) / 2, (ch - sh * scale) / 2
    return (ox + box[0] * sw * scale, oy + box[1] * sh * scale, ox + box[2] * sw * scale, oy + box[3] * sh * scale)


def avoid_zone(face, canvas_size):
    """Face box grown to hair, raised hands and shoulders."""
    x0, y0, x1, y1 = face
    fw, fh = x1 - x0, y1 - y0
    cw, ch = canvas_size
    return (max(0, x0 - .7 * fw), max(0, y0 - 1.1 * fh), min(cw, x1 + .7 * fw), min(ch, y1 + .5 * fh))


def _overlap(a, b):
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return max(0.0, w) * max(0.0, h)


def spots(card_w, card_h, width, height, top=True, below=None):
    """Candidate top-left corners, most preferred first. top=False: mid-height spots that stay above the
    caption area (captions sit in the lower third); `below` = bottom of the face zone."""
    mx, my = round(width * .05), round(height * .07)
    right, left = width - mx - card_w, mx
    if width > height * 1.2:
        if top:
            return [(right, round(height * .09)), (left, round(height * .09))]
        middle = (height - card_h) // 2
        return [(right, middle), (left, middle)]
    if top:
        return [((width - card_w) // 2, my), (left, my), (right, my)]
    limit = round(height * .62) - card_h
    found = [(left, y) for y in (round(height * .36),) if my <= y <= limit] + \
            [(right, y) for y in (round(height * .36),) if my <= y <= limit]
    if below is not None and my <= below + round(height * .01) <= limit:
        y = below + round(height * .01)
        found += [((width - card_w) // 2, y), (left, y), (right, y)]
    return found or [(left, max(my, limit)), (right, max(my, limit))]


def _rect(spot, w, h):
    return (spot[0], spot[1], spot[0] + w, spot[1] + h)


def place_card(card_w, card_h, width, height, avoid=None):
    """(scale, (x, y)) for the card: full size at the top when the face allows, else smaller at the top,
    else smaller at mid-height on the side; never on the face when any spot is free."""
    if avoid is None:
        return 1.0, spots(card_w, card_h, width, height)[0]
    tries = [(scale, True) for scale in (1.0, .75, .58)] + [(scale, False) for scale in (.75, .58)]
    for scale, top in tries:
        w, h = round(card_w * scale), round(card_h * scale)
        for spot in spots(w, h, width, height, top, round(avoid[3])):
            if _overlap(_rect(spot, w, h), avoid) == 0:
                return scale, spot
    w, h = round(card_w * .58), round(card_h * .58)
    options = spots(w, h, width, height) + spots(w, h, width, height, False)
    return .58, min(options, key=lambda p: _overlap(_rect(p, w, h), avoid))


def choose_spot(card_w, card_h, width, height, avoid=None):
    """Top-left corner for a card that keeps its size (first free top spot)."""
    options = spots(card_w, card_h, width, height)
    free = [p for p in options if avoid is None or _overlap(_rect(p, card_w, card_h), avoid) == 0]
    return free[0] if free else options[0]
