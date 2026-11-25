# Dot web UI: design brief v3 ("Quiet")

Supersedes `design-brief-v2.md` where they conflict. Showcase of every primitive: `/kit` (dev only, 404 in production), screenshots via `node scripts/kit.mjs <slot> <outDir>` against `scripts/dev-stack.mjs <slot>`.

## Direction
Text-forward and calm. Hierarchy comes from spacing, type weight and tone steps, not outlines. One neutral ramp (3 steps), one accent used sparingly, hairlines only where they separate regions (sidebar edge, tab baseline, menu separators). Controls are quiet until hovered; secondary actions live in menus. Kept from v2: the live state dot, Onest + JetBrains Mono, mode colour scale with icon + label.

## Palette
Warm graphite neutrals (stone, not blue-grey) and one muted sage-green accent. No gradients, glow, glass blur, cyan, electric blue or purple anywhere. Chosen against the "AI tech" look: cool teal/cyan on near-black plus a radial glow. Sage is calm, reads as ink-on-paper rather than neon, and keeps AA in both themes. It is also used rarely: links, focus ring, primary button, selected state, check marks. Success green is a separate, more saturated hue and always has an icon or word.

| Token | Light | Dark |
|---|---|---|
| `--bg` | #f7f6f3 | #141311 |
| `--surface` (raised, menus, dialogs) | #fffefc | #1b1a17 |
| `--surface-2` | #efede8 | #232220 |
| `--surface-3` | #e5e2db | #2d2b27 |
| `--border` / `--hairline` | #e4e1da | #2b2925 |
| `--text` | #1c1b18 | #ebe8e2 |
| `--text-muted` | #5c584f | #a39e94 |
| `--text-faint` | #736d62 | #8b857a |
| `--accent`, `--accent-text` | #3a6a50 | #93bfa3 |
| `--accent-contrast` (label on accent) | #ffffff | #101a14 |
| `--success` / `--warning` / `--danger` / `--info` | #2a7a3b / #8a5a00 / #b03a32 / #2f6a9a | #74bd86 / #d9a03a / #e5857a / #7fb0d6 |
| dot idle / thinking / waiting | #7b776e / #a8700a / #4f7ca3 | #7a766d / #d9a03a / #7fa6c6 |
| mode plan / default / acceptEdits / auto / bypass | #2f7a55 / #5f5b53 / #7d6a2e / #a0523f / #b3302a | #6fbf94 / #a39e94 / #cdb36a / #d98a73 / #f07a70 |

All pairs pass (text 7:1+, text roles 4.5:1+, dots 3:1+) in both themes; the table is computed live in `/kit` from the resolved CSS variables. Accent was picked after the ui-ux-pro-max palette data returned only the stock "dev tool slate + run green" and cyan options, which are the look being replaced.

Quiet fills (alpha tints of text, work on every surface): `--fill-soft` 5% (resting soft button, input), `--fill-hover` 6%, `--fill-active` 10%, `--fill-accent` 14%, `--fill-accent-strong` 22%. Tones for status badges: `--tone-ok|warn|bad|info`.

## Type scale
Onest (UI, prose), JetBrains Mono (code, kbd). `--fs-xs` 12, `--fs-sm` 13, `--fs-md` 14, `--fs-ui` 15, `--fs-prose` 15.5, `--fs-lg` 17, `--fs-xl` 20, `--fs-hero` 28. Weights: 400 body, 500 controls and labels, 600 headings and primary actions. Headings use `letter-spacing: -0.01em` and `text-wrap: balance`. No all-caps eyebrows, no gradient text. Tone steps: text, `--text-muted`, `--text-faint` (faint is for hints and counts only, still 4.5:1).

## Spacing, radii, hit sizes
Spacing `--s-1..7` = 4, 8, 12, 16, 24, 32, 48. Radii: `--r-xs` 6 (badge, kbd), `--r-sm` 8 (menu item, chip, segment), `--r-ctl` 10 (button, input), `--r-menu` 12, `--r-card` 14, `--r-composer` 20, `--r-full`. Hit: `--hit` 40, `--hit-sm` 32, `--hit-touch` 44 (used automatically on `pointer: coarse`).

