"""Build the final Dot brand set into brand/final/ (SVG, states, rasters).

uv run --with fonttools --with pillow --with playwright python brand/tools/export_final.py <JetBrainsMono[wght].ttf>
"""

from __future__ import annotations

import base64
import io
import sys
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from PIL import Image
from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent.parent / "final"
CHROME = next(
    Path.home().glob(
        ".cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell"
    )
)

ACCENT = "#2E9CC4"
DARK_TILE, DARK_LINE = "#11181B", "#2B3134"
LIGHT_TILE, LIGHT_LINE = "#F1F5F7", "#D3DCE0"
INK_DARK, INK_LIGHT = "#161C1E", "#E7ECEE"  # text on light bg / on dark bg
STATES = {  # dark tile / light tile
    "idle": ("#5E6B72", "#78858D"),
    "thinking": ("#F0B440", "#B87A0B"),
    "waiting": (ACCENT, "#1F8CB4"),
}


def n(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".")


def rrect(x, y, w, h, r) -> str:
    return (
        f"M{n(x + r)} {n(y)}H{n(x + w - r)}A{n(r)} {n(r)} 0 0 1 {n(x + w)} {n(y + r)}V{n(y + h - r)}"
        f"A{n(r)} {n(r)} 0 0 1 {n(x + w - r)} {n(y + h)}H{n(x + r)}A{n(r)} {n(r)} 0 0 1 {n(x)} {n(y + h - r)}"
        f"V{n(y + r)}A{n(r)} {n(r)} 0 0 1 {n(x + r)} {n(y)}Z"
    )


def circ(cx, cy, r) -> str:
    return f"M{n(cx - r)} {n(cy)}a{n(r)} {n(r)} 0 1 0 {n(2 * r)} 0a{n(r)} {n(r)} 0 1 0 {n(-2 * r)} 0Z"


def svg(w, h, label, body, extra="") -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {n(w)} {n(h)}" role="img" '
        f'aria-label="{label}"{extra}>{body}</svg>\n'
    )


def write(name, text):
    (OUT / name).write_text(text, encoding="utf-8")


# ---------- font ----------
def load_font(path: str, wght: int = 600) -> TTFont:
    f = instancer.instantiateVariableFont(TTFont(path), {"wght": wght})
    buf = io.BytesIO()
    f.save(buf)
    buf.seek(0)
    return TTFont(buf)


class Word:
    """'Dot' outlined at a given cap height; ink box measured, origin at ink top-left."""

    def __init__(self, font: TTFont, cap: float, text="Dot"):
        self.gs, self.cmap = font.getGlyphSet(), font.getBestCmap()
        self.text = text
        self.adv = font["hmtx"][self.cmap[ord("o")]][0]
        self.k = cap / self.b("D")[3]
        self.cap = cap
        first, last = self.b(text[0]), self.b(text[-1])
        self.ink_l = first[0] * self.k
        self.ink_r = (len(text) - 1) * self.adv * self.k + last[2] * self.k
        self.width = self.ink_r - self.ink_l

    def b(self, ch):
        bp = BoundsPen(self.gs)
        self.gs[self.cmap[ord(ch)]].draw(bp)
        return bp.bounds

    def d(self, left, base) -> str:
        """Path data with ink left edge at `left`, baseline at `base`."""
        out = []
        for i, ch in enumerate(self.text):
            pen = SVGPathPen(self.gs, ntos=n)
            ox = left - self.ink_l + i * self.adv * self.k
            self.gs[self.cmap[ord(ch)]].draw(
                TransformPen(pen, (self.k, 0, 0, -self.k, ox, base))
            )
            out.append(pen.getCommands())
        return "".join(out)


# ---------- tile geometry (ratios fixed by the chosen option C) ----------
RX = 0.25  # corner radius / tile size


def tile_color(x, y, s, dot_r, fills, line=None) -> str:
    tile, dot = fills
    cx, cy = x + s / 2, y + s / 2
    if line:
        sw = 1.5 * s / 56
        h = sw / 2
        body = (
            f'<rect x="{n(x + h)}" y="{n(y + h)}" width="{n(s - sw)}" height="{n(s - sw)}" rx="{n(RX * s - h)}" '
            f'fill="{tile}" stroke="{line}" stroke-width="{n(sw)}"/>'
        )
    else:
        body = f'<rect x="{n(x)}" y="{n(y)}" width="{n(s)}" height="{n(s)}" rx="{n(RX * s)}" fill="{tile}"/>'
    return body + f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(dot_r)}" fill="{dot}"/>'


def tile_path(x, y, s, dot_r) -> str:
    return rrect(x, y, s, s, RX * s) + circ(x + s / 2, y + s / 2, dot_r)


DOT_MARK, DOT_LOCKUP, DOT_SMALL = 12 / 56, 0.2, 0.29  # dot radius / tile size


