"""One eased direction per real shot. A timer never reverses framing inside it."""
from .curve import ZoomEvent


def cut_events(shots, settings, profile, fps, words=()):
    events = []
    for index, (start, end) in enumerate(shots):
        start, end = round(start * fps) / fps, round(end * fps) / fps
        if end <= start:
            continue
        # Leave most of even a short shot settled, without an overshoot or a
        # second direction. Eight-second shots stay settled for all eight.
        requested = profile.cut_ramp if index % 2 == 0 else profile.cut_ramp_out
        ramp = min(requested, (end - start) / 2)
        ramp = max(1 / fps, round(ramp * fps) / fps)
        inside = [w.text for w in words if start <= w.start < end]
        events.append(ZoomEvent('cut_in' if index % 2 == 0 else 'cut_out',
            start, min(end, start + ramp), end, end, settings.level,
            text=' '.join(inside), word_text='', strength=2))
    return events


def checks(plan, Check):
    """Judge actual frame curves against cuts, including long/last/no-cut shots."""
    import numpy as np
    from .curve import build_curve, quantize
    from .settings import STRENGTH

    fps = float(plan.get('fps', 30))
    curve = np.asarray(plan.get('curve', []), dtype=float)
    events = plan.get('events', [])
    shots = plan.get('shots', [])
    anchors = plan.get('anchors', [])
    frame_kinds = plan.get('anchor_kinds', [])
    limit = STRENGTH.get(plan.get('settings', {}).get('strength'), 1.12)
    centres = np.asarray(plan.get('camera_centres', []), dtype=float)
    fixed = plan.get('framing') == 'fixed_focal'
    path_problems = []
    problems, moving, held, levels = [], [], [], []
    for i, (a, b) in enumerate(shots):
        matching = [e for e in events if abs(e['start']-a) <= .51/fps and abs(e['end']-b) <= .51/fps]
        expected = 'cut_in' if i % 2 == 0 else 'cut_out'
        if len(matching) != 1 or matching[0].get('kind') != expected:
            problems.append(f'{a:.2f}s: missing {expected} shot'); continue
        e = matching[0]
        f0, f1 = round(a*fps), min(len(curve), round(b*fps))
        done = min(f1, round(e['word']*fps))
        ramp = e['word']-a
        requested = plan.get('profile', {}).get('cut_ramp' if expected=='cut_in' else 'cut_ramp_out', .8 if expected=='cut_in' else .7)
        wanted = min(requested, (b-a)/2)
        if abs(ramp-wanted) > 1.1/fps or ramp <= 0:
            moving.append(f'{a:.2f}s: wrong entrance duration')
        if e['hold_end'] != e['end'] or abs(e['level']-limit) > .0003:
            problems.append(f'{a:.2f}s: framing reverses before the cut')
        segment = curve[f0:f1]
        diff = np.diff(segment)
        if (expected == 'cut_in' and np.any(diff < -.00015)) or (expected == 'cut_out' and np.any(diff > .00015)):
            problems.append(f'{a:.2f}s: both directions within one shot')
        target = limit if expected == 'cut_in' else 1.0
        if not len(segment) or abs(segment[0]-(1.0 if expected == 'cut_in' else limit)) > .0003:
            levels.append(f'{a:.2f}s: wrong starting framing')
        if done < f1 and np.any(np.abs(curve[done:f1]-target) > .0003):
            held.append(f'{a:.2f}-{b:.2f}s: framing did not hold until the cut')
        theoretical = quantize(build_curve([ZoomEvent(**e)], len(curve), fps))[f0:f1]
        if len(segment) != len(theoretical) or np.any(np.abs(segment-theoretical) > .00015):
            moving.append(f'{a:.2f}s: rendered curve does not follow the eased entrance')
        if fixed:
            if centres.shape != (len(curve),2) or not np.isfinite(centres).all():
                path_problems.append(f'{a:.2f}s: missing camera path'); continue
            # A pure zoom about ONE point has translation linear in scale.
            # The old per-frame face recenter/clamp made a bent path here.
            lo, hi = int(np.argmin(segment)), int(np.argmax(segment))
            if segment[hi]-segment[lo] > .0001:
                progress = (segment-segment[lo])/(segment[hi]-segment[lo])
                camera = centres[f0:f1]
                line = camera[lo]+progress[:,None]*(camera[hi]-camera[lo])
                if np.max(np.abs(camera-line)) > .00002:
                    path_problems.append(f'{a:.2f}s: focal point changes during the zoom')
            shot_anchors=anchors[f0:f1]
            if shot_anchors and any(anchor != shot_anchors[0] for anchor in shot_anchors):
                path_problems.append(f'{a:.2f}s: speaker anchor changes inside the shot')
    zoomed = [i for i,z in enumerate(curve) if z > 1.004]
    safe = sum(i < len(anchors) and bool(anchors[i]) and
               (not frame_kinds or frame_kinds[i] in ('face','speaker')) for i in zoomed) / max(1,len(zoomed))
    finite = bool(len(curve)) and bool(np.isfinite(curve).all())
    return [
        Check('zoom.level', 'Zoom stays inside the selected strength', finite and
              float(curve.min()) >= .9999 and float(curve.max()) <= limit+.00015 and not levels,
              value='; '.join(levels) or f'100% to {limit:.0%}'),
        Check('zoom.cuts', 'One alternating direction at each actual clip boundary',
              bool(shots) and len(events)==len(shots) and not problems,
              value='; '.join(problems) or f'{len(shots)} shots, alternating in/out'),
        Check('zoom.eased', 'Slower sine-eased entrances without overshoot or abrupt steps',
              not moving, value='; '.join(moving) or '0.8 s in / 0.7 s out; gentle start and landing'),
        Check('zoom.hold', 'Framing stays fixed until the next cut, with no timed reversal',
              not held and not problems, value='; '.join(held) or 'held to each cut, including the ending'),
        Check('zoom.face', 'Close framing uses a verified face or speaker throughout',
              not plan.get('settings',{}).get('face',True) or safe >= .99, value=f'{safe:.0%} verified'),
        *([Check('zoom.fixed_focal', 'One fixed focal point per shot; no second pan or retargeting',
                 not path_problems, value='; '.join(path_problems) or 'single straight camera path in every shot')]
          if fixed else []),
    ]
