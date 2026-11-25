# Picks the GPU overlay from DOT_GPU_BACKEND in .env (see deploy/profiles).
COMPOSE = bash deploy/scripts/compose.sh

.PHONY: sync lint fmt test integration lockcheck ci init up up-browser up-voice vault-key vault-rotate down logs models model profile bench gate privacy-check

sync:
	uv sync --all-packages --group dev

lint:
	uv run ruff check .
	uv run ruff format --check .

fmt:
	uv run ruff check --fix .
	uv run ruff format .

# Unit tests, one package at a time (each has its own pytest config). Integration is separate.
test:
	uv run pytest backend/tests -m "not integration"
	uv run pytest services/sandbox-runner/tests
	uv run pytest services/browser-worker/tests
	uv run --project services/voice-worker pytest services/voice-worker/tests
	uv run pytest cli/tests
	uv run pytest deploy/tests

# Real-protocol smoke: fake llama-server over HTTP, real sandbox subprocess, real SQLite.
integration:
	uv run pytest backend/tests -m integration

lockcheck:
	uv lock --check

ci: lint lockcheck test integration

init:
	sh deploy/scripts/init_workspace.sh

up: init
	$(COMPOSE) up -d

up-browser: init
	@grep -Eq '^DOT_BROWSER_TOKEN=.+' .env || { echo "set DOT_BROWSER_TOKEN in .env first"; exit 1; }
	$(COMPOSE) --profile browser up -d

# Create DOT_VAULT_KEY in .env if absent (never printed). See docs/operations.md "Credential vault".
vault-key:
	sh deploy/scripts/vault_key.sh

# Re-encrypt the vault under a new key (stops and restarts dot-backend, backs the DB up).
vault-rotate:
	sh deploy/scripts/vault_rotate.sh

up-voice: init
	@grep -Eq '^DOT_VOICE_TOKEN=.+' .env || { echo "set DOT_VOICE_TOKEN in .env first (openssl rand -hex 32)"; exit 1; }
	@test -f models/voice/parakeet-tdt-0.6b-v2-int8/encoder.int8.onnx || { echo "voice models missing in models/voice (docs/operations.md)"; exit 1; }
	$(COMPOSE) --profile voice up -d --build dot-voice dot-backend

down:
	$(COMPOSE) --profile browser --profile voice down

# Follow logs: make logs [S=dot-backend]
logs:
	$(COMPOSE) --profile browser --profile voice logs -f --tail=100 $(S)

# Fetch the GGUF named by DOT_MODEL_FILE (.env) into ./models. Set DOT_MODEL_URL, or
# DOT_MODEL_REPO (huggingface-cli or curl), and DOT_MODEL_SHA256 for the mandatory check.
# Nothing is downloaded by any other target. Details: docs/operations.md.
models:
	bash deploy/scripts/download_models.sh $(ARGS)

# Apply a hardware profile: make profile NAME=<deploy/profiles/NAME.env>. Validates it and
# writes the llama settings into .env (override a key: SET=DOT_VISION=cpu). Then `make up`. See docs/operations.md.
profile:
	uv run python deploy/scripts/dotctl.py profile "$(NAME)" $(foreach s,$(SET),--set $(s))

# Switch the model: make model NAME=<file, stem or registry name in ./models>. Updates .env
# (model, projector, context) and recreates dot-llm (running turns fail). See docs/operations.md.
model:
	bash deploy/scripts/switch_model.sh "$(NAME)"

# M0 gate: llama-bench in the dot-llm image (docker) with native comparison steps.
bench:
	bash deploy/scripts/bench_llm.sh

# M1 gate: needs the llm up (make up). 20 tool-call tasks + 10-turn prefix-reuse probe.
gate:
	uv run deploy/scripts/m1_model_gate.py $(ARGS)

# Egress, ports, file modes, web bundle and CSP checks against the running stack (docs/privacy.md).
privacy-check:
	bash deploy/scripts/privacy_check.sh
