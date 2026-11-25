"""Palette generator and contrast gate. Source of truth for src/styles/palettes.css and palettes-code.css.
Usage: uv run python scripts/palettes.py [--write]   (prints the contrast report; --write regenerates the CSS).
Neutrals and accents are defined in OKLCH; every text role is fitted by lightness until it meets its target on every surface it sits on."""

import math
import pathlib
import sys


def lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def gam(c):
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def oklch_rgb(L, C, H):
    a, b = C * math.cos(math.radians(H)), C * math.sin(math.radians(H))
    l_, m_, s_ = (
        L + 0.3963377774 * a + 0.2158037573 * b,
        L - 0.1055613458 * a - 0.0638541728 * b,
        L - 0.0894841775 * a - 1.2914855480 * b,
    )
    l, m, s = l_**3, m_**3, s_**3
    return (
        4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
    )


def hexc(L, C, H):
    for _ in range(40):  # reduce chroma until in gamut
        r = oklch_rgb(L, C, H)
        if all(-0.0005 <= x <= 1.0005 for x in r):
            break
        C *= 0.95
    return "#%02x%02x%02x" % tuple(
        round(min(1, max(0, gam(max(0, x)))) * 255) for x in r
    )


def lum(h):
    r, g, b = (lin(int(h[i : i + 2], 16) / 255) for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def cr(a, b):
    x, y = sorted((lum(a), lum(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


def fit(H, C, L0, target, bgs, dark):
    """Move L away from the surfaces (up in dark, down in light) until contrast >= target on all bgs."""
    L = L0
    for _ in range(200):
        h = hexc(L, C, H)
        if all(cr(h, b) >= target for b in bgs):
            return h
        L += 0.004 if dark else -0.004
    return h


def ang(a, b):
    return (b - a + 540) % 360 - 180


# name: neutral hue, neutral chroma, accent hue, accent chroma
PAL = {
    "sage": (85, 0.006, 160, 0.075),
    "clay": (70, 0.007, 40, 0.115),
    "ink": (260, 0.007, 255, 0.085),
    "plum": (340, 0.007, 345, 0.08),
    "sand": (90, 0.013, 78, 0.10),
    "mono": (0, 0.0, 0, 0.0),
}
LIGHT = dict(bg=0.972, surface=0.996, s2=0.944, s3=0.91, border=0.915)
DARK = dict(bg=0.18, surface=0.215, s2=0.25, s3=0.295, border=0.285)


def build(name, dark):
    nh, nc, ah, ac = PAL[name]
    N = DARK if dark else LIGHT
    sc = nc * (1.0 if not dark else 1.0)
    bg, surface, s2, s3, border = (
        hexc(N[k], sc, nh) for k in ("bg", "surface", "s2", "s3", "border")
    )
    if dark:
        bg, surface, s2, s3 = bg, surface, s2, s3
    surf = [bg, surface, s2, s3]
    out = dict(bg=bg, surface=surface, s2=s2, s3=s3, border=border)
    out["text"] = fit(nh, nc * 1.2, 0.93 if dark else 0.21, 12, surf, dark)
    out["muted"] = fit(nh, nc * 1.5, 0.74 if dark else 0.46, 6.5, surf, dark)
    out["faint"] = fit(nh, nc * 1.6, 0.64 if dark else 0.53, 4.6, surf, dark)
    if name == "mono":
        acc = "#e6e6e6" if dark else "#2b2b2b"
    else:
        acc = fit(ah, ac, 0.75 if dark else 0.50, 5.5, surf, dark)
    out["accent"] = acc
    out["on_accent"] = (
        "#101010" if cr(acc, "#101010") >= cr(acc, "#ffffff") else "#ffffff"
    )
    k = 0.7 if name == "mono" else (0.88 if name in ("sage", "ink", "plum") else 1.0)

    def sem(h, c, tgt=4.6):
        hh = h + max(-5, min(5, 0.05 * ang(h, ah))) if name != "mono" else h
        return fit(hh, c * k, 0.73 if dark else 0.48, tgt, surf, dark)

    out["success"], out["warning"] = sem(150, 0.13), sem(78, 0.12)
    out["danger"], out["info"] = sem(25, 0.15), sem(245, 0.11)
    out["thinking"] = fit(78, 0.13 * k, 0.80 if dark else 0.62, 3.2, [bg], dark)
    out["waiting"] = fit(245, 0.09 * k, 0.74 if dark else 0.56, 3.2, [bg], dark)
    out["m_plan"], out["m_auto"], out["m_bypass"] = (
        sem(165, 0.10, 4.6),
        sem(50, 0.11, 4.6),
        sem(25, 0.15, 4.6),
    )
    out["m_accept"] = sem(95, 0.09, 4.6)
    out["m_default"] = out["muted"]
    out["charts"] = [
        fit(
            h,
            0.115 * (0.8 if name == "mono" else 1),
            0.70 if dark else 0.56,
            3.2,
            [surface, bg],
            dark,
        )
        for h in ((ah if name != "mono" else 160), 245, 78, 340, 165, 25)
    ]
    codeL = dict(
        kw=(245, 0.11),
        str=(150, 0.11),
        fn=(78, 0.12),
        const=(25, 0.13),
        num=(300, 0.10),
    )
    out["code"] = {
        k2: fit(h, c, 0.76 if dark else 0.43, 4.8, [s2, s3, surface], dark)
        for k2, (h, c) in codeL.items()
    }
    out["code"]["comment"] = out["faint"]
    out["code"]["punct"] = out["muted"]
    return out


def css(name, L, D, sel):
    g = lambda k: f"light-dark({L[k]}, {D[k]})"
    rows = [
        ("bg", "bg"),
        ("surface", "surface"),
        ("surface-2", "s2"),
        ("surface-3", "s3"),
        ("border", "border"),
        ("text", "text"),
        ("text-muted", "muted"),
        ("text-faint", "faint"),
        ("accent", "accent"),
        ("accent-text", "accent"),
        ("accent-contrast", "on_accent"),
        ("success", "success"),
        ("warning", "warning"),
        ("danger", "danger"),
        ("info", "info"),
        ("state-thinking", "thinking"),
        ("state-waiting", "waiting"),
        ("mode-plan", "m_plan"),
        ("mode-default", "m_default"),
        ("mode-acceptEdits", "m_accept"),
        ("mode-auto", "m_auto"),
        ("mode-bypass", "m_bypass"),
    ]
    return f"{sel} {{\n" + "".join(f"  --{a}: {g(b)};\n" for a, b in rows) + "}\n"


def css_code(L, D, sel):
    g = lambda k: f"light-dark({L['code'][k]}, {D['code'][k]})"
    s = f"{sel} {{\n"
    for i in range(6):
        s += f"  --chart-{i + 1}: light-dark({L['charts'][i]}, {D['charts'][i]});\n"
    for a, b in (
        ("constant", "const"),
        ("string", "str"),
        ("string-expression", "str"),
        ("comment", "comment"),
        ("keyword", "kw"),
        ("function", "fn"),
        ("punctuation", "punct"),
        ("link", "kw"),
        ("number", "num"),
    ):
        s += f"  --sh-token-{a}: {g(b)};\n"
    return s + "}\n"


if __name__ == "__main__":
    root = pathlib.Path(__file__).resolve().parent.parent / "src/styles"
    a = [
        "/* GENERATED by scripts/palettes.py. Six palettes: sage (default, :root), clay, ink, plum, sand, mono. Do not edit by hand. */\n:root { color-scheme: light dark; }\n"
    ]
    b = [
        "/* GENERATED by scripts/palettes.py. Chart series and syntax-highlight tokens per palette (shiki css-variables theme). */\n:root { --sh-foreground: var(--text); --sh-background: transparent; --sh-token-parameter: var(--text); }\n"
    ]
    sw = []
    print(
        "palette  scheme  text  muted faint accent on-acc succ  warn  dang  info  think wait  plan  auto  bypass  code(min)  chart(min)"
    )
    for n in PAL:
        L, D = build(n, False), build(n, True)
        sel = ":root" if n == "sage" else f':root[data-palette="{n}"]'
        a.append(css(n, L, D, sel))
        b.append(css_code(L, D, sel))
        sw.append(
            f'.pal-sw[data-p="{n}"] {{ --p-bg: light-dark({L["bg"]}, {D["bg"]}); --p-surf: light-dark({L["s2"]}, {D["s2"]}); --p-acc: light-dark({L["accent"]}, {D["accent"]}); }}'
        )
        for sch, P in (("light", L), ("dark", D)):
            s = [P["bg"], P["surface"], P["s2"], P["s3"]]
            w = lambda k: min(cr(P[k], x) for x in s)
            cc = min(cr(P["code"][k], x) for k in P["code"] for x in s[2:])
            ch = min(cr(c, P["surface"]) for c in P["charts"])
            print(
                f"{n:8} {sch:6} {w('text'):5.1f} {w('muted'):5.1f} {w('faint'):5.1f} {w('accent'):5.1f} {cr(P['accent'], P['on_accent']):6.1f} {w('success'):5.1f} {w('warning'):5.1f} {w('danger'):5.1f} {w('info'):5.1f} {cr(P['thinking'], P['bg']):5.1f} {cr(P['waiting'], P['bg']):5.1f} {w('m_plan'):5.1f} {w('m_auto'):5.1f} {w('m_bypass'):6.1f} {cc:9.1f} {ch:10.1f}"
            )
    if "--write" in sys.argv:
        (root / "palettes.css").write_text(
            "".join(a) + "\n/* picker swatches */\n" + "\n".join(sw) + "\n"
        )
        (root / "palettes-code.css").write_text("".join(b))
