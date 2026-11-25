"""Build the Dot brand set (v3 Quiet: graphite tile, sage dot) into brand/final/.

uv run --no-project --with pillow --with playwright python brand/tools/export_final.py
The wordmark is pre-outlined in wordmark.json (JetBrains Mono 600), so no font file is needed.
"""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "final"
WM = json.loads((HERE / "wordmark.json").read_text())
CHROME = next(
    Path.home().glob(
        ".cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell"
    )
)

SAGE_ON_DARK, SAGE_ON_LIGHT = "#93BFA3", "#3A6A50"
DARK_TILE, DARK_LINE = "#1C1B18", "#34322D"
LIGHT_TILE, LIGHT_LINE = "#EBE8E2", "#D4D0C6"
INK_DARK, INK_LIGHT = "#1C1B18", "#EBE8E2"
STATES = {  # on dark tile, on light tile
    "idle": ("#7A766D", "#7B776E"),
    "thinking": ("#D9A03A", "#A8700A"),
    "waiting": ("#7FA6C6", "#4F7CA3"),
}
RX = 0.27  # corner radius / tile size
DOT_MARK, DOT_LOCKUP, DOT_SMALL = 0.215, 0.2, 0.29  # dot radius / tile size


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


def tile(x, y, s, dot_r, tile_fill, dot_fill, line=None) -> str:
    cx, cy = x + s / 2, y + s / 2
    if line:
        sw = 1.5 * s / 56
        h = sw / 2
        body = (
            f'<rect x="{n(x + h)}" y="{n(y + h)}" width="{n(s - sw)}" height="{n(s - sw)}" rx="{n(RX * s - h)}" '
            f'fill="{tile_fill}" stroke="{line}" stroke-width="{n(sw)}"/>'
        )
    else:
        body = f'<rect x="{n(x)}" y="{n(y)}" width="{n(s)}" height="{n(s)}" rx="{n(RX * s)}" fill="{tile_fill}"/>'
    return (
        body + f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(dot_r)}" fill="{dot_fill}"/>'
    )


def tile_path(x, y, s, dot_r) -> str:
    return rrect(x, y, s, s, RX * s) + circ(x + s / 2, y + s / 2, dot_r)


def word(scale, left, top) -> str:
    """Wordmark placed with its ink box top-left at (left, top)."""
    tx = left - WM["left"] * scale
    ty = top - WM["top"] * scale
    return f"translate({n(tx)} {n(ty)}) scale({n(scale)})"


WM_W = WM["right"] - WM["left"]
WM_H = WM["base"] - WM["top"]
CUR = "currentColor"
DOTVAR = "var(--dot,#93BFA3)"


