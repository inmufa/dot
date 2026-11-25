# Design audit of v3 ("Quiet") and stage 2 briefs

Screens: `shots/audit/` (gitignored; regenerate with `node scripts/audit.mjs 3204 shots/audit`, `node scripts/kit-all.mjs 4 shots/audit/kit`). Naming: `d-{light|dark}-NN-*` desktop 1440 flow, `{tablet|phone|tiny}-{scheme}-N-*` at 768/390/320, `pal-{palette}-{scheme}-N-*` six palettes on home, widgets, approval, `kit/kit-{palette}-{scheme}.png` the kit for every palette, `kit/fs-*-sheet.png` motion frame sheets.
Caveat: palette and font edits landed on the live dev stack while the audit ran, so some dark `d-*` shots already show the new neutrals and Plex Mono. Layout findings are unaffected. The N badge at the bottom-left of every shot is the Next dev indicator, not UI.

## Ranked defects

P0 (fix in stage 2, visible every day)
1. **Nested containers in approvals** (`d-light-08-plan`): card > "ExitPlanMode" label > grey inset > white code block. Three boxes for one plan. Quiet rule is hierarchy by spacing. One surface (the card), plan body directly on it, code block the only inset.
2. **Tinted alert boxes in widgets** (`phone-light-2-widgets`): four full-width pastel fills (info, ok, warn, bad) with outlined icons, different radius from every other card. Reads as a stock alert kit. Replace with a left-aligned icon + text row on the page tone, tone only on the icon and title, hairline separation.
3. **Top bar and column misalignment** (`d-light-03-answer`): title starts at the main area edge, the conversation column is centred 740px; the eye jumps. Align the top bar content to the column edge (or centre the title in the column) when the canvas is closed.
4. **Layout animation on panes**: `.app` transitions `grid-template-columns` (sidebar, rail, canvas). With canvas open at 1440 the main column is narrower than 740px so the transcript reflows every frame. Measure with a frame sheet while resizing; replace per the Motion rules below.
5. **Stop circle during approval** (`d-light-07-approval`): while a decision is pending the composer shows the black solid Stop disc. The run is paused, not running; show the disabled send state, not an alarming solid black circle.

P1
6. **Sidebar row alignment**: rows with a state dot (`Add structured logging`, `Почему падает`) push the title right; rows without do not. Titles must share one x (fixed 20px lead column, see `ListRow`).
7. **Menu and chip text size**: menu hints and the meta row (mode, Context, model) are 12px faint on the page tone, near-illegible on 320 where they clip (`tiny-dark-4-approval`). Meta row needs wrap or truncation rules: model name truncates first, Context never.
8. **Code block density**: code was 12px JetBrains Mono against 15.5 prose, header row ("python" + Copy) as tall as two code lines (`d-light-06-code`). Now 13px Plex Mono, header folds into a hover-only copy button.
9. **Approval action row on phone** (`phone-dark-4-approval`, `tiny-dark-4-approval`): three full-width stacked buttons about 56px tall each push the diff off screen. Use one primary + one quiet secondary row, Reject as text.
10. **Tab indicator**: each tab faded its own underline (no travel). Now one sliding bar (`Tabs`); canvas tabs must use it, check the Browser tab URL bar spacing under it (`d-light-14-canvas-browser`).
11. **Empty states** (`d-light-13-canvas-preview`, `d-light-14-canvas-browser`): one grey sentence at the top-left of a large blank panel. Needs a centred quiet block: icon, one line, one action.
12. **Panels share no rhythm** (`d-light-20..27`): Tasks, Memory, Skills, Settings use different header spacing, row heights and meta styles; each re-implements a row. Move to `ListRow` and one panel header (title 18/600, 16px gutter, 24px section gap).
13. **Home vertical balance** (`d-light-01-home`): greeting + composer sit at 40% height with a 300px void under; sidebar shows skeleton rows during load with no fade. Anchor the block at optical centre (46%), fade skeletons out.

