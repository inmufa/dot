# Third-party material

## Bundled skills (`skills/`)

Copied unmodified, except for an added `requires:` frontmatter line on atlassian-mcp, docx, pptx, xlsx, frontend-slides and impeccable. skill-creator: its scripts for description optimisation (`run_eval.py`, `improve_description.py`) call the `claude` CLI, which Dot does not ship, so those scripts do not work in Dot; the skill itself needs no binary and declares none.

License evidence, per group:
- Jeffallan skills (MIT): each SKILL.md frontmatter says `license: MIT` and names the author; the upstream repository LICENSE (MIT, "Copyright (c) 2025", no holder named) is kept as `skills/LICENSE-Jeffallan-claude-skills.txt`.
- docx, pdf, pptx, xlsx, skill-creator (Apache-2.0): each directory ships a `LICENSE.txt` containing the Apache License 2.0 text, as provided with the skills; the frontmatter of docx/pdf/pptx/xlsx says "Complete terms in LICENSE.txt". No copyright holder is named in those files.
- impeccable (Apache-2.0): evidence is the frontmatter line `license: Apache 2.0` only; the standard Apache-2.0 text was added as `impeccable/LICENSE.txt`.
- frontend-slides (MIT): `LICENSE` file, Copyright (c) 2025 Zara Zhang.


| Skill | Author | License |
|---|---|---|
| api-designer | https://github.com/Jeffallan | MIT |
| architecture-designer | https://github.com/Jeffallan | MIT |
| atlassian-mcp | https://github.com/Jeffallan | MIT |
| code-reviewer | https://github.com/Jeffallan | MIT |
| database-optimizer | https://github.com/Jeffallan | MIT |
| debugging-wizard | https://github.com/Jeffallan | MIT |
| devops-engineer | https://github.com/Jeffallan | MIT |
| django-expert | https://github.com/Jeffallan | MIT |
| docx | not stated | Apache-2.0 (LICENSE.txt) |
| fastapi-expert | https://github.com/Jeffallan | MIT |
| feature-forge | https://github.com/Jeffallan | MIT |
| frontend-slides | Zara Zhang (LICENSE) | MIT (LICENSE) |
| fullstack-guardian | https://github.com/Jeffallan | MIT |
| impeccable | not stated | Apache-2.0 |
| javascript-pro | https://github.com/Jeffallan | MIT |
| mcp-developer | https://github.com/Jeffallan | MIT |
| nextjs-developer | https://github.com/Jeffallan | MIT |
| pdf | not stated | Apache-2.0 (LICENSE.txt) |
| playwright-expert | https://github.com/Jeffallan | MIT |
| postgres-pro | https://github.com/Jeffallan | MIT |
| pptx | not stated | Apache-2.0 (LICENSE.txt) |
| prompt-engineer | https://github.com/Jeffallan | MIT |
| python-pro | https://github.com/Jeffallan | MIT |
| react-expert | https://github.com/Jeffallan | MIT |
| react-native-expert | https://github.com/Jeffallan | MIT |
| secure-code-guardian | https://github.com/Jeffallan | MIT |
| security-reviewer | https://github.com/Jeffallan | MIT |
| skill-creator | not stated | Apache-2.0 (LICENSE.txt) |
| spec-miner | https://github.com/Jeffallan | MIT |
| sql-pro | https://github.com/Jeffallan | MIT |
| test-master | https://github.com/Jeffallan | MIT |
| the-fool | https://github.com/Jeffallan | MIT |
| typescript-pro | https://github.com/Jeffallan | MIT |
| vue-expert | https://github.com/Jeffallan | MIT |
| websocket-engineer | https://github.com/Jeffallan | MIT |
| xlsx | not stated | Apache-2.0 (LICENSE.txt) |

## Skipped (not copied)

Rule: only skills whose frontmatter or LICENSE file states MIT or Apache-2.0 are bundled.

| Skill | Reason |
|---|---|
| animation-performance | no license declared |
| break-ui | no license declared |
| emil-design-eng | no license declared |
| figma | no license declared |
| hyperframes | no license declared |
| hyperframes-cli | no license declared |
| hyperframes-registry | no license declared |
| improve-animations | no license declared |
| logo-design | no license declared |
| media-use | no license declared |
| review-animations | no license declared |
| slideshow | no license declared |
| ui-ux-pro-max | no license declared |
| backend-dev (synced) | no license declared |
| deep-research (synced) | no license declared |
| docs (synced) | no license declared |
| import-memory (synced) | no license declared |
| morning (synced) | no license declared |
| built-in-browser (synced) | proprietary (all rights reserved, Anthropic) |
| chrome-browser (synced) | proprietary (all rights reserved, Anthropic) |
| computer-use (synced) | proprietary (all rights reserved, Anthropic) |
| playbook | private pointer, excluded by owner |