def build(font: TTFont):
    OUT.mkdir(exist_ok=True)
    variants = {  # name -> (tile, line, dot, ink, mono)
        "color-darktile": (DARK_TILE, DARK_LINE, ACCENT, INK_DARK),
        "color-lighttile": (LIGHT_TILE, LIGHT_LINE, ACCENT, INK_LIGHT),
    }
    mono = {
        "mono-on-dark": INK_LIGHT,
        "mono-on-light": INK_DARK,
    }  # one colour, dot is a hole

    # --- mark-tile (56 box, tile edge to edge)
    sz = 56
    for v, (tile, line, dot, _ink) in variants.items():
        write(
            f"mark-tile-{v}.svg",
            svg(sz, sz, "Dot", tile_color(0, 0, sz, sz * DOT_MARK, (tile, dot), line)),
        )
    for v, c in mono.items():
        write(
            f"mark-tile-{v}.svg",
            svg(
                sz,
                sz,
                "Dot",
                f'<path fill="{c}" fill-rule="evenodd" d="{tile_path(0, 0, sz, sz * DOT_MARK)}"/>',
            ),
        )

    # --- mark-small (<=24 px): bigger dot, tile fills grid, no outline
    sz = 64
    for v, (tile, _l, dot, _i) in variants.items():
        write(
            f"mark-small-{v}.svg",
            svg(sz, sz, "Dot", tile_color(0, 0, sz, sz * DOT_SMALL, (tile, dot))),
        )
    write("mark-small.svg", (OUT / "mark-small-color-darktile.svg").read_text())
    write("icon.svg", (OUT / "mark-small-color-darktile.svg").read_text())
    for v, c in mono.items():
        write(
            f"mark-small-{v}.svg",
            svg(
                sz,
                sz,
                "Dot",
                f'<path fill="{c}" fill-rule="evenodd" d="{tile_path(0, 0, sz, sz * DOT_SMALL)}"/>',
            ),
        )

    # --- horizontal lockup: tile 48, cap 26, gap 14
    tsz, cap, gap = 48, 26, 14
    w = Word(font, cap)
    wid = tsz + gap + w.width
    base = tsz / 2 + cap / 2
    wd = w.d(tsz + gap, base)
    for v, (tile, line, dot, ink) in variants.items():
        write(
            f"lockup-horizontal-{v}.svg",
            svg(
                wid,
                tsz,
                "Dot",
                tile_color(0, 0, tsz, tsz * DOT_LOCKUP, (tile, dot), line)
                + f'<path fill="{ink}" d="{wd}"/>',
            ),
        )
    for v, c in mono.items():
        write(
            f"lockup-horizontal-{v}.svg",
            svg(
                wid,
                tsz,
                "Dot",
                f'<path fill="{c}" fill-rule="evenodd" d="{tile_path(0, 0, tsz, tsz * DOT_LOCKUP)}{wd}"/>',
            ),
        )
    hmeta = (wid, tsz)

    # --- stacked lockup: tile 64, cap 24, gap 18, centred
    tsz, cap, gap = 64, 24, 18
    w2 = Word(font, cap)
    wid2, hgt2 = max(tsz, w2.width), tsz + gap + cap
    tx, wx = (wid2 - tsz) / 2, (wid2 - w2.width) / 2
    wd2 = w2.d(wx, tsz + gap + cap)
    for v, (tile, line, dot, ink) in variants.items():
        write(
            f"lockup-stacked-{v}.svg",
            svg(
                wid2,
                hgt2,
                "Dot",
                tile_color(tx, 0, tsz, tsz * DOT_LOCKUP, (tile, dot), line)
                + f'<path fill="{ink}" d="{wd2}"/>',
            ),
        )
    for v, c in mono.items():
        write(
            f"lockup-stacked-{v}.svg",
            svg(
                wid2,
                hgt2,
                "Dot",
                f'<path fill="{c}" fill-rule="evenodd" d="{tile_path(tx, 0, tsz, tsz * DOT_LOCKUP)}{wd2}"/>',
            ),
        )

    # --- state variants (hard colours), dark and light tile
    sz = 56
    for st, (cd, cl) in STATES.items():
        write(
            f"dot-{st}.svg",
            svg(
                sz,
                sz,
                f"Dot {st}",
                tile_color(0, 0, sz, sz * DOT_MARK, (DARK_TILE, cd), DARK_LINE),
            ),
        )
        write(
            f"dot-{st}-lighttile.svg",
            svg(
                sz,
                sz,
                f"Dot {st}",
                tile_color(0, 0, sz, sz * DOT_MARK, (LIGHT_TILE, cl), LIGHT_LINE),
            ),
        )

    # --- animated thinking: pulse ring + soft dot breathe; reduced motion = static ring
    amber = STATES["thinking"][0]
    cx = sz / 2
    r = sz * DOT_MARK
    anim = (
        "<style>.r{transform-box:fill-box;transform-origin:center;opacity:.35}"
        "@media (prefers-reduced-motion:no-preference){"
        ".r{animation:p 1.6s ease-out infinite}.d{animation:b 1.6s ease-in-out infinite}"
        "@keyframes p{0%{transform:scale(1);opacity:.7}100%{transform:scale(1.7);opacity:0}}"
        "@keyframes b{0%,100%{opacity:1}50%{opacity:.72}}}</style>"
    )
    body = (
        anim
        + f'<rect x="0.75" y="0.75" width="54.5" height="54.5" rx="13.25" fill="{DARK_TILE}" stroke="{DARK_LINE}" stroke-width="1.5"/>'
        f'<circle class="r" cx="{n(cx)}" cy="{n(cx)}" r="{n(r)}" fill="none" stroke="{amber}" stroke-width="2"/>'
        f'<circle class="d" cx="{n(cx)}" cy="{n(cx)}" r="{n(r)}" fill="{amber}"/>'
    )
    write("mark-thinking-animated.svg", svg(sz, sz, "Dot thinking", body))
    return hmeta