P2
14. **Radius drift**: card 14, bubble 16, composer 20 and dialogs 14 mixed in one screen. Now 16/18/22 on one scale, nested radius = outer - padding.
15. **Hardcoded colours**: tooltip used a blue-grey pair outside the palette (fixed, now inverse text/bg), syntax tokens were blue-grey regardless of palette (fixed, per palette), `::selection` fixed 35% (now `--selection`).
16. **Focus ring**: `:focus-visible` forced `border-radius: 10px` on every element, squaring pills and circles. Now ring only; components own radius.
17. **Menu has no exit** (menus vanished instantly): fixed in `Popover` (100ms exit); dialogs and sheets now exit faster than they enter.
18. **Skeletons**: opacity pulse is fine (kept), but widths are uniform bars; vary widths in lists.
19. **Light mode contrast margin**: v3 light text-faint was 4.9:1 on bg but 4.1:1 on surface-3 (selected rows). Palettes are regenerated so every text role holds on all three surfaces.
20. **Mode colours**: auto (terracotta) and bypass (red) were close in hue on clay; now fitted separately per palette, still icon + label.

## Fonts
Candidates checked with fontTools on the @fontsource woff2 files (Latin, Cyrillic, Uzbek Cyrillic Қ Ғ Ў Ҳ, Uzbek Latin U+02BB/U+02BC, and `-> <= >= x`):

| Family | Latin | Cyrillic | Қ Ғ Ў Ҳ | oʻ gʻ | arrows |
|---|---|---|---|---|---|
| Onest | yes | yes | yes | yes | yes |
| Inter, IBM Plex Sans, Source Sans 3, Commissioner | yes | yes | yes | yes | no |
| Geist, Golos Text | yes | yes | yes | NO (U+02BB) | no |
| Manrope, Wix Madefor | yes | yes | NO | NO | no |
| Figtree, Hanken, Instrument Sans, Rethink | yes | NO | NO | NO | no |
| JetBrains Mono (was) | yes | yes | NO (Қ Ғ Ҳ) | NO | no |
| Geist Mono, Fira Code | yes | yes | yes | NO | no |
| IBM Plex Mono | yes | yes | yes | yes | no |
| Commit Mono, Spline Sans Mono | yes | NO | NO | NO | partial |

Decision: **Onest stays** for UI and prose (only candidate with full coverage including punctuation; Inter and Plex Sans are covered but read as the default tech look). **JetBrains Mono is replaced by IBM Plex Mono**: JetBrains lacked Қ Ғ Ҳ and both modifier letters, so Uzbek in code blocks, tool output and paths fell back to a mismatched face. Plex Mono covers all of it, has a calmer, less "IDE" colour that fits Quiet, and pairs with Onest's humanist-geometric shapes. Arrows and comparison glyphs fall back to Onest (declared in `--ff-mono`). Weights shipped: 400 and 500, latin + latin-ext + cyrillic + cyrillic-ext (unicode-range, only used subsets download). Onest stays variable. Net: fonts are not in the JS bundle; JetBrains variable removed.
Unverified: first-load JS gz measurement (no production build run; no JS dependencies changed besides removing one CSS-only font package).

## Stage 2 briefs
Use only tokens and primitives from `design-brief-v3.md` "v3.1 final". Do not add colours, radii or durations. Every item applies to every similar element.