## Elevation
No outlines on controls. Depth only for things that float: `--ring` (1px at 8% alpha) + `--shadow-menu` for menus and popovers, `--shadow-dialog` for dialogs and sheets. Shadows are warm-tinted. Flat containers use tone only. z: `--z-dialog` 50, `--z-menu` 60, `--z-tip` 70.

## Motion
Transform and opacity only. Press/hover/pressed are colour changes (no scale, no size change, no layout shift). Floating panels: 150ms scale .96 -> 1 with transform-origin set from the anchor side (`data-origin`), reduced motion = fade. Tabs underline: scaleX with `--t-snap`. Switch knob and check marks: `--t-snap`. Entrances one-shot, exits faster. Use `--dur-*`, `--ease-out` and the spring tokens in motion.css.

## Components (src/components/ui, import from `@/components/ui`)
Each file has co-located CSS, loaded globally through `styles.ts` (imported in layout.tsx). Zero app state.
- **Button** `variant` solid|soft|ghost|danger, `size` sm|md|lg, `icon`, `loading` (width stable). States: rest, hover, active, focus-visible, disabled, loading. Solid is for the one primary action per view. Classes `btn btn-primary|btn-ghost|btn-danger btn-sm|btn-lg` still work in raw markup.
- **IconButton** `label` (required, becomes aria-label and a Tooltip), `pressed` (tinted background, same size), no border ever. Forwards ref (menu anchor).
- **Popover** (anchor helper): portal, `position: fixed`, `side` auto|top|bottom, `align` start|end, flips by free space, clamps to viewport, closes on outside press, Esc, Tab; focus goes in on open and back to the anchor on close. Plain `.floating` class, not the native-popover `.pop` (never use `.pop` for non-popover menus).
- **Menu / MenuItem / MenuSeparator / MenuLabel**: role=menu, arrows, Home/End, first-letter jump, `selected` makes a radio item with a check, `danger`, `disabled`, `hint`, `icon`, `keepOpen`. **DropdownMenu** = trigger render-prop (`{ref,onClick,aria-*}`) + Menu with own state; items auto-close.
- **Tabs**: underline, roving tabindex, arrow keys, optional `count`.
- **Chip** (interactive, `selected` tint, `color` for mode colours) and **Badge** (static; tones neutral, accent, ok, warn, bad, info; legacy `allow|ask|deny` data-tones kept).
- **Field / Input / Textarea / Select**: filled, no border; focus = inset 1.5px accent; error = inset danger + `role=alert` text. `Field` takes a render function that wires id and aria. Select is native with a chevron.
- **Switch / Checkbox / Radio**: native inputs, 44px target on touch, optional description.
- **Segmented**: radio group, selected = raised surface. Raw `.seg > label > input` markup still styled.
- **Tooltip**: wraps one control, 450ms delay (instant when chained), hidden on touch, Esc closes.
- **Card** tone flat|raised|sunken|accent; **Section** (title, hint, action).
- **Kbd**, **Skeleton/Skeletons/StateBox/ErrorBox**, **StateDot**, **ModeIcon** (unchanged).
- **Sheet** (side on desktop, bottom sheet on phone; `center` for dialogs) and **Dialog** (confirm: quiet cancel + one action, `danger`).

## Anti-tells (reject in review)
Borders on icon buttons, chips or cards; rows of visible secondary buttons; x icons that change a control's size; pill badges; gradients, glow, blur chrome, neon; accent used as decoration; same radius everywhere; fade-and-slide on every section; hover-lift on cards; all-caps labels; menus that differ in look or keyboard behaviour; colour as the only signal.

## Addendum: sidebar, home, top bar (stage 2)
- **Sidebar** 260px, page tone (`--bg`) with one inset hairline on its edge. Header: collapse and pen (borderless). Then a single filled element (search, Ctrl K), a collapsible Projects label, chat rows as plain text grouped by day (dot only while thinking or waiting, active = `--fill-active`, always-visible faint "..." menu: rename inline, pin, archive, delete via Dialog), and a "Dot" account row at the bottom that opens the tools Menu upward. Chats appear after their first message; titles type themselves.
- **Closed state: a slim 56px rail**, not fully hidden. Reason: a hidden sidebar with a floating toggle needs its own spot over the top bar content and loses the pen and search; the rail keeps the four things you reach for (expand, new chat, search, account) in one evenly spaced column of 40px borderless buttons with tooltips and nothing to clip. Mobile always uses the drawer.
- **Home**: no glow or gradient; greeting types out with the dot after the last letter and glides to the top bar; the model line is plain faint text with a status dot (word only when loading or offline), details in a kit Popover; recent chats are text rows.
- **Top bar**: flat (no border, no blur): state dot (word only when not idle), typed title, canvas toggle (pressed tint), rewind. Mode, context and verbosity live in the composer.
- The dock's top fade is now a solid `--bg` band (no gradient).