## Dot-native skills

Written for Dot, no third-party code: code-review, simplify, security-review, init, loop, schedule, run, update-config, dot-help.

## Runtime components (not modified, not redistributed in this repository)

| Component | Use | License | Evidence |
|---|---|---|---|
| llama.cpp (`ghcr.io/ggml-org/llama.cpp:server-vulkan-b12464`) | model server container | MIT | LICENSE in the llama.cpp source, "Copyright (c) 2023-2026 The ggml authors" |
| SearXNG (`searxng/searxng`, pinned tag) | internal search container | AGPL-3.0 | GitHub license API for searxng/searxng. Used as an unmodified upstream image with our `settings.yml`; Dot code does not link it. If you modify it and expose it to others, AGPL obligations apply to you. |
| Playwright 1.65.2 (Python) and Chromium | browser worker | Apache-2.0 (Playwright); Chromium is BSD-3-Clause plus the licenses of its bundled components | Playwright from installed package metadata; the Chromium build is downloaded by `playwright install` at image build time and is not stored in this repository (Chromium terms not individually verified) |
| sherpa-onnx 2.0.3 | voice worker | Apache-2.0 | PyPI metadata |
| NVIDIA Parakeet-TDT-0.6B-v2 (int8 ONNX by csukuangfj) | speech-to-text model, mounted from `models/voice`, not stored in this repository | CC-BY-4.0 | Model card; attribution: "Parakeet-TDT-0.6B-v2, Copyright NVIDIA Corporation, licensed under CC-BY-4.0" |
| Kokoro-82M v1.0 (sherpa-onnx packaging by csukuangfj) | text-to-speech model, mounted from `models/voice`, not stored in this repository | Apache-2.0 | docs/speech-gate.md, bundled LICENSE |
| uv 0.13.9 (`ghcr.io/astral-sh/uv`) | build tool in images | Apache-2.0 or MIT (GitHub reports Apache-2.0) | GitHub license API |
| ruff 0.17.6 | linter, copied into the sandbox image | MIT | installed package metadata and GitHub license API |
| Python 3.12 and Debian slim base images, Node 24 | image bases | PSF-2.0, Debian free software licenses, MIT | not individually verified |

## Python dependencies (direct, from `uv.lock`)

Versions and licenses read from installed package metadata (`importlib.metadata`).

| Package | Used by | Version | License |
|---|---|---|---|
| fastapi | backend, sandbox, browser | 0.165.0 | MIT |
| uvicorn | backend, sandbox, browser | 0.54.0 | BSD-3-Clause |
| pydantic | contracts | 2.14.4 | MIT |
| pydantic-settings | backend, sandbox, browser | 2.16.3 | MIT |
| sqlalchemy | backend | 2.1.9 | MIT |
| aiosqlite | backend | 0.22.1 | MIT |
| httpx | backend, cli | 0.28.1 | BSD-3-Clause |
| pyyaml | backend | 6.0.3 | MIT |
| **bashlex** | backend (shell classifier) | 0.18 | **GPL-3.0-or-later** |
| trafilatura | backend, browser | 2.3.1 | Apache-2.0 |
| mcp | backend | 1.30.0 | MIT |
| playwright | browser | 1.65.2 | Apache-2.0 |
| textual | cli | 8.2.8 | MIT |
| pytest, pytest-asyncio, ruff (dev only) | tests | 9.2.0, 1.5.0, 0.17.6 | MIT, Apache-2.0, MIT |

Open point for the owner: bashlex is GPLv3+ and is imported by the backend. That matters only if you distribute Dot (or an image containing it) to others; for private use it has no effect. Decide on a replacement (for example a tree-sitter based parser) or on the license of the combined work before any distribution. Transitive dependencies are pinned in `uv.lock` and were not audited one by one.

## Web UI dependencies (direct, `services/web-ui/package.json`)

Versions and licenses from `package-lock.json`.

| Package | Version | License |
|---|---|---|
| next | 15.5.29 | MIT |
| react, react-dom | 19.3.1 | MIT |
| shiki | 4.6.0 | MIT |
| lucide-react | 1.77.0 | ISC |
| @fontsource-variable/onest (font Onest) | 5.3.1 | OFL-1.1 |
| @fontsource/ibm-plex-mono (font IBM Plex Mono) | 5.3.0 | OFL-1.1 |
| dev: typescript | 5.9.3 | Apache-2.0 |
| dev: vitest, eslint | 4.1.12, 9.39.5 | MIT |
| dev: playwright-core | 1.65.1 | Apache-2.0 |
| dev: @axe-core/playwright | 4.14.0 | MPL-2.0 |

The production dependency tree also contains the `@img/sharp-libvips-*` binaries (LGPL-3.0-or-later, optional platform dependencies of Next's image handling) and one CC-BY-4.0 package; they are installed unmodified from npm.
