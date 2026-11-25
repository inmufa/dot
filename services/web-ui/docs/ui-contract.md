# UI contract v2 (assumed until `docs/api-contract.md` "UI features v2" lands)

Everything here is optional: a 404 or 405 means "not available yet" and flips the capability flag in `src/lib/api/caps.ts`. All HTTP goes through `src/lib/api/`; this file is the single rewiring point. Wire names are snake_case.

## Sessions
- `SessionInfo` gains optional: `pinned: bool`, `archived: bool`, `project: string|null`, `state: "idle"|"running"|"waiting"`, `parent_id: string|null`, `updated_at: iso`, `effort: Effort`.
- `GET /v1/sessions?include_archived=0|1` , `PATCH /v1/sessions/{id}` body `{title?, pinned?, archived?}` -> SessionInfo, `DELETE /v1/sessions/{id}` -> `{ok}`.
- `GET /v1/search?q=` -> `[{session_id, title, snippet, seq}]` (cap `search`).
- `GET /v1/sessions/{id}/export?format=md|json` -> text body (cap `export`).
- `POST /v1/sessions/{id}/regenerate` SSE like chat (cap `regenerate`); `POST /v1/sessions/{id}/branch {to_seq}` -> SessionInfo (cap `branch`).
- `PUT /v1/sessions/{id}/effort {effort}` -> SessionInfo (cap `effort`).

## Chat request
`POST /v1/sessions/{id}/chat` body: `{message, effort?, plan?, research?, attachments?: string[]}`.

## Effort
`type Effort = "off"|"low"|"medium"|"high"|"max"`. UI labels: Instant, Low, Medium (default), High, Max. The word `ultrathink` in a message means max for that turn.

## Commands (cap `commands`)
`GET /v1/commands` -> `[{name, args: string|null, description, group: "core"|"session"|"tools"|"extra", available: bool, reason: string|null}]`. Built-in fallback list in `src/lib/commands/registry.ts`.

## Attachments (cap `attachments`)
`POST /v1/sessions/{id}/attachments` multipart `file` -> `{id, name, mime, size, kind: "image"|"doc"|"text"}`; limits 5 files, 20 MB.

## Files and canvas (cap `files`)
- `GET /v1/sessions/{id}/files` -> `[{path, size, mtime, kind: "html"|"md"|"image"|"csv"|"code"|"other"}]`.
- `GET /v1/sessions/{id}/files/content?path=` -> raw bytes with real content type (HTML is served with a sandbox CSP).

## Projects (cap `projects`)
`GET /v1/projects` -> `[{id, name, instructions, session_count}]`, `PATCH /v1/projects/{id} {name?, instructions?}`; `POST /v1/sessions {project?}`.

## Telemetry and models (cap `telemetry`, `models`)
- `GET /v1/telemetry` -> `{model, state: "ready"|"loading"|"down", ctx_used, ctx_limit, vram_used_mb, vram_total_mb, tok_s, slots: {busy, total}, vision: bool, voice: bool}`.
- `GET /v1/models` -> `[{id, name, active: bool, size_mb, note}]`, `POST /v1/models/select {id}`.

## Stream events (added)
- `{type:"widget", call_id, kind, title?, props}`: display widget (see kinds below), persisted in the tool call.
- `{type:"sources", items:[{n, title, url, snippet?}]}`.
- `question` gains optional `fields` (form) and may carry empty `options` when `fields` is present.
- `token` events with `thinking: true` stay as today; the UI measures thinking time client side.

## Widget kinds (`Present`)
| kind | props |
|---|---|
| table | `{columns:[{key,label,type?:"text"|"number"}], rows:[Record<string,string|number|null>], caption?}` |
| chart | `{type:"bar"|"line"|"area"|"pie", series:[{name, points:[{x:string|number, y:number}]}], x_label?, y_label?, unit?}` (pie uses `series[0]`) |
| stats | `{items:[{label, value:number|string, unit?, delta?:number, hint?}]}` |
| steps | `{items:[{title, detail?, status:"done"|"active"|"todo"|"error"}]}` |
| checklist | `{items:[{text, done:boolean}]}` |
| cards | `{items:[{title, body?, badge?, meta?:[{label,value}]}]}` |
| callout | `{level:"info"|"success"|"warning"|"danger", title?, body}` |
| tabs | `{tabs:[{label, body}]}` (body is markdown) |
| accordion | `{items:[{title, body}]}` |
| choices | `{options:[string]}` (quick replies; a click sends exactly the label) |

Caps: 200 rows, 12 columns, 8 series x 200 points, 30 items, strings 2000 chars; anything else degrades to a code block.

## Form fields (`question.fields`)
`[{id, type: "single_select"|"multi_select"|"text"|"number"|"slider"|"toggle"|"date"|"rank", label, help?, required?, options?:[{label, description?}], min?, max?, step?, default?, placeholder?, multiline?}]`. Answer: `POST /v1/questions/{id}/answer {fields: {<id>: value}}` (string, number, boolean, string[] for multi_select and rank, ISO date for date). Legacy `{selected, other}` keeps working.

## Voice and vision (cap `voice`, `vision`)
Reported by telemetry (`voice`, `vision` booleans). Until true, the mic and image controls show a "not available yet" state. Planned: `POST /v1/voice/transcribe`, `/speak`.
