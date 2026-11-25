---
name: artifacts
description: Build an interactive page (chart, dashboard, calculator, small game, visual explainer) as one self-contained HTML file that previews and runs in Dot's canvas. Use for "make a chart", "visualize", "interactive", "dashboard", "calculator", "demo page".
triggers: chart, graph, plot, visualize, dashboard, interactive, calculator, game, simulation, html page, artifact
---

# Interactive artifacts

Write ONE self-contained `.html` file with Write. Dot opens it in the Preview tab and runs it.
Scripts work, but the page lives in a locked box:

- No network of any kind: no fetch, XHR, WebSocket, CDN script, web font, remote image or
  `<link>`. Anything remote is blocked and shows up as an error.
- No access to the parent app, cookies or storage. Do not use localStorage or `window.parent`.
- Allowed: inline `<script>` and `<style>`, `data:` and `blob:` images, `<canvas>`, SVG, CSS animations.

## Charts
Load the bundled Chart.js 4 with exactly this tag (Dot inlines it, nothing is fetched):

```html
<script src="dot-chart.js"></script>
```

Then use `new Chart(canvas, { type, data, options })`. Put the data inline in the script as
JS arrays. Types: line, bar, pie, doughnut, radar, scatter, bubble, polarArea. Set
`options.responsive = true` and give the canvas a parent with a fixed height.

## Rules for a good one
1. Single file, no build step, no imports. Plain JS (no frameworks, no modules from URLs).
2. Embed the data. If the data is big, sample or aggregate it first with Bash, then paste the result.
3. Make it responsive (works at 360 px wide) and readable in a dark or light page: set
   `color-scheme: light dark` and use system fonts.
4. Label axes and units, add a title, keep legends short. Controls (sliders, selects,
   buttons) must update the view live.
5. Wrap risky code in try/catch and show a visible message instead of a blank page.

## Fixing problems
Errors and blocked requests are collected by the preview. When the user clicks "Fix with
Dot" you receive them in a message: Read the file, fix the cause, Write the whole file again.
Do not add network calls to work around a blocked request: embed the data instead.
