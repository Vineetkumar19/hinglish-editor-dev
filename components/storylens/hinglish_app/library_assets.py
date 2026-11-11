"""Browse the local Premiere and Resolve packs without starting an editor."""
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
import math
import os
import subprocess

ROOT = Path(r'D:\Editing\Cinematics AE templates')
RESOLVE_LUT_ROOT = Path(os.environ.get('PROGRAMDATA', 'C:/ProgramData')) / 'Blackmagic Design/DaVinci Resolve/Support/LUT'
RESOLVE_LUT_GROUPS = ('ACES', 'Arri', 'Astrodesign', 'Blackmagic Design', 'DCI', 'DJI',
                      'Film Looks', 'HDR Hybrid Log-Gamma', 'HDR ST 2084', 'Leica',
                      'Olympus', 'Panasonic', 'RED', 'Samsung', 'Sony', 'VFX IO')
SECTIONS = {
    'Premier Pro': {'.prproj': 'Premiere project', '.mogrt': 'Motion Graphics template'},
    'Davinci': {'.cube': 'LUT', '.drx': 'PowerGrade', '.dctle': 'DCTL',
                '.dctl': 'DCTL', '.setting': 'Fusion title', '.drfx': 'Resolve template'},
    'SpeedRamp': {'.drfx': 'Resolve template'},
    'Travel': {'.prproj': 'Premiere project', '.mogrt': 'Motion Graphics template'},
}
TEXT_PACKS = {
    'minimal-typography-pack-mogrt-2022-04-30-18-02-56-utc': 'Minimal Typography',
    'text-animations-for-premiere-pro-61400130': 'Text Animations',
    'Premium_motion_textsV2': 'Premium Motion Text V2',
}
PACK_NAMES = {
    'earth-zoom-transitions-62596084_': 'Earth Zoom Transitions',
    'handy-transitions-for-premiere-pro-22125468': 'Handy Transitions',
    'invert-flash-cinematic-transitions-for-premiere-pr-62294040': 'Invert Flash Transitions',
    'split-transitions-for-premiere-pro-61872104_': 'Split Transitions',
    'FilmVerse_Full_Plugin_V2.1_for_Davinci_Resolve': 'FilmVerse 2.1',
    'JUST_KAY_Node_Structure_Titles_ver.1.0': 'Just Kay Node Structure Titles',
    'LUTs_for_Sony': 'Sony LUTs',
    'speed-ramp-pro-56510269_': 'Speed Ramp Pro',
    'travelio-travel-maps-for-premiere-pro-59505993': 'Travelio Maps',
    **TEXT_PACKS,
}
SWATCHES = ((.13,.13,.13),(.28,.28,.28),(.48,.48,.48),(.67,.67,.67),(.85,.85,.85),
            (.68,.44,.31),(.77,.59,.48),(.62,.25,.22),(.31,.48,.24),(.24,.42,.63))


def _files(folder, formats, *, root=None):
    if not folder.is_dir():
        return
    base = (root or ROOT).resolve()
    for path in folder.rglob('*'):
        if path.suffix.lower() not in formats or path.name.startswith('.') or '__MACOSX' in path.parts:
            continue
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(base):
            continue
        if path.stat().st_size > 1:
            yield path


def _identity(path):
    return sha256(path.relative_to(ROOT).as_posix().casefold().encode()).hexdigest()[:24]


def _pack_name(name):
    return PACK_NAMES.get(name,name.replace('_',' '))


def _rows(section):
    formats = SECTIONS.get(section,{})
    if not formats:
        return
    source = ROOT/section
    for path in _files(source,formats):
        relative = path.relative_to(source)
        pack = relative.parts[0] if len(relative.parts)>1 else path.stem
        if path.suffix.lower()=='.cube' and _lut(path) is None:
            continue
        yield _pack_name(pack),path,formats[path.suffix.lower()]
    if section=='Premier Pro':
        for pack,name in TEXT_PACKS.items():
            for path in _files(ROOT/'Text templates'/pack,{'.mogrt'}):
                yield name,path,'Motion Graphics template · AE-authored'


