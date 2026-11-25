# Build context: repo root. Standalone uv project (own lockfile), not a workspace member.
FROM python:3.12.16-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.9@sha256:d3b601f0c7b118bc1753febf7c41cc80981df678445e0254284eecf84db79a7d /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY services/voice-worker/pyproject.toml services/voice-worker/uv.lock ./
COPY services/voice-worker/src src
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12.16-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df
# libgomp1: onnxruntime inside sherpa-onnx links OpenMP; the slim image lacks it.
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /app/.venv /app/.venv
ENV PATH=/app/.venv/bin:$PATH PYTHONUNBUFFERED=1 DOT_VOICE_MODEL_DIR=/models/voice
RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin dot
USER dot
WORKDIR /tmp
EXPOSE 8092
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD ["python", "-c", "import urllib.request as u; u.urlopen('http://localhost:8092/health', timeout=3)"]
CMD ["uvicorn", "dot_voice.main:app_factory", "--factory", "--host", "0.0.0.0", "--port", "8092"]
