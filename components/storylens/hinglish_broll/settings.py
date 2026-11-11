"""B-roll timing profiles and the user's local B-roll settings (API keys, footage folders)."""
from dataclasses import dataclass, field, asdict, replace
from pathlib import Path
import json

LOCAL_SETTINGS = 'config.broll.local.json'
SHORT_FORM_LIMIT = 180.0  # seconds; longer timelines use YouTube long-form rules


@dataclass(frozen=True)
class Profile:
    name: str
    min_len: float          # shortest B-roll clip
    max_len: float          # longest B-roll clip
    min_gap: float          # face time required between two B-roll clips
    min_spacing: float      # minimum distance between two B-roll starts
    max_coverage: float     # share of the timeline B-roll may cover
    hook: float             # protected opening seconds
    tail: float             # protected closing seconds
    ideal: float            # preferred clip length when the phrase is shorter


BASE = {
    # With spoken-line timing a B-roll lasts exactly as long as its line (capped at max_len).
    'short': Profile('short', 1.5, 4.0, 1.5, 3.2, .42, 2.0, 1.0, 2.2),
    'long': Profile('long', 3.0, 6.0, 10.0, 17.0, .22, 5.0, 2.0, 4.5),
}
DENSITY = {'low': (1.6, .6), 'medium': (1.0, 1.0), 'high': (.7, 1.35)}


def profile_for(duration, density='medium'):
    if density not in DENSITY:
        raise ValueError('Density must be low, medium or high')
    base = BASE['short' if duration <= SHORT_FORM_LIMIT else 'long']
    spacing, coverage = DENSITY[density]
    return replace(base, min_spacing=base.min_spacing * spacing,
                   min_gap=base.min_gap*(.5 if density=='high' else 1.),
                   max_coverage=min(.6, base.max_coverage * coverage))


@dataclass
class BrollSettings:
    density: str = 'medium'
    device: str = 'cpu'
    cpu_threads: int = 4
    vision_model: str = 'openai/clip-vit-base-patch32'
    min_similarity: float = .22       # CLIP cosine below this is treated as "no good match"
    use_library: bool = True
    use_pexels: bool = True
    use_pixabay: bool = True
    use_commons: bool = True
    use_web: bool = True
    image_fallback: bool = False  # retained for old settings files; Add B-roll is videos only
    handle_seconds: float = 3.0
    pexels_key: str = ''
    pixabay_key: str = ''
    library_folders: list[str] = field(default_factory=list)
    results_per_query: int = 12

    def __post_init__(self):
        self.image_fallback = False
        if self.density not in DENSITY:
            raise ValueError('Density must be low, medium or high')
        if self.device not in ('cpu', 'cuda'):
            raise ValueError('Device must be cpu or cuda')
        if not 0 <= self.min_similarity <= 1:
            raise ValueError('min_similarity must be between 0 and 1')
        if not 0 <= self.handle_seconds <= 10:
            raise ValueError('B-roll trim handles must be between 0 and 10 seconds')
        self.library_folders = [str(f) for f in self.library_folders if str(f).strip()]

    def sources(self):
        chosen = []
        if self.use_library and self.library_folders: chosen.append('library')
        if self.use_pexels and self.pexels_key: chosen.append('pexels')
        if self.use_pixabay and self.pixabay_key: chosen.append('pixabay')
        if self.use_commons: chosen.append('commons')
        if self.use_web: chosen.append('web')
        return chosen


USER_KEYS = ('pexels_key', 'pixabay_key', 'library_folders', 'use_library', 'use_pexels', 'use_pixabay',
             'use_commons', 'use_web', 'image_fallback')


def load_settings(root, **overrides):
    """Merge saved user choices with per-run overrides (density, device, ...)."""
    file = Path(root) / LOCAL_SETTINGS
    data = json.loads(file.read_text(encoding='utf-8-sig')) if file.exists() else {}
    data = {k: v for k, v in data.items() if k in BrollSettings.__dataclass_fields__}
    data.update({k: v for k, v in overrides.items() if v is not None})
    return BrollSettings(**data)


def save_user_settings(root, values):
    """Store only the user-facing fields. Empty key strings keep the saved key."""
    file = Path(root) / LOCAL_SETTINGS
    data = json.loads(file.read_text(encoding='utf-8-sig')) if file.exists() else {}
    for key in USER_KEYS:
        if key not in values:
            continue
        value = values[key]
        if key.endswith('_key'):
            value = str(value or '').strip()
            if not value:
                continue
        elif key == 'library_folders':
            value = [str(v).strip() for v in value if str(v).strip()]
            # Preserve saved removable/offline libraries while changing other
            # settings. Validate newly added folders without erasing old choices.
            saved={str(v).casefold() for v in data.get('library_folders',[])}
            missing = [v for v in value if v.casefold() not in saved and not Path(v).is_dir()]
            if missing:
                raise ValueError('B-roll footage folder not found: ' + missing[0])
        else:
            value = bool(value)
        data[key] = value
    data['image_fallback'] = False
    BrollSettings(**{k: v for k, v in data.items() if k in BrollSettings.__dataclass_fields__})
    file.write_text(json.dumps(data, indent=2), encoding='utf-8')
    return public_settings(root)


def public_settings(root):
    """Settings safe to show in the UI: keys are masked, never returned."""
    s = load_settings(root)
    mask = lambda key: ('saved ••••' + key[-4:]) if key else ''
    return {'pexels_key': mask(s.pexels_key), 'pixabay_key': mask(s.pixabay_key),
            'library_folders': s.library_folders, 'use_library': s.use_library,
            'use_pexels': s.use_pexels, 'use_pixabay': s.use_pixabay,
            'use_commons': s.use_commons, 'use_web': s.use_web, 'image_fallback': s.image_fallback}
