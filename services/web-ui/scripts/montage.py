"""Tile frames (NNN_TTTms.jpg) into a labelled contact sheet. Usage: uv run --with pillow python scripts/montage.py <frameDir> <out.png> <cols> <tileW>"""

import pathlib
import sys

from PIL import Image, ImageDraw

d, out, cols, w = (
    pathlib.Path(sys.argv[1]),
    sys.argv[2],
    int(sys.argv[3]),
    int(sys.argv[4]),
)
fs = sorted(d.glob("*.jpg"))
ims = [Image.open(f).convert("RGB") for f in fs]
ims = [i.resize((w, int(i.height * w / i.width))) for i in ims]
h = max(i.height for i in ims) + 14
rows = (len(ims) + cols - 1) // cols
S = Image.new("RGB", (cols * w, rows * h), "white")
dr = ImageDraw.Draw(S)
for k, (f, i) in enumerate(zip(fs, ims)):
    x, y = (k % cols) * w, (k // cols) * h
    S.paste(i, (x, y + 14))
    dr.text((x + 3, y + 1), f.stem.split("_")[1], fill="black")
S.save(out)
