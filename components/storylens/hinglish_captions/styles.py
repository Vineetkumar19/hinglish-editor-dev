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
    'serif_circle_draft': {
        'name':'Caption 06 - Serif Circle','tag':'CINEMATIC','category':'cinematic',
        'font':'Inter-SemiBold.ttf','base':'#FFFFFF','accent':'#58F69D','surface':None,
        'case':'normal','layout':'serif_circle','default_position':.65,
        'word_visibility':'phrase','no_pop':True,'max_words':7,
        'description':'Compact white captions, italic emphasis and hand-drawn annotations. Vertical: four words; horizontal: seven.'},
    'kinetic_gold_draft': {
        'name':'Caption 08 - Kinetic Gold','tag':'CINEMATIC','category':'cinematic',
        'font':'BarlowCondensed-SemiBold.ttf','base':'#FFFFFF','accent':'#FFCC00','surface':None,
        'case':'normal','layout':'kinetic_gold','default_position':.65,
        'word_visibility':'phrase','no_pop':True,'max_words':11,
        'description':'Reusable reference layouts: yellow emphasis, staggered white support, inline phrases, compound groups, moving echo text and curved brush strokes.'},
    'cinematic_mixed_draft': {
        'name':'Cinematic Script Mix','tag':'CINEMATIC','category':'cinematic',
        'font':'Roboto-Regular.ttf','base':'#FFFFFF','accent':'#FFFFFF','surface':None,
        'case':'normal','layout':'cinematic_reference','default_position':.456,
        'word_visibility':'phrase','no_pop':True,'max_words':7,
        'description':'Cursive lead word, clean support and bold emphasis. Vertical: four words; horizontal: seven.'},
    'cinematic_clean_draft': {
        'name':'Cinematic Clean Reveal','tag':'CINEMATIC','category':'cinematic',
        'font':'Roboto-Regular.ttf','base':'#FFFFFF','accent':'#FFFFFF','surface':None,
        'case':'normal','layout':'cinematic_reference','default_position':.464,
        'word_visibility':'phrase','no_pop':True,'max_words':7,
        'description':'Clean white type with cumulative word reveals. Vertical: four words; horizontal: seven.'},
    'caption_5': {
        'name': 'Caption 05 - Bold Red Word Clusters', 'tag': 'VIDEO 5', 'category': 'editorial',
        'font': 'Inter-Variable.ttf', 'base': '#060606', 'accent': '#B30C36',
        'surface': None, 'case': 'normal', 'layout': 'caption_five',
        'default_position': .45, 'word_visibility': 'phrase', 'no_pop': True,
        'max_words': 5,
        'description': 'Heavy black word clusters, red and blue emphasis, condensed keywords and precise rising word entrances.'},
    'caption_4': {
        'name': 'Caption 04 - Legacy Serif', 'tag': 'VIDEO 4', 'category': 'editorial',
        'font': 'timesbi.ttf', 'base': '#F2F2F2', 'accent': '#F2F2F2',
        'surface': None, 'case': 'normal', 'layout': 'caption_four',
        'default_position': .42, 'word_visibility': 'phrase', 'no_pop': True,
        'max_words': 5,
        'description': 'Italic serif keyword, small offset support, soft focus reveals and slow camera motion. Every overflow word continues on another slide.'},
    'caption_3': {
        'name': 'Caption 03 - Serif Soft Focus', 'tag': 'VIDEO 3', 'category': 'editorial',
        'font': 'caption-three/CaptionThree-BoldItalic.ttf', 'base': '#242422', 'accent': '#259DD0',
        'surface': None, 'case': 'normal', 'layout': 'caption_three',
        'default_position': .42, 'word_visibility': 'phrase', 'no_pop': True,
        'max_words': 5,
        'description': 'Reference serif typography, staggered support, varied text arrangements, soft focus and continuous camera motion. Fixed word slots survive script edits.'},
    'caption_2': {
        'name': 'Caption 02 - Lime Keyword Zoom', 'tag': 'VIDEO 2', 'category': 'editorial',
        'font': 'Inter-Bold.otf', 'base': '#FFFFFF', 'accent': '#E0FD56',
        'surface': None, 'case': 'normal', 'layout': 'caption_two',
        'default_position': 732/1280, 'word_visibility': 'phrase', 'no_pop': True,
        'max_words': 5,
        'description': 'Lime emphasis with compact white support, fixed text positions and reference motion. Up to five words per slide on black.'},
    'caption_1': {
        'name': 'Caption 01 - Blue Keyword Stack', 'tag': 'VIDEO 1', 'category': 'editorial',
        'font': 'Inter-Bold.otf', 'base': '#FFFFFF', 'accent': '#25A8FC',
        'surface': None, 'case': 'normal', 'layout': 'caption_one',
        'default_position': .6234375, 'word_visibility': 'phrase', 'no_pop': True,
        'max_words': 10,
        'description': 'Small top text and one large word. Long main words use two lines; shorter words add a bottom line aligned to the main word.'},
    'documentary_outline': {
        'name': 'Documentary Outline', 'tag': 'REFERENCE', 'category': 'cinematic',
        'font': 'impact.ttf', 'base': '#FFFFFF', 'accent': '#FFFFFF',
        'surface': None, 'case': 'upper', 'layout': 'kinetic_documentary',
        'reference_effect': 'outline',
        'default_position': .86015625, 'word_visibility': 'phrase', 'no_pop': True,
        'description': 'White outlined hero word with compact bold support. No stripes; 10% smaller by default.'},
    'documentary_echo': {
        'name': 'Documentary Echo', 'tag': 'REFERENCE', 'category': 'cinematic',
        'font': 'impact.ttf', 'base': '#FFFFFF', 'accent': '#FFFFFF',
        'surface': None, 'case': 'upper', 'layout': 'kinetic_documentary',
        'reference_effect': 'echo',
        'default_position': .86015625, 'word_visibility': 'phrase', 'no_pop': True,
        'description': 'White solid hero word with a faint outline echo and bold support. No stripes; 10% smaller by default.'},
    'kinetic_documentary': {
        'name': 'Kinetic Documentary', 'tag': 'REFERENCE', 'category': 'cinematic',
        'font': 'impact.ttf', 'base': '#FFFFFF', 'accent': '#F4B400',
        'surface': None, 'case': 'upper', 'layout': 'kinetic_documentary',
        'default_position': .86015625, 'word_visibility': 'phrase', 'no_pop': True,
        'description': 'Shorts 16 white lettering and word reveals, without stripes; 10% smaller by default.'},
    'typography_1': {
        'name': 'Typography 1', 'tag': 'PREMIUM', 'category': 'cinematic', 'font': 'impact.ttf',
        'base': '#FFFFFF', 'accent': '#F12722', 'surface': None, 'case': 'upper',
        'layout': 'typography_1',
        'description': 'Cinematic type choreography with colored strips, glow, blur and camera motion.'},
    'typography_2': {
        'name': 'Typography 2', 'tag': 'PREMIUM', 'category': 'aesthetic', 'font': 'arial.ttf',
        'base': '#FFFFFF', 'accent': '#137FF6', 'surface': None, 'case': 'normal',
        'layout': 'typography_2',
        'description': 'Elegant red script and progressive blue signal bars with precise word reveals.'},
    'typography_3': {
        'name': 'Typography 3', 'tag': 'PREMIUM', 'category': 'editorial',
        'font': 'Roboto-Black.ttf', 'base': '#FFFFFF', 'accent': '#FFFFFF',
        'surface': None, 'case': 'normal', 'layout': 'typography_3', 'no_pop': True,
        'default_position': .235,
        'description': 'Measured editorial type with a bold anchor, aligned support and soft focus motion.'},
    'typography_4': {
        'name': 'Typography 4', 'tag': 'PREMIUM', 'category': 'editorial',
        'font': 'Roboto-Black.ttf', 'base': '#F4F4F4', 'accent': '#52C7FF',
        'surface': None, 'case': 'normal', 'layout': 'typography_4', 'no_pop': True,
        'default_position': .235,
        'description': 'Clean progressive type with a white-to-cyan final word and measured linear fades.'},
    'typography_5': {
        'name': 'Typography 5', 'tag': 'PREMIUM', 'category': 'aesthetic',
        'font': 'arial.ttf', 'base': '#F4F4F4', 'accent': '#EF4937',
        'surface': None, 'case': 'normal', 'layout': 'typography_5', 'no_pop': True,
        'max_words': 10,
        'default_position': .220,
        'reference_geometry': {'support_ratio': 26/82, 'top_origin': .01,
                               'bottom_origin': .88, 'inset': .07,
                               'centered_headers': ['fasle']},
        'reference_recipes': [
            {'text': 'pe jab sab dhundhala ho jata hai,', 'hero': 3},
            {'text': 'Machine ka tab koi vajan nahi rahata', 'hero': 0},
            {'text': 'hai, vo gayab ho jati hai,', 'hero': 0, 'bottom_inset': .48},
            {'text': 'jata hai toh bas ek shareer,', 'hero': 5},
            {'text': 'vakt aur fasle ko par karta hua,', 'hero': 2},
            {'text': 'rpm, vahee hota hai vo ehasas, vo', 'hero': 5},
            {'text': 'ek khas ehasas jo kano mai gunjne', 'hero': 2},
        ],
        'description': 'Great Vibes calligraphy with compact editorial support and soft-focus word reveals.'},
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


# Owner's shared starting point: centered, 15% below vertical center.
for _key,_style in TEMPLATES.items():
    if _key != 'caption_1':_style['default_position'] = .65


# Keep legacy definitions for reopening saved projects, outside the style pickers.
SELECTABLE_TEMPLATES = {
    key: TEMPLATES[key]
    for key in ('caption_1', 'caption_2', 'caption_3', 'caption_4', 'caption_5', 'typography_3', 'typography_4', 'typography_5', 'cinematic_mixed_draft', 'cinematic_clean_draft', 'kinetic_gold_draft', 'serif_circle_draft', 'kinetic_documentary', 'documentary_outline', 'documentary_echo')
}


def template(name):
    if name not in TEMPLATES:
        raise ValueError('Unknown caption template: ' + str(name))
    return TEMPLATES[name]


def font_file(font_id, style_name):
    if font_id not in FONT_CHOICES:
        raise ValueError('Unknown caption font: ' + str(font_id))
    return FONT_CHOICES[font_id]['file'] or template(style_name)['font']
