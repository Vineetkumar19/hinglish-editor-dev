"""Render the eight Typography 1 scenes and their motion states for visual review."""

from pathlib import Path
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hinglish_captions.core import CaptionCue, CaptionWord
from hinglish_captions.renderer import draw_caption


HERE = Path(__file__).resolve().parent
SAMPLES = [
    "99 percent flats tumhare liye band hain",
    "Bhai nahi thi",
    "Madurai me alag hi struggle hai yahan",
    "WiFi fridge AC room milega jugaad se",
    "Sirf chair deewarein bed almari geyser",
    "Rapido book karna 60 rupees hai yahan",
    "Character assassination na hi karun",
    "Har order pe choose kiya na",
]


def cue_for(index, text):
    start = index / 30
    words = text.split()
    timed = tuple(CaptionWord(word, start + i * .2, start + (i + 1) * .2)
                  for i, word in enumerate(words))
    return CaptionCue(timed, start, start + 2)


def sheet(states, filename):
    tile_w, tile_h = 360, 640
    result = Image.new("RGB", (tile_w * len(states), tile_h * len(SAMPLES)), "black")
    draw = ImageDraw.Draw(result)
    for row, text in enumerate(SAMPLES):
        cue = cue_for(row, text)
        for col, elapsed in enumerate(states):
            frame = draw_caption(1080, 1920, cue, cue.start + elapsed,
                                 "typography_1", position=.55)
            frame = Image.alpha_composite(Image.new("RGBA", frame.size, "black"), frame)
            result.paste(frame.convert("RGB").resize((tile_w, tile_h)),
                         (col * tile_w, row * tile_h))
            draw.text((col * tile_w + 8, row * tile_h + 8),
                      f"layout {row} / {elapsed:.2f}s", fill="white")
    result.save(HERE / filename, quality=92)


if __name__ == "__main__":
    sheet([.75], "typography1-v2-layouts-latest.jpg")
    sheet([.04, .14, .28, .65, 1.78], "typography1-v2-motion.jpg")