### A. Sidebar, home, top bar, command palette
- Replace session and nav rows with `ListRow` (fixed lead column; dot goes in the lead slot; "..." in the actions slot, faint at rest, `--text-muted` on hover/focus). Titles must align across rows with and without a dot. Group labels 12/500 faint with 16px above, 4px below. Pinned first.
- Sidebar open/close and rail: remove the `grid-template-columns` transition. Sidebar content slides with `translateX` over `--dur-slow` `--ease-drawer`; snap the grid on the first frame. Rail icons fade, no width tween. Phone drawer already transform based; unify easing.
- Account row: avatar via `Avatar`/`Mark`, "Dot" label, chevron faint; menu opens upward with `Menu` origin-aware.
- Home: greeting uses `--fs-hero` with `--ls-hero`, block at 46% height, composer width = column. Skeleton rows fade out (`anim-fade` exit). Dot glide uses `--dur-slower` and `--ease-in-out`, transform only. Keep 100 greetings, typed letter by letter.
- Top bar: align to the column edge; state label only when not idle; canvas toggle pressed tint; no border. Title typing uses `anim-chunk` per character span, not layout.
- Command palette: `anim-pop` center, no animation when opened by Ctrl K (`data-kb`). Rows via `ListRow`. Result groups 12/500 faint.
- Details: see "Details by stage 2 area" at the end of this file.
- Toasts: mount exists (`ToastProvider` in layout). Use for archive (with Undo), copy, rename failure; remove ad hoc banners where a toast fits.

### B. Conversation, composer, widgets
- User bubble `--r-bubble`, `--tint-user`; message actions appear on hover/focus in a reserved row (no layout shift), 32px quiet icon buttons.
- Prose 16/1.62 `--lh-prose`, max `--prose`; headings 18/600; lists 4px between items; tables hairline only. Inline code `--code-scale`, `--surface-2`, `--r-xs`. Code block: 13px `--fs-code`, no header row at rest; language + copy as a hover/focus corner cluster; horizontal scroll with fade edge.
- Streaming: new text span gets `anim-chunk`; caret is the state dot style, not a block. Thinking indicator uses `think-dot` keyframes (three dots 0/160/320ms delay), tool rows `anim-item`.
- Activity block: one line per step, expand with `grid-template-rows` is layout; use opacity + `anim-fade` and instant height.
- Approval and plan card: ONE surface (flatten the nesting, see defect 1), actions row: primary + quiet secondary, Reject text button with `Kbd` hint; on phone same row, never three stacked full-width buttons. While pending, composer shows disabled send, not Stop.
- Widgets: replace tinted alert boxes (defect 2); charts use `--chart-1..6` only, axis text `--text-faint`, tabular numerals; cards = flat surface-2 or hairline separated, no nested radius mismatch.
- Composer: keep the one-row layout. Send circle morphs to Stop with a cross-fade of the two icons (opacity + scale 0.9 -> 1, `--t-snap`) and the disc colour change `--t-color`; width fixed. Meta row wraps by priority (model truncates first); Think toggle and mic keep 40/44px targets. Slash menu `anim-pop`, instant on keyboard.
- Rewind and context popovers: `Popover`, not custom `ctx-pop` styling; `--float-bg`, `--elev-1`.

### C. Canvas, panels, settings, browser tab, voice UI
- Canvas open: canvas pane `translateX(100%) -> 0` over `--dur-slow`, grid snaps; resize drag has no transition. Tabs use the sliding indicator; tab panels swap with `anim-view`.
- Empty states for Preview, Files, Browser: `StateBox` centred, icon + one line + one action.
- Browser tab: URL bar is a filled `Input` row 40px, back/forward/reload quiet icon buttons, loading = `Progress` indeterminate under the bar (2px), not a spinner.
- Panels (Tasks, Schedules, Memory, Skills, MCP, Tools, Audit, Rewind): one header, one gutter, `ListRow` rows, `Badge` tones for status, `Section` for groups, `Dialog` for destructive confirms, `Toast` for results.
- Settings: sections 24px apart, one control per row (label left, control right, help under label), palette picker as a 3x2 grid of swatches (use `.pal-sw`), density segmented, switches with description. Check all six palettes in light and dark with `/kit?palette=X&theme=Y`.
- Voice UI: recording dot uses `--danger` with `breathe`, level meter transform-only (`scaleY`), transcript text `anim-chunk`; keep mic and send hit targets; reduced motion = static dot.
- All screens: verify 1440/768/390/320, light/dark, six palettes (home, widgets, approval at minimum), `prefers-reduced-motion`, touch targets 44px on coarse pointers, safe areas on the dock and sheets.