# ---------- raster ----------
def raster_svg(page, svg_text: str, w: int, h: int, bg="transparent") -> Image.Image:
    uri = "data:image/svg+xml;base64," + base64.b64encode(svg_text.encode()).decode()
    page.set_viewport_size({"width": w, "height": h})
    page.set_content(
        f'<body style="margin:0;background:{bg}"><img src="{uri}" width="{w}" height="{h}" style="display:block"></body>'
    )
    page.wait_for_function("document.images[0].complete")
    return Image.open(io.BytesIO(page.screenshot(omit_background=True)))


def fullbleed(size, ratio=0.2) -> str:
    return svg(
        size,
        size,
        "Dot",
        f'<rect width="{size}" height="{size}" fill="{DARK_TILE}"/>'
        f'<circle cx="{n(size / 2)}" cy="{n(size / 2)}" r="{n(size * ratio)}" fill="{ACCENT}"/>',
    )


def rasters(font):
    small = (OUT / "mark-small.svg").read_text()
    mark = (OUT / "mark-tile-color-darktile.svg").read_text()
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=str(CHROME))
        pg = b.new_page()
        ico = [raster_svg(pg, small, s, s).convert("RGBA") for s in (16, 32, 48)]
        _write_ico(ico)
        ico[1].save(OUT / "favicon-32.png")
        raster_svg(pg, fullbleed(180), 180, 180).convert("RGB").save(
            OUT / "apple-touch-icon.png"
        )
        for s in (192, 512):
            c = Image.new("RGBA", (s, s))
            m = int(s * 0.9)
            c.paste(raster_svg(pg, mark, m, m), ((s - m) // 2,) * 2)
            c.save(OUT / f"icon-{s}.png")
        raster_svg(pg, fullbleed(512, 0.17), 512, 512).convert("RGB").save(
            OUT / "icon-maskable-512.png"
        )
        raster_svg(pg, fullbleed(512, 0.21), 512, 512).convert("RGB").save(
            OUT / "avatar-512.png"
        )
        # og image: light-tile lockup on dark bg, 1200x630
        lock = (OUT / "lockup-horizontal-color-lighttile.svg").read_text()
        og_w, og_h = 1200, 630
        og = Image.new("RGB", (og_w, og_h), "#090E11")
        lw = 540  # lockup spans 45% of the width
        lh = round(lw / hmeta_ratio(lock))
        ov = raster_svg(pg, lock, lw, lh)
        og.paste(ov, ((og_w - lw) // 2, (og_h - lh) // 2), ov)
        og.save(OUT / "og-image.png")
        b.close()


def _write_ico(imgs):
    # ICO container with PNG payloads (16/32/48)
    pngs = []
    for im in imgs:
        buf = io.BytesIO()
        im.save(buf, "PNG")
        pngs.append((im.width, buf.getvalue()))
    head = b"\0\0\1\0" + len(pngs).to_bytes(2, "little")
    off = 6 + 16 * len(pngs)
    ents, data = b"", b""
    for sz, png in pngs:
        ents += (
            bytes([sz, sz, 0, 0])
            + (1).to_bytes(2, "little")
            + (32).to_bytes(2, "little")
        )
        ents += len(png).to_bytes(4, "little") + off.to_bytes(4, "little")
        off += len(png)
        data += png
    (OUT / "favicon.ico").write_bytes(head + ents + data)


def hmeta_ratio(svg_text: str) -> float:
    vb = svg_text.split('viewBox="')[1].split('"', maxsplit=1)[0].split()
    return float(vb[2]) / float(vb[3])


if __name__ == "__main__":
    f = load_font(sys.argv[1])
    build(f)
    rasters(f)
