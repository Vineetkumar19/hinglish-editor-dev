"""Make a short, reproducible motion reel of the eight Typography 1 layouts."""

from pathlib import Path
import sys

import av
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hinglish_captions.core import CaptionCue, CaptionWord
from hinglish_captions.renderer import draw_caption


ROOT = Path(__file__).resolve().parent
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
FPS = 24
SCENE_FRAMES = 42
WIDTH, HEIGHT = 540, 960


def main():
    destination = ROOT / "Typography-1-motion-preview.mp4"
    with av.open(str(destination), "w") as output:
        stream = output.add_stream("libx264", rate=FPS)
        stream.width, stream.height, stream.pix_fmt = WIDTH, HEIGHT, "yuv420p"
        stream.options = {"crf": "19", "preset": "fast"}
        for scene, text in enumerate(SAMPLES):
            start = scene * SCENE_FRAMES / FPS
            end = start + SCENE_FRAMES / FPS
            words = text.split()
            cue = CaptionCue(tuple(CaptionWord(word,
                                               start + i * (end - start) / len(words),
                                               start + (i + 1) * (end - start) / len(words))
                                   for i, word in enumerate(words)), start, end)
            for frame_index in range(SCENE_FRAMES):
                seconds = start + frame_index / FPS
                layer = draw_caption(WIDTH, HEIGHT, cue, seconds,
                                     "typography_1", position=.55)
                rgb = Image.alpha_composite(Image.new("RGBA", (WIDTH, HEIGHT), "black"), layer)
                frame = av.VideoFrame.from_ndarray(np.asarray(rgb.convert("RGB")), format="rgb24")
                frame.pts = scene * SCENE_FRAMES + frame_index
                for packet in stream.encode(frame):
                    output.mux(packet)
        for packet in stream.encode():
            output.mux(packet)
    print(destination)


if __name__ == "__main__":
    main()
