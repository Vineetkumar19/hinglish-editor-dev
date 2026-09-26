"""Smart Visuals timing profiles and local choices (which brain, pop-ups). API keys come from B-roll settings."""
from dataclasses import dataclass, replace
from pathlib import Path
import json

from hinglish_broll.settings import BASE, DENSITY, SHORT_FORM_LIMIT, Profile, load_settings as load_broll

LOCAL_SETTINGS = 'config.visuals.local.json'
BRAINS = ('auto', 'ollama', 'local')

# Full-screen visuals follow B-roll rules (they hide the face). Pop-ups (logo / face cards) keep the
# face visible, so they may come sooner, also inside the opening hook, and more often.
POPUP = {
    'short': Profile('popup', 1.2, 3.0, .6, 2.2, .45, 0.0, .4, 2.2),
    'long': Profile('popup', 1.5, 3.5, 2.0, 6.0, .20, 0.0, 1.0, 2.6),
}


def profiles_for(duration, density='medium'):
    """(full-screen profile, pop-up profile) for this timeline length and density."""
    if density not in DENSITY:
        raise ValueError('Density must be low, medium or high')
    form = 'short' if duration <= SHORT_FORM_LIMIT else 'long'
    spacing, coverage = DENSITY[density]
    full, pop = BASE[form], POPUP[form]
    # Visuals of real things are the point of this feature: a little denser than generic B-roll.
    full = replace(full, min_spacing=full.min_spacing * spacing * .85,
                   max_coverage=min(.6, full.max_coverage * coverage * 1.15))
    pop = replace(pop, min_spacing=pop.min_spacing * spacing, max_coverage=min(.6, pop.max_coverage * coverage))
    return full, pop


@dataclass
class VisualsSettings:
    density: str = 'medium'
    device: str = 'cpu'
    cpu_threads: int = 4
    brain: str = 'auto'                 # auto: Ollama thinking model when running, else the bundled Qwen
    think_model: str = 'qwen3:8b'       # Ollama model (knows famous people, brands and history better)
    popups: bool = True                 # logo / face cards when a name is said
    vision_model: str = 'openai/clip-vit-base-patch32'
    use_stock: bool = True              # Pexels / Pixabay (keys from B-roll settings) for places and things
    use_web: bool = True                # search the whole web: images from any site, YouTube/web videos
    evaluator: str = 'auto'             # auto: vision model (Ollama) else CLIP type check; vlm | clip | off
    vision_check_model: str = 'qwen2.5vl:7b'
    pexels_key: str = ''
    pixabay_key: str = ''
    language: str = 'en'                # Wikipedia / Wikidata language for names and descriptions

    def __post_init__(self):
        if self.density not in DENSITY:
            raise ValueError('Density must be low, medium or high')
        if self.device not in ('cpu', 'cuda'):
            raise ValueError('Device must be cpu or cuda')
        if self.brain not in BRAINS:
            raise ValueError('Brain must be auto, ollama or local')
        if self.evaluator not in ('auto', 'vlm', 'clip', 'off'):
            raise ValueError('Evaluator must be auto, vlm, clip or off')


def load_settings(root, **overrides):
    """Saved choices (config.visuals.local.json, optional) + stock keys from B-roll settings + per-run overrides."""
    file = Path(root) / LOCAL_SETTINGS
    data = json.loads(file.read_text(encoding='utf-8-sig')) if file.exists() else {}
    data = {k: v for k, v in data.items() if k in VisualsSettings.__dataclass_fields__
            and not k.endswith('_key')}          # keys live only in the B-roll settings file
    broll = load_broll(root)
    data['pexels_key'] = broll.pexels_key if broll.use_pexels else ''
    data['pixabay_key'] = broll.pixabay_key if broll.use_pixabay else ''
    data.update({k: v for k, v in overrides.items() if v is not None})
    return VisualsSettings(**data)
