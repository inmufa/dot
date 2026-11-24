"""Build brand/options-board.html (self-contained) from brand/options/*.svg and optionally screenshot it.

python3 brand/tools/build_board.py [--png brand/options-board.png]
"""

from __future__ import annotations

import argparse
import html
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN = (
    "<image",
    "<text",
    "<script",
    "<foreignObject",
    "font-family",
    "<mask",
    "<filter",
)

# id -> (title, architecture, full file, small-size file, mono knock-out?, rationale)
OPTS = [
    (
        "A",
        "Dot on a rule",
        "Symbol only",
        "A-symbol-dot-rule",
        "A-symbol-dot-rule",
        (False, False),
        "One solid dot resting on a prompt rule: the period at the end of a sentence, the cursor line of a terminal.",
        "The purest read of the brief: the mark IS the state indicator. Weakness: no letter, so it is ownable only through repetition and the rule is the only thing separating it from a generic status LED.",
    ),
    (
        "B",
        "dot, the o is the dot",
        "Wordmark",
        "B-wordmark-dot-as-o",
        "B-cut-d-bowl",
        (True, False),
        "Lowercase JetBrains Mono Semibold, outlined. The o is replaced by a solid disc at 86% of its height.",
        "Name and idea in one glance; the dot is a letter, so the state indicator sits in the name. Weakness: needs a small cut (d with a filled bowl) below about 96 px wide, and the disc must stay larger than a period or it reads as a typo.",
    ),
    (
        "C",
        "Tile + Dot",
        "Lockup",
        "C-lockup-tile-dot",
        "C-cut-tile",
        (True, True),
        "Rounded tile holding the dot, set beside a capitalised Dot wordmark in the same mono face.",
        "The most practical set: tile is the favicon, app icon and avatar, the lockup is the header. Quietest and most conventional; the dot is large and survives 16 px. Weakness: tile-plus-dot is close to many status and app icons.",
    ),
    (
        "D",
        "D with a dot counter",
        "Letterform as symbol",
        "D-letterform-d-counter",
        "D-letterform-d-counter",
        (False, False),
        "Geometric D, flat stem and a true semicircular bowl; the counter is a circle that holds the live dot.",
        "Initial and idea fused: the counter is the dot's home, so state changes happen inside the letter. Distinct silhouette, works in one colour as a cut-out. Weakness: the inner dot is small at 16 px, so the favicon cut needs a bigger dot and smaller hole.",
    ),
    (
        "E",
        "Ring and dot",
        "Monogram / orbit",
        "E-orbit-ring-dot",
        "E-orbit-ring-dot",
        (False, False),
        "Open ring (310 degrees, round caps) around a centre dot; the gap sits upper right like a spinner start.",
        "Reads as a state ring: it can rotate while thinking. Strong motion story. Weakness: closest to power and loading icons, and the ring is thin at 16 px unless thickened.",
    ),
]

