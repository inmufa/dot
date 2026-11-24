# Dot brand guideline

Dot is one dot. The mark is a rounded tile with a single dot at its centre; the name is set in JetBrains Mono (outlined, never typed live). The dot is also the live state indicator of the product.

## Files
| Need | File |
|---|---|
| Symbol, 25 px and up | `mark-tile-*.svg` |
| Symbol, 24 px and below (tabs, status bars) | `mark-small-*.svg`, `icon.svg` |
| Name with symbol | `lockup-horizontal-*.svg` (default), `lockup-stacked-*.svg` (square spaces) |
| States | `dot-idle|thinking|waiting[-lighttile].svg`, `mark-thinking-animated.svg` |
| Web | `favicon.ico`, `favicon-32.png`, `apple-touch-icon.png`, `icon-192.png`, `icon-512.png`, `icon-maskable-512.png`, `tokens.css` |
| Social | `og-image.png` (1200x630), `avatar-512.png` (circle-safe) |
| Terminal | `tui-mark.txt`, `tui_mark.py` |

Suffixes: `color-darktile` (accent dot on a dark tile, for light backgrounds), `color-lighttile` (accent dot on a light tile, for dark backgrounds), `mono-on-dark` (one light ink, the dot is a hole, for dark backgrounds), `mono-on-light` (one dark ink, dot is a hole, for light backgrounds). One-colour files take the colour of whatever is behind the hole.

## Clear space
Keep free space equal to the dot diameter (about 40 percent of the tile edge) on every side of the symbol or lockup. Nothing enters it: no text, edges or other logos.

## Minimum sizes
- Symbol: 16 px with `mark-small`; 24 px with `mark-tile`. Below 24 px never use `mark-tile`, its dot is too small.
- Horizontal lockup: 96 px wide (tile 38 px). Stacked lockup: 64 px wide.
- Print: symbol 6 mm, horizontal lockup 25 mm.

## Colour
| Role | Light | Dark |
|---|---|---|
| Accent (the dot) | `#2E9CC4` | `#2E9CC4` |
| Tile | `#11181B` | `#F1F5F7` |
| Wordmark | `#161C1E` | `#E7ECEE` |
| Idle | `#78858D` | `#5E6B72` |
| Thinking | `#B87A0B` | `#F0B440` |
| Waiting | `#1F8CB4` | `#2E9CC4` |

Accent is the only brand colour. Amber belongs to "thinking" and is used for nothing else. The accent dot on the light tile is 2.9:1 against the tile: that is the logo, fine as is, but do not use the accent on a light tile for UI state; use the state colours above, which pass 3:1.

## The three states
- **Idle** (dim grey): Dot is ready and doing nothing.
- **Thinking** (amber, pulsing): Dot is working. Use `mark-thinking-animated.svg`; it pulses a ring and respects `prefers-reduced-motion` (shows a still ring).
- **Waiting** (accent): Dot needs the user, for example to approve an action.

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
