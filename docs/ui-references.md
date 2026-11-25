# UI references for the Dot web cockpit

Research date: 2026-11-24. Products: ChatGPT, Claude (claude.ai + Claude Code on the web/desktop), Gemini, Grok.

Method and honesty note: I could not open the live products (login walls), so this is built from official release notes, help centers, vendor blogs and docs, plus secondary coverage. Every claim has a URL. `[UNVERIFIED]` means it came from a secondary or aggregator source, or from memory that I could not confirm. Pixel details (exact hex values, font sizes, line length) are almost entirely unverified; the vendors do not publish them. Treat those as "describe, then test in Dot".

Sources index (used throughout):
- OpenAI release notes: https://help.openai.com/en/articles/6825453-chatgpt-release-notes
- ChatGPT Work: https://openai.com/index/chatgpt-for-your-most-ambitious-work/
- ChatGPT agent (2025 baseline): https://openai.com/index/introducing-chatgpt-agent/
- Claude Code desktop redesign: https://claude.com/blog/claude-code-desktop-redesign
- Claude Code desktop docs: https://code.claude.com/docs/en/desktop
- Claude Code on the web docs: https://code.claude.com/docs/en/claude-code-on-the-web
- Claude Code permission modes: https://code.claude.com/docs/en/permission-modes
- Claude app release notes: https://support.claude.com/en/articles/12138966-release-notes
- Gemini release notes: https://gemini.google/release-notes/
- Gemini I/O 2026 redesign (9to5Google): https://9to5google.com/2026/05/19/gemini-app-google-io-2026/
- Gemini Spark/Task help: https://support.google.com/gemini/answer/17094507
- Gemini Deep Research help: https://support.google.com/gemini/answer/15719111
- Grok Automations: https://x.ai/news/grok-automations
- Grok Bot: https://x.ai/news/introducing-grok-bot
- Grok overview: https://x.ai/grok

Date caveat: the OpenAI notes page mentions models and products (GPT-6.x, Work, Space) that I took at face value from the fetched page; WebSearch snippets of the same page disagreed on "latest" date. Re-check before quoting dates externally.

---

## 1. ChatGPT (chatgpt.com + desktop app)

### Layout
- Left sidebar, collapsible. 2026 changes: pin chats and projects, Recents either one combined list or grouped by project (Jun 18); sidebar search covers chats, projects, images, documents (Jul 14); "Space replaces Library" in the sidebar (Nov 20); remaining Work usage shown in sidebar (Aug 7); locked chats hidden from history/pinned/search (Oct 20). Source: OpenAI release notes.
- Desktop app is now one app with a global switcher Chat / Work / Codex; Chat and Work conversations are mixed in Recents (Jul 16). Menu order: Work above Codex, Scheduled, Sites. Source: release notes, https://openai.com/index/chatgpt-for-your-most-ambitious-work/
- Mobile: sidebar simplified; Images, Codex, Pulse, Apps in a horizontal strip above chats and projects (Mar 26). Android sidebar shows up to 8 recents (Aug 21).
- Header: model picker. Since Apr 28 2026 the model picker lives in the composer on web (Plus/Pro/Business); on iOS/Android it sits at the top of the conversation (Jun 10). Picker options as of Jun 10: Instant, Medium, High, Extra High, Pro Standard, Pro Extended. Later notes add GPT-6.x entries. Thinking effort moved into the picker; a Think button/slider exists (Aug 6/14).
- Content column width and composer placement: centered column, composer pinned to bottom. [UNVERIFIED, standard knowledge, no 2026 official source]
- Long conversations (more than 5 responses) get a table of contents on web (Jun 8).

### Home / empty state
- Greeting-style heading plus the composer in the center; suggestion chips exist in some states. [UNVERIFIED for 2026]
- Mobile plan-based shortcuts strip (see above).

### Message presentation
- Assistant answers are unboxed text on the page background; user messages are in a bubble. [UNVERIFIED, from general knowledge]
- Personalization (Dec 2025): adjust warmth, enthusiasm, headers/lists, emoji individually; tone presets Default, Friendly, Efficient, Professional, Candid, Quirky (Nov 2025). Shows the product treats response style as a setting, not only a prompt.
- Responses embed interactive charts (Jun 8), more visuals, and highlighted people/places/ideas that open a side panel with facts and sources (Jan 30).
- Long-form writing opens in a full-screen editor that can be saved to Library (Jun 8). Canvas was removed for GPT-5.5 models (May 28); "writing and code blocks in chat replace it".
- Fonts: [UNVERIFIED] OpenAI uses a custom sans (ChatGPT Sans / Soehne lineage). No official doc found.

