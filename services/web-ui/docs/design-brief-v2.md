# Dot web cockpit: design brief v2

Supersedes `design-brief.md` where they conflict (v1 said no gradients, no glass, mono chrome, 6px radius). Spec: `~/Downloads/dot_plan_ui.md` (sections 1-14). Mode: Operate (task first, brand in precise details).

## Subject and mood
One person, one workstation, one local model. A workshop where an agent works and the owner supervises. Mood words: calm, precise, alive. Target finish: ChatGPT / Claude / Gemini / Grok polish, with Dot's own identity.

## The memorable things (spend boldness here, keep the rest quiet)
1. The live dot (grey idle, amber thinking, blue waiting) everywhere state appears.
2. Permission modes as a colour and shield-icon scale: plan green, default slate, acceptEdits violet, auto magenta, bypass red (plus a thin red line along the top for the whole session).
3. The effort pill beside send, with a sliding highlight and bars that fill.

## Type
- Prose and UI: **Onest Variable** (neutral modern sans). Verified with fontTools: covers Cyrillic, Uzbek Қ Ғ Ў, and Uzbek Latin oʻ gʻ (U+02BB, U+02BC, U+2018). Geist, Golos Text and Manrope were rejected: no U+02BB glyph. Inter covers everything but is the default tell.
- Code, paths, wordmark, small labels, numbers in tables: **JetBrains Mono Variable**.
- Scale: UI 13-15 px, prose 15.5 px / 1.65 (compact: 14.5 / 1.55), greeting 28 px, tabular numbers on meters, `text-wrap: balance` on headings, `pretty` on prose. Prose measure capped (72ch / 740 px column).

## Colour (tokens in `src/styles/brand.css`, `light-dark()`, follows the system theme, dark first by habit)
Soft dark `#0e1316` (not black), three surface steps, accent `#2E9CC4` (accent-text `#4db3da` dark / `#02789b` light for AA), user bubble = accent 8 percent. Mode colours (dark / light): plan `#4CC38A/#1B7F52`, default `#93A6B0/#56666F`, acceptEdits `#A58BFA/#6B4FD8`, auto `#E06FC0/#B2308F`, bypass `#FF6B6B/#C62828`; chip tint = mode colour at 12 percent; always with icon and label. Gradients and glow only on: home backdrop, effort pill active state, ultrathink word, thinking shimmer; brand-blue/amber, never a generic purple.

## Shape and elevation
Radii: controls 10, cards 14, bubbles 16, composer 20, chips full. Shadow only on the composer and popovers (`--shadow-float`, `--shadow-pop`); 1 px inner top highlight (`--hi`) on raised surfaces; backdrop blur only on the sticky top bar and popovers.

## Layout (`src/styles/layout.css`)
Grid `[sidebar 280 | rail 56] [main] [canvas 380-760 resizable]`, column widths animate with a spring. Conversation column 740 px centred. Floating composer dock over the bottom of the stage (`--dock-h` reserved by the transcript). Mobile (<= 56rem): sidebar = drawer, canvas and panels = bottom sheets, 44 px targets, safe-area insets. On Home the same `.dock` is centred vertically (`.main[data-home="true"]`) and glides down when the first message is sent.

## Motion system (`src/styles/motion.css`)
- Springs are CSS `linear()` curves sampled from damped springs: `--t-snap` (180 ms, press, small popovers), `--t-soft` (250 ms), `--t-pop` (400 ms, slight overshoot for chips), `--t-sheet` (340 ms, panels and columns). Use as `transition: transform var(--t-snap)`. `--ease-out`, `--ease-drawer` for fades. Dynamic values: WAAPI helper in `src/lib/motion/`.
- Transform and opacity only (exceptions need a comment: grid column width animation on sidebar/canvas, clip-path reveals, height springs via `grid-template-rows: 0fr -> 1fr`).
- Press `scale(0.97)`; popovers origin-aware (`.pop`, `data-origin`), enter `scale(0.96)` + fade, exit faster than enter; never animate from scale(0); stagger 30-80 ms capped; first view only for chart draw-in and count-up.
- No animation on keyboard-initiated actions (palette open, a/s/r, slash menu open/nav).
- `prefers-reduced-motion`: fades only, static dot ring, no shimmer travel, no caret breathing.
- Hover effects behind `@media (hover: hover) and (pointer: fine)`.
- Performance: no animated blur above 8 px, no `transition: all`, no per-frame setState (write `style.transform`), no inherited CSS variable animation.

## Anti-tells (keep reviewing against these)
No ALL-CAPS tracked eyebrows, no numbered markers on non-sequences, no three-equal-card grids, no emoji icons (lucide line icons, one set), no purple gradient, no gradient text, no cards in cards, no `A · B · C` meta strings as decoration. Empty states say what to do in a sentence and show the real shortcut.

## Architecture (contracts every work package relies on)
- `src/lib/state/app.tsx`: `AppProvider` / `useApp()` is the hub (sessions `S`, `chat`, `ui`, `settings`, `effort`, `commands`, `telemetry`, `send`, `stop`, `decide`, `regenerate`, `branchFromUser`, `rewindToUser`, `compact`, `host`). Components are zero-prop and read it. `ui` (src/hooks/useUiState.ts): sidebar mode, drawer, panel, canvas `{open, tab, width}`, overlay (`palette | help | effort | model`).
- Capabilities: `src/lib/api/caps.ts` `feature(id, fn)` turns 404/405 into "not available yet" (returns null, flips `useCaps()[id]` to `"no"`). Every feature control must render a designed disabled or hidden state for `"no"`.
- API: `src/lib/api/client.ts` + `docs/ui-contract.md` (assumed until the backend's "UI features v2" section lands in `docs/api-contract.md`; wire to it when it does).
- Stream: `src/lib/stream/{events,reducer,history,turns}.ts`. `groupTurns(items, running)` gives turns with one `ActivityGroup` each; `thinkingLabel`, `activityLabel`. Items carry `at`, `endedAt`, `thinkStartedAt/thinkMs`, `seq`.
- Commands: `src/lib/commands/{registry,runner}.ts`, effort `src/lib/effort/levels.ts`, modes `src/lib/modes/meta.ts` (+ `ui/ModeIcon`), day grouping `src/lib/util/days.ts`.
- Folders: `components/{ui,shell,sidebar,home,chat,activity,composer,canvas,panels,widgets}` (each < 12 entries, files < 300 lines). Component CSS is co-located (`Foo.css` imported by `Foo.tsx`), shared tokens in `src/styles/`.

## Reviewing motion and screens
`scripts/dev-stack.mjs <slot>` starts mock + `next dev` on `3200+slot` / `8800+slot`. `scripts/pw.mjs` has `launch`, `newPage`, `VIEWPORTS`, and `frameSheet(page, dir, name, action)` which records a CDP screencast during `action()` and tiles the frames with timestamps into a PNG; Read the PNG. Judge every interaction that way, not only static shots.
