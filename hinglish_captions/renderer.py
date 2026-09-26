from fractions import Fraction
from pathlib import Path
import math

from .core import active_word
from .styles import font_file, template


def _color(value, alpha=255):
    value = value.lstrip('#')
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4)) + (alpha,)


def _font_path(name):
    path = Path(r'C:\Windows\Fonts') / name
    if not path.is_file():
        raise ValueError('Required Windows font is missing: ' + name)
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


def _draw_typography_one_v2(width, height, cue, seconds, font_id, position, size_scale):
    """A scene-based typography system distilled from all four supplied references."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    raw_words = [word.text.upper() for word in cue.words]
    words = [word.strip('.,!?…:;\"\'') or word for word in raw_words]
    if not words:
        return Image.new('RGBA', (width, height), (0, 0, 0, 0))
    size_scale = min(1.8, max(.55, float(size_scale)))
    portraitish = height >= width
    main_target = round(width * (.29 if portraitish else .15) * size_scale)
    max_width = width * .88
    main_path = _font_path(font_file(font_id, 'typography_1'))
    small_path = _font_path('arialbd.ttf')
    script_path = _font_path('segoesc.ttf')
    scratch = ImageDraw.Draw(Image.new('RGBA', (width, height)))
    center_y = height * min(.90, max(.10, float(position)))
    seed = sum(ord(char) for char in cue.text)
    variant = round(cue.start * 30) % 8
    palette = [('#F12722', '#850B0B'), ('#F4B400', '#8E5D00'), ('#1769F5', '#07388F')]
    accent, deep = palette[round(cue.start * 100) % 3]

    def chunks(count):
        count = min(count, len(raw_words))
        return [' '.join(raw_words[round(i * len(raw_words) / count):round((i + 1) * len(raw_words) / count)])
                for i in range(count)]

    def font(text, target=main_target, limit=max_width, path=main_path):
        return _fit_font(scratch, [text], path, target, limit, max(12, round(target * .38)))

    def text_layer(text, selected_font, y, fill='#FFFFFF', outline=False, alpha=255,
                   shadow=True, x_shift=0):
        layer = Image.new('RGBA', (width, height), (0, 0, 0, 0)); draw = ImageDraw.Draw(layer)
        stroke = max(1, selected_font.size // 30)
        tw, th, left, top = _text_metrics(draw, text, selected_font, stroke)
        x = (width - tw) / 2 + x_shift
        baseline = y - top
        if outline:
            draw.text((x, baseline), text, font=selected_font, fill=(0, 0, 0, 0),
                      stroke_width=max(1, selected_font.size // 22),
                      stroke_fill=(255, 255, 255, alpha))
            return layer
        if shadow:
            distance = max(2, selected_font.size // 13)
            draw.text((x + distance, baseline + distance), text, font=selected_font,
                      fill=(0, 0, 0, round(alpha * .72)), stroke_width=stroke + 2,
                      stroke_fill=(0, 0, 0, round(alpha * .58)))
        draw.text((x, baseline), text, font=selected_font, fill=_color(fill, alpha),
                  stroke_width=stroke, stroke_fill=(5, 5, 6, round(alpha * .92)))
        return layer

    def bar_layer(text, selected_font, y, color=accent, back=deep, alpha=255, width_boost=1.0):
        layer = Image.new('RGBA', (width, height), (0, 0, 0, 0)); draw = ImageDraw.Draw(layer)
        stroke = max(1, selected_font.size // 34)
        tw, th, left, top = _text_metrics(draw, text, selected_font, stroke)
        pad_x, pad_y = selected_font.size * .16, selected_font.size * .045
        bar_w = min(width * .92, (tw + 2 * pad_x) * width_boost)
        x1 = (width - bar_w) / 2; x2 = x1 + bar_w
        y1 = y - pad_y; y2 = y + th + pad_y
        offset = max(3, round(selected_font.size * .07))
        glow = Image.new('RGBA', layer.size, (0, 0, 0, 0)); gd = ImageDraw.Draw(glow)
        gd.rectangle((x1, y1, x2, y2), fill=_color(color, round(alpha * .75)))
        glow = glow.filter(ImageFilter.GaussianBlur(max(5, selected_font.size // 9)))
        glow.putalpha(glow.getchannel('A').point(lambda value: round(value * .48)))
        layer = Image.alpha_composite(layer, glow); draw = ImageDraw.Draw(layer)
        draw.rectangle((x1 - offset, y1 + offset, x2 - offset, y2 + offset),
                       fill=_color(back, round(alpha * .96)))
        draw.rectangle((x1, y1, x2, y2), fill=_color(color, alpha))
        tx = (width - tw) / 2
        draw.text((tx + max(2, selected_font.size // 18), y - top + max(2, selected_font.size // 18)),
                  text, font=selected_font, fill=(0, 0, 0, round(alpha * .76)),
                  stroke_width=stroke + 1, stroke_fill=(0, 0, 0, round(alpha * .55)))
        draw.text((tx, y - top), text, font=selected_font, fill=(255, 255, 255, alpha),
                  stroke_width=stroke, stroke_fill=(248, 248, 248, alpha))
        return layer

    elements = []
    # Each tuple is (layer, entrance delay, reveal side). Layouts intentionally vary per phrase.
    if variant == 0:  # Small setup plus two large strips, matching 99% / BAND / HAIN.
        bar_words = raw_words[-2:] if len(raw_words) > 1 else raw_words
        setup = ' '.join(raw_words[:-len(bar_words)])
        fonts = [font(line, main_target * 1.05, width * .78) for line in bar_words]
        heights = [_text_metrics(scratch, line, f)[1] for line, f in zip(bar_words, fonts)]
        setup_font = font(setup or ' ', main_target * .25, width * .80, small_path)
        setup_h = _text_metrics(scratch, setup or ' ', setup_font)[1] if setup else 0
        total = setup_h + sum(heights) + main_target * .08 * (len(bar_words) + (1 if setup else 0))
        y = center_y - total / 2
        if setup:
            elements.append((text_layer(setup, setup_font, y), .01, 'left'))
            y += setup_h + main_target * .08
        for index, (line, selected, line_h) in enumerate(zip(bar_words, fonts, heights)):
            elements.append((bar_layer(line, selected, y, accent, deep), .07 + index * .13,
                             'left' if index % 2 == 0 else 'right'))
            y += line_h + main_target * .08
    elif variant == 1:  # Giant clean statement with one colored lower strip.
        lines = chunks(2)
        top_font = font(lines[0], main_target * .86, max_width)
        bottom_font = font(lines[1], main_target * 1.02, max_width)
        top_h = _text_metrics(scratch, lines[0], top_font)[1]
        y = center_y - top_h * .75
        elements += [(text_layer(lines[0], top_font, y), .02, 'left'),
                     (bar_layer(lines[1], bottom_font, y + top_h + main_target * .08), .15, 'left')]
    elif variant == 2:  # Small setup, huge boxed keyword, small resolve.
        hero_index = max(range(len(words)), key=lambda index: (len(words[index]), index))
        before = ' '.join(raw_words[:hero_index]); hero = words[hero_index]
        after = ' '.join(raw_words[hero_index + 1:])
        hero_font = font(hero, main_target * 1.13, max_width)
        hero_h = _text_metrics(scratch, hero, hero_font)[1]
        small_font = font(before or after or ' ', main_target * .25, max_width, small_path)
        small_h = _text_metrics(scratch, before or after or ' ', small_font)[1]
        y = center_y - hero_h * .48
        if before: elements.append((text_layer(before, small_font, y - small_h - main_target * .18), .01, 'left'))
        elements.append((bar_layer(hero, hero_font, y), .09, 'left'))
        if after: elements.append((text_layer(after, small_font, y + hero_h + main_target * .18), .22, 'right'))
    elif variant == 3:  # Filled hero with a large outline echo underneath.
        hero_index = max(range(len(words)), key=lambda index: (len(words[index]), index))
        hero = words[hero_index]; rest = ' '.join(raw_words[:hero_index] + raw_words[hero_index + 1:])
        hero_font = font(hero, main_target * 1.05, max_width)
        hero_h = _text_metrics(scratch, hero, hero_font)[1]
        echo_font = font(hero, main_target * 1.22, width * .93)
        elements += [(text_layer(hero, echo_font, center_y + hero_h * .28, outline=True, alpha=92), .02, 'right'),
                     (text_layer(hero, hero_font, center_y - hero_h * .40), .08, 'left')]
        if rest:
            rest_font = font(rest, main_target * .24, max_width, small_path)
            elements.append((text_layer(rest, rest_font, center_y + hero_h * .64), .20, 'right'))
    elif variant == 4:  # Handwritten cue followed by a hard red-strip answer.
        script_text = raw_words[0]
        answer_words = raw_words[1:] or raw_words
        middle = ' '.join(answer_words[:-2]) if len(answer_words) > 3 else ''
        answer = ' '.join(answer_words[-2:]) if middle else ' '.join(answer_words)
        script_font = font(script_text, main_target * .42, width * .70, script_path)
        answer_font = font(answer, main_target * .92, max_width)
        answer_h = _text_metrics(scratch, answer, answer_font)[1]
        script_h = _text_metrics(scratch, script_text, script_font)[1]
        middle_font = font(middle, main_target * .52, max_width) if middle else None
        middle_h = _text_metrics(scratch, middle, middle_font)[1] if middle else 0
        gap = main_target * .13
        stack_h = script_h + middle_h + answer_h + gap * (2 if middle else 1)
        first_y = center_y - stack_h / 2
        elements.append((text_layer(script_text, script_font, first_y,
                                    shadow=True), .01, 'right'))
        if middle:
            elements.append((text_layer(middle, middle_font, first_y + script_h + gap), .11, 'right'))
            bar_y = first_y + script_h + gap + middle_h + gap
        else:
            bar_y = first_y + script_h + gap
        elements.append((bar_layer(answer, answer_font, bar_y, '#F12722', '#850B0B'), .20, 'left'))
    elif variant == 5:  # Three-line poster stack with the final idea punched in color.
        lines = chunks(min(3, len(raw_words)))
        selected_fonts = [font(line, main_target * (.72 if len(lines) == 3 else .88), max_width)
                          for line in lines]
        heights = [_text_metrics(scratch, line, f)[1] for line, f in zip(lines, selected_fonts)]
        total = sum(heights) + main_target * .12 * (len(lines) - 1); y = center_y - total / 2
        for index, (line, selected, line_h) in enumerate(zip(lines, selected_fonts, heights)):
            maker = bar_layer if index == len(lines) - 1 else text_layer
            elements.append((maker(line, selected, y), .03 + index * .12,
                             'left' if index % 2 == 0 else 'right'))
            y += line_h + main_target * .12
    elif variant == 6:  # Number / fact card in a yellow strip.
        hero_index = next((i for i, word in enumerate(words) if any(c.isdigit() for c in word)),
                          max(range(len(words)), key=lambda index: len(words[index])))
        hero = words[hero_index]; before = ' '.join(raw_words[:hero_index]); after = ' '.join(raw_words[hero_index + 1:])
        hero_font = font(hero, main_target * 1.28, width * .82)
        hero_h = _text_metrics(scratch, hero, hero_font)[1]
        small_font = font((before + ' ' + after).strip() or ' ', main_target * .27, max_width, small_path)
        small_h = _text_metrics(scratch, before or after or ' ', small_font)[1]
        hero_y = center_y - hero_h * .48
        if before: elements.append((text_layer(before, small_font, hero_y - small_h - main_target * .17), .01, 'left'))
        elements.append((bar_layer(hero, hero_font, hero_y, '#F4B400', '#8E5D00'), .09, 'left'))
        if after: elements.append((text_layer(after, small_font, hero_y + hero_h + main_target * .17), .21, 'right'))
    else:  # Wide two-line slogan with a highlighted keyword.
        lines = chunks(2)
        first_font = font(lines[0], main_target * .72, max_width)
        second_font = font(lines[1], main_target * .94, max_width)
        first_h = _text_metrics(scratch, lines[0], first_font)[1]
        y = center_y - first_h * .72
        elements += [(text_layer(lines[0], first_font, y), .02, 'right'),
                     (bar_layer(lines[1], second_font, y + first_h + main_target * .08), .14, 'left')]

    elapsed = max(0.0, seconds - cue.start)
    remaining = max(0.0, cue.end - seconds)
    composition = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    for layer, delay, side in elements:
        reveal = _ease_out((elapsed - delay) / .24)
        if reveal <= 0:
            continue
        bbox = layer.getbbox()
        if not bbox:
            continue
        item = layer.crop(bbox)
        visible_width = max(1, round(item.width * reveal))
        slide = round((1 - reveal) * width * .055)
        if side == 'right':
            visible = item.crop((item.width - visible_width, 0, item.width, item.height))
            x = bbox[2] - visible_width + slide
        else:
            visible = item.crop((0, 0, visible_width, item.height))
            x = bbox[0] - slide
        composition.alpha_composite(visible, (x, bbox[1]))

    enter = _ease_out(elapsed / .32); leave = _ease_out(remaining / .28)
    crop = composition.getbbox()
    if not crop:
        return composition
    content = composition.crop(crop)
    life = min(1.0, elapsed / max(.1, cue.end - cue.start))
    scale = .82 + .18 * enter + .035 * life + .08 * (1 - leave)
    content = content.resize((max(1, round(content.width * scale)), max(1, round(content.height * scale))),
                             Image.Resampling.LANCZOS)
    blur = (1 - enter) * width / 58 + (1 - leave) * width / 72
    if blur > .25:
        content = content.filter(ImageFilter.GaussianBlur(blur))
    opacity = min(1.0, enter * 1.4, leave * 1.35)
    if opacity < 1:
        content.putalpha(content.getchannel('A').point(lambda value: round(value * opacity)))
    direction = -1 if seed % 2 else 1
    x = (crop[0] + crop[2]) / 2 - content.width / 2 + direction * (1 - enter) * width * .10
    y = (crop[1] + crop[3]) / 2 - content.height / 2 + math.sin(life * math.pi) * height * .006
    result = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    result.alpha_composite(content, (round(x), round(y)))
    return result


def draw_caption(width, height, cue, seconds, style_name, font_id='template', position=.70, size_scale=1.0):
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    style = template(style_name)
    if style.get('layout') == 'typography_1':
        return _draw_typography_one_v2(width, height, cue, seconds, font_id, position, size_scale)
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
        if style_name == 'karaoke' and index == active:
            line_y = min(height - 3, y + metric[1] + max(1, font.size * .08))
            draw.rounded_rectangle((x, line_y, x + word_width, line_y + max(3, font.size // 12)),
                                   radius=3, fill=_color(style['accent']))
        x += word_width + spacing
    return image


def render_overlay(path, cues, width, height, duration, fps=30, style_name='punch', progress=print,
                   font_id='template', position=.70, size_scale=1.0):
    import av
    import numpy as np
    path = Path(path)
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
                pixels = np.asarray(draw_caption(width, height, cue, seconds, style_name,
                                                  font_id, position, size_scale), dtype=np.uint8)
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