### Composer
- Large paste (over 10k chars) auto-converts to an attachment (Jun 22 Free/Go, Aug 4 Enterprise/Edu). Pasted formatting preserved on web (Aug 7). "Add from library" in composer menu (Aug 7). Android quick-tools menu (Feb 13). iOS: long-press send picks a model for one message (Jun 8). Codex composer predictions accepted with Tab (beta, Oct 9).
- Voice works inside the regular chat with text and visuals alongside (Nov 25 2025), "Separate mode" setting restores old UI. Dictation button stays after text is added (Android, Aug 14).
- You can interrupt a long-running query to add details without losing progress (Nov 5 2025). GPT-6 can start answering while still thinking/using tools (Oct 7).
- Send/stop, Enter to send, Shift+Enter newline: [UNVERIFIED, assumed].

### Thinking / streaming display
- Thinking effort is a user control (slider for Plus/Pro, Think button for Free/Go, Aug 6/14). "Thought for Xs" collapsed header: I could not find an official 2026 description. [UNVERIFIED] Community threads discuss reasoning traces in UI: https://community.openai.com/t/observed-gpt-reasoning-traces-displayed-in-the-chatgpt-ui/1359726

### Tool / agent activity
- Agent (2025 baseline): runs on its own virtual computer, on-screen narration shows what it is doing, visual browser shows output, Takeover mode for logins (inputs not stored), asks permission before consequential actions (purchases), Watch Mode for critical tasks (sending email), can pause/interrupt/redirect, stop with partial results, phone notification on completion. Source: https://openai.com/index/introducing-chatgpt-agent/
- Work (Jul 9 2026 onward): follow progress, answer questions, change direction, approve important actions; user decides access, check-in cadence, approval points; Auto-review checks important connected-tool actions before they run; local (files, apps, Computer Use clicks/types in background) or cloud (built-in browser); plugins via "@" app name; Scheduled tasks (once, repeat, event trigger, monitor). Source: https://openai.com/index/chatgpt-for-your-most-ambitious-work/
- Codex has a side panel for PR review. Same source. Mobile Codex approvals exist (May 14, release notes).
- Code blocks became interactive (Feb 19): inline editing, preview of diagrams and mini apps, split-screen review.

### Citations
- Highlighted entities open a side panel with sources (Jan 30). Box/Dropbox/SharePoint files previewed beside the conversation, citations link back (Sep 10). Cmd+click on search results opens a new tab (Feb 27). Inline pill/footnote style: [UNVERIFIED].

### Theming, motion, a11y, shortcuts
- Light/dark/system. Hex values: not published. Cmd+A selects only conversation content (Feb 13). Other shortcuts: [UNVERIFIED]. No a11y notes found.

---

## 2. Claude (claude.ai, Claude Code on web and desktop)

### Layout
- Claude Code redesign (Apr 14 2026): session sidebar listing all active and recent sessions across repos, filter by status/project/environment, group by project, sessions auto-archive when PR merges/closes. Panes (terminal, file editor, preview, diff, chat) are drag-and-drop in a grid. Source: https://claude.com/blog/claude-code-desktop-redesign
- claude.ai/code got a matching look with a sessions sidebar (week 17 digest): https://code.claude.com/docs/en/whats-new/2026-w17.md
- Web: a Changes card in a panel beside chat shows `+42 -18`; click to open diff; panel toggled via "Activity panel" or "Show session rail". Source: https://code.claude.com/docs/en/claude-code-on-the-web
- Consumer Claude: Chat and Cowork merged into one experience (Sep 16), shared home for projects and artifacts (Jul 7), Customize section groups skills/plugins/connectors (Feb 25), mobile redesign rolling out Nov 20 (iOS 26+). Source: Claude release notes.
- Context + plan usage button: Context card in session details panel shows window % and breakdown by category; usage ring shows plan usage. Source: https://code.claude.com/docs/en/desktop
- Content column width: [UNVERIFIED], narrow reading column, generally ~700px.