def catalogue(section):
    packs = {}
    for name,path,kind in _rows(section):
        packs.setdefault(name,[]).append({
            'id':_identity(path),'name':path.name,'format':kind,
            'variant':next((item.replace(' Version','') for item in path.parts
                            if item in ('Studio Version','Non-Studio Version')), ''),
        })
    return [{'id':'external-'+sha256((section+name).encode()).hexdigest()[:24],
             'kind':'external-pack','name':name,
             'files':sorted(files,key=lambda row:(row['variant'].casefold(),row['name'].casefold()))}
            for name,files in sorted(packs.items())]


def reveal(section, asset_id):
    for _,path,_ in _rows(section):
        if _identity(path)==asset_id:
            subprocess.Popen(['explorer.exe','/select,',str(path)])
            return {'message':'File selected in Explorer.'}
    raise ValueError('Refresh the library and choose a file from this pack.')


def _lut(path):
    try:
        return _parse_lut(path,path.stat().st_mtime_ns,path.stat().st_size)
    except (OSError,ValueError,UnicodeError):
        return None


@lru_cache(maxsize=64)
def _parse_lut(path, modified, size_bytes):
    if size_bytes>8_000_000:
        raise ValueError('LUT is too large to preview.')
    grid = 0
    values = []
    for raw in path.read_text('utf-8-sig').splitlines():
        line = raw.partition('#')[0].strip()
        if not line or line.startswith('TITLE '):
            continue
        if line.startswith('LUT_3D_SIZE '):
            grid = int(line.split()[1])
            if not 2<=grid<=65:
                raise ValueError('Unsupported LUT grid.')
            continue
        if line in ('DOMAIN_MIN 0 0 0','DOMAIN_MAX 1 1 1'):
            continue
        rgb = tuple(float(channel) for channel in line.split())
        if len(rgb)!=3 or not all(math.isfinite(v) for v in rgb):
            raise ValueError('Invalid LUT samples.')
        values.append(rgb)
    if not grid or len(values)!=grid**3:
        raise ValueError('Incomplete 3D LUT.')
    def swatch(rgb):
        lo = [min(grid-2,int(v*(grid-1))) for v in rgb]
        steps = [v*(grid-1)-index for v,index in zip(rgb,lo)]
        out = [0.,0.,0.]
        for z in (0,1):
            for y in (0,1):
                for x in (0,1):
                    row = values[lo[0]+x+(lo[1]+y)*grid+(lo[2]+z)*grid*grid]
                    weight = math.prod(f if d else 1-f for d,f in zip((x,y,z),steps))
                    for index,value in enumerate(row):
                        out[index]+=weight*value
        return '#' + ''.join(f'{round(255*max(0,min(1,v))):02x}' for v in out)
    return {'grid':grid,'preview':[swatch(rgb) for rgb in SWATCHES]}


def luts():
    groups = {
        'Cine LUTs':'Sony Cine2 / Cine4',
        'S-LOG2 LUTs':'Sony S-Log2',
    }
    data = []
    for path in _files(ROOT/'Davinci',{'.cube'}):
        group = groups.get(path.parent.name)
        preview = _lut(path)
        if group and preview:
            data.append({'id':_identity(path),'name':path.stem,'group':group,**preview})
    return {'luts':sorted(data,key=lambda row:(row['group'],row['name'])),
            'built_in':resolve_luts(),
            'neutral':['#'+''.join(f'{round(255*v):02x}' for v in rgb) for rgb in SWATCHES]}


def resolve_luts():
    """Read factory 3D LUTs from the installed Resolve library, excluding user folders."""
    rows = []
    for group in RESOLVE_LUT_GROUPS:
        for path in sorted(_files(RESOLVE_LUT_ROOT / group, {'.cube'}, root=RESOLVE_LUT_ROOT)):
            relative = path.relative_to(RESOLVE_LUT_ROOT)
            rows.append({'id':relative.as_posix(), 'name':path.stem,
                         'group':' / '.join(relative.parts[:-1])})
    return rows


def lut_file(asset_id):
    for path in _files(ROOT/'Davinci',{'.cube'}):
        if _identity(path)==asset_id and _lut(path) and path.parent.name in ('Cine LUTs','S-LOG2 LUTs'):
            return path
    raise ValueError('Choose a LUT from the Color Grade menu.')
