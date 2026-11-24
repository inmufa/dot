"""Generate the five logo option SVGs (64-grid, outlined text, no live fonts).

uv run --with fonttools python brand/tools/gen_options.py <JetBrainsMono[wght].ttf>
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

OUT = Path(__file__).resolve().parent.parent / "options"
ACCENT = "#2E9CC4"
NS = 'xmlns="http://www.w3.org/2000/svg"'
DOT = f"var(--dot,{ACCENT})"


def load_font(path: str, wght: int) -> TTFont:
    f = TTFont(path)
    f = instancer.instantiateVariableFont(f, {"wght": wght})
    buf = io.BytesIO()
    f.save(buf)
    buf.seek(0)
    return TTFont(buf)


class Glyphs:
    def __init__(self, font: TTFont, size_asc: float):
        self.font = font
        self.gs = font.getGlyphSet()
        self.cmap = font.getBestCmap()
        self.adv = font["hmtx"][self.cmap[ord("o")]][0]
        self.scale = (
            size_asc / self.bounds("d")[3]
        )  # ascender (d top) -> size_asc units

    def bounds(self, ch):
        bp = BoundsPen(self.gs)
        self.gs[self.cmap[ord(ch)]].draw(bp)
        return bp.bounds

    def path(self, ch, x, base):
        pen = SVGPathPen(self.gs, ntos=lambda v: f"{v:.2f}".rstrip("0").rstrip("."))
        tp = TransformPen(pen, (self.scale, 0, 0, -self.scale, x, base))
        self.gs[self.cmap[ord(ch)]].draw(tp)
        return pen.getCommands()

    def center(self, ch, x, base):
        b = self.bounds(ch)
        return (
            x + (b[0] + b[2]) / 2 * self.scale,
            base - (b[1] + b[3]) / 2 * self.scale,
            (b[2] - b[0]) / 2 * self.scale,
            (b[3] - b[1]) / 2 * self.scale,
        )


class _Scaled:
    def __init__(self, g, k):
        self.gs, self.cmap, self.scale = g.gs, g.cmap, g.scale * k


def svg(vb: str, label: str, body: str) -> str:
    return (
        f'<svg {NS} viewBox="{vb}" role="img" aria-label="{label}">\n{body}\n</svg>\n'
    )


def halo(cx, cy, r):
    return (
        f'<circle class="halo" cx="{cx}" cy="{cy}" r="{r}" fill="none" '
        f'stroke-width="2" style="stroke:{DOT};stroke-opacity:var(--halo,0)"/>'
    )


def write(name, text):
    (OUT / name).write_text(text, encoding="utf-8")


def main(fontfile: str) -> None:
    font = load_font(fontfile, 600)

    # A: dot on a prompt rule. Dot r13 (diam 26 on nominal 24 = overshoot).
    write(
        "A-symbol-dot-rule.svg",
        svg(
            "0 0 64 64",
            "Dot",
            "\n".join(
                [
                    halo(32, 26, 18),
                    f'<circle cx="32" cy="26" r="13" style="fill:{DOT}"/>',
                    '<path d="M16 50H48" stroke="currentColor" stroke-width="4" stroke-linecap="round" fill="none"/>',
                ]
            ),
        ),
    )

    # B: wordmark "dot", the o is the live dot. Ascender height 40 units.
    g = Glyphs(font, 40)
    adv, base, x0 = g.adv * g.scale, 52, 6
    ox = x0 + adv
    cx, cy, _rx, ry = g.center("o", ox, base)
    r = round(
        ry * 0.86, 2
    )  # slightly under o height: solid disc reads heavier than a ring
    w = round(x0 * 2 + adv * 3, 2)
    write(
        "B-wordmark-dot-as-o.svg",
        svg(
            f"0 0 {w} 64",
            "dot",
            "\n".join(
                [
                    f'<path d="{g.path("d", x0, base)} {g.path("t", x0 + 2 * adv, base)}" fill="currentColor"/>',
                    halo(round(cx, 2), round(cy, 2), round(r + 4, 2)),
                    f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r}" style="fill:{DOT}"/>',
                ]
            ),
        ),
    )
    # B small cut: d with its bowl filled by the dot, fitted to the 64 grid
    k = 1.4
    bx0, by0, bx1, by1 = g.bounds("d")
    gx = 32 - (bx0 + bx1) / 2 * g.scale * k  # glyph origin so ink is centred
    gy = 32 + (by0 + by1) / 2 * g.scale * k
    ocx, ocy, _orx, ory = g.center("o", 0, 0)  # bowl centre, relative to origin
    write(
        "B-cut-d-bowl.svg",
        svg(
            "0 0 64 64",
            "dot",
            "\n".join(
                [
                    f'<path d="{Glyphs.__dict__["path"](_Scaled(g, k), "d", gx, gy)}" fill="currentColor"/>',
                    halo(
                        round(gx + ocx * k, 2),
                        round(gy + ocy * k, 2),
                        round(ory * k * 0.55, 2),
                    ),
                    f'<circle cx="{gx + ocx * k:.2f}" cy="{gy + ocy * k:.2f}" r="{ory * k * 0.42:.2f}" style="fill:{DOT}"/>',
                ]
            ),
        ),
    )

    # C: tile + wordmark "Dot" (cap height ~ 26)
    gc = Glyphs(font, 26)
    advc = gc.adv * gc.scale
    basec = 45
    tx = 66
    write(
        "C-lockup-tile-dot.svg",
        svg(
            f"0 0 {round(tx + advc * 3 + 8, 2)} 64",
            "Dot",
            "\n".join(
                [
                    (
                        '<rect x="8" y="8" width="48" height="48" rx="12" stroke-width="1.5" '
                        'style="fill:var(--tile,#11181B);stroke:var(--tile-line,none)"/>'
                    ),
                    halo(32, 32, 14),
                    f'<circle cx="32" cy="32" r="9.5" style="fill:{DOT}"/>',
                    f'<path d="{gc.path("D", tx, basec)} {gc.path("o", tx + advc, basec)} {gc.path("t", tx + 2 * advc, basec)}" fill="currentColor"/>',
                ]
            ),
        ),
    )
    write(
        "C-cut-tile.svg",
        svg(
            "0 0 64 64",
            "Dot",
            "\n".join(
                [
                    (
                        '<rect x="4" y="4" width="56" height="56" rx="14" stroke-width="1.5" '
                        'style="fill:var(--tile,#11181B);stroke:var(--tile-line,none)"/>'
                    ),
                    halo(32, 32, 17),
                    f'<circle cx="32" cy="32" r="12" style="fill:{DOT}"/>',
                ]
            ),
        ),
    )

    # D: geometric D, circular counter holds the dot (evenodd cut-out)
    write(
        "D-letterform-d-counter.svg",
        svg(
            "0 0 64 64",
            "Dot",
            "\n".join(
                [
                    (
                        '<path fill-rule="evenodd" fill="currentColor" d="M12 8H30A24 24 0 0 1 30 56H12Z '
                        'M31 21A11 11 0 1 0 31 43A11 11 0 1 0 31 21Z"/>'
                    ),
                    halo(31, 32, 9.5),
                    f'<circle cx="31" cy="32" r="6" style="fill:{DOT}"/>',
                ]
            ),
        ),
    )

    # E: open ring (state ring) around a centre dot; gap at upper right
    write(
        "E-orbit-ring-dot.svg",
        svg(
            "0 0 64 64",
            "Dot",
            "\n".join(
                [
                    (
                        '<path d="M54.55 23.79A24 24 0 1 1 40.21 9.45" fill="none" stroke="currentColor" '
                        'stroke-width="5" stroke-linecap="round"/>'
                    ),
                    halo(32, 32, 15),
                    f'<circle cx="32" cy="32" r="9" style="fill:{DOT}"/>',
                ]
            ),
        ),
    )


if __name__ == "__main__":
    main(sys.argv[1])
