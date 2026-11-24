COMPOSE = docker compose --env-file .env -f deploy/compose/compose.base.yml

.PHONY: sync lint fmt test integration lockcheck ci init up up-browser down logs models bench gate

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

down:
	$(COMPOSE) --profile browser down

# Follow logs: make logs [S=dot-backend]
logs:
	$(COMPOSE) --profile browser logs -f --tail=100 $(S)

# Fetch the GGUF named by DOT_MODEL_FILE (.env) into ./models. Set DOT_MODEL_URL, or
# DOT_MODEL_REPO (huggingface-cli or curl), and DOT_MODEL_SHA256 for the mandatory check.
# Nothing is downloaded by any other target. Details: docs/operations.md.
models:
	bash deploy/scripts/download_models.sh $(ARGS)

# M0 gate: llama-bench in the dot-llm image (docker) with native comparison steps.
bench:
	bash deploy/scripts/bench_llm.sh

# M1 gate: needs the llm up (make up). 20 tool-call tasks + 10-turn prefix-reuse probe.
gate:
	uv run deploy/scripts/m1_model_gate.py $(ARGS)
