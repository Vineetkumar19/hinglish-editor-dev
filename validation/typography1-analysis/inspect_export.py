"""Inspect rendered editor MOV frames rather than only renderer stills."""

from pathlib import Path

import av
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[2]
FOLDER = ROOT / "output/captions/20260920-160836-70fd9b/001-phase2-retake-fixture-6b2647c045747676d91a-semantic-30fps"
MOV = FOLDER / "media/premium-captions.mov"
TIMES = [3.08, 3.24, 3.60, 4.16, 4.68, 13.10, 13.60, 14.20, 14.68]


def main():
    tiles = []
    with av.open(str(MOV)) as video:
        rate = float(video.streams.video[0].average_rate)
        target_frames = {round(t * rate): t for t in TIMES}
        for index, frame in enumerate(video.decode(video=0)):
            if index not in target_frames:
                continue
            rgba = frame.to_image().convert("RGBA")
            black = Image.alpha_composite(Image.new("RGBA", rgba.size, "black"), rgba)
            tile = black.convert("RGB").resize((360, 360))
            ImageDraw.Draw(tile).text((8, 8), f"{target_frames[index]:.2f}s", fill="white")
            tiles.append(tile)
    contact = Image.new("RGB", (360 * 3, 360 * 3), "black")
    for index, tile in enumerate(tiles):
        contact.paste(tile, ((index % 3) * 360, (index // 3) * 360))
    destination = Path(__file__).resolve().parent / "typography1-real-export.jpg"
    contact.save(destination, quality=94)
    print(destination)


if __name__ == "__main__":
    main()
