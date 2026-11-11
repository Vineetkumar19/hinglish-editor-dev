"""Explicit renderer selection. Unknown engines never fall back to another engine."""
import re
from pathlib import Path

ENGINES = {'remotion': 'Remotion', 'motion-canvas': 'Motion Canvas', 'hyperframes': 'Hyperframes'}
NATIVE_STYLES = {'theme:studio','theme:elements','theme:gsap','theme:product','theme:explainer'}
NATIVE_TEMPLATES = {'asset_hero','motion_title','motion_number','product_card','explainer_steps','element_motion'}
ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / 'tools/motion-engines-runtime'


def selected_engine(text='', value='remotion'):
    value = str(value)
    if value not in ENGINES:
        raise ValueError('Motion engine unavailable: choose Remotion, Motion Canvas or Hyperframes.')
    # Only explicit engine instructions override the selected control. Script text
    # mentioning a tool is ordinary content, not a renderer instruction.
    header = re.split(r'\bSCRIPT\s*:', text, maxsplit=1, flags=re.I)[0]
    match = re.search(r'\b(?:use|using|with|engine\s*[:=])\s*(remotion|motion[ -]?canvas|hyperframes?)\b',header,re.I)
    if match:
        name=re.sub(r'[ -]','',match[1].lower())
        return {'remotion':'remotion','motioncanvas':'motion-canvas','hyperframe':'hyperframes','hyperframes':'hyperframes'}[name]
    return value


def ensure_engine(engine):
    if engine not in ENGINES:
        raise ValueError('Motion engine unavailable: choose Remotion, Motion Canvas or Hyperframes.')
    if engine=='hyperframes':return
    package='remotion' if engine=='remotion' else '@motion-canvas/core'
    if not (RUNTIME/'node_modules'/package/'package.json').is_file():
        raise ValueError(f'Motion engine unavailable: {ENGINES[engine]} is not installed. Restore tools/motion-engines-runtime before retrying the saved request.')


def validate_style(engine, style):
    ensure_engine(engine)
    if engine!='hyperframes' and style not in NATIVE_STYLES:
        raise ValueError('Motion engine style unavailable: choose Connected studio, Element animation, Clean motion, Product spotlight or Step explainer for this engine. Saved reference cards and orbital 3D retain Hyperframes.')