## v3.1 final (design system pass)
Supersedes the values above where they differ. Direction, owner decisions and the anti-tells are unchanged. Live reference: `/kit` with the palette and scheme switcher (`/kit?palette=clay&theme=dark`), contrast computed from resolved CSS variables for every pair below. Audit and stage 2 changelists: `design-audit-v3.md`.

### Character: the workshop log
Owner feedback: v3 reads as "Claude mixed with ChatGPT" (warm paper, soft grey sidebar, centred column, rounded bubble and pill composer). Quiet stays (flat, no gradient, glow or blur, hierarchy by type and spacing) but Dot now has its own identity. Check for every screen: with the logo hidden, could it be Claude, ChatGPT, Gemini, Grok, Linear or Notion? If yes, push further.

**Personality.** A workshop tool that belongs to one person: calm, exact, a little dry. It keeps a log of what it did and shows its work. Microcopy is terse, concrete, slightly wry, never cute-AI: "Nothing logged yet.", "Edited 2 files. Tests pass.", "Needs your call.", not "Oops!" or "Let's get started!".

**Candidates** (throwaway CSS on the real UI, `shots/audit/character/`, script `scripts/character.mjs`; the mock auto-opens its last chat, so the "home" shots show the chat view with the home composer styling):
- **A. Workshop log** (`A_logbook-*`): conversation is a log. Left-anchored column, mono time in a left gutter, a vertical rail with dot nodes, entries instead of bubbles, ruled composer, index-style sidebar with dotted leaders and mono times.
- **B. Soft round** (`B_round-*`): rounded everything, heavy display weight, big friendly dot. Reads as a consumer chat app, close to the ChatGPT bubble-and-pill layout in a different font. Rejected.
- **C. Matrix terminal** (`C_matrix-*`): dot-matrix background, uppercase mono labels, square boxes. A terminal cliche, loud texture on every screen, hurts reading. Rejected.

**Pick: A, the workshop log.** It is the only one whose structure differs from Claude and ChatGPT (their structure is a centred column of alternating blocks; ours is a ledger with a time gutter and a rail), it turns what Dot already is (a tool that acts in steps, with approvals, activity and rewind) into the layout, and it needs no decoration: the rail, the dots and the mono records are the identity. B and C are skins; A is a layout.

**Signature motif: the dot.** One shape, three sizes (`--dot-s` 6, `--dot-m` 10, `--dot-l` 18). It is the live state, the rail node of every entry, the list bullet and leader, the streaming caret, the progress head, the one accent dot in empty-state matrices, and the glide from greeting to top bar. Icons use round caps and joins (stroke 1.75) to match. Accent colour is spent on dots and the rail first.

**Signature typographic voice: two voices.** Onest speaks (prose, UI, the greeting in Light 300 at hero size, headings 600). IBM Plex Mono records (`.rec`: clock times, step numbers, paths, counts, model, tokens, kbd), always tabular, 12px, +0.02em, faint. No third family (bundle stays small; both cover Latin, Cyrillic, Uzbek). Mono micro labels are lowercase, used sparingly; no all-caps eyebrows. Rounded display faces with full Uzbek coverage (Nunito) were tested and rejected as cute; serif display (Roboto Serif, the only one with full coverage) is the Claude look.

**Signature layout: left rail, open right.** The conversation column anchors left (`--col-left`) instead of centring; width `--column-log` 52rem including a `--log-gutter` 4.5rem time column; the empty right side is where the canvas opens, so opening it never reflows the text. The composer is a ruled slot at the column width (`--r-composer` 12, flat surface, 2px accent rule under it on focus), its prompt dot sits on the rail line, send stays a solid round dot. The sidebar is an index: chat rows are plain text with a dotted leader and a mono relative time ("14:02", "Mon", "Nov 18"), group labels are mono lowercase with counts, the active row is marked by a rail dot plus the quiet fill, not a rounded pill.

