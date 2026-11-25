# Dot brand guideline

Dot is one dot. The mark is a rounded tile with a single dot at its centre; the name is set in JetBrains Mono (outlined, never typed live). The dot is also the live state indicator of the product. v3 (Quiet): the tile is warm graphite or paper, the dot is muted sage; the in-app mark follows the user's palette.

## Files
| Need | File |
|---|---|
| Symbol, 25 px and up | `mark-tile-*.svg`, `mark.svg` (currentColor tile, dot from `--dot`, for inlining) |
| Symbol, 24 px and below (tabs, status bars) | `mark-small-*.svg`, `mark-small-currentcolor.svg`, `icon.svg` |
| Name with symbol | `lockup-horizontal-*.svg` (default; `lockup-horizontal.svg` is the currentColor form), `lockup-stacked-*.svg` (square spaces) |
| States | `dot-idle|thinking|waiting[-lighttile].svg`, `mark-thinking-animated.svg` |
| Web | `favicon.ico`, `favicon-32.png`, `apple-touch-icon.png`, `icon-192.png`, `icon-512.png`, `icon-maskable-512.png`, `tokens.css` |
| Social | `og-image.png` (1200x630), `avatar-512.png` (circle-safe) |
| Terminal | `tui-mark.txt`, `tui_mark.py` |

Suffixes: `color-darktile` (sage dot on a graphite tile, for light backgrounds), `color-lighttile` (sage dot on a paper tile, for dark backgrounds), `mono-on-dark` (one light ink, the dot is a hole, for dark backgrounds), `mono-on-light` (one dark ink, dot is a hole, for light backgrounds). One-colour files take the colour of whatever is behind the hole. `currentColor` files: set `color` for the tile and wordmark, `--dot` for the dot (default `#93BFA3`, light sage, for dark tiles; set `#3A6A50` when the tile is light).

## Clear space
Keep free space equal to the dot diameter (about 40 percent of the tile edge) on every side of the symbol or lockup. Nothing enters it: no text, edges or other logos.

## Minimum sizes
- Symbol: 16 px with `mark-small`; 24 px with `mark-tile`. Below 24 px never use `mark-tile`, its dot is too small.
- Horizontal lockup: 96 px wide (tile 38 px). Stacked lockup: 64 px wide.
- Print: symbol 6 mm, horizontal lockup 25 mm.

## Colour
| Role | Light UI | Dark UI |
|---|---|---|
| Tile | `#1C1B18` (hairline `#34322D`) | `#EBE8E2` (hairline `#D4D0C6`) |
| Dot (sage) | `#93BFA3` on the dark tile | `#3A6A50` on the light tile |
| Wordmark | `#1C1B18` | `#EBE8E2` |
| Idle | `#7B776E` | `#7A766D` |
| Thinking | `#A8700A` | `#D9A03A` |
| Waiting | `#4F7CA3` | `#7FA6C6` |

Sage is the only brand colour; the values match `--accent` and `--state-*` in `services/web-ui/src/styles/brand.css`. Amber belongs to "thinking". Static files ship in sage; the app's inline mark (`components/ui/Mark.tsx`) renders the tile and dot in the opposite colour scheme to the page, so it contrasts with it and takes the accent of whichever of the six palettes is active. Sage on its tile is 8.4:1 (dark tile) and 5.1:1 (light tile).

## The three states
- **Idle** (dim grey): Dot is ready and doing nothing.
- **Thinking** (amber, pulsing): Dot is working. Use `mark-thinking-animated.svg`; it pulses a ring and respects `prefers-reduced-motion` (shows a still ring).
- **Waiting** (slate blue): Dot needs the user, for example to approve an action.

Colour must not be the only signal: pair the dot with a text label ("Thinking", "Needs approval") next to it. Do not use the states as decoration; a lit dot always means something is happening.

## Do
- Use the supplied SVGs or PNGs unchanged; scale proportionally.
- Choose the variant by background: dark tile on light, light tile or cut-out on dark.
- Use the one-colour cut-out where only one ink is available (stamps, embossing, fax, single-colour print).
- Keep the dot centred in the tile.

## Don't
- Do not retype the name in another font or add a tagline to the lockup.
- Do not recolour the tile or dot, add gradients, glows, shadows or outlines.
- Do not move the dot off centre, change its size, or turn it into a ring or a face.
- Do not place the dark tile on a dark background without its outline, or the accent on a busy photo.
- Do not use the amber or idle colours for the static logo.
- Do not stretch, rotate or crop the tile.