## Audit gaps (not captured)
Slash menu (`d-*-09`), the session "..." menu (`d-*-18` hit the wrong row) and the approval screen in the palette run and in several responsive runs timed out because the mock session was left waiting on the plan approval from the prior step (the approval dialog never reappeared). Re-run after resetting the mock between steps. Tablet and tiny coverage is partial for the same reason. Dialog frame sheets: menu, dialog, tab, toast exist; sidebar toggle and send morph sheets are not recorded (send morph is not implemented yet, stage 2 item B).

## Details (completeness pass)
Method: code grep of every user-facing datum and interaction, plus the screenshots above. Confirmed gaps (G), partially done (P), checked and fine (OK).

Data not shown or feedback missing
- G: **User-message attachments** were not rendered (history meta had them). `UserAtts.tsx` + Turn.css now exist; stage 2 B makes them final: image thumbnails 96px (`--r-card` inner radius), max 3 per row then "+N" tile, lightbox on click (Sheet center, Esc, arrows), file tiles with type icon, name truncated with `title`, size in `.meta`; alt text = file name (done).
- G: **No message timestamps.** Show time on hover/focus of a message (12px faint, in the actions row, `title` with full date); day separators in long chats ("Today", "Yesterday") as quiet centred labels.
- G: **Disabled controls give no reason**: plus, Plan, Think and mic are `disabled={!id}` on a fresh home; disabled buttons swallow tooltips. Use `aria-disabled` + Tooltip "Start a chat first" (Tooltip must work on aria-disabled), never silent.
- G: **Flash line is ad hoc**: 16 `setFlash` calls render a bare `<p class="flash">`. Replace with `useToast` (copy confirmations "Copied", rename failed, title generated, archive with Undo, upload failed, background task finished). Keep `role=status`.
- G: **No upload error path found** (no size/type/failed message in composer attachments). Add per-attachment error state (danger icon + reason + retry/remove) and a toast for rejected drops.
- G: **Composer paste of images** not handled (only the browser frame handles paste). Add `onPaste` to the composer: image files become attachments with a toast on rejection.
- G: **Session rows truncate without a `title`** (full name only in the rename dialog). Add `title` (or the Tooltip after 450ms) on truncated rows, panel rows, tool names, file paths, and model name in the meta row.
- P: Copy confirmation: code block and message copy swap the icon (OK); `copyLast` uses flash (see above). Unify: icon swap + `aria-live` announcement, no toast for inline copy buttons.
- P: Chat title generation: titles type in, but there is no toast or announce when a background title lands while another chat is open; add a silent `aria-live` update only.
- P: Page title: `useDotState` sets `Dot` / "Thinking - Dot" (OK); add the chat title ("Refactor auth - Dot") and a favicon variant per state (`dot-idle|thinking|waiting.svg` exist in `public/`, wire them) so a background tab shows approval needed.
- OK: jump-to-latest / follow-output button exists (`Transcript.tsx`); drag-drop overlay hook exists; `dir="auto"` on widget text and tool descriptions; image alt text on browser, preview, attachments; `aria-live` on transcript, table, code copy, mic, toasts.
- G: `dir="auto"` is missing on user bubbles, chat titles in the sidebar and memory items (RTL, mixed Cyrillic/Latin names); add it, and `unicode-bidi: plaintext` on message text. Emoji and long unbroken tokens: add `overflow-wrap: anywhere` on bubbles, rows and table cells (break-ui pass not run on the new primitives; run it in stage 2).