**Signature motion: the dot is the actor.** It types the greeting (the dot is the caret), glides to the top bar (`--dur-glide` 520ms, transform only), pulses while thinking, pops a rail node per step (`anim-node`, 60ms stagger) so a turn visibly "splits" into steps, travels along a hairline as indeterminate progress and becomes the head of determinate progress. Everything else stays still.

**Palettes as one character.** Structure, type and dot logic are identical in all six; palettes change temperature and the dot colour, and the rail follows (`--rail` = accent 26% into the border). sage: moss, shop notebook (default); clay: kiln terracotta; ink: blueprint; plum: dark-room ledger; sand: parchment and ochre; mono: graphite, the dot is ink.

**Primitives built for it:** `Entry` (gutter time + rail node + body), `Bullet`, `.rec`, `ListRow` with `leader` and `time`, `Progress` with a dot head (determinate and travelling), `StateBox grid` / `DotGrid` (sparse dot matrix at 16% with one accent dot, empty states only), `anim-node`, tokens `--dot-*`, `--rail`, `--leader`, `--log-gutter`, `--col-left`, `--column-log`. Shown in `/kit` under "Character".

### Fonts
Onest variable (UI and prose) + **IBM Plex Mono** 400/500 (code, kbd, paths). JetBrains Mono removed: no Қ Ғ Ҳ, no U+02BB/U+02BC. `--ff-mono` falls back to Onest for arrows and comparison glyphs. Self-hosted through @fontsource; no CDN.

### Type scale (roles)
| Token | px | Use | line-height | tracking |
|---|---|---|---|---|
| `--fs-xs` | 12 | hints, counts, meta row, kbd | 1.4 | `--ls-meta` +0.006em |
| `--fs-sm` | 13 | secondary UI, captions, code (`--fs-code`) | 1.4 / code 1.55 | 0 |
| `--fs-md` | 14 | controls, menus, rows | 1.4 | 0 |
| `--fs-ui` | 15 | default text, inputs | 1.5 | 0 |
| `--fs-prose` | 16 (15 compact) | assistant prose | 1.62 | 0 |
| `--fs-lg` | 18 | section, dialog titles | 1.2 | `--ls-head` -0.012em |
| `--fs-xl` | 22 | page titles | 1.2 | -0.012em |
| `--fs-hero` | 28 to 34 clamp, weight `--fs-hero-weight` 300 | home greeting (Onest Light) | 1.2 | `--ls-hero` -0.025em |
| `.rec` | 12 mono | time, step, path, count (record voice) | 1.4 | `--ls-rec` +0.02em |
Weights 400 / 500 (controls, labels) / 600 (headings). Headings `text-wrap: balance`, paragraphs and list items `pretty`. Tabular numerals on inputs, `.num`, `.meta`; code has ligatures off and inline code is `0.88em`. Class helpers `.meta`, `.title`.

### Colour
Generated by `uv run python scripts/palettes.py --write` into `palettes.css` (neutrals, accent, semantic, state, mode, picker swatches) and `palettes-code.css` (chart-1..6, syntax). Never hand edit. Neutrals are OKLCH ramps per palette: light L .972 / .996 / .944 / .910 (bg, surface, surface-2, surface-3), dark .18 / .215 / .25 / .295; hairline `--border`. Every text role is fitted by lightness until it passes on all three surfaces: text 12:1+, muted 6.5:1+, faint 4.6:1+, accent and semantic 4.6:1+ (accent 5.5 target), mode colours 4.6:1+, dots 3.2:1+, charts 3:1+, code tokens 4.6:1+ on surface-2 and surface-3. Semantic hues (success 150, warning 78, danger 25, info 245) shift up to 5 degrees toward the palette accent and scale chroma per palette. Dark floating panels use `--float-bg` (surface-2). Palettes: sage (default) h160, clay h40, ink h255, plum h345, sand h78, mono (neutral accent, hued semantics and charts so data stays readable). Selection `--selection`, focus ring `--focus` (2px page gap + 2px accent), quiet fills 5 / 7 / 11 % text alpha (rest / hover / pressed), accent fills 14 / 22 %. `scripts/palettes.py` prints the full light and dark contrast table (all pass).