### Home / empty state
- Consumer: greeting plus composer. [UNVERIFIED for 2026 wording]
- Code: environment selector (Local / Cloud / SSH) chosen when starting a session; mode picked in row under prompt box. Source: desktop docs.

### Message presentation and typography
- Anthropic ships custom faces "Anthropic Sans", "Anthropic Serif", "Anthropic Mono" (declared in claude.ai CSS); earlier brand pairing Styrene + Tiempos. Which face is used for chat body: sources conflict, treat as UNVERIFIED. https://type.today/en/journal/anthropic ; https://assets-proxy.anthropic.com/claude-ai/v1/_next/static/css/026d87fb2c6610cf.css
- The serif-leaning warm look (cream/paper light mode, terracotta accent) is widely described but hex values are only in third-party design-token dumps: UNVERIFIED. https://www.webdesignhot.com/design.md/claude-ai/
- Inline charts/diagrams render in responses (Mar 12), interactive apps on mobile (Mar 25). Highlight a part of a draft and type a change to edit in place (Jun 12).

### Composer
- Mode selector (Manual / Accept edits / Plan / Auto / Bypass) directly under prompt box; model, effort, mode menus have shortcuts Cmd+Shift+I, Cmd+Shift+E, Cmd+Shift+M. Queued messages: send while Claude works, it queues, click x to take it back into the box. Esc stops. Tab or Right Arrow accepts a suggested prompt. Sources: desktop docs, web docs.
- Voice on mobile; dictation on mobile and desktop. Source: https://claude.com/blog/your-thinking-partner

