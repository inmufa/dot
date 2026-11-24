# Build context: repo root. Only the backend and dot-contracts are built into the image.
FROM python:3.12.16-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.9@sha256:d3b601f0c7b118bc1753febf7c41cc80981df678445e0254284eecf84db79a7d /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# The workspace needs every member's pyproject to resolve.
COPY pyproject.toml uv.lock ./
COPY packages/dot-contracts packages/dot-contracts
COPY backend/pyproject.toml backend/pyproject.toml
COPY services/sandbox-runner/pyproject.toml services/sandbox-runner/pyproject.toml
COPY services/browser-worker/pyproject.toml services/browser-worker/pyproject.toml
COPY cli/pyproject.toml cli/pyproject.toml
COPY backend/backend backend/backend
RUN uv sync --frozen --no-dev --no-editable --package dot-backend

FROM python:3.12.16-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df
RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin dot \
    && mkdir /data /workspace /memory \
    && chown dot:dot /data /workspace /memory
COPY --from=build /app/.venv /app/.venv
COPY deploy/config/dot /etc/dot
COPY skills /opt/dot/skills
ENV PATH=/app/.venv/bin:$PATH PYTHONUNBUFFERED=1 DOT_DB_PATH=/data/dot.db \
    DOT_WORKSPACE=/workspace \
    DOT_DEFAULT_PERMISSIONS_PATH=/etc/dot/default_permissions.json \
    DOT_SKILLS_DIR=/opt/dot/skills \
    DOT_GLOBAL_RULES_PATH=/etc/dot/global_rules.md \
    DOT_MEMORY_DIR=/memory
USER dot
WORKDIR /data
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=5 \
    CMD ["python", "-c", "import urllib.request as u; u.urlopen('http://localhost:8000/health', timeout=3)"]
CMD ["uvicorn", "backend.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
