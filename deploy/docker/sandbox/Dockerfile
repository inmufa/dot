# Build context: repo root.
FROM python:3.12.16-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.9@sha256:d3b601f0c7b118bc1753febf7c41cc80981df678445e0254284eecf84db79a7d /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY packages/dot-contracts packages/dot-contracts
COPY backend/pyproject.toml backend/pyproject.toml
COPY services/sandbox-runner/pyproject.toml services/sandbox-runner/pyproject.toml
COPY services/browser-worker/pyproject.toml services/browser-worker/pyproject.toml
COPY cli/pyproject.toml cli/pyproject.toml
COPY services/sandbox-runner/src services/sandbox-runner/src
RUN uv sync --frozen --no-dev --no-editable --package dot-sandbox

# Data-analysis venv for the agent's Bash (pandas, numpy, matplotlib, openpyxl), hash-pinned.
FROM build AS analysis
COPY deploy/docker/sandbox/analysis.txt /tmp/analysis.txt
RUN uv venv /opt/analysis --python /usr/local/bin/python3.12 \
    && uv pip install --python /opt/analysis/bin/python --require-hashes --no-deps \
        --compile-bytecode -r /tmp/analysis.txt

FROM python:3.12.16-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ripgrep fd-find git nodejs curl ca-certificates bash \
    && ln -s /usr/bin/fdfind /usr/local/bin/fd \
    && rm -rf /var/lib/apt/lists/*
# uv for user projects; ruff is the post-edit linter (same version as uv.lock).
COPY --from=ghcr.io/astral-sh/uv:0.13.9@sha256:d3b601f0c7b118bc1753febf7c41cc80981df678445e0254284eecf84db79a7d /uv /usr/local/bin/uv
COPY --from=ghcr.io/astral-sh/ruff:0.17.6@sha256:2671e9bf3e50c24a88e731f209f9bf01c0360da6857ae36bca680b222efc3528 /ruff /usr/local/bin/ruff
RUN useradd --uid 1000 --create-home --shell /bin/bash dot \
    && mkdir /workspace \
    && chown dot:dot /workspace
COPY --from=build /app/.venv /app/.venv
COPY --from=analysis /opt/analysis /opt/analysis
# /opt/analysis/bin first: the agent's `python` has pandas and matplotlib; uvicorn stays in /app/.venv.
ENV PATH=/opt/analysis/bin:/app/.venv/bin:$PATH PYTHONUNBUFFERED=1 DOT_WORKSPACE=/workspace \
    MPLBACKEND=Agg MPLCONFIGDIR=/tmp/matplotlib
USER dot
WORKDIR /workspace
EXPOSE 8090
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
    CMD ["curl", "-fsS", "http://localhost:8090/health"]
CMD ["uvicorn", "dot_sandbox.main:app_factory", "--factory", "--host", "0.0.0.0", "--port", "8090"]