CSS = """
@property --halo { syntax: '<number>'; inherits: true; initial-value: 0; }
:root { --page:#f0f8fc; --card:#fff; --text:#161c1e; --muted:#5b656a; --line:#d5dee3;
  --accent-ui:#027a9d; }
:root[data-theme=dark] { --page:#090e11; --card:#11171a; --text:#e7ecee; --muted:#97a0a4; --line:#2b3134; --accent-ui:#2e9cc4; }
* { box-sizing:border-box; }
body { margin:0; background:var(--page); color:var(--text); font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif; }
header,main,footer { max-width:1180px; margin:0 auto; padding:0 24px; }
header { padding-top:28px; display:flex; gap:16px; align-items:baseline; flex-wrap:wrap; }
h1 { margin:0; font-size:22px; letter-spacing:-.01em; }
header p { margin:0; color:var(--muted); flex:1 1 320px; }
button { font:inherit; color:var(--text); background:var(--card); border:1px solid var(--line); border-radius:8px; padding:6px 12px; cursor:pointer; }
button:focus-visible { outline:2px solid var(--accent-ui); outline-offset:2px; }
h2 { font-size:15px; margin:32px 0 10px; }
.opt { background:var(--card); border:1px solid var(--line); border-radius:14px; margin:16px 0; padding:18px; }
.opt h3 { margin:0; font-size:17px; } .opt h3 small { color:var(--muted); font-weight:400; margin-left:8px; }
.why { color:var(--muted); margin:6px 0 14px; max-width:80ch; } .why b { color:var(--text); font-weight:600; }
.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:12px; }
.panel { border-radius:10px; padding:12px; border:1px solid var(--line); }
.cap { font-size:11px; opacity:.75; margin-bottom:8px; }
.row { display:flex; align-items:flex-end; gap:16px; flex-wrap:wrap; }
.cell { display:flex; flex-direction:column; align-items:center; gap:4px; font-size:10px; opacity:.9; }
.cell svg { display:block; height:var(--h); width:auto; }
.pl { --bg:#f0f8fc; --ink:#161c1e; --accent:#2C9AC2; --amber:#B87A0B; --idle:#85919A; --tile:#11181B; --tile-line:none; background:var(--bg); color:var(--ink); }
.pd { --bg:#090e11; --ink:#e7ecee; --accent:#2E9CC4; --amber:#F0B440; --idle:#5E6B72; --tile:#1b252a; --tile-line:#3a464c; background:var(--bg); color:var(--ink); }
.panel { --dot:var(--accent); }
.mono { --dot:currentColor; --tile:currentColor; --tile-line:none; }
.mono .knock { --dot:var(--bg); }
.st-idle { --dot:var(--idle); --halo:0; } .st-think { --dot:var(--amber); --halo:.55; } .st-wait { --dot:var(--accent); --halo:.9; }
.st-think { animation:pulse 1.6s ease-in-out infinite; }
@keyframes pulse { 0%,100% { --halo:0; } 50% { --halo:.7; } }
@media (prefers-reduced-motion:reduce) { .st-think { animation:none; --halo:.55; } }
.trio { display:flex; gap:18px; align-items:flex-end; flex-wrap:wrap; } .trio .cell { max-width:100%; }
.pal { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:8px; }
.sw { border:1px solid var(--line); border-radius:10px; overflow:hidden; background:var(--card); }
.sw i { display:block; height:44px; } .sw span { display:block; padding:6px 8px; font-size:12px; }
.sw code { color:var(--muted); font-size:11px; }
table { border-collapse:collapse; width:100%; font-size:13px; } td,th { text-align:left; padding:6px 8px; border-bottom:1px solid var(--line); }
.rec { border-left:4px solid var(--accent-ui); padding:4px 16px; background:var(--card); border-radius:0 10px 10px 0; }
footer { padding-bottom:48px; color:var(--muted); font-size:12px; }
.side { display:flex; gap:12px; flex-wrap:wrap; }
"""

JS = """
const root=document.documentElement;
function set(t){root.dataset.theme=t;try{localStorage.setItem('dotTheme',t)}catch(e){}}
let t=null;try{t=localStorage.getItem('dotTheme')}catch(e){}
set(t||(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'));
document.getElementById('tg').onclick=()=>set(root.dataset.theme==='dark'?'light':'dark');
"""


def load(name: str) -> str:
    svg = (ROOT / "options" / f"{name}.svg").read_text(encoding="utf-8").strip()
    root = ET.fromstring(svg)  # noqa: S314 - own SVGs from options/, parse check
    if (
        "viewBox" not in root.attrib
        or "width" in root.attrib
        or "height" in root.attrib
    ):
        sys.exit(f"{name}: viewBox required, width/height forbidden")
    bad = [t for t in FORBIDDEN if t in svg]
    if bad:
        sys.exit(f"{name}: forbidden {bad}")
    return svg


def cells(svg: str, heights, label=lambda h: f"{h}") -> str:
    return "".join(
        f'<div class="cell" style="--h:{h}px">{svg}<span>{label(h)}</span></div>'
        for h in heights
    )


def option(o) -> str:
    oid, title, arch, full_n, small_n, knock, build, why = o
    full, small = load(full_n), load(small_n)
    ks, kf = (" knock" if x else "" for x in knock)

    def panel(theme):
        return f'<div class="panel {theme}">'

    out = [
        f'<section class="opt" id="{oid}"><h3>{oid} - {html.escape(title)}<small>{arch}</small></h3>',
        f'<p class="why"><b>Construction.</b> {html.escape(build)}<br><b>Verdict.</b> {html.escape(why)}</p>',
        '<div class="grid">',
    ]
    for theme, name in (("pl", "Light"), ("pd", "Dark")):
        out.append(
            f'<div class="panel {theme}"><div class="cap">{name}: small tier 16 / 32 / 64 px</div>'
            f'<div class="row">{cells(small, (16, 32, 64))}</div>'
            f'<div class="cap" style="margin-top:12px">Full mark, 32 / 64 px high</div>'
            f'<div class="row">{cells(full, (32, 64))}</div></div>'
        )
    for theme, name in (("pl", "Light"), ("pd", "Dark")):
        out.append(
            f'<div class="panel {theme} mono"><div class="cap">{name}: one colour (dot is a cut-out where it sits on ink)</div>'
            f'<div class="row"><div class="row{ks}">{cells(small, (16, 32, 64))}</div>'
            f'<div class="row{kf}">{cells(full, (48,), lambda h: "full")}</div></div></div>'
        )
    for theme, name in (("pl", "Light"), ("pd", "Dark")):
        trio = "".join(
            f'<div class="cell st-{s}" style="--h:{36 if full_n.startswith("B") else 48}px">{full}<span>{lab}</span></div>'
            for s, lab in (
                ("idle", "idle"),
                ("think", "thinking (pulse)"),
                ("wait", "awaiting approval"),
            )
        )
        out.append(
            f'<div class="panel {theme}"><div class="cap">{name}: state trio</div><div class="trio">{trio}</div>'
            f'<div class="cap" style="margin-top:12px">State dot at 16 px</div><div class="row">'
            + "".join(
                f'<div class="cell st-{s}" style="--h:16px">{small}<span>{s}</span></div>'
                for s in ("idle", "think", "wait")
            )
            + "</div></div>"
        )
    out.append("</div></section>")
    return "\n".join(out)