### Thinking / streaming display
- Transcript view modes (caret beside title, Ctrl+O cycles): Normal (tool calls collapsed to summaries, full text), Thinking (adds Claude's thinking; only appears after thinking exists), Verbose (every tool call, read, step plus thinking). Redesign blog names Verbose/Normal/Summary: the three-level idea is the same, label names differ between docs. Sources: desktop docs, redesign blog.
- Responses stream. "Thought for Xs" style header for consumer chat: [UNVERIFIED].

### Tool / agent activity
- Background tasks pane lists subagents, background shell commands, workflows; click to see output or stop. Suggested task card with Start / Do it here / Options / Start all. Plan pane in side panel. Side chat (Cmd+; or /btw) branches off with context but does not write back to the main thread. Sources: desktop docs, redesign blog.
- Cloud setup shows a live checklist of provisioning steps (clone, setup script); messages typed meanwhile are queued. Source: web docs.
- Plugin suggestion cards inline with an Add button (cloud). Source: web docs. (Upsell-ish; see section 8.)
- Subagents and `/compact` `/context` `/clear` work in cloud sessions; auto-compaction triggers before the window fills. Source: web docs.

### Approvals / permissions
- Six modes with a status line in the CLI (manual, accept edits, plan, auto, don't ask, bypass). In Manual mode you accept or reject each change in the diff. Plan approval offers: Yes and use auto mode / Yes manually approve edits / No keep planning; Ctrl+G edits plan in editor. Some actions always prompt (explicit ask rules, recognized rm/rmdir critical-path removals). Deny rules apply in every mode. Auto mode: a classifier reviews actions; "Recently blocked" tab lists denials you can approve for a retry. Source: https://code.claude.com/docs/en/permission-modes
- Desktop approval cards: computer-use app access (Allow for this session / Deny, with tier View only / Click only / Full access), browser pane external sites (Allow once / Always allow / Deny, per site), approval card before archiving another session. Source: desktop docs.
- Diff review: hover a line, click + to comment, Enter adds, Cmd/Ctrl+Enter submits all comments; Claude applies and shows a new diff. Compare against any branch. Code review card with "Walk through in changes", "Fix this one", "Apply fixes". Sources: desktop docs, web docs.
- Rewind: "Rewind to here" exists on messages (referenced in web docs troubleshooting). UI detail UNVERIFIED.

### Citations, code blocks
- Web search citations style in consumer chat: [UNVERIFIED]. Code blocks: copy button and language label are standard [UNVERIFIED for 2026].

### Errors / loading
- Named, actionable errors: "Session creation failed", "Your new session couldn't start. Your prompt is back in the box you sent it from." Failed sends restore the prompt to the composer. Source: web docs. Good pattern.

### Shortcuts, a11y
- Cmd+/ lists all shortcuts; Cmd+N new session; Cmd+Shift+B browser pane; Cmd+Shift+D diff pane; Ctrl+` terminal; Cmd+\ close pane; Esc stop. Source: desktop docs. No command palette documented. A11y: no notes found.

---

## 3. Gemini (gemini.google.com + apps)

### Layout and redesign
- "Neural Expressive" design language announced at I/O 2026 (May 19): fluid animation, vibrant colors, haptics, new typography, pill-shaped prompt box; rolling out to Android, iOS, web. Source: https://9to5google.com/2026/05/19/gemini-app-google-io-2026/
- Home: gradient background, logo and greeting centered; model picker dropdown top-left; temporary chat and account switcher top-right. Mobile drawer: New chat, Search chats, Library (was My stuff), Notebooks, Recent; profile and settings at bottom; top-level tabs "Chat" and "Spark" (Spark later renamed Task in help, with a Chat/Task toggle by the prompt box). Sources: 9to5Google; https://support.google.com/gemini/answer/17094507
- Left menu got a Customize entry (Oct 13); Skills in chat, stackable, replacing Gems (Sep 30). Source: Gemini release notes.
- Desktop: Mac app opens with Option+Space (Apr 15), Windows app with Alt+Space (Sep 10), hold Fn to dictate (Jul 29). Source: release notes.
- Responses restructured: most important info first in bold, with inline images, timelines, interactive visualizations ("generative interfaces"). Source: 9to5Google; https://blog.google/products/gemini/gemini-3-gemini-app

### Composer
- Pill-shaped; mobile "+" opens a bottom sheet: photo carousel, Camera, Files, Drive, Notebooks, then tools (Guided learning, Deep research, Canvas, Create music/video/image, Personal Intelligence). Voice on the opposite end. Live is inline (centered waveform pill: video/screen share left, mute/close right) rather than fullscreen. Source: 9to5Google.
- Deep Think chosen in the prompt bar (Feb 12). Model dropdown: 3.1 Pro, 3.5 Flash, 3.6 Flash (release notes).
- Stop button in the text box during tasks. Source: Spark/Task help.

### Thinking / research display
- Deep Research: Gemini first shows a research plan; "Edit plan" lets you change it in natural language before it starts. Source: https://support.google.com/gemini/answer/15719111
- "Show thinking" panel: [UNVERIFIED for 2026, no source found].

### Agent activity (Task, formerly Spark)
- Progress chip at top of the thread opens a work panel listing steps as Completed / Current / Planned, plus a Files section (files read or updated, clickable). Scheduled-task chip with Pause/Resume. "View live" shows the remote browser; "Take over task" then "Go back to Gemini". Export as .txt, .md, or to Drive. Source: https://support.google.com/gemini/answer/17094507
- Approvals: confirmation before each browsing task; sensitive actions always need approval (sending communications, purchases, submitting web forms, signing in). If you deny, Gemini stops and does not try another way. Same source.
- Mobile "Halo" UI shows live updates and task progress; Daily Brief in side panel. Source: 9to5Google.
- Tasks run multi-step work in the background, now free for eligible users, startable by text or forwarded email (Nov 17). Source: release notes.

### Citations, code, theming, a11y
- Sources/citation style, code block copy/run: [UNVERIFIED]. Theming: light/dark with a gradient hero; no hex published. Typography: "new typography" announced, face not named in sources I read (Google Sans family is likely [UNVERIFIED]). Motion is a stated pillar (fluid animations, haptics). No a11y notes found.

---

## 4. Grok (grok.com)

Weakest evidence of the four; xAI publishes little UI documentation.

### Layout
- Sidebar items reported around Nov 2026: Library, Grok Bot, Projects; the Imagine tab was removed ~Nov 13 and /imagine now opens chat with Image/Video mode on. Sources are tracker/aggregator pages: https://techdevnotes.com/releases/grok-web/20260817-231253Z-968f27c78bbf and https://www.roborhythms.com/?p=36564 [UNVERIFIED, conflicting about Projects].
- Official x.ai/grok says users switch modes for search, reasoning, voice, or imagery. Source: https://x.ai/grok
- Think / DeepSearch / Voice toggles above or in the input bar (aggregator, Aug 2026): [UNVERIFIED]. One source claims reasoning is always on in newer models with no toggle: conflicting.

### Automations (official)
- Jobs Grok runs on its own: triggers are schedule (once/daily/weekdays/weekly/monthly/yearly in your timezone), incoming email with sender/recipient/subject filters, manual "Run now". Editor: Triggers section with Add Trigger, Instructions box, Connectors and Skills fields, file attachments, a mode picker (shown as "Auto"), result delivery (email, app notification, both, neither), Overview and Runs tabs where each run's conversation can be reviewed. Lives at grok.com/automations and in mobile apps; can be created from chat; suggested templates. Source: https://x.ai/news/grok-automations
- Good reference for Dot's Tasks/schedules view.

### Grok Bot (official, Aug 11 2026 beta)
- Persistent cloud-computer agents that sign into your tools, remember across tasks, save shown workflows as routines, and "only come back when something needs your approval"; group-chat mode where bots coordinate. Presented as a separate download (desktop and iOS), not inside grok.com. The approval UI is not described. Source: https://x.ai/news/introducing-grok-bot
- Note: the page's download button reportedly points to a cursor domain; irrelevant to design but flags that Bot is partner-distributed.

### Thinking / DeepSearch display, message style, composer, citations
- Think shows a reasoning trace; DeepSearch shows steps and sources: [UNVERIFIED], no official 2026 UI description found. Sources mixing X posts and web results inconsistently distinguished: [UNVERIFIED].
- Dark-first look, black background: [UNVERIFIED], widely observed but no source.
- Voice 3.0 announced (https://x.ai/news): details not read.
- Shortcuts, a11y, code blocks, mobile: not found.

---

## 5. Feature inventory (feature x product)

Legend: Y = verified, with source; Y? = likely true but only from secondary sources or old (2025) sources; ? = not verified; N = verified absent or removed.

| Feature | ChatGPT | Claude | Gemini | Grok |
|---|---|---|---|---|
| Deep research | Y? (exists since 2025; not re-verified in 2026 notes) | Y? ("Research" in Help Center collection, https://support.claude.com/en/collections/18031719-features-and-capabilities) | Y, with editable plan: https://support.google.com/gemini/answer/15719111 | Y? DeepSearch (2025, https://techcrunch.com/2025/02/17/elon-musks-ai-company-xai-releases-its-latest-flagship-ai-grok-3) |
| Plan mode / plan then execute | Y? (guide only; Work page does not describe plan mode, https://openai.com/index/chatgpt-for-your-most-ambitious-work/) | Y, Plan mode with approve options: https://code.claude.com/docs/en/permission-modes | Y (editable research plan; Task work panel shows Planned steps) https://support.google.com/gemini/answer/17094507 | ? |
| Canvas / artifacts | Canvas removed for GPT-5.5, replaced by interactive code blocks and full-screen writing editor (release notes) | Y, artifacts and Artifacts tab (Sep 16), Claude Design (Apr 17): release notes | Y, Canvas in tool list: https://9to5google.com/2026/05/19/gemini-app-google-io-2026/ | Y? (Canvas-like tool 2025: https://techcrunch.com/2025/04/15/grok-gains-a-canvas-like-tool-for-creating-docs-and-apps) |
| Code execution / data analysis | Y? (interactive code blocks Feb 19 verified; data analysis sandbox not re-verified) | Y (file creation, analysis: https://claude.com/blog/your-thinking-partner) | ? | ? |
| Agent / computer use / browser | Y, Work + Computer Use + built-in browser: https://openai.com/index/chatgpt-for-your-most-ambitious-work/ | Y, Claude in Chrome (https://claude.com/blog/your-thinking-partner); computer use with per-app tiers in Code desktop | Y, Task (ex-Spark), Chrome auto browse, take over: https://support.google.com/gemini/answer/17094507 | Y, Grok Bot (separate app): https://x.ai/news/introducing-grok-bot |
| Scheduled tasks | Y, Work tasks and Scheduled page (Jun 17) | Y, cloud scheduled tasks/routines: https://code.claude.com/docs/en/claude-code-on-the-web (links to routines) | Y, scheduled-task chip, Tasks free Nov 17 | Y, Automations: https://x.ai/news/grok-automations |
| Connectors / MCP | Y, plugins with "@" (Work page) | Y, connectors and plugins in Customize; MCP in Claude Code | Y, extensions (Workspace, Maps, YouTube): https://gemini.google/overview/ | Y, connectors in Automations/Bot; MCP named for Bot: https://x.ai/news/introducing-grok-bot |
| Projects / custom instructions / personas | Y, projects with project-only memory (Aug 14), personalization sliders and tone presets | Y, projects; Customize (skills) | Y, Gems being replaced by Skills (Sep 30); Notebooks | Projects: ? (sources conflict) |
| Memory | Y, memory with Sources (May 5) | Y: https://claude.com/blog/your-thinking-partner | Y, "memories" and import from other apps (Mar 26) | Y, Bot memory: https://x.ai/news/introducing-grok-bot; chat memory ? |
| Voice mode | Y, in-chat voice (Nov 25 2025) | Y, mobile voice, dictation | Y, Live inline in chat (May 19) | Y, Voice 3.0 headline on https://x.ai/news (details unread) |
| Image generation / editing | Y? (image gen referenced in tool strips; not re-verified) | N? no native image generation listed; inline charts/diagrams only (Mar 12) | Y, "Create image" in tool sheet (9to5Google) | Y, Imagine (image and video) mode; Imagine tab removed Nov 2026 |
| Video generation | ? | ? | Y, "Create video" (9to5Google) | Y, Imagine Video 1.5 (https://x.ai/news) |
| Image / file / PDF understanding | Y, file library, attachments | Y? | Y, long document synthesis: https://gemini.google/overview/ | ? |
| Study / learning modes | ? | ? | Y, Guided learning (tool sheet) | ? |
| Share / export | Y? (sharing faster Feb 27) | Y, share session links: https://code.claude.com/docs/en/share-sessions.md | Y, public links, export .txt/.md/Drive | ? |
| Edit-and-branch / regenerate | Y, edit messages with images (Feb 27); retry menu (Mar 17) | Y, Rewind to here; side chat branch; queued message take-back | ? | ? |
| Model picker | Y, in composer (Apr 28) | Y, model/effort menus with shortcuts | Y, top-left dropdown | Y? model selector (Grok 4.3 Beta in picker, secondary) |

Many "Y?" cells are standard features I know existed in 2025; a Dot owner decision should not hinge on them without a second look.

---

## 6. Cross-cutting findings

### 6.1 What all four share (table stakes)
1. Persistent left sidebar with new chat, search, and recent history; collapsible; account and settings at the bottom.
2. One text composer, anchored at the bottom, with attachments (+), a mode/tool menu, voice entry, and a send button that becomes stop during generation.
3. Model and reasoning-effort chooser reachable from the composer or header, simplified to a few named tiers.
4. Streaming responses; ability to interrupt or steer mid-run (ChatGPT interrupt, Claude queued messages and Esc, Gemini Stop, Grok Bot approvals loop).
5. Dedicated long-running agent surface with: background execution, notifications when done, approval only for consequential actions, a visible takeover path (ChatGPT Takeover, Gemini Take over task, Claude computer-use cards, Grok Bot returns when approval is needed).
6. Scheduled/recurring automation as a first-class object (Work Scheduled page, Gemini scheduled-task chip, Claude routines, Grok Automations).
7. Connectors/plugins as a user-visible list, with per-use scoping.
8. Memory and personalization settings, with user-controllable scope.
9. Rich inline outputs (charts, diagrams, interactive visuals) rather than only text.
10. Side panel for secondary content (sources, files, diff, plan, work progress).

### 6.2 Best single idea from each
- ChatGPT: "approve at the moment of consequence, with auto-review for connected tools", plus the mid-run interrupt that keeps progress. Also: large paste becomes an attachment chip so the composer stays clean.
- Claude: transcript view modes (Normal / Thinking / Verbose) and the diff pane with line comments batched into the next message, plus queued messages you can take back. Best match to Dot's job.
- Gemini: the work panel (Completed / Current / Planned steps plus a Files section) and the editable plan before execution.
- Grok: Automations editor (Triggers, Instructions, Connectors, Skills, result delivery, Overview and Runs tabs) as a simple, legible spec for scheduled agent work.

### 6.3 Wrong for a local agent cockpit
- Upsell UI: plan badges, usage-limit nags, "Ultra only" locks, remaining Work usage in sidebar, plugin suggestion cards with Add buttons, partner download links.
- Personality tone presets and emoji sliders, greeting copy, mascot gradients (Gemini pulsating gradient, Neural Expressive motion). Decoration costs focus.
- Cloud-first assumptions: remote VM provisioning checklists, GitHub App onboarding, "environment expired".
- Hiding agent steps behind a single "Thinking..." spinner. A cockpit owner needs the steps.
- Auto-switching models without a visible indicator (ChatGPT retired it Sep 14 for Plus/Pro, notes).
- Product sprawl in navigation (Chat / Work / Codex / Sites / Scheduled / Pulse / Apps) and constant renames (Library to Space, Spark to Task, Gems to Skills, Imagine tab removed). Stable names matter.
- Social/share features and public links by default.

---

## 7. Recommendations for Dot

### 7.1 Information architecture
Single left rail, three groups, stable names:
- Work: Sessions (grouped by project, with status dot: running, needs approval, error, idle), Tasks (scheduled and background), Approvals inbox (count badge).
- Context: Projects, Memory, Skills, MCP servers.
- System: Models (local GPU status), Settings.
A global command palette (Ctrl+K) must reach every item, session, mode and model. Claude and ChatGPT docs show no palette, so this is an easy differentiator.
Persistent top status strip, one line, always visible: model + backend state (e.g. "local GPU: loaded, 21 GB/24 GB, 38 tok/s"), permission mode chip, context meter, tainted-content shield indicator.

### 7.2 Home screen
No greeting or marketing chips. A composer in the center plus, below it: resume list (3 to 5 recent sessions with status), "Needs your attention" (pending approvals, failed tasks), and scheduled tasks due next. Project and permission mode chosen before first message, remembered per project (Claude remembers mode per folder, desktop docs). Optional starter prompts only from the user's own saved prompts and skills.

### 7.3 Conversation view
- Center column, comfortable reading measure (about 70 to 80 characters for prose; code blocks may be wider and scroll horizontally). Sans UI font, optional serif toggle for prose; mono for code. Test, do not copy: specific sizes are unverified for all four.
- User messages as a compact block; assistant prose unboxed. Tool activity as a distinct, quieter lane between them.
- Three view levels copied from Claude: Summary (tool calls collapsed to one-line summaries), Normal, Verbose (every call plus reasoning). Per-session toggle, shortcut, remembered.
- Reasoning: collapsed "Thought for Xs" row, expandable; local models may emit raw traces: label them as raw. Show elapsed time and tokens.
- Queue messages while the agent runs; show them as chips with an x to retract (Claude pattern). Esc stops; stop leaves partial work and says what was applied.
- Right side panel, tabbed and resizable: Plan, Changes (diff), Tasks/Subagents, Context, Sources. Panel state is per session.

### 7.4 Dot-specific features, how to show them
- Permission modes (5 levels): a mode chip in the composer row and the status strip, cycle with Shift+Tab (matches Claude CLI), full menu with Ctrl+Shift+M. Color plus icon plus word, never color alone. Each level has a one-line plain description in the menu. The highest level needs a confirm step and a persistent red-bordered banner while active. Deny rules shown as always-on regardless of mode, as Claude documents.
- Tool calls: row per call: icon, tool, one-line arg summary, duration, status. Expand for full input/output. Group consecutive reads. Long output truncates with "show all".
- Approval diffs: inline card in the stream at the point of the request, with the unified diff, Approve / Deny / Approve for session / Edit; keyboard-first (Y, N, A). Also appear in the Approvals inbox so nothing is lost when away. Line comments batched into the next message (Claude pattern, Cmd/Ctrl+Enter). Split/unified toggle. Denied means stop and say so (Gemini: do not try another way).
- Subagents: nested, collapsible block in the stream with name, goal, status, and a link into a Tasks pane entry (Claude "Background tasks" pane). Cancel button per subagent.
- Tasks: Grok Automations-style spec (trigger, instructions, connectors, skills, delivery) with Overview and Runs tabs; Gemini-style Completed/Current/Planned list for the live plan.
- Context meter with compaction: a small ring or bar in the status strip, click opens category breakdown (Claude Context card). Show a threshold marker where compaction triggers, a "compacted here" divider in the transcript with the summary expandable, and a Compact now action with optional focus text. After compaction the earlier messages remain readable but are marked as summarized for the model.
- Rewind: "Rewind to here" on every user message, with a preview of what file changes would be reverted; creates a branch rather than destroying the later turns by default. Side chat (Claude Ctrl+;) for questions that must not pollute context.
- Memory: Memory page plus an inline chip "memory used" when a memory influenced a turn, with a one-click view and forget. No silent writes: new memories shown as a proposal.
- MCP: per-server row with state (connected, auth needed, error), tool list, per-tool permission, and last call. Tool calls display server/tool.
- Skills: list with description, source, enabled; slash and "@" invocation; show "skill loaded" row in the stream.
- Tainted / untrusted content shield: untrusted content (web pages, files from outside, MCP output) rendered with a distinct left rule and a "untrusted" tag; any tool call whose arguments derive from tainted content gets a visible "influenced by untrusted input" badge in the approval card, and cannot be auto-approved in lower modes. Shield state (on, N items quarantined) in the status strip. None of the four has this; it is Dot's differentiator. No reference to copy: design and user-test it.
- Local GPU model status: model name, quantization, VRAM used/total, load state, tokens/s, queue; click to load/unload/swap. When the model is loading or the GPU is busy, show it in the composer as a disabled-with-reason send button rather than a silent spinner. Errors like out-of-memory are first-class messages with a fix action.

### 7.5 Errors, empty, loading
- Every error names the cause and gives one action; failed sends return the prompt to the composer (Claude).
- Skeletons only for lists; streaming text needs no skeleton. Empty states say what to do next in one line with the shortcut.
- Offline or backend-down state banner with last-seen time.

### 7.6 Theming, motion, mobile, a11y
- Dark and light, system default; semantic tokens (surface, text, border, accent, danger, warn, ok, tainted) so permission and taint colors are consistent. Do not depend on hex values from the products; none are officially published.
- Motion: 120 to 200 ms for state changes, no looping decorative animation (Gemini's fluid motion is not a goal). Respect prefers-reduced-motion. Stream text without per-token animation.
- Mobile: one pane at a time; bottom composer; approvals as a bottom sheet with large Approve/Deny; notifications for approvals and finished tasks (ChatGPT agent and Claude mobile both do this). Diffs read-only on phone, comment support optional.
- Accessibility: all approvals operable by keyboard; focus returns to composer after approve/deny; live region announces "approval needed" and "run finished"; status never conveyed by color alone; minimum 4.5:1 text contrast; visible focus ring; ARIA roles for tree and tabs. Nothing in the four vendors' public material documents a11y, so this is a Dot standard, not a copied one.
- Shortcuts to ship: Ctrl+K palette, Ctrl+/ shortcut list, Ctrl+N new session, Esc stop, Shift+Tab cycle mode, Ctrl+O cycle view level, Ctrl+Shift+D diff pane, Ctrl+; side chat, Ctrl+Enter submit review comments (all but Ctrl+K taken from Claude Code desktop docs).

### 7.7 Anti-patterns to avoid
- Spinner-only "Thinking..." with no steps.
- Approval dialogs as modals that block reading the transcript; use inline cards that can be scrolled around.
- Per-action prompts with no "approve for session" (prompt fatigue; Claude added Auto mode for this).
- Mixing model output and system chrome in the same visual style (user cannot tell what the agent said versus what Dot did).
- Hidden mode changes or hidden model auto-switching.
- Decorative gradients, mascots, greeting copy, upsell cards.
- Renaming and relocating core nav items.
- Destructive actions (delete session, bypass mode, rewind that drops work) without confirm.
- Color-only status.

---

## 8. Design principles for Dot (short list)
1. The cockpit shows state, not personality: always visible mode, model, context, shield, GPU.
2. Steps over spinners: every agent action is a row you can expand, never a hidden wait.
3. Ask at the moment of consequence, inline, with the diff, and make the keyboard path faster than the mouse.
4. Permission is a visible, one-keystroke-changeable property, with plain-language levels and an always-on deny layer.
5. Untrusted content is visually and structurally distinct everywhere it appears.
6. Three levels of detail (Summary, Normal, Verbose) for the same transcript, not three screens.
7. Nothing is lost when you step away: queue, approvals inbox, notifications, resumable sessions.
8. Reversible by default: rewind, retract queued message, branch instead of overwrite.
9. Stable names and layout; one primary rail, one command palette, no upsell or promo surfaces.
10. Calm motion, high contrast, full keyboard and screen-reader support, because this tool is used for hours.