Interaction feel
- G: Icon sizes are 12/13/14/15/16/18/20/36 (about 140 uses). Standardise to 16 (inline and menu), 18 (toolbar and icon buttons), 20 (empty states), stroke 1.75 everywhere (only 7 files set `strokeWidth`; set it once via a shared `Icon` wrapper or lucide `defaultProps`).
- G: Cursor styles: 30 declarations, set by hand per component. Rule: `cursor: pointer` on `button, [role=button], a, summary, label[for]`; `not-allowed` on `:disabled`; `text` on inputs; `grab/grabbing` on resizers; one rule in `base.css`.
- G: Scrollbars: only 4 rules; transcript, panels, code blocks and the sidebar list use the OS default. Add one themed thin scrollbar (`scrollbar-width: thin; scrollbar-color: var(--fill-active) transparent`) for `.transcript, .sheet-body, .sb-list, pre`. Overscroll: 9 containers set `overscroll-behavior: contain`; apply to every scroller and `overscroll-behavior-y: none` on `body`.
- G: Hover, active and focus feedback were audited per component in the kit (OK for kit primitives). Not yet verified on: sidebar nav rows, activity head, tool rows, source chips, widget accordion, message action icons, slash options, rewind rows. Stage 2 must give every clickable the quiet hover fill, pressed fill and the single focus ring, via `ListRow` or the `.btn` rules.
- G: Keyboard navigation: Menu has arrows, Home/End, first-letter (OK). Not verified in slash menu, command palette, session "..." menu, canvas tabs (roving, now OK in `Tabs`), segmented controls, widget accordions. Test each with keys only.
- G: Text selection: `::selection` is now tokenised; check selection inside code blocks, tables (copy as TSV) and user bubbles (selection colour against `--tint-user`).
- OK: safe-area: dock, sheets and toasts use `env(safe-area-inset-bottom)` (toast now via `--safe-b`). Not verified: left/right insets in landscape (`--safe-l|r` added, unused).
- G: Empty/loading/error states per list: Tasks, Schedules, Memory, Skills, MCP, Tools, Audit, Rewind, Files, Browser, search results each need all three via `StateBox`/`ErrorBox`/`Skeletons`; the audit captured only the happy paths (mock has "worst" cases in `e2e`, use them).
- G: Home greeting must fit ONE line on desktop (owner raised `.home-title` to 48ch); at 390 and 320 it may wrap to two balanced lines (`text-wrap: balance`). The dot glide to the top bar is being fixed by the owner; verify with a frame sheet after (target 520ms, transform only).

## Details by stage 2 area (add to the briefs above)
- A (sidebar, home, top bar, palette): row `title` tooltips, `dir=auto`, page title + state favicon, toast for archive Undo, kbd-initiated palette without animation, home one-line greeting.
- B (conversation, composer, widgets): attachments on sent messages (final design), message timestamps and day separators, paste and drop with error states, disabled-state reasons, copy feedback unified, `dir=auto` and wrapping on bubbles, aria-live for streaming kept polite and throttled, jump-to-latest styling with unread count.
- C (canvas, panels, settings, browser, voice): empty/loading/error state per list and tab, truncation tooltips on paths and names, scrollbar and overscroll rules, keyboard-only pass on every menu and tab list, icon size/stroke standard, cursor rule.


## Stage 2 character changelist (supersedes layout items above where they conflict)
Identity and tokens are in `design-brief-v3.md` "Character: the workshop log". Test each screen by hiding the logo: it must not read as Claude, ChatGPT, Gemini, Grok, Linear or Notion.

