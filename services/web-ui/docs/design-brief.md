# Dot web cockpit: design brief

## Subject world
One person, one workstation, one local model. The cockpit is a quiet workshop terminal in a browser: a bench where an agent works and the owner supervises. Things that live here: a prompt line, diffs, tool calls, permission modes, a context budget, an audit trail. Mode: Operate (task first, brand in precise details).

## Three mood words
Calm. Precise. Workshop.

## Palette (brand tokens, `brand/final/tokens.css`)
- Ink and paper: neutrals tinted toward hue 227 (light `#f0f8fc` / `#161c1e`, dark `#090e11` / `#e7ecee`).
- One accent `#2E9CC4` (`--accent-text` on light for AA text).
- Amber `--state-thinking` is reserved for "thinking", nothing else.
- Grey `--state-idle` for idle.
- Semantic success/warning/danger only for verdicts, diffs and errors.

## Type
- JetBrains Mono: wordmark, chrome, labels, tool rows, code, diffs, numbers (tabular).
- Onest (Latin, Cyrillic): assistant prose and long text. Both ship via fontsource, no network at runtime.
- Scale 12 / 13 / 14 / 16 on a 1.125 step; prose 15px at 1.6, line length capped at 72ch.

## The one memorable thing
The dot. A single 10px circle is the live state of the whole product: grey idle, amber pulsing ring while thinking, accent while it needs you. It lives in the top bar, in every session row, as the prompt glyph in the composer, and in the browser tab icon. Approval arrival is the only other moment of motion: the card rises 8px and the dot flips to accent. Everything else stays still.

## Structure rules
- Left rail (sessions) + one transcript column + docked composer. No cards-in-cards; rows separated by hairlines, not boxes.
- One radius for controls (6px), one for panels (10px). Elevation by border and surface step, not shadow.
- State is always dot plus text label, never colour alone.
- Phone: rail becomes a drawer, 16px gutters, composer docked above the safe area.

## Motion
transform and opacity only, 120-220ms, ease-out custom curve; nothing animates for keyboard-initiated actions; `prefers-reduced-motion` turns the pulse into a static ring and removes translation.

## Anti-tells check
No gradients, glass, glow, emoji icons, ALL-CAPS eyebrows, numbered markers, or three-card grids. Empty states say what to do in a sentence and show the real shortcut.
