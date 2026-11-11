from fractions import Fraction
from pathlib import Path
import math
from contextvars import ContextVar

from .core import active_word, hero_span, important_word_index
from .styles import font_file, template

_word_timing_mode=ContextVar('word_timing_mode',default=None)


def _word_visible(cue,index,seconds):
    mode=_word_timing_mode.get()
    if mode=='phrase':
        return cue.start<=seconds<cue.end and cue.words[index].start<=seconds
    return mode!='styled_spoken' or cue.words[index].start<=seconds<cue.words[index].end


def _word_alpha(cue,index,seconds,alpha):
    return alpha if _word_visible(cue,index,seconds) else 0


WORD_COLOR_CHOICES = {
    '#F04444',  # red
    '#FFD400',  # yellow
    '#1677FF',  # blue
    '#0B2E8F',  # dark blue
    '#52C7FF',  # light blue
    '#8B5CF6',  # purple
}


def _color(value, alpha=255):
    value = value.lstrip('#')
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4)) + (alpha,)


def _font_path(name):
    bundled = Path(__file__).with_name('fonts') / name
    if bundled.is_file():
        return bundled
    path = Path(r'C:\Windows\Fonts') / name
    if not path.is_file():
        raise ValueError('Required caption font is missing: ' + name + '. Run tools/prepare_laptop_fonts.py.')
    return path