### Spacing, radii, layout, elevation
Spacing `--s-1..8` = 4, 8, 12, 16, 24, 32, 48, 64 (`--s-0` 2px optical only). Radii 6 / 8 / 10 / 12 / 16 / full (`--r-xs, sm, ctl, menu, card, full`), plus `--r-bubble` 12 (attachments, quotes), `--r-composer` 12 (ruled slot, not a pill), `--r-sheet` 22 (bottom sheets only); nested radius = outer minus padding. Elevation `--elev-1` menu, popover, tooltip, toast; `--elev-2` dialog; `--elev-3` side sheet; all tinted by `--shadow-ink`, plus `--ring`; no glow. z: dock 6, sidebar 40, dialog 50, menu 60, tip 70, toast 80. Layout: sidebar 260 (resizable), rail 56, column 740, canvas min 22rem; breakpoints 56rem (drawer, bottom sheets), 40rem (phone), 80rem (wide). Density: `--row-h` 36 roomy / 32 compact / 44 coarse, `--hit` 40 / 36 / 44. Safe areas `--safe-t|b|l|r`.

### Motion (src/styles/motion.css)
Durations: instant 80 (press tint), fast 120 (hover, colour), base 180 (menu and chip enter), sheet 240 (dialog, sheet, tab indicator), slow 320 (sidebar, canvas), slower 520 (greeting dot glide only), exit 100 (every exit). Easings: `--ease-out` for anything the user caused, `--ease-in` exits only, `--ease-in-out` for on-screen movement, `--ease-drawer` for panes and sheets; springs `--t-snap|soft|pop|sheet`.
| Interaction | Rule |
|---|---|
| press, hover | colour or tint only, `--t-color`; no scale on buttons; `.press` only for round send/stop |
| menu, popover, tooltip | `anim-pop`, origin from `data-origin` (anchor side), 180ms in, 100ms out (`data-state="closed"`, Popover keeps it mounted 110ms); tooltip fade 120ms, 450ms delay, instant when chained |
| dialog, sheet | enter 240ms (`--ease-out` / drawer), exit 160ms `--ease-in`; scrim fades alone |
| list item added live | `anim-item` 4px rise + fade; never on first paint |
| tab indicator | one bar, `transform` translate + scaleX, `--t-move` |
| panes (sidebar, canvas) | slide content with `translateX`; the grid snaps (no `grid-template-columns` tween); drag resize has no transition |
| toast | `anim-toast` in, pop-out 100ms, pause on hover |
| streaming text | `anim-chunk` fade 120ms linear per span; thinking dots `think-dot` |
| skeleton | opacity pulse, not shimmer |
| route or panel body swap | `anim-view` 180ms fade |
| send to stop | icon cross-fade + scale .9 -> 1 `--t-snap`, fixed width |
| keyboard-initiated (palette, shortcuts) | `data-kb="true"` kills animation |
Only `transform` and `opacity` animate. Reduced motion: no travel, scale or loops; 100ms fades remain.

### Components (`@/components/ui`)
Button, IconButton, Menu family, DropdownMenu, Popover (with exit), Tooltip, Tabs (sliding indicator), Chip, Badge, Field/Input/Textarea/Select, Switch/Checkbox/Radio, Segmented, Card, Section, Kbd, Mark, StateDot, Skeleton/StateBox/ErrorBox, Sheet, Dialog, plus new: **Toast** (`ToastProvider` in layout, `useToast()`), **Progress** (determinate and indeterminate), **Avatar** (initials, chart-token colour), **ListRow** (lead / title / meta / leader / time / actions slot, hover, selected, focus), **Entry** and **Bullet** (logbook), `DotGrid`.

### Do and don't
Do: take colours only from tokens; pick radius by role; use `ListRow` for every list; keep exits shorter than enters; check six palettes in both schemes. Don't: centre the conversation column, draw chat bubbles or a pill composer, add a serif display face, use all-caps eyebrows, texture anything but empty states, add hex colours, tinted alert boxes, nested cards, shadows with colour, durations outside the scale, `.pop` for menus, animation on keyboard repeat actions, `font-weight` outside 400/500/600.
