# Interactive artifacts

An HTML file Dot writes opens in the Preview tab and runs, scripts included.

## Boundary
- The iframe is `sandbox="allow-scripts"`. Never add `allow-same-origin`: the page would get this app's origin.
- The backend serves it with a CSP that leaves inline script/style and `data:`/`blob:` images only. `connect-src 'none'`, no frames, no forms, nothing remote. The artifact cannot fetch, open a socket, load a CDN file, or reach `parent` (opaque origin).
- The only channel out is `postMessage` to the parent, used by the built-in error reporter. The Preview tab reads only messages whose source is its own iframe and whose shape is `{dotArtifact: 1, ...}`.
- Covered by `backend/tests/test_artifact_preview.py` (headers, inlining) and the `artifacts()` e2e (`scripts/e2e-features.mjs`): a probe page tries fetch, XHR, WebSocket, a remote image, `parent.document`, `top.location`, storage and cookies, and every one must be blocked.

## Chart library
Chart.js 4.6.2 (MIT; `backend/backend/sessions/assets/chart.umd.js`, license beside it), vendored, no CDN. Why this one: the model knows its API best (a small local model hallucinates fewer options), one UMD file, covers line/bar/pie/doughnut/radar/scatter/bubble, about 210 kB. uPlot is smaller but has no pie or radar. A page asks for it with `<script src="dot-chart.js"></script>`; the backend swaps that tag for the inlined library, so nothing is fetched.

## Writing them
The built-in skill `skills/artifacts/SKILL.md` tells the model the limits and the rules.

## Fix with Dot
The Preview tab collects errors and console warnings and lists them under the page. "Fix with Dot" sends them, with an optional note, as a normal chat message (queued if Dot is busy).
