# Dot brand

Logo work for Dot: five explored options and the exported final set (option C, tile and dot, v3 colourway: graphite tile, sage dot) in `final/`.

## What is where
- `options-board.html` - open this first. Self-contained, works offline, light/dark toggle. Compares the five options at 16/32/64 px, on light and dark, in one colour, and as the three state dots (idle, thinking, awaiting approval).
- `options-board.png` - screenshot of the board.
- `brief.md` - the one-page brief the options were judged against.
- `options/` - the SVG masters, 64-unit grid, text already converted to outlines.
  - `A-symbol-dot-rule.svg` symbol only
  - `B-wordmark-dot-as-o.svg`, `B-cut-d-bowl.svg` wordmark and its small-size cut
  - `C-lockup-tile-dot.svg`, `C-cut-tile.svg` lockup and its tile symbol
  - `D-letterform-d-counter.svg` letterform as symbol
  - `E-orbit-ring-dot.svg` ring and dot
- `tokens.css`, `palette-report.txt` - the original blue ramp (v1 exploration, superseded; the live tokens are in `services/web-ui/src/styles/brand.css`).
- `fonts/JetBrainsMono-OFL.txt` - licence of the wordmark font (JetBrains Mono, SIL Open Font License 1.1). The font file is not shipped; only outlines are used.
- `final/` - the exported set: lockups (horizontal, stacked), tile marks, small mark, state dots, animated thinking mark, favicon/PWA/OG rasters, TUI mark, `tokens.css`, `brand-guideline.md`.
- `tools/` - scripts that regenerate everything.

## Using the SVGs
The ink uses `currentColor`. The dot reads CSS variables with a fallback: `--dot` (colour), `--halo` (0 to 1, the pulse ring), `--tile`, `--tile-line`. `mark.svg`, `mark-small-currentcolor.svg` and `lockup-horizontal.svg` use `currentColor` for tile and wordmark. Opened on its own, an SVG shows the default sage with no halo. Set them in CSS to show a state, for example `--dot: #B87A0B; --halo: .6` for thinking.

## State colours
| State | On dark tile | On light tile |
|---|---|---|
| Idle | `#7A766D` | `#7B776E` |
| Thinking | `#D9A03A` | `#A8700A` |
| Waiting | `#7FA6C6` | `#4F7CA3` |

## Rebuild

```bash
# final/ set (pillow + playwright; the wordmark is pre-outlined in tools/wordmark.json)
uv run --no-project --with pillow --with playwright python brand/tools/export_final.py
# options/*.svg (needs the JetBrains Mono variable TTF from google/fonts, ofl/jetbrainsmono)
uv run --with fonttools python brand/tools/gen_options.py path/to/JetBrainsMono[wght].ttf
# board + screenshot (needs a Playwright headless Chromium for the PNG)
python3 brand/tools/build_board.py --png brand/options-board.png
# palette
python3 ~/projects/playbook/logo/scripts/palette.py "#2E9CC4" --ramp -o brand/tokens.css
```