def build():
    OUT.mkdir(exist_ok=True)
    variants = {
        "color-darktile": (DARK_TILE, DARK_LINE, SAGE_ON_DARK, INK_DARK),
        "color-lighttile": (LIGHT_TILE, LIGHT_LINE, SAGE_ON_LIGHT, INK_LIGHT),
    }
    mono = {"mono-on-dark": INK_LIGHT, "mono-on-light": INK_DARK}

    # mark-tile (56 grid)
    sz = 56
    for v, (t, line, dot, _ink) in variants.items():
        write(
            f"mark-tile-{v}.svg",
            svg(sz, sz, "Dot", tile(0, 0, sz, sz * DOT_MARK, t, dot, line)),
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
    # inline-capable mark: tile = currentColor, dot = --dot
    write("mark.svg", svg(sz, sz, "Dot", tile(0, 0, sz, sz * DOT_MARK, CUR, DOTVAR)))

    # mark-small (<=24 px): bigger dot, no outline
    sz = 64
    for v, (t, _l, dot, _i) in variants.items():
        write(
            f"mark-small-{v}.svg",
            svg(sz, sz, "Dot", tile(0, 0, sz, sz * DOT_SMALL, t, dot)),
        )
    small = (OUT / "mark-small-color-darktile.svg").read_text()
    write("mark-small.svg", small)
    write("icon.svg", small)
    write(
        "mark-small-currentcolor.svg",
        svg(sz, sz, "Dot", tile(0, 0, sz, sz * DOT_SMALL, CUR, DOTVAR)),
    )
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

    # horizontal lockup: tile 48, cap 26, gap 14 (wordmark path is already at cap 26)
    tsz, gap = 48, 14
    wid = tsz + gap + WM_W
    wtf = word(1, tsz + gap, (tsz - WM_H) / 2)
    for v, (t, line, dot, ink) in variants.items():
        write(
            f"lockup-horizontal-{v}.svg",
            svg(
                wid,
                tsz,
                "Dot",
                tile(0, 0, tsz, tsz * DOT_LOCKUP, t, dot, line)
                + f'<path fill="{ink}" transform="{wtf}" d="{WM["d"]}"/>',
            ),
        )
    write(
        "lockup-horizontal.svg",
        svg(
            wid,
            tsz,
            "Dot",
            tile(0, 0, tsz, tsz * DOT_LOCKUP, CUR, DOTVAR)
            + f'<path fill="{CUR}" transform="{wtf}" d="{WM["d"]}"/>',
        ),
    )
    for v, c in mono.items():
        write(
            f"lockup-horizontal-{v}.svg",
            svg(
                wid,
                tsz,
                "Dot",
                f'<path fill="{c}" fill-rule="evenodd" d="{tile_path(0, 0, tsz, tsz * DOT_LOCKUP)}"/>'
                f'<path fill="{c}" transform="{wtf}" d="{WM["d"]}"/>',
            ),
        )

    # stacked lockup: tile 64, cap 24, gap 18
    tsz, cap, gap = 64, 24, 18
    k = cap / WM_H
    ww = WM_W * k
    wid2, hgt2 = max(tsz, ww), tsz + gap + cap
    tx = (wid2 - tsz) / 2
    wtf2 = word(k, (wid2 - ww) / 2, tsz + gap)
    for v, (t, line, dot, ink) in variants.items():
        write(
            f"lockup-stacked-{v}.svg",
            svg(
                wid2,
                hgt2,
                "Dot",
                tile(tx, 0, tsz, tsz * DOT_LOCKUP, t, dot, line)
                + f'<path fill="{ink}" transform="{wtf2}" d="{WM["d"]}"/>',
            ),
        )
    for v, c in mono.items():
        write(
            f"lockup-stacked-{v}.svg",
            svg(
                wid2,
                hgt2,
                "Dot",
                f'<path fill="{c}" fill-rule="evenodd" d="{tile_path(tx, 0, tsz, tsz * DOT_LOCKUP)}"/>'
                f'<path fill="{c}" transform="{wtf2}" d="{WM["d"]}"/>',
            ),
        )

    # state variants
    sz = 56
    for st, (cd, cl) in STATES.items():
        write(
            f"dot-{st}.svg",
            svg(
                sz,
                sz,
                f"Dot {st}",
                tile(0, 0, sz, sz * DOT_MARK, DARK_TILE, cd, DARK_LINE),
            ),
        )
        write(
            f"dot-{st}-lighttile.svg",
            svg(
                sz,
                sz,
                f"Dot {st}",
                tile(0, 0, sz, sz * DOT_MARK, LIGHT_TILE, cl, LIGHT_LINE),
            ),
        )

    # animated thinking
    amber = STATES["thinking"][0]
    c, r = sz / 2, sz * DOT_MARK
    anim = (
        "<style>.r{transform-box:fill-box;transform-origin:center;opacity:.35}"
        "@media (prefers-reduced-motion:no-preference){"
        ".r{animation:p 1.6s ease-out infinite}.d{animation:b 1.6s ease-in-out infinite}"
        "@keyframes p{0%{transform:scale(1);opacity:.7}100%{transform:scale(1.7);opacity:0}}"
        "@keyframes b{0%,100%{opacity:1}50%{opacity:.72}}}</style>"
    )
    sw = 1.5
    body = (
        anim
        + f'<rect x="{n(sw / 2)}" y="{n(sw / 2)}" width="{n(sz - sw)}" height="{n(sz - sw)}" rx="{n(RX * sz - sw / 2)}" fill="{DARK_TILE}" stroke="{DARK_LINE}" stroke-width="{sw}"/>'
        f'<circle class="r" cx="{n(c)}" cy="{n(c)}" r="{n(r)}" fill="none" stroke="{amber}" stroke-width="2"/>'
        f'<circle class="d" cx="{n(c)}" cy="{n(c)}" r="{n(r)}" fill="{amber}"/>'
    )
    write("mark-thinking-animated.svg", svg(sz, sz, "Dot thinking", body))


def raster_svg(page, svg_text: str, w: int, h: int) -> Image.Image:
    uri = "data:image/svg+xml;base64," + base64.b64encode(svg_text.encode()).decode()
    page.set_viewport_size({"width": w, "height": h})
    page.set_content(
        f'<body style="margin:0;background:transparent"><img src="{uri}" width="{w}" height="{h}" style="display:block"></body>'
    )
    page.wait_for_function("document.images[0].complete")
    return Image.open(io.BytesIO(page.screenshot(omit_background=True)))


def fullbleed(size, ratio) -> str:
    return svg(
        size,
        size,
        "Dot",
        f'<rect width="{size}" height="{size}" fill="{DARK_TILE}"/>'
        f'<circle cx="{n(size / 2)}" cy="{n(size / 2)}" r="{n(size * ratio)}" fill="{SAGE_ON_DARK}"/>',
    )


def rasters():
    small = (OUT / "mark-small.svg").read_text()
    mark = (OUT / "mark-tile-color-darktile.svg").read_text()
    lock = (OUT / "lockup-horizontal-color-lighttile.svg").read_text()
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=str(CHROME))
        pg = b.new_page()
        ico = [raster_svg(pg, small, s, s).convert("RGBA") for s in (16, 32, 48)]
        _write_ico(ico)
        ico[1].save(OUT / "favicon-32.png")
        raster_svg(pg, fullbleed(180, 0.2), 180, 180).convert("RGB").save(
            OUT / "apple-touch-icon.png"
        )
        for s in (192, 512):
            cv = Image.new("RGBA", (s, s))
            m = int(s * 0.9)
            cv.paste(raster_svg(pg, mark, m, m), ((s - m) // 2,) * 2)
            cv.save(OUT / f"icon-{s}.png")
        raster_svg(pg, fullbleed(512, 0.17), 512, 512).convert("RGB").save(
            OUT / "icon-maskable-512.png"
        )
        raster_svg(pg, fullbleed(512, 0.21), 512, 512).convert("RGB").save(
            OUT / "avatar-512.png"
        )
        ow, oh, lw = 1200, 630, 540
        lh = round(lw / hmeta_ratio(lock))
        og = Image.new("RGB", (ow, oh), "#141311")
        ov = raster_svg(pg, lock, lw, lh)
        og.paste(ov, ((ow - lw) // 2, (oh - lh) // 2), ov)
        og.save(OUT / "og-image.png")
        b.close()


def _write_ico(imgs):
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
    build()
    rasters()