def build() -> str:
    cards = "\n".join(option(o) for o in OPTS)
    pal = [
        (
            "Accent / awaiting",
            "#2C9AC2 light, #2E9CC4 dark",
            "3.0:1 on light bg, 6.2:1 on dark bg",
            "#2E9CC4",
        ),
        (
            "Thinking (amber)",
            "#B87A0B light, #F0B440 dark",
            "3.4:1 on light, 10.5:1 on dark",
            "#D8982A",
        ),
        (
            "Idle (dim)",
            "#85919A light, #5E6B72 dark",
            "3.0:1 on light, 3.5:1 on dark",
            "#74808A",
        ),
        ("Ink", "#161C1E light, #E7ECEE dark", "16:1 on either bg", "#161C1E"),
        ("Surface", "#F0F8FC light, #090E11 dark", "tinted toward hue 227", "#F0F8FC"),
    ]
    sw = "".join(
        f'<div class="sw"><i style="background:{c}"></i><span><b>{n}</b><br><code>{h}</code><br>{r}</span></div>'
        for n, h, r, c in pal
    )
    return f"""<!doctype html>
<html lang="en" data-theme="light"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dot logo options</title><style>{CSS}</style></head><body>
<header><h1>Dot: logo options</h1><p>Five architectures, one dot. Each is tested at 16 / 32 / 64 px on light and dark, in one colour, and as the three live states. Text is outlined (JetBrains Mono, SIL OFL 1.1). Nothing is exported yet.</p>
<button id="tg" type="button" aria-label="Toggle page theme">Light / dark</button></header>
<main>
<h2>Palette (OKLCH ramp from #2E9CC4, hue 227; palette.py exit 0, all WCAG checks pass)</h2>
<div class="pal">{sw}</div>
<p style="color:var(--muted);font-size:12px">One accent hue. Amber is reserved for the thinking state, never decoration. Full ramp and tokens: tokens.css, palette-report.txt. Idle on dark is 3.5:1, above the 3:1 graphic floor; light-theme accent is exactly 3.0:1, so on light backgrounds the dot needs size, not thinner strokes.</p>
<h2>Options</h2>
{cards}
<h2>Recommendation</h2>
<div class="rec"><p><b>D, the letterform with the dot counter</b>, used with a Dot wordmark in JetBrains Mono, and the bare dot lifted out as the product's state indicator.</p>
<ul><li>It is the only option where letter and idea are one object: the dot lives in the D, so idle / thinking / waiting happen inside the brand mark.</li>
<li>Strongest silhouette of the five and a clean one-colour version (the counter is a true cut-out).</li>
<li>The dot alone (A's core) already exists in the UI as the status light, so the mark and the live indicator rhyme without duplicating.</li>
<li>Fix before export: a favicon cut with a larger dot (r 7.5) and smaller hole (r 10); the 16 px dot is only about 1.5 px in the current draft.</li>
<li>Fallback if the owner wants zero risk at 16 px: C (tile), which is the most robust app icon.</li></ul></div>
</main>
<footer><p>Source: brand/options/*.svg, brand/tools/. Open licence record: brand/fonts/JetBrainsMono-OFL.txt.</p></footer>
<script>{JS}</script></body></html>"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--png", type=Path)
    a = ap.parse_args()
    out = ROOT / "options-board.html"
    out.write_text(build(), encoding="utf-8")
    print("wrote", out)
    if a.png:
        cache = Path.home() / ".cache/ms-playwright"
        c = sorted(
            cache.glob(
                "chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell"
            )
        ) or sorted(cache.glob("chromium_headless_shell-*/*/chrome-headless-shell"))
        if not c:
            sys.exit("no headless chrome")
        subprocess.run(  # noqa: S603 - fixed args, local chrome binary
            [
                str(c[-1]),
                "--no-sandbox",
                "--hide-scrollbars",
                f"--screenshot={a.png.resolve()}",
                "--window-size=1280,5200",
                out.resolve().as_uri(),
            ],
            check=True,
            capture_output=True,
        )
        print("wrote", a.png)


if __name__ == "__main__":
    main()