### A. Sidebar, home, top bar, palette
- Sidebar = index. Chat rows: `ListRow leader time` (plain text, dotted leader, mono relative time; "14:02" today, weekday this week, "Nov 18" older); the state dot goes in the lead slot (thinking/waiting only) and the active row gets a rail dot plus quiet fill, no pill radius. Group labels are mono lowercase with a count ("today 5", "pinned 2"), 12px faint, no caps. Nav rows (Tasks, Schedules, Memory, Skills) stay plain with 16px round-cap icons and a mono count on the right where known. Search = the one filled element, with `Ctrl K` as `Kbd`. Rail mode: the same icons, plus a vertical dotted line connecting them to the account dot.
- Account row at the bottom: "Dot" in Onest 600 with the live dot (not a mark tile), mono model name under it in faint.
- Home: left-anchored at `--col-left`, same left edge as the conversation column. Greeting in Onest Light (`--fs-hero-weight`), ONE line on desktop, the dot as caret then gliding (520ms) into the top bar. Under it one mono line: model, context window, "local" status (`.rec`). Recent chats are index rows (leader + time). The composer sits at 46% height on the rail, left aligned, not centred. Remove the centred stack.
- Top bar: state dot, mono chat number or time started, typed title in Onest 600, canvas toggle, rewind. Align its left edge with the column.
- Command palette: index rows with leaders; groups in mono lowercase; instant on Ctrl K (`data-kb`).
- Microcopy: "Nothing logged yet.", "No chats today.", "Archived. Undo".

### B. Conversation, composer, widgets
- Replace bubbles with entries: `Entry` per turn. User entry: mono "you" label above, text in Onest 600, no fill. Assistant entry: flowing text on the rail, state dot as node (live while streaming, static after). Time in the gutter (hover shows full date in `title`). Tool steps are logbook lines: `step 3 · edit · src/app.py · 0.4s` in `.rec`, expandable, each with a rail node that pops in (`anim-node`, stagger). Approval is an entry with an accent node and "needs your call" in the gutter; one flat surface, no nested boxes. On phones the gutter folds above the entry (already in `Entry`).
- Prose: list bullets are dots (`li::marker` replaced by a 6px accent-tinted dot), blockquotes get a rail line, headings 600 with a mono number if they are steps, tables use `.rec` for numeric columns, code blocks 13px Plex Mono with mono language label at the corner, no header bar.
- Streaming caret: a 6px dot, breathing, instead of the 2px bar. Thinking: the dot pulses plus a mono counter ("thinking 12s").
- Composer: ruled slot (`--r-composer`, surface, 2px accent rule under on focus), prompt dot on the rail line to its left (becomes amber/blue with state), controls as specified by the owner (one row; + and Plan left; Think, mic, send right; send a solid round dot). Meta row under it in `.rec`: mode, Research chip, "Context 22%", model.
- Attachments on sent messages: part of the entry, thumbnails with 12px radius, mono size/type under tiles.
- Widgets: charts use `--chart-*` with direct labels, numbers `.rec`; alerts become entry-like lines (dot + title, no fills); empty widgets use `DotGrid`.
- Microcopy: "Edited 2 files. Tests pass.", "Needs your call.", "Stopped by you at 14:03.", errors "Backend unreachable. Is dot-llm running?".

### C. Canvas, panels, settings, browser tab, voice UI
- Canvas opens into the empty right side without moving the text (column is left anchored); tabs Preview, Files, Browser with the sliding indicator; empty states = `StateBox grid` with a one-line wry hint.
- Panels become registers: each item a `ListRow` (leader + mono value on the right: next run, size, count, status), section headers in mono lowercase with counts, hairline rules, no cards. Tasks: step numbers in the gutter (`Entry`-style). Audit log: literally a log (`Entry` with time gutter and rail). Memory: dated entries. Schedules: mono cron string and next-run time.
- Settings: label left, control right, help in faint; palette picker shows each palette as bg + surface + dot (as now) with its name and one-word note; density segmented; section titles Onest 600, group labels mono lowercase.
- Browser tab: URL bar filled input, loading = `Progress` indeterminate (the dot travels on a hairline).
- Voice UI: recording = the dot (danger tone) breathing and a transform-only level line; transcript streams with `anim-chunk`; stop = dot-to-square morph.
- Loading states: `Progress` or skeleton lines; errors `ErrorBox` with mono code; empty `StateBox grid`.