def _fit_font(draw, words, font_path, target, max_width, min_size):
    from PIL import ImageFont
    size = target
    text = ' '.join(words)
    while size > min_size:
        font = ImageFont.truetype(str(font_path), size)
        if draw.textbbox((0, 0), text, font=font, stroke_width=max(1, size // 28))[2] <= max_width:
            return font
        size -= 2
    return ImageFont.truetype(str(font_path), min_size)


def _text_metrics(draw, text, font, stroke_width=0):
    left, top, right, bottom = draw.textbbox(
        (0, 0), text, font=font, stroke_width=stroke_width
    )
    return right - left, bottom - top, left, top


def _ease_out(value):
    value = min(1.0, max(0.0, value))
    return 1 - (1 - value) ** 3


def _ease_out_back(value, overshoot=1.15):
    """A restrained settle: fast resolve, tiny overshoot, then a clean hold."""
    value = min(1.0, max(0.0, value))
    shifted = value - 1
    return 1 + (overshoot + 1) * shifted ** 3 + overshoot * shifted ** 2


def _clean_word(value):
    return ''.join(character for character in str(value).casefold()
                   if character.isalnum() or character == '%')


def _typography_three_anchor(words):
    """Pick the clearest content word without the late-word bias used by Typography 1."""
    from .template_patterns import stable_anchor
    saved=stable_anchor(words,_typography_three_anchor)
    if saved is not None:return saved
    stop={'a','an','the','and','or','but','of','to','in','on','at','for','aur','jo','toh','hi','hai','hain','tha','thi','na','mein','me','ka','ki','ke','ko','se','pe','par','bhi','ye','yeh','woh','wo','usme','isme','ek','bas','sirf','ab','tab','phir','fir'}
    return max(range(len(words)),key=lambda i:(len(_clean_word(words[i]))*3+(30 if any(c.isdigit() for c in _clean_word(words[i])) else 0)-(100 if _clean_word(words[i]) in stop else 0),-i),default=0)


def _typography_five_anchor(words):
    """Choose a script hero while rejecting the reference's awkward short-lead pattern."""
    if not words:
        return 0
    from .template_patterns import stable_anchor
    saved=stable_anchor(words,_typography_five_anchor)
    if saved is not None:return saved
    tokens = [_clean_word(value) for value in words]
    recipe=next((r for r in template('typography_5').get('reference_recipes',[])
                 if tokens==[_clean_word(value) for value in r['text'].split()]),None)
    if recipe is not None:
        return recipe['hero']
    if len(tokens[0])>=7:return 0
    stop={'a','an','the','and','or','but','of','to','in','on','at','for','aur','jo','toh','hi','hai','hain','tha','thi','na','mein','me','ka','ki','ke','ko','se','pe','par','bhi','ye','yeh','woh','wo','usme','isme','ek','bas','sirf','ab','tab','phir','fir'}
    candidates=list(range(1,len(words))) if len(words)>1 else [0]
    return max(candidates,key=lambda i:(len(tokens[i])*3-(100 if tokens[i] in stop else 0)+(18 if any(c.isdigit() for c in tokens[i]) else 0),-i))


def _safe_word_colors(cue, word_colors):
    values = list(word_colors or [])
    return [value.upper() if isinstance(value, str) and value.upper() in WORD_COLOR_CHOICES else None
            for value in (values + [None] * len(cue.words))[:len(cue.words)]]


def _draw_typography_one(width, height, cue, seconds, font_id, position, size_scale):
    """Render the reference-inspired premium composition on a transparent layer."""
    from PIL import Image, ImageDraw, ImageFilter
    words = [word.text.upper() for word in cue.words]
    if not words:
        return Image.new('RGBA', (width, height), (0, 0, 0, 0))
    clean = [word.strip('.,!?…:;\"\'') or word for word in words]
    hero_index = max(range(len(clean)), key=lambda index: (len(clean[index]), index))
    hero = clean[hero_index]
    top = ' '.join(words[:hero_index])
    bottom = ' '.join(words[hero_index + 1:])
    font_path = _font_path(font_file(font_id, 'typography_1'))
    size_scale = min(1.8, max(.55, float(size_scale)))
    canvas = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    portrait = height > width
    hero_ratio = .145 if portrait else (.13 if width == height else .085)
    hero_target = round(width * hero_ratio * size_scale)
    hero_font = _fit_font(draw, [hero], font_path, hero_target, width * .78, max(14, hero_target // 2))
    small_target = max(12, round(hero_font.size * .28))
    top_font = _fit_font(draw, [top or ' '], font_path, small_target, width * .80, max(9, small_target // 2))
    bottom_font = _fit_font(draw, [bottom or ' '], font_path, max(13, round(hero_font.size * .34)),
                            width * .82, max(9, small_target // 2))
    stroke = max(1, hero_font.size // 34)
    hero_w, hero_h, hero_left, hero_top = _text_metrics(draw, hero, hero_font, stroke)
    top_w, top_h, top_left, top_top = _text_metrics(draw, top or ' ', top_font)
    bottom_w, bottom_h, bottom_left, bottom_top = _text_metrics(draw, bottom or ' ', bottom_font)
    gap = max(5, round(hero_font.size * .10))
    group_h = (top_h + gap if top else 0) + hero_h + (gap + bottom_h if bottom else 0)
    center_y = height * min(.92, max(.10, float(position)))
    group_y = center_y - group_h / 2
    hero_y = group_y + (top_h + gap if top else 0)
    hero_x = (width - hero_w) / 2
    seed = sum(ord(char) for char in cue.text)
    palette = [('#F12722', '#8A0C0B'), ('#F4B400', '#9A6500'), ('#1A66F4', '#073A9F')]
    accent, deep = palette[round(cue.start * 100) % len(palette)]
    elapsed = max(0.0, seconds - cue.start)
    remaining = max(0.0, cue.end - seconds)
    enter = _ease_out(elapsed / .30)
    leave = _ease_out(remaining / .28)
    bar_reveal = _ease_out((elapsed - .05) / .24)
    top_reveal = _ease_out(elapsed / .20)
    hero_reveal = _ease_out((elapsed - .07) / .24)
    bottom_reveal = _ease_out((elapsed - .22) / .25)
    pad_x, pad_y = hero_font.size * .18, hero_font.size * .05
    bar_left = hero_x - pad_x
    bar_right = hero_x + hero_w + pad_x
    visible_right = bar_left + (bar_right - bar_left) * bar_reveal

    # Offset strips give the composition the layered, editorial depth seen in the references.
    strip = Image.new('RGBA', canvas.size, (0, 0, 0, 0)); sd = ImageDraw.Draw(strip)
    offset = max(3, round(width * .012))
    sd.rounded_rectangle((bar_left - offset, hero_y + offset, visible_right - offset,
                          hero_y + hero_h + pad_y * 2 + offset), radius=max(2, hero_font.size // 24),
                         fill=_color(deep, round(225 * hero_reveal)))
    sd.rounded_rectangle((bar_left, hero_y - pad_y, visible_right,
                          hero_y + hero_h + pad_y), radius=max(2, hero_font.size // 25),
                         fill=_color(accent, round(255 * hero_reveal)))
    glow = strip.filter(ImageFilter.GaussianBlur(max(5, round(width / 85))))
    glow.putalpha(glow.getchannel('A').point(lambda value: round(value * .48)))
    canvas = Image.alpha_composite(canvas, glow)
    canvas = Image.alpha_composite(canvas, strip)
    draw = ImageDraw.Draw(canvas)

    # A large outline echo and dark extrusion make the text remain legible over real footage.
    echo_font = hero_font
    echo_alpha = round(85 * hero_reveal)
    draw.text((hero_x + max(3, hero_font.size * .08), hero_y - hero_top + max(3, hero_font.size * .08)),
              hero, font=echo_font, fill=(0, 0, 0, 0), stroke_width=max(1, hero_font.size // 28),
              stroke_fill=(255, 255, 255, echo_alpha))
    if top:
        tx = (width - top_w) / 2
        draw.text((tx + 2, group_y - top_top + 3), top, font=top_font,
                  fill=(0, 0, 0, round(190 * top_reveal)))
        draw.text((tx, group_y - top_top), top, font=top_font,
                  fill=(255, 255, 255, round(245 * top_reveal)))
    shadow = max(2, hero_font.size // 15)
    draw.text((hero_x + shadow, hero_y - hero_top + shadow), hero, font=hero_font,
              fill=(0, 0, 0, round(220 * hero_reveal)), stroke_width=stroke + 1,
              stroke_fill=(0, 0, 0, round(180 * hero_reveal)))
    draw.text((hero_x, hero_y - hero_top), hero, font=hero_font,
              fill=(255, 255, 255, round(255 * hero_reveal)), stroke_width=stroke,
              stroke_fill=(245, 245, 245, round(245 * hero_reveal)))
    if bottom:
        by = hero_y + hero_h + gap
        bx = (width - bottom_w) / 2
        draw.text((bx + 2, by - bottom_top + 3), bottom, font=bottom_font,
                  fill=(0, 0, 0, round(190 * bottom_reveal)))
        draw.text((bx, by - bottom_top), bottom, font=bottom_font,
                  fill=(255, 255, 255, round(255 * bottom_reveal)))

    # Camera push, directional entrance and defocused exit happen on the full composition.
    direction = -1 if seed % 2 else 1
    drift = direction * (1 - enter) * width * .13
    life = min(1.0, elapsed / max(.1, cue.end - cue.start))
    scale = .86 + .14 * enter + .025 * life + .08 * (1 - leave)
    crop = canvas.getbbox()
    if not crop:
        return canvas
    content = canvas.crop(crop)
    content = content.resize((max(1, round(content.width * scale)), max(1, round(content.height * scale))),
                             Image.Resampling.LANCZOS)
    blur = max(0.0, (1 - enter) * width / 70 + (1 - leave) * width / 85)
    if blur > .2:
        content = content.filter(ImageFilter.GaussianBlur(blur))
    alpha_factor = min(1.0, enter * 1.35, leave * 1.3)
    if alpha_factor < 1:
        content.putalpha(content.getchannel('A').point(lambda value: round(value * alpha_factor)))
    result = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    anchor_x = (crop[0] + crop[2]) / 2 + drift
    anchor_y = (crop[1] + crop[3]) / 2 + math.sin(life * math.pi) * height * .006
    result.alpha_composite(content, (round(anchor_x - content.width / 2),
                                     round(anchor_y - content.height / 2)))
    return result


def _draw_typography_one_v2(width, height, cue, seconds, font_id, position, size_scale,
                            word_colors=None):
    """A scene-based typography system distilled from all four supplied references."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    original_words = [word.text.strip('.,!?…:;\"\'') or word.text for word in cue.words]
    raw_words = [word.upper() for word in original_words]
    words = [word.strip('.,!?…:;\"\'') or word for word in raw_words]
    if not words:
        return Image.new('RGBA', (width, height), (0, 0, 0, 0))
    size_scale = min(1.8, max(.55, float(size_scale)))
    portraitish = height >= width
    main_target = round(width * (.225 if portraitish else .13) * size_scale)
    max_width = width * .86
    main_path = _font_path(font_file(font_id, 'typography_1'))
    small_path = _font_path('arialbd.ttf')
    handwriting_path = _font_path('Inkfree.ttf')
    scratch = ImageDraw.Draw(Image.new('RGBA', (width, height)))
    center_y = height * min(.90, max(.10, float(position)))
    seed = sum(ord(char) for char in cue.text)
    variant = round(cue.start * 30) % 8
    palette = [('#F12722', '#850B0B'), ('#F4B400', '#8E5D00'), ('#1769F5', '#07388F')]
    accent, deep = palette[round(cue.start * 100) % 3]
    chosen_colors = _safe_word_colors(cue, word_colors)

    def colored_tokens(text, fallback, word_indices=None):
        result = []
        used = set()
        for order,token in enumerate(text.split()):
            clean = _clean_word(token)
            match = next((index for index, source in enumerate(original_words)
                          if index not in used and _clean_word(source) == clean), None)
            if word_indices is not None:
                match=word_indices[order]
            if match is not None:
                used.add(match)
            result.append((token, chosen_colors[match] if match is not None and chosen_colors[match]
                           else fallback,match))
        return result

    def paint_tokens(draw, x, baseline, text, selected_font, fallback, alpha, outline=False,word_indices=None):
        cursor = x
        space = draw.textlength(' ', font=selected_font)
        for token, token_color,index in colored_tokens(text, fallback,word_indices):
            if index is not None and not _word_visible(cue,index,seconds):
                cursor += draw.textlength(token,font=selected_font)+space
                continue
            token_alpha=alpha
            if index is not None and _word_timing_mode.get()=='phrase':
                token_alpha=round(alpha*_ease_out((seconds-cue.words[index].start)/.24))
            if outline:
                draw.text((cursor, baseline), token, font=selected_font, fill=(0, 0, 0, 0),
                          stroke_width=max(1, round(selected_font.size * .012)),
                          stroke_fill=_color(token_color, token_alpha))
            else:
                draw.text((cursor, baseline), token, font=selected_font,
                          fill=_color(token_color, token_alpha))
            from .scene_capture import tag_draw
            tag_draw(draw,index,token,selected_font,(cursor,baseline),token_color,token_alpha/255,outline)
            cursor += draw.textlength(token, font=selected_font) + space

    def chunks(count):
        count = min(count, len(raw_words))
        return [' '.join(raw_words[round(i * len(raw_words) / count):round((i + 1) * len(raw_words) / count)])
                for i in range(count)]

    def font(text, target=main_target, limit=max_width, path=main_path):
        return _fit_font(scratch, [text], path, target, limit, max(12, round(target * .38)))

    def text_layer(text, selected_font, y, fill='#FFFFFF', outline=False, alpha=255,
                   shadow=True, x_shift=0,word_indices=None):
        layer = Image.new('RGBA', (width, height), (0, 0, 0, 0)); draw = ImageDraw.Draw(layer)
        stroke = 0
        tw, th, left, top = _text_metrics(draw, text, selected_font, stroke)
        x = (width - tw) / 2 + x_shift
        baseline = y - top
        if outline:
            ink = Image.new('RGBA', layer.size, (0, 0, 0, 0)); ink_draw = ImageDraw.Draw(ink)
            paint_tokens(ink_draw, x, baseline, text, selected_font, '#FFFFFF', alpha, outline=True,word_indices=word_indices)
            glow = ink.filter(ImageFilter.GaussianBlur(max(2, selected_font.size // 34)))
            glow.putalpha(glow.getchannel('A').point(lambda value: round(value * .16)))
            return Image.alpha_composite(glow, ink)
        ink = Image.new('RGBA', layer.size, (0, 0, 0, 0)); ink_draw = ImageDraw.Draw(ink)
        paint_tokens(ink_draw, x, baseline, text, selected_font, fill, alpha,word_indices=word_indices)
        glow = ink.filter(ImageFilter.GaussianBlur(max(2, selected_font.size // 28)))
        glow.putalpha(glow.getchannel('A').point(lambda value: round(value * .20)))
        return Image.alpha_composite(glow, ink)

    def bar_layer(text, selected_font, y, color=accent, back=deep, alpha=255, width_boost=1.0,word_indices=None):
        layer = Image.new('RGBA', (width, height), (0, 0, 0, 0)); draw = ImageDraw.Draw(layer)
        stroke = 0
        tw, th, left, top = _text_metrics(draw, text, selected_font, stroke)
        pad_x = selected_font.size * .14
        natural_width = (tw + 2 * pad_x) * width_boost
        minimum_width = min(width * .64, max(width * .46, tw * 1.28))
        bar_w = min(width * .92, max(natural_width, minimum_width))
        x1 = (width - bar_w) / 2; x2 = x1 + bar_w
        # The reference uses one flat color strip through the middle of the letters.
        # It is deliberately shorter than the glyphs and has no offset/extruded copy.
        y1 = y + th * .27; y2 = y + th * .79
        glow = Image.new('RGBA', layer.size, (0, 0, 0, 0)); gd = ImageDraw.Draw(glow)
        gd.rectangle((x1, y1, x2, y2), fill=_color(color, round(alpha * .42)))
        glow = glow.filter(ImageFilter.GaussianBlur(max(3, selected_font.size // 24)))
        glow.putalpha(glow.getchannel('A').point(lambda value: round(value * .34)))
        layer = Image.alpha_composite(layer, glow); draw = ImageDraw.Draw(layer)
        draw.rectangle((x1, y1, x2, y2), fill=_color(color, alpha))
        tx = (width - tw) / 2
        paint_tokens(draw, tx, y - top, text, selected_font, '#FFFFFF', alpha,word_indices=word_indices)
        return layer

    def sandwich_parts():
        start, end = hero_span(original_words)
        return (' '.join(raw_words[:start]), ' '.join(raw_words[start:end]),
                ' '.join(raw_words[end:]))

    def sandwich_layers(top, hero, bottom, *, outline=False, stripe=None, echo=False):
        top_count=len(top.split());hero_count=len(hero.split())
        top_ids=list(range(top_count));hero_ids=list(range(top_count,top_count+hero_count));bottom_ids=list(range(top_count+hero_count,len(cue.words)))
        hero_font = font(hero, main_target * 1.16, max_width)
        hero_h = _text_metrics(scratch, hero, hero_font)[1]
        small_font = font((top + ' ' + bottom).strip() or ' ', main_target * .27,
                          max_width, small_path)
        small_h = _text_metrics(scratch, top or bottom or ' ', small_font)[1]
        gap = main_target * .10
        total = hero_h + (small_h + gap if top else 0) + (small_h + gap if bottom else 0)
        hero_y = center_y - total / 2 + (small_h + gap if top else 0)
        rows = []
        if echo:
            echo_font = font(hero.split()[-1], main_target * 1.34, width * .94)
            rows.append((text_layer(hero.split()[-1], echo_font, hero_y + hero_h * .30,
                                    outline=True, alpha=54,word_indices=[hero_ids[-1]]), .01, 'right'))
        if top:
            rows.append((text_layer(top, small_font, hero_y - small_h - gap,word_indices=top_ids), .02, 'left'))
        maker = (lambda value, chosen, ypos: bar_layer(value, chosen, ypos, stripe, deep,word_indices=hero_ids)) if stripe else None
        hero_layer = maker(hero, hero_font, hero_y) if maker else text_layer(hero, hero_font, hero_y,
                                                                            outline=outline,word_indices=hero_ids)
        rows.append((hero_layer, .10, 'left'))
        if bottom:
            rows.append((text_layer(bottom, small_font, hero_y + hero_h + gap,word_indices=bottom_ids), .21, 'right'))
        return rows

    elements = []
    # Each phrase uses one of the exact visual grammars visible in the references.
    if variant == 0:  # Filled two-line hero with a faint outline echo behind it.
        setup_count = max(0, len(raw_words) - 3)
        top = ' '.join(raw_words[:setup_count])
        hero_words = raw_words[setup_count:]
        if len(hero_words) >= 3:
            upper, lower = ' '.join(hero_words[:-1]), hero_words[-1]
            upper_font = font(upper, main_target * 1.08, max_width)
            lower_font = font(lower, main_target * .94, max_width)
            upper_h = _text_metrics(scratch, upper, upper_font)[1]
            lower_h = _text_metrics(scratch, lower, lower_font)[1]
            small_font = font(top or ' ', main_target * .26, max_width, small_path)
            small_h = _text_metrics(scratch, top or ' ', small_font)[1] if top else 0
            total = small_h + upper_h + lower_h + main_target * .14
            y = center_y - total / 2
            echo_font = font(lower, main_target * 1.30, width * .94)
            elements.append((text_layer(lower, echo_font, y + small_h + upper_h * .72,
                                        outline=True, alpha=54,word_indices=[len(raw_words)-1]), .01, 'right'))
            if top:
                elements.append((text_layer(top, small_font, y,word_indices=list(range(setup_count))), .03, 'left'))
                y += small_h + main_target * .07
            elements.append((text_layer(upper, upper_font, y,word_indices=list(range(setup_count,len(raw_words)-1))), .10, 'left'))
            elements.append((text_layer(lower, lower_font, y + upper_h + main_target * .04,word_indices=[len(raw_words)-1]), .19, 'right'))
        else:
            top, hero, bottom = sandwich_parts()
            elements = sandwich_layers(top, hero, bottom, echo=True)
    elif variant == 1:  # Flat fact card: small top, giant fact, small bottom.
        start, end = hero_span(original_words)
        elements = sandwich_layers(' '.join(raw_words[:start]), ' '.join(raw_words[start:end]),
                                   ' '.join(raw_words[end:]), stripe='#F4B400')
    elif variant == 2:  # Hollow outline hero with aligned supporting lines.
        top, hero, bottom = sandwich_parts()
        elements = sandwich_layers(top, hero, bottom, outline=True)
    elif variant == 3:  # Semantic hero on a single wide red strip.
        top, hero, bottom = sandwich_parts()
        elements = sandwich_layers(top, hero, bottom, stripe='#F12722')
    elif variant == 4:  # Pure glow sandwich.
        top, hero, bottom = sandwich_parts()
        elements = sandwich_layers(top, hero, bottom)
    elif variant == 5:  # Natural handwriting + connector + flat blue hero strip.
        if len(original_words) == 1:
            elements = sandwich_layers('', raw_words[0], '', stripe='#1769F5')
        else:
            script_count = min(2, max(1, len(original_words) - 2))
            script_text = ' '.join(original_words[:script_count])
            remainder = raw_words[script_count:]
            hero_offset = important_word_index(remainder)
            connector = ' '.join(remainder[:hero_offset]); hero = remainder[hero_offset]
            bottom = ' '.join(remainder[hero_offset + 1:])
            script_font = font(script_text, main_target * .42, max_width, handwriting_path)
            hero_font = font(hero, main_target * 1.16, max_width)
            small_font = font((connector + ' ' + bottom).strip() or ' ', main_target * .26,
                              max_width, small_path)
            script_h = _text_metrics(scratch, script_text, script_font)[1]
            hero_h = _text_metrics(scratch, hero, hero_font)[1]
            small_h = _text_metrics(scratch, connector or bottom or ' ', small_font)[1]
            gap = main_target * .07
            total = script_h + hero_h + gap + (small_h + gap if connector else 0) + (small_h + gap if bottom else 0)
            y = center_y - total / 2
            elements.append((text_layer(script_text, script_font, y,word_indices=list(range(script_count))), .01, 'right')); y += script_h + gap
            if connector:
                elements.append((text_layer(connector, small_font, y,word_indices=list(range(script_count,script_count+hero_offset))), .09, 'left')); y += small_h + gap
            elements.append((bar_layer(hero, hero_font, y, '#1769F5', deep,word_indices=[script_count+hero_offset]), .16, 'left')); y += hero_h + gap
            if bottom:
                elements.append((text_layer(bottom, small_font, y,word_indices=list(range(script_count+hero_offset+1,len(raw_words)))), .25, 'right'))
    elif variant == 6:  # Filled hero with oversized outline echo.
        top, hero, bottom = sandwich_parts()
        elements = sandwich_layers(top, hero, bottom, echo=True)
    else:  # Clean aligned sandwich without a stripe.
        top, hero, bottom = sandwich_parts()
        elements = sandwich_layers(top, hero, bottom)

    elapsed = max(0.0, seconds - cue.start)
    remaining = max(0.0, cue.end - seconds)
    composition = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    for layer, delay, side in elements:
        linear = min(1.0, max(0.0, (elapsed - delay) / .24))
        if linear <= 0:
            continue
        bbox = layer.getbbox()
        if not bbox:
            continue
        item = layer.crop(bbox)
        resolve = _ease_out(linear)
        settle = _ease_out_back(linear)
        scale_x = .88 + .12 * settle
        scale_y = .94 + .06 * settle
        item = item.resize((max(1, round(item.width * scale_x)),
                            max(1, round(item.height * scale_y))), Image.Resampling.LANCZOS)
        entry_blur = (1 - resolve) * max(4, width / 72)
        if entry_blur > .25:
            item = item.filter(ImageFilter.GaussianBlur(entry_blur))
        alpha = min(1.0, linear * 1.65)
        if alpha < 1:
            item.putalpha(item.getchannel('A').point(lambda value: round(value * alpha)))
        direction = 1 if side == 'right' else -1
        slide = direction * (1 - resolve) * width * .032
        center_x = (bbox[0] + bbox[2]) / 2 + slide
        center_y_item = (bbox[1] + bbox[3]) / 2
        composition.alpha_composite(item, (round(center_x - item.width / 2),
                                            round(center_y_item - item.height / 2)))

    # The supplied reference settles after the short entrance.  It does not
    # float continuously.  Only the entrance and final defocus move the camera.
    enter = _ease_out(elapsed / .28)
    leave = 1 if _word_timing_mode.get()=='phrase' else _ease_out(remaining / .24)
    crop = composition.getbbox()
    if not crop:
        return composition
    content = composition.crop(crop)
    scale = .975 + .025 * _ease_out_back(elapsed / .28) - .018 * (1 - leave)
    content = content.resize((max(1, round(content.width * scale)), max(1, round(content.height * scale))),
                             Image.Resampling.LANCZOS)
    blur = (1 - enter) * width / 105 + (1 - leave) * width / 82
    if blur > .25:
        content = content.filter(ImageFilter.GaussianBlur(blur))
    opacity = min(1.0, enter * 1.7, leave * 1.55)
    if opacity < 1:
        content.putalpha(content.getchannel('A').point(lambda value: round(value * opacity)))
    direction = -1 if seed % 2 else 1
    x = (crop[0] + crop[2]) / 2 - content.width / 2 + direction * (1 - enter) * width * .025
    y = (crop[1] + crop[3]) / 2 - content.height / 2
    result = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    result.alpha_composite(content, (round(x), round(y)))
    return result


def _draw_typography_two(width, height, cue, seconds, font_id, position, size_scale,
                         word_colors=None):
    """Render the red-script/blue-signal choreography measured from ``as.mp4``."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    if not cue.words:
        return Image.new('RGBA', (width, height), (0, 0, 0, 0))
    colors = _safe_word_colors(cue, word_colors)
    texts = [word.text for word in cue.words]
    size_scale = min(1.8, max(.55, float(size_scale)))
    portraitish = height >= width
    # Measurements from the 1280x720 reference put the main signal text near
    # 90 px and the supporting words near 55-65 px.  The support is deliberately
    # substantial: it aligns with the strip instead of behaving like a footnote.
    main_size = max(18, round(width * (.115 if portraitish else .072) * size_scale))
    support_size = max(12, round(main_size * .70))
    bar_size = max(18, round(width * (.088 if portraitish else .055) * size_scale))
    main_path = _font_path(font_file(font_id, 'typography_2'))
    support_path = _font_path('arial.ttf') if font_id == 'template' else main_path
    # The reference letterforms (especially the long ``j`` descender and the
    # joined ``at`` in "jata") match Dancing Script, not Monotype Corsiva.
    script_path = _font_path('DancingScript-Regular.ttf') if font_id == 'template' else main_path
    support_font = ImageFont.truetype(str(support_path), support_size)
    bar_font = ImageFont.truetype(str(main_path), bar_size)
    bar_support_font = ImageFont.truetype(str(support_path), bar_size)
    scratch = ImageDraw.Draw(Image.new('RGBA', (width, height)))
    center_y = height * min(.90, max(.10, float(position)))
    elapsed = max(0.0, seconds - cue.start)
    remaining = max(0.0, cue.end - seconds)
    duration = max(.08, cue.end - cue.start)
    # In the supplied edit, compact one/two-word beats are the red calligraphy
    # scenes; longer speech groups use the blue signal strip.  A random choice
    # made identical text render differently and produced the rejected layouts.
    script_scene = len(texts) <= 2

    def fit(selected_font, values, maximum):
        text = ' '.join(values)
        current = selected_font
        while current.size > 10 and scratch.textbbox((0, 0), text, font=current)[2] > maximum:
            current = ImageFont.truetype(str(current.path), current.size - 1)
        return current

    def word_fill(index, fallback):
        return colors[index] or fallback

    composition = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(composition)
    enter = _ease_out(elapsed / .28)
    leave = 1 if _word_timing_mode.get()=='phrase' else _ease_out(remaining / .20)

    if script_scene:
        # The reference advances one red calligraphic word at a time and keeps
        # only one white neighbouring word on screen.  It never shrinks the
        # remainder of the sentence into a subtitle underneath.
        hero = 0
        hero_text = texts[hero]
        letters = sum(character.isalnum() for character in hero_text)
        script_scale = min(2.24, 1.80 + max(0, letters - 2) * .22)
        script_font = ImageFont.truetype(str(script_path),
                                         max(20, round(main_size * script_scale)))
        selected = fit(script_font, [hero_text], width * .76)
        bbox = scratch.textbbox((0, 0), hero_text, font=selected)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        support_index = 1 if len(texts) > 1 else None
        support_text = texts[support_index] if support_index is not None else ''
        sw = scratch.textbbox((0, 0), support_text, font=support_font)[2] if support_text else 0
        hero_y = center_y - th * .55
        hx = (width - tw) / 2
        ink = Image.new('RGBA', composition.size, (0, 0, 0, 0)); ink_draw = ImageDraw.Draw(ink)
        ink_draw.text((hx, hero_y - bbox[1]), hero_text, font=selected,
                      fill=_color(word_fill(hero, '#A73C2B'), _word_alpha(cue,hero,seconds,255)))
        from .scene_capture import tag_draw
        tag_draw(ink_draw,hero,hero_text,selected,(hx,hero_y-bbox[1]),word_fill(hero,'#A73C2B'),_word_alpha(cue,hero,seconds,1))
        glow = ink.filter(ImageFilter.GaussianBlur(max(2, round(selected.size * .045))))
        glow.putalpha(glow.getchannel('A').point(lambda value: round(value * .08)))
        composition = Image.alpha_composite(composition, glow)
        composition = Image.alpha_composite(composition, ink)
        if support_text:
            draw = ImageDraw.Draw(composition)
            # Every supplied two-word example shares the same right edge.  A
            # descender word such as "jata" leaves space at lower-right, while
            # "ek khas" and "ek mukam" sit immediately below the script word.
            side_support = any(character.lower() in 'gjpqy' for character in hero_text)
            cursor = hx + bbox[2] - sw - selected.size * .08
            baseline = (hero_y + th * .63 if side_support else
                        hero_y + th + selected.size * .06)
            draw.text((cursor, baseline), support_text, font=support_font,
                      fill=_color(word_fill(support_index, '#ABABA8'),
                                  _word_alpha(cue,support_index,seconds,round(255 * _ease_out(
                                      (seconds-cue.words[support_index].start)/.20
                                      if _word_timing_mode.get()=='phrase' else (elapsed-.10)/.20)))))
            tag_draw(draw,support_index,support_text,support_font,(cursor,baseline),word_fill(support_index,'#ABABA8'),_word_alpha(cue,support_index,seconds,_ease_out((seconds-cue.words[support_index].start)/.20)))
    else:
        count = len(texts)
        if count == 1:
            top_left, top_right, bar_indices = None, None, [0]
        elif count <= 3:
            top_left, top_right, bar_indices = 0, None, list(range(1, count))
        else:
            top_left, top_right, bar_indices = 0, count - 1, list(range(1, count - 1))
        if not bar_indices:
            bar_indices = [count - 1]
        reveal_step = max(.10, min(.20, duration * .10))
        visible_count = max(0, min(len(bar_indices), int(max(0, elapsed - .16) / reveal_step) + 1))
        visible_indices = bar_indices[:visible_count]
        if _word_timing_mode.get():visible_indices=bar_indices
        full_text = ' '.join(texts[index] for index in bar_indices)
        selected = fit(bar_font, [full_text], width * .72)
        space = scratch.textlength(' ', font=selected)
        full_width = sum(scratch.textlength(texts[index], font=selected) for index in bar_indices)
        full_width += space * max(0, len(bar_indices) - 1)
        pad_x = selected.size * .29
        target_width = min(width * .82, max(width * .09, full_width + pad_x * 2))
        bar_height = selected.size * 1.39
        bar_left = (width - target_width) / 2
        bar_top = center_y - bar_height / 2
        expansion = _ease_out((elapsed - .04) / .28)
        current_width = max(2, target_width * expansion)
        # The signal grows from a one-pixel caret into one flat, square-cornered strip.
        bar_alpha = round(255 * min(1, enter * 1.8))
        glow = Image.new('RGBA', composition.size, (0, 0, 0, 0)); glow_draw = ImageDraw.Draw(glow)
        glow_draw.rectangle((bar_left, bar_top, bar_left + current_width, bar_top + bar_height),
                            fill=_color('#137FF6', round(bar_alpha * .30)))
        glow = glow.filter(ImageFilter.GaussianBlur(max(2, round(selected.size * .08))))
        composition = Image.alpha_composite(composition, glow); draw = ImageDraw.Draw(composition)
        draw.rectangle((bar_left, bar_top, bar_left + current_width, bar_top + bar_height),
                       fill=_color('#137FF6', bar_alpha))
        if visible_indices:
            baseline = bar_top + (bar_height - selected.size) / 2 - scratch.textbbox((0, 0), 'Ag', font=selected)[1]
            cursor = bar_left + pad_x
            positions = []
            for order, index in enumerate(visible_indices):
                local = _ease_out((elapsed - .16 - order * reveal_step) / .16)
                if _word_timing_mode.get():
                    local=_ease_out((seconds-cue.words[index].start)/.16) if _word_visible(cue,index,seconds) else 0
                positions.append((cursor, index, local))
                cursor += draw.textlength(texts[index], font=selected) + space
            shadow_layer = Image.new('RGBA', composition.size, (0, 0, 0, 0))
            shadow_draw = ImageDraw.Draw(shadow_layer)
            for cursor, index, local in positions:
                shadow_draw.text((cursor + selected.size * .025, baseline + selected.size * .035),
                                 texts[index], font=selected,
                                 fill=_color('#000000', round(130 * local)))
            shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(max(1, selected.size * .025)))
            composition = Image.alpha_composite(composition, shadow_layer)
            draw = ImageDraw.Draw(composition)
            for cursor, index, local in positions:
                draw.text((cursor, baseline), texts[index], font=selected,
                          fill=_color(word_fill(index, '#FFFFFF'), round(255 * local)))
                from .scene_capture import tag_draw
                tag_draw(draw,index,texts[index],selected,(cursor,baseline),word_fill(index,'#FFFFFF'),local)
        top_y = bar_top - bar_support_font.size * 1.36
        if top_left is not None:
            local = _ease_out((elapsed - .04) / .20)
            local=_word_alpha(cue,top_left,seconds,local)
            draw.text((bar_left, top_y), texts[top_left], font=bar_support_font,
                      fill=_color(word_fill(top_left, '#FFFFFF'), round(255 * local)))
            from .scene_capture import tag_draw
            tag_draw(draw,top_left,texts[top_left],bar_support_font,(bar_left,top_y),word_fill(top_left,'#FFFFFF'),local)
        if top_right is not None:
            local = _ease_out((elapsed - .16 - len(bar_indices) * reveal_step) / .18)
            if _word_timing_mode.get():local=_ease_out((seconds-cue.words[top_right].start)/.18) if _word_visible(cue,top_right,seconds) else 0
            text_width = draw.textlength(texts[top_right], font=bar_support_font)
            right_x = bar_left + target_width - text_width
            if top_left is not None:
                left_width = draw.textlength(texts[top_left], font=bar_support_font)
                if left_width + text_width + bar_support_font.size * .18 > target_width:
                    right_x = bar_left + left_width + draw.textlength(' ', font=bar_support_font)
            draw.text((right_x, top_y), texts[top_right], font=bar_support_font,
                      fill=_color(word_fill(top_right, '#FFFFFF'), round(255 * local)))
            from .scene_capture import tag_draw
            tag_draw(draw,top_right,texts[top_right],bar_support_font,(right_x,top_y),word_fill(top_right,'#FFFFFF'),local)

    crop = composition.getbbox()
    if not crop:
        return composition
    content = composition.crop(crop)
    scale = .985 + .015 * _ease_out_back(elapsed / .28) - .012 * (1 - leave)
    content = content.resize((max(1, round(content.width * scale)), max(1, round(content.height * scale))),
                             Image.Resampling.LANCZOS)
    blur = (1 - enter) * width / 92 + (1 - leave) * width / 105
    if blur > .22:
        content = content.filter(ImageFilter.GaussianBlur(blur))
    opacity = min(1.0, enter * 1.8, leave * 1.7)
    if opacity < 1:
        content.putalpha(content.getchannel('A').point(lambda value: round(value * opacity)))
    result = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    x = (crop[0] + crop[2]) / 2 - content.width / 2 - (1 - enter) * width * .018
    y = (crop[1] + crop[3]) / 2 - content.height / 2
    result.alpha_composite(content, (round(x), round(y)))
    return result


def _draw_typography_three(width, height, cue, seconds, font_id, position, size_scale,
                           word_colors=None):
    """Render the measured bold-anchor composition from the Typography 3 reference."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    if not cue.words:
        return Image.new('RGBA', (width, height), (0, 0, 0, 0))
    texts = [word.text for word in cue.words]
    colors = _safe_word_colors(cue, word_colors)
    size_scale = min(1.8, max(.55, float(size_scale)))
    hero_index = _typography_three_anchor(texts)
    hero_path = _font_path(font_file(font_id, 'typography_3'))
    support_path = (_font_path('Roboto-Regular.ttf') if font_id == 'template'
                    else hero_path)
    # The supplied 720-wide portrait uses a 70 px Roboto Black anchor and
    # 29 px Roboto Regular support. These ratios preserve that measurement.
    portraitish = height >= width
    hero_size = max(16, round(width * (.0972 if portraitish else .055) * size_scale))
    support_size = max(10, round(hero_size * .414))
    hero_font = ImageFont.truetype(str(hero_path), hero_size)
    support_font = ImageFont.truetype(str(support_path), support_size)
    scratch = ImageDraw.Draw(Image.new('RGBA', (width, height)))

    top_indices = list(range(hero_index))
    bottom_indices = list(range(hero_index + 1, len(texts)))

    def line_width(indices, selected_font):
        if not indices:
            return 0.0
        space = scratch.textlength(' ', font=selected_font)
        return (sum(scratch.textlength(texts[index], font=selected_font) for index in indices) +
                space * (len(indices) - 1))

    maximum = width * .82
    while hero_font.size > 12:
        widest = max(scratch.textlength(texts[hero_index], font=hero_font),
                     line_width(top_indices, support_font),
                     line_width(bottom_indices, support_font))
        if widest <= maximum:
            break
        hero_size -= 1
        support_size = max(9, round(hero_size * .414))
        hero_font = ImageFont.truetype(str(hero_path), hero_size)
        support_font = ImageFont.truetype(str(support_path), support_size)

    def ink_metrics(text, selected_font):
        box = scratch.textbbox((0, 0), text, font=selected_font)
        return box[2] - box[0], box[3] - box[1], box[0], box[1]

    hero_w, hero_h, hero_left, hero_top = ink_metrics(texts[hero_index], hero_font)
    top_text = ' '.join(texts[index] for index in top_indices)
    bottom_text = ' '.join(texts[index] for index in bottom_indices)
    top_w, top_h, _, _ = ink_metrics(top_text, support_font) if top_text else (0, 0, 0, 0)
    bottom_w, bottom_h, _, _ = (ink_metrics(bottom_text, support_font)
                                if bottom_text else (0, 0, 0, 0))
    gap_above = max(1, round(hero_size * .025))
    gap_below = max(3, round(hero_size * .115))
    group_h = hero_h
    if top_indices:
        group_h += top_h + gap_above
    if bottom_indices:
        group_h += bottom_h + gap_below
    center_y = height * min(.92, max(.08, float(position)))
    group_y = center_y - group_h / 2
    hero_y = group_y + (top_h + gap_above if top_indices else 0)
    top_y = group_y
    bottom_y = hero_y + hero_h + gap_below
    group_w = max(hero_w, top_w, bottom_w)
    group_x = (width - group_w) / 2

    composition = Image.new('RGBA', (width, height), (0, 0, 0, 0))

    def draw_word(index, x, ink_y, selected_font, bbox_top):
        if not _word_visible(cue,index,seconds):return
        # The reference does not fly the phrase in or shrink it away. Each new
        # word blooms at its final location: dim and heavily defocused, quickly
        # overshooting its final size, then locking into focus after ~7 frames.
        local_elapsed = seconds - cue.words[index].start
        progress = min(1.0, max(0.0, local_elapsed / .28))
        if progress <= 0:
            return
        reveal = _ease_out(local_elapsed / .22)
        settle = _ease_out_back(progress, 2.1)
        scale = max(.04, .55 + .45 * settle)
        fill = colors[index] or '#FFFFFF'
        box = scratch.textbbox((0, 0), texts[index], font=selected_font)
        ink_w, ink_h = box[2] - box[0], box[3] - box[1]
        pad = max(6, round(selected_font.size * .30))
        tile = Image.new('RGBA', (max(1, ink_w + pad * 2), max(1, ink_h + pad * 2)),
                         (0, 0, 0, 0))
        tile_draw = ImageDraw.Draw(tile)
        offset = max(1, round(selected_font.size * .035))
        origin = (pad - box[0], pad - box[1])
        tile_draw.text((origin[0] + offset, origin[1] + offset), texts[index],
                       font=selected_font, fill=(0, 0, 0, round(145 * reveal)))
        tile_draw.text(origin, texts[index], font=selected_font,
                       fill=_color(fill, round(255 * reveal)))
        from .scene_capture import tag_draw
        tag_draw(tile_draw,index,texts[index],selected_font,origin,fill,reveal)
        tile = tile.resize((max(1, round(tile.width * scale)),
                            max(1, round(tile.height * scale))), Image.Resampling.LANCZOS)
        focus = progress * progress * (3 - 2 * progress)
        local_blur = (1 - focus) * max(2.4, selected_font.size * .23)
        if local_blur > .2:
            tile = tile.filter(ImageFilter.GaussianBlur(local_blur))
        center_x = x + (box[0] + box[2]) / 2
        center_y = ink_y + ink_h / 2
        composition.alpha_composite(tile, (round(center_x - tile.width / 2),
                                           round(center_y - tile.height / 2)))

    def draw_line(indices, y, selected_font):
        cursor = group_x
        space = scratch.textlength(' ', font=selected_font)
        for index in indices:
            box = scratch.textbbox((0, 0), texts[index], font=selected_font)
            draw_word(index, cursor, y, selected_font, box[1])
            cursor += scratch.textlength(texts[index], font=selected_font) + space

    if top_indices:
        draw_line(top_indices, top_y, support_font)
    draw_word(hero_index, group_x, hero_y, hero_font, hero_top)
    if bottom_indices:
        draw_line(bottom_indices, bottom_y, support_font)

    halo = composition.filter(ImageFilter.GaussianBlur(max(.7, hero_size * .025)))
    halo.putalpha(halo.getchannel('A').point(lambda value: round(value * .13)))
    composition = Image.alpha_composite(halo, composition)

    from .kinetic import zoom_group
    return zoom_group(composition, seconds-cue.words[hero_index].start,
                      (width/2, center_y))


def _draw_typography_four(width, height, cue, seconds, font_id, position, size_scale,
                          word_colors=None):
    """Render Typography 4's fixed two-line layout and six-frame word fades."""
    from PIL import Image, ImageDraw, ImageFont

    if not cue.words:
        return Image.new('RGBA', (width, height), (0, 0, 0, 0))
    texts = [word.text for word in cue.words]
    colors = _safe_word_colors(cue, word_colors)
    size_scale = min(1.8, max(.55, float(size_scale)))
    font_path = _font_path(font_file(font_id, 'typography_4'))
    portraitish = height >= width
    target_size = max(14, round(width * (.068 if portraitish else .040) * size_scale))
    scratch = ImageDraw.Draw(Image.new('L', (width, height), 0))
    font = ImageFont.truetype(str(font_path), target_size)
    # Keep the font's original kerning and letter spacing inside every word.
    # Only the blank between complete words is tightened slightly, as requested.
    def word_space(selected_font):
        return scratch.textlength(' ', font=selected_font) * .82
    top_indices = list(range(max(0, len(texts) - 1)))
    accent_index = len(texts) - 1

    def line_width(indices, selected_font):
        if not indices:
            return 0.0
        return (sum(scratch.textlength(texts[index], font=selected_font) for index in indices) +
                word_space(selected_font) * (len(indices) - 1))

    maximum = width * .84
    while font.size > 11 and max(line_width(top_indices, font),
                                 scratch.textlength(texts[accent_index], font=font)) > maximum:
        font = ImageFont.truetype(str(font_path), font.size - 1)

    def ink_box(text):
        return scratch.textbbox((0, 0), text, font=font)

    top_boxes = [ink_box(texts[index]) for index in top_indices]
    accent_box = ink_box(texts[accent_index])
    top_height = max((box[3] - box[1] for box in top_boxes), default=0)
    accent_height = accent_box[3] - accent_box[1]
    gap = max(2, round(font.size * .10)) if top_indices else 0
    group_height = top_height + gap + accent_height
    center_y = height * min(.92, max(.08, float(position)))
    group_top = center_y - group_height / 2
    top_y = group_top
    accent_y = group_top + top_height + gap
    image = Image.new('RGBA', (width, height), (0, 0, 0, 0))

    def reveal(index):
        # The 25 fps reference adds roughly 1/6 opacity per frame and reaches
        # full opacity on frame six. Its phrases then cut without an outro.
        if not _word_visible(cue,index,seconds):return 0
        return min(1.0, max(0.0, (seconds - cue.words[index].start) / .24))

    def word_mask(index, x, ink_y):
        box = ink_box(texts[index])
        mask = Image.new('L', (width, height), 0)
        draw = ImageDraw.Draw(mask)
        draw.text((x - box[0], ink_y - box[1]), texts[index], font=font, fill=255)
        opacity = reveal(index)
        if opacity < 1:
            mask = mask.point(lambda value: round(value * opacity))
        return mask

    def composite_solid(index, x, ink_y, fallback):
        opacity = reveal(index)
        if opacity <= 0:
            return
        mask = word_mask(index, x, ink_y)
        fill = Image.new('RGBA', (width, height), _color(colors[index] or fallback, 255))
        fill.putalpha(mask)
        from .scene_capture import tag
        box=ink_box(texts[index])
        fill=tag(fill,index,texts[index],font,x-box[0],ink_y-box[1]+font.getmetrics()[0],color=colors[index] or fallback,alpha=opacity)
        image.alpha_composite(fill)

    if top_indices:
        top_width = line_width(top_indices, font)
        cursor = (width - top_width) / 2
        for index in top_indices:
            composite_solid(index, cursor, top_y, '#F4F4F4')
            cursor += scratch.textlength(texts[index], font=font) + word_space(font)

    accent_width = scratch.textlength(texts[accent_index], font=font)
    accent_x = (width - accent_width) / 2
    if colors[accent_index]:
        composite_solid(accent_index, accent_x, accent_y, colors[accent_index])
    elif reveal(accent_index) > 0:
        mask = word_mask(accent_index, accent_x, accent_y)
        gradient = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        pixels = gradient.load()
        start_y = max(0, round(accent_y))
        end_y = min(height, max(start_y + 1, round(accent_y + accent_height)))
        top_rgb = (244, 244, 244)
        bottom_rgb = (82, 199, 255)
        grad_draw = ImageDraw.Draw(gradient)
        for y in range(start_y, end_y):
            mix = (y - start_y) / max(1, end_y - start_y - 1)
            rgb = tuple(round(a + (b - a) * mix) for a, b in zip(top_rgb, bottom_rgb))
            grad_draw.line((0, y, width, y), fill=rgb + (255,))
        gradient.putalpha(mask)
        from .scene_capture import tag
        box=ink_box(texts[accent_index])
        gradient=tag(gradient,accent_index,texts[accent_index],font,accent_x-box[0],accent_y-box[1]+font.getmetrics()[0],gradient=[[0,'#F4F4F4'],[1,'#52C7FF']],alpha=reveal(accent_index))
        image.alpha_composite(gradient)
    from .kinetic import zoom_group
    return zoom_group(image, seconds-cue.words[accent_index].start,
                      (width/2, center_y))


def _draw_typography_five(width, height, cue, seconds, font_id, position, size_scale,
                          word_colors=None):
    """Render Typography 5's red calligraphic hero and interlocking support lines."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    if not cue.words:
        return Image.new('RGBA', (width, height), (0, 0, 0, 0))
    texts = [word.text for word in cue.words]
    colors = _safe_word_colors(cue, word_colors)
    geometry=template('typography_5')['reference_geometry']
    recipe=next((r for r in template('typography_5')['reference_recipes']
                 if [_clean_word(w) for w in texts]==[_clean_word(w) for w in r['text'].split()]),{})
    from .template_patterns import rebound
    if rebound(texts):recipe={}
    if not recipe:
        from .template_patterns import transfer
        recipe=transfer(texts,template('typography_5')['reference_recipes']) or {}
    size_scale = min(1.8, max(.55, float(size_scale)))
    hero_index = _typography_five_anchor(texts)
    # Great Vibes is the measured face in the reference. At 720 px wide the
    # source uses about 120 px script and 36 px Arial support.
    script_path = _font_path('GreatVibes-Regular.ttf')
    support_path = (_font_path('arial.ttf') if font_id == 'template'
                    else _font_path(font_file(font_id, 'typography_5')))
    script_size = max(24, round(width * .1667 * size_scale))
    support_size = max(12, round(width * .1667 * geometry['support_ratio'] * size_scale))
    script_font = ImageFont.truetype(str(script_path), script_size)
    support_font = ImageFont.truetype(str(support_path), support_size)
    scratch = ImageDraw.Draw(Image.new('L', (width, height), 0))
    top_indices = list(range(hero_index))
    bottom_indices = list(range(hero_index + 1, len(texts)))

    def word_space(selected_font):
        return scratch.textlength(' ', font=selected_font) * .92

    def line_width(indices, selected_font):
        if not indices:
            return 0.0
        return (sum(scratch.textlength(texts[index], font=selected_font) for index in indices)
                + word_space(selected_font) * (len(indices) - 1))

    def fit_fonts():
        nonlocal script_size, support_size, script_font, support_font
        maximum = width * .86
        while script_size > 20:
            widest = max(scratch.textlength(texts[hero_index], font=script_font),
                         line_width(top_indices, support_font),
                         line_width(bottom_indices, support_font))
            if widest <= maximum:
                return
            script_size -= 1
            support_size = max(11, round(script_size * geometry['support_ratio']))
            script_font = ImageFont.truetype(str(script_path), script_size)
            support_font = ImageFont.truetype(str(support_path), support_size)

    fit_fonts()
    hero_box = scratch.textbbox((0, 0), texts[hero_index], font=script_font)
    hero_w, hero_h = hero_box[2] - hero_box[0], hero_box[3] - hero_box[1]
    top_w = line_width(top_indices, support_font)
    bottom_w = line_width(bottom_indices, support_font)
    center_y = height * min(.92, max(.08, float(position)))
    # The reference shares font origins, so support overlaps the tall script
    # ascenders. A descender (hai,) can also tuck into the following line.
    script_origin_y = 0.0
    top_origin_y = script_size * geometry['top_origin']
    bottom_origin_y = script_size * geometry['bottom_origin']
    hero_ink_y = script_origin_y + hero_box[1]
    top_box = scratch.textbbox((0, 0), ' '.join(texts[i] for i in top_indices) or 'H', font=support_font)
    bottom_box = scratch.textbbox((0, 0), ' '.join(texts[i] for i in bottom_indices) or 'H', font=support_font)
    top_ink_y = top_origin_y + top_box[1]
    bottom_ink_y = bottom_origin_y + bottom_box[1]
    group_top = min(hero_ink_y, top_ink_y if top_indices else hero_ink_y)
    group_bottom = max(hero_ink_y + hero_h,
                       bottom_origin_y + bottom_box[3] if bottom_indices else hero_ink_y + hero_h)
    offset = center_y - (group_top + group_bottom) / 2
    hero_ink_y += offset
    top_origin_y += offset
    bottom_origin_y += offset

    hero_x = (width - hero_w) / 2
    inset = script_size * geometry['inset']
    top_x = hero_x + inset
    bottom_x = hero_x + hero_w - bottom_w - script_size*recipe.get('bottom_inset',geometry['inset'])
    if _clean_word(texts[hero_index]) in geometry['centered_headers']:
        top_x=hero_x+(hero_w-top_w)/2

    # Shift the complete arrangement into a clean 7% safe area without changing
    # the relationships between its lines.
    used = [(hero_x, hero_x + hero_w)]
    if top_indices:
        used.append((top_x, top_x + top_w))
    if bottom_indices:
        used.append((bottom_x, bottom_x + bottom_w))
    left, right = min(item[0] for item in used), max(item[1] for item in used)
    safe_left, safe_right = width * .07, width * .93
    shift = max(0.0, safe_left - left) + min(0.0, safe_right - right)
    hero_x += shift
    top_x += shift
    bottom_x += shift

    image = Image.new('RGBA', (width, height), (0, 0, 0, 0))

    def draw_word(index, x, ink_y, selected_font, fallback):
        if not _word_visible(cue,index,seconds):return
        local = seconds - cue.words[index].start
        progress = min(1.0, max(0.0, local / .28))
        if progress <= 0:
            return
        show = _ease_out(local / .24)
        focus = progress * progress * (3 - 2 * progress)
        scale = .94 + .06 * _ease_out(progress)
        box = scratch.textbbox((0, 0), texts[index], font=selected_font)
        ink_w, ink_h = box[2] - box[0], box[3] - box[1]
        pad = max(8, round(selected_font.size * .18))
        tile = Image.new('RGBA', (max(1, ink_w + pad * 2), max(1, ink_h + pad * 2)),
                         (0, 0, 0, 0))
        tile_draw = ImageDraw.Draw(tile)
        origin = (pad - box[0], pad - box[1])
        tile_draw.text(origin, texts[index], font=selected_font,
                       fill=_color(colors[index] or fallback, round(255 * show)))
        from .scene_capture import tag_draw
        tag_draw(tile_draw,index,texts[index],selected_font,origin,colors[index] or fallback,show)
        if scale != 1:
            tile = tile.resize((max(1, round(tile.width * scale)),
                                max(1, round(tile.height * scale))), Image.Resampling.LANCZOS)
        blur = (1 - focus) * max(1.5, selected_font.size * .075)
        if blur > .18:
            tile = tile.filter(ImageFilter.GaussianBlur(blur))
        center_x = x + ink_w / 2
        center_word_y = ink_y + ink_h / 2
        image.alpha_composite(tile, (round(center_x - tile.width / 2),
                                     round(center_word_y - tile.height / 2)))

    def draw_line(indices, x, origin_y):
        cursor = x
        for index in indices:
            word_box = scratch.textbbox((0, 0), texts[index], font=support_font)
            draw_word(index, cursor + word_box[0], origin_y + word_box[1], support_font, '#F4F4F4')
            cursor += scratch.textlength(texts[index], font=support_font) + word_space(support_font)

    if top_indices:
        draw_line(top_indices, top_x, top_origin_y)
    draw_word(hero_index, hero_x, hero_ink_y, script_font, '#EF4937')
    if bottom_indices:
        draw_line(bottom_indices, bottom_x, bottom_origin_y)
    return image


def draw_caption(width, height, cue, seconds, style_name, font_id='template', position=.70,
                 size_scale=1.0, word_colors=None,word_visibility='phrase'):
    from .template_patterns import source_text,source_slot
    pattern_token=source_text.set(cue.template_source or cue.text)
    slot_token=source_slot.set(cue.template_slot)
    token=_word_timing_mode.set(word_visibility)
    try:
        if word_visibility=='phrase' and template(style_name).get('layout') and not cue.start<=seconds<cue.end:
            from PIL import Image
            return Image.new('RGBA',(width,height),(0,0,0,0))
        return _draw_caption(width,height,cue,seconds,style_name,font_id,position,size_scale,word_colors)
    finally:
        _word_timing_mode.reset(token)
        source_text.reset(pattern_token)
        source_slot.reset(slot_token)


def _draw_caption(width, height, cue, seconds, style_name, font_id='template', position=.70,
                  size_scale=1.0, word_colors=None):
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    style = template(style_name)
    if style.get('layout')=='cinematic_reference':
        from .cinematic_reference import render
        return render(width,height,cue,seconds,style_name,font_id,position,size_scale,word_colors,_word_timing_mode.get() or 'phrase')
    if style.get('layout')=='kinetic_gold':
        from .kinetic_gold import render
        return render(width,height,cue,seconds,font_id,position,size_scale,word_colors,_word_timing_mode.get() or 'phrase')
    if style.get('layout')=='serif_circle':
        from .serif_circle import render
        return render(width,height,cue,seconds,font_id,position,size_scale,word_colors,_word_timing_mode.get() or 'phrase')
    maximum = style.get('max_words', 5)
    if len(cue.words) > maximum and not _editor_composition.get() and style.get('layout') not in ('caption_three','caption_four','caption_five'):
        raise ValueError(f'A caption frame cannot contain more than {maximum} words')
    if style.get('layout') == 'caption_five':
        from .caption_five import render
        result=render(width,height,cue,seconds,font_id,position,word_colors,
                      _word_timing_mode.get() or 'phrase')
        if size_scale!=1:
            scale=max(.08,min(4,float(size_scale)))
            result=result.transform((width,height),Image.Transform.AFFINE,
                (1/scale,0,width*.5-width*.5/scale,0,1/scale,height*position-height*position/scale),
                resample=Image.Resampling.BICUBIC)
        return result
    if style.get('layout') == 'caption_four':
        from .caption_four import render
        result=render(width,height,cue,seconds,font_id,position,word_colors,
                      _word_timing_mode.get() or 'phrase')
        if size_scale!=1:
            scale=max(.08,min(4,float(size_scale)))
            result=result.transform((width,height),Image.Transform.AFFINE,
                (1/scale,0,width*.5-width*.5/scale,0,1/scale,height*position-height*position/scale),
                resample=Image.Resampling.BICUBIC)
        return result
    if style.get('layout') == 'caption_three':
        from .caption_three import render
        result=render(width,height,cue,seconds,font_id,position,word_colors,
                      _word_timing_mode.get() or 'phrase')
        if size_scale!=1:
            scale=max(.08,min(4,float(size_scale)))
            result=result.transform((width,height),Image.Transform.AFFINE,
                (1/scale,0,width*.5-width*.5/scale,0,1/scale,height*position-height*position/scale),
                resample=Image.Resampling.BICUBIC)
        return result
    if style.get('layout') == 'caption_two':
        from .caption_two import render
        result=render(width,height,cue,seconds,font_id,position,word_colors,
                      _word_timing_mode.get() or 'phrase')
        if size_scale!=1:
            scale=max(.08,min(4,float(size_scale)))
            result=result.transform((width,height),Image.Transform.AFFINE,
                (1/scale,0,width*.5-width*.5/scale,0,1/scale,height*position-height*position/scale),
                resample=Image.Resampling.BICUBIC)
        return result
    if style.get('layout') == 'caption_one':
        from .caption_one import render
        result = render(width, height, cue, seconds, font_id, position, word_colors,
                        _word_timing_mode.get() or 'phrase')
        if size_scale != 1:
            scale = max(.08, min(4, float(size_scale)))
            result = result.transform((width, height), Image.Transform.AFFINE,
                (1/scale, 0, width*.5-width*.5/scale,
                 0, 1/scale, height*position-height*position/scale),
                resample=Image.Resampling.BICUBIC)
        return result
    if style.get('layout') == 'kinetic_documentary':
        from .kinetic import render
        result = render(width, height, cue, seconds, font_id, position, word_colors,
                        _word_timing_mode.get() or 'phrase', style_name)
        if size_scale != 1:
            scale = max(.08, min(4, float(size_scale)))
            result = result.transform((width, height), Image.Transform.AFFINE,
                (1/scale, 0, width*.5-width*.5/scale,
                 0, 1/scale, height*position-height*position/scale),
                resample=Image.Resampling.BICUBIC)
        return result
    if style.get('layout') == 'typography_1':
        return _draw_typography_one_v2(width, height, cue, seconds, font_id, position, size_scale,
                                       word_colors)
    if style.get('layout') == 'typography_2':
        return _draw_typography_two(width, height, cue, seconds, font_id, position, size_scale,
                                    word_colors)
    if style.get('layout') == 'typography_3':
        return _draw_typography_three(width, height, cue, seconds, font_id, position, size_scale,
                                      word_colors)
    if style.get('layout') == 'typography_4':
        return _draw_typography_four(width, height, cue, seconds, font_id, position, size_scale,
                                     word_colors)
    if style.get('layout') == 'typography_5':
        return _draw_typography_five(width, height, cue, seconds, font_id, position, size_scale,
                                     word_colors)
    image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    active = active_word(cue, seconds)
    visible_words = (cue.words[active],) if style.get('one_word') else cue.words
    if style.get('one_word'):
        active = 0
    texts = [w.text.upper() if style['case'] == 'upper' else w.text for w in visible_words]
    font_path = _font_path(font_file(font_id, style_name))
    # Scale down cleanly for proxy/test footage as well as 1080p and 4K media.
    size_scale = min(1.8, max(.55, float(size_scale)))
    target = max(10, round(width * (.056 if width >= height else .078) * size_scale))
    base_font = _fit_font(draw, texts, font_path, target, width * .86, max(8, round(target * .58)))
    elapsed = max(0.0, seconds - cue.words[active].start)
    pop = 1 + .12 * max(0, 1 - elapsed / .14) * math.sin(min(1, elapsed / .14) * math.pi)
    fonts = [base_font] * len(texts)
    if not style.get('no_pop'):
        active_path = font_path
        if font_id == 'template' and style.get('active_font'):
            active_path = _font_path(style['active_font'])
        fonts[active] = ImageFont.truetype(str(active_path), max(12, round(base_font.size * pop)))
    spacing = max(8, base_font.size // 5)
    metrics = [_text_metrics(draw, text, font, max(1, font.size // 25))
               for text, font in zip(texts, fonts)]
    widths = [item[0] for item in metrics]
    total = sum(widths) + spacing * (len(widths) - 1)
    x = (width - total) / 2
    max_height = max(item[1] for item in metrics)
    center_y = height * min(.92, max(.10, float(position)))
    safe_bottom = max(3, round(height * .045))
    y = min(center_y - max_height / 2, height - max_height - safe_bottom)
    y = max(max(2, round(height * .035)), y)
    if style['surface']:
        pad_x, pad_y = base_font.size * .42, base_font.size * .22
        draw.rounded_rectangle((x - pad_x, y - pad_y, x + total + pad_x, y + max_height + pad_y),
                               radius=base_font.size * .38, fill=_color(style['surface'], 245))
    if style_name == 'neon':
        glow = Image.new('RGBA', image.size, (0, 0, 0, 0)); gd = ImageDraw.Draw(glow); gx = x
        for index, (text, font, word_width, metric) in enumerate(zip(texts, fonts, widths, metrics)):
            word_y = y - metric[3]
            gd.text((gx, word_y), text, font=font, fill=_color(style['accent'], 210), stroke_width=5,
                    stroke_fill=_color(style['accent'], 190))
            gx += word_width + spacing
        image = Image.alpha_composite(glow.filter(ImageFilter.GaussianBlur(max(6, base_font.size // 7))), image)
        draw = ImageDraw.Draw(image)
    for index, (text, font, word_width, metric) in enumerate(zip(texts, fonts, widths, metrics)):
        word_y = y - metric[3]
        fill = _color(style['accent'] if index == active else style['base'])
        if style['surface']:
            stroke, shadow = 0, 0
        else:
            stroke, shadow = max(2, font.size // 24), max(2, font.size // 18)
            draw.text((x + shadow, word_y + shadow), text, font=font, fill=(0, 0, 0, 150),
                      stroke_width=stroke + 2, stroke_fill=(0, 0, 0, 115))
        draw.text((x, word_y), text, font=font, fill=fill, stroke_width=stroke,
                  stroke_fill=(10, 10, 12, 220))
        from .scene_capture import tag_draw
        tag_draw(draw,index,text,font,(x,word_y),'#'+bytes(fill[:3]).hex(),stroke_width=stroke,stroke_color='#0A0A0C')
        if style_name == 'karaoke' and index == active:
            line_y = min(height - 3, y + metric[1] + max(1, font.size * .08))
            draw.rounded_rectangle((x, line_y, x + word_width, line_y + max(3, font.size // 12)),
                                   radius=3, fill=_color(style['accent']))
        x += word_width + spacing
    return image


from contextvars import ContextVar
_editor_composition=ContextVar('editor_composition',default=False)


def draw_editor_caption(width,height,cue,seconds,style_name,font_id,layout,visibility,word_colors=None):
    """Free positioning/scaling shared by interactive previews and real exports."""
    from PIL import Image,ImageDraw,ImageFont
    canvas=Image.new('RGBA',(width,height),(0,0,0,0))
    if not cue.start<=seconds<cue.end:return canvas
    if visibility=='styled_spoken' and not any(word.start<=seconds<word.end for word in cue.words):return canvas
    if visibility=='spoken':
        index=next((i for i,word in enumerate(cue.words) if word.start<=seconds<word.end),None)
        if index is None:return canvas
        style=template(style_name);word=cue.words[index]
        size=max(2,round(width*(.078 if height>width else .056)*layout['size']))
        font=ImageFont.truetype(str(_font_path(font_file(font_id,style_name))),size)
        text=word.text.upper() if style.get('case')=='upper' else word.text
        stroke=max(1,round(size/24));draw=ImageDraw.Draw(canvas)
        box=draw.textbbox((0,0),text,font=font,stroke_width=stroke)
        x=width*layout['x']-(box[2]-box[0])/2-box[0]
        y=height*layout['y']-(box[3]-box[1])/2-box[1]
        colors=_safe_word_colors(cue,word_colors);color=colors[index] or style['base']
        draw.text((x,y),text,font=font,fill=_color(color),stroke_width=stroke,stroke_fill=(10,10,12,230))
        from .scene_capture import tag_draw
        tag_draw(draw,index,text,font,(x,y),color,stroke_width=stroke,stroke_color='#0A0A0C')
        return canvas
    # Transform the original full composition about its design anchor. Cropping
    # to the changing ink bounds and recentering each frame erased camera motion
    # and moved progressive words as they appeared.
    native_y=template(style_name).get('default_position',.70)
    token=_editor_composition.set(True)
    try:
        original=draw_caption(width,height,cue,seconds,style_name,font_id,native_y,1,word_colors,word_visibility=visibility)
    finally:
        _editor_composition.reset(token)
    scale=float(layout['size'])
    if scale==1 and layout['x']==.5 and layout['y']==native_y:
        return original
    dx=width*(layout['x']-.5);dy=height*(layout['y']-native_y)
    if scale==1 and abs(dx-round(dx))<1e-8 and abs(dy-round(dy))<1e-8:
        canvas.paste(original,(round(dx),round(dy)))
        return canvas
    inverse=(1/scale,0,width*.5-width*layout['x']/scale,
             0,1/scale,height*native_y-height*layout['y']/scale)
    return original.transform((width,height),Image.Transform.AFFINE,inverse,
                              resample=Image.Resampling.BICUBIC)


def render_overlay(path, cues, width, height, duration, fps=30, style_name='punch', progress=print,
                   font_id='template', position=.70, size_scale=1.0, word_colors=None,
                   cue_layouts=None,word_visibility='phrase',device='cpu'):
    if device == 'cuda':
        raise RuntimeError('Transparent caption MOV export has no GPU encoder in this path. CPU fallback is disabled. Keep the editable captions and use the GPU video preview or native editable Adobe export.')
    import av
    import numpy as np
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.stem + '.partial.mov')
    if partial.exists(): partial.unlink()
    cue_index = 0
    frame_rate = Fraction(fps)
    total = max(1, math.ceil(duration * float(frame_rate)))
    with av.open(str(partial), 'w', format='mov') as output:
        stream = output.add_stream('qtrle', rate=frame_rate)
        stream.width, stream.height, stream.pix_fmt = width, height, 'argb'
        blank = None
        for number in range(total):
            seconds = number / float(frame_rate)
            while cue_index < len(cues) and seconds >= cues[cue_index].end:
                cue_index += 1
            cue = cues[cue_index] if cue_index < len(cues) and cues[cue_index].start <= seconds < cues[cue_index].end else None
            if cue:
                cue_colors = word_colors[cue_index] if word_colors and cue_index < len(word_colors) else None
                if cue_layouts is not None or word_visibility in ('spoken','styled_spoken'):
                    layout=cue_layouts[cue_index] if cue_layouts is not None else {'x':.5,'y':position,'size':size_scale}
                    image=draw_editor_caption(width,height,cue,seconds,style_name,font_id,layout,word_visibility,cue_colors)
                else:image=draw_caption(width,height,cue,seconds,style_name,font_id,position,size_scale,cue_colors)
                pixels = np.asarray(image, dtype=np.uint8)
            else:
                if blank is None: blank = np.zeros((height, width, 4), dtype=np.uint8)
                pixels = blank
            frame = av.VideoFrame.from_ndarray(pixels, format='rgba').reformat(format='argb')
            frame.pts, frame.time_base = number, 1 / frame_rate
            for packet in stream.encode(frame): output.mux(packet)
            if number % max(1, round(float(frame_rate) * 4)) == 0:
                progress(f'  Rendering captions {min(100, round(number / total * 100))}%')
        for packet in stream.encode(): output.mux(packet)
    partial.replace(path)
    progress('  Rendering captions 100%')
