FONT_CHOICES = {
    'template': {'name': 'Template default', 'file': None, 'css': 'inherit'},
    'impact': {'name': 'Impact', 'file': 'impact.ttf', 'css': 'Impact, sans-serif'},
    'arial': {'name': 'Arial Bold', 'file': 'arialbd.ttf', 'css': 'Arial, sans-serif'},
    'bahnschrift': {'name': 'Bahnschrift', 'file': 'bahnschrift.ttf', 'css': 'Bahnschrift, sans-serif'},
    'segoe': {'name': 'Segoe Bold', 'file': 'segoeuib.ttf', 'css': 'Segoe UI, sans-serif'},
    'georgia': {'name': 'Georgia Serif', 'file': 'georgiab.ttf', 'css': 'Georgia, serif'},
    'script': {'name': 'Segoe Script', 'file': 'segoesc.ttf', 'css': 'Segoe Script, cursive'},
    'trebuchet': {'name': 'Trebuchet Bold', 'file': 'trebucbd.ttf', 'css': 'Trebuchet MS, sans-serif'},
}


TEMPLATES = {
    'typography_1': {
        'name': 'Typography 1', 'tag': 'PREMIUM', 'category': 'cinematic', 'font': 'impact.ttf',
        'base': '#FFFFFF', 'accent': '#F12722', 'surface': None, 'case': 'upper',
        'layout': 'typography_1',
        'description': 'Cinematic type choreography with colored strips, glow, blur and camera motion.'},
    'flash_cut': {
        'name': 'Flash Cut', 'tag': 'CINEMATIC', 'category': 'cinematic', 'font': 'impact.ttf',
        'base': '#FFFFFF', 'accent': '#FFF200', 'surface': None, 'case': 'upper',
        'description': 'Hard cinematic title with yellow keyword impact.'},
    'soft_focus': {
        'name': 'Soft Focus', 'tag': 'CINEMATIC', 'category': 'cinematic', 'font': 'segoeuib.ttf',
        'active_font': 'segoesc.ttf', 'base': '#FFFFFF', 'accent': '#FF5A45', 'surface': None,
        'case': 'normal', 'description': 'Clean white setup with a handwritten red focus word.'},
    'soft_2': {
        'name': 'Soft 2.0', 'tag': 'CINEMATIC', 'category': 'aesthetic', 'font': 'segoeuib.ttf',
        'base': '#FFFFFF', 'accent': '#FFFFFF', 'surface': None, 'case': 'normal', 'no_pop': True,
        'description': 'Restrained aesthetic captions for polished lifestyle edits.'},
    'real_estate': {
        'name': 'Real Estate', 'tag': 'CINEMATIC', 'category': 'cinematic', 'font': 'impact.ttf',
        'base': '#FFFFFF', 'accent': '#D7FF23', 'surface': None, 'case': 'normal',
        'description': 'Large stacked energy with a lime hero word.'},
    'signal_bar': {
        'name': 'Signal Bar', 'tag': 'CINEMATIC', 'category': 'boxed', 'font': 'arialbd.ttf',
        'base': '#FFFFFF', 'accent': '#FFFFFF', 'surface': '#087DF5', 'case': 'normal', 'no_pop': True,
        'description': 'Bright blue signal bar for clear phrase highlights.'},
    'cinematic_cut': {
        'name': 'Cinematic Cut', 'tag': 'CINEMATIC', 'category': 'cinematic', 'font': 'impact.ttf',
        'base': '#FFFFFF', 'accent': '#FFFFFF', 'surface': None, 'case': 'normal',
        'description': 'Bold size contrast for fast cinematic pacing.'},
    'focus_signal': {
        'name': 'Focus Signal', 'tag': 'CINEMATIC', 'category': 'oneword', 'font': 'arialbd.ttf',
        'base': '#FFFFFF', 'accent': '#FFFFFF', 'surface': '#087DF5', 'case': 'normal', 'one_word': True,
        'description': 'One focused word at a time inside a crisp blue signal.'},
    'aura_script': {
        'name': 'Aura Script', 'tag': 'AESTHETIC', 'category': 'aesthetic', 'font': 'segoeuib.ttf',
        'active_font': 'segoesc.ttf', 'base': '#FFFFFF', 'accent': '#FFF06A', 'surface': None,
        'case': 'normal', 'description': 'Bold italic energy with a soft handwritten accent.'},
    'punch': {
        'name': 'Creator Punch', 'tag': 'VIRAL', 'category': 'cinematic', 'font': 'impact.ttf',
        'base': '#FFFFFF', 'accent': '#FF7638', 'surface': None, 'case': 'upper',
        'description': 'Bold word pops with warm orange emphasis.'},
    'karaoke': {
        'name': 'Kinetic Karaoke', 'tag': 'DYNAMIC', 'category': 'karaoke', 'font': 'arialbd.ttf',
        'base': '#FFFFFF', 'accent': '#52E2D1', 'surface': None, 'case': 'normal',
        'description': 'Fast word tracking with a clean cyan focus.'},
    'pill': {
        'name': 'Studio Pill', 'tag': 'CLEAN', 'category': 'boxed', 'font': 'arialbd.ttf',
        'base': '#111318', 'accent': '#E64F2E', 'surface': '#F7F4EE', 'case': 'normal',
        'description': 'Editorial white pill with a confident accent.'},
    'editorial': {
        'name': 'Editorial Serif', 'tag': 'LUXE', 'category': 'editorial', 'font': 'georgiab.ttf',
        'base': '#FFFFFF', 'accent': '#F1C56A', 'surface': None, 'case': 'normal',
        'description': 'Refined serif captions with restrained gold.'},
    'neon': {
        'name': 'Midnight Glow', 'tag': 'NEON', 'category': 'aesthetic', 'font': 'bahnschrift.ttf',
        'base': '#FFFFFF', 'accent': '#B882FF', 'surface': None, 'case': 'upper',
        'description': 'Purple glow made for dark podcast footage.'},
    'minimal': {
        'name': 'Quiet Minimal', 'tag': 'TIMELESS', 'category': 'aesthetic', 'font': 'segoeuib.ttf',
        'base': '#FFFFFF', 'accent': '#FFFFFF', 'surface': None, 'case': 'normal', 'no_pop': True,
        'description': 'Simple typography, subtle motion and no noise.'},
}


def template(name):
    if name not in TEMPLATES:
        raise ValueError('Unknown caption template: ' + str(name))
    return TEMPLATES[name]


def font_file(font_id, style_name):
    if font_id not in FONT_CHOICES:
        raise ValueError('Unknown caption font: ' + str(font_id))
    return FONT_CHOICES[font_id]['file'] or template(style_name)['font']
