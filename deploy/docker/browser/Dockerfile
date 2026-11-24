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
COPY services/browser-worker/src services/browser-worker/src
RUN uv sync --frozen --no-dev --no-editable --package dot-browser

FROM python:3.12.16-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df
COPY --from=build /app/.venv /app/.venv
ENV PATH=/app/.venv/bin:$PATH PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers
# Chromium plus its system libraries; the playwright CLI comes from the locked venv.
# libatomic1: the node binary bundled with playwright needs it and the slim image lacks it.
RUN apt-get update && apt-get install -y --no-install-recommends libatomic1 \
    && playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/* \
    && chmod -R a+rX /opt/pw-browsers
RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin dot \
    && mkdir /profiles && chown dot:dot /profiles
USER dot
# Read-only rootfs: Chromium writes under /tmp (tmpfs) and /profiles.
ENV HOME=/tmp \
    DOT_BROWSER_NO_SANDBOX=1 \
    DOT_BROWSER_PROFILES_DIR=/profiles
WORKDIR /tmp
EXPOSE 8091
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD ["python", "-c", "import urllib.request as u; u.urlopen('http://localhost:8091/health', timeout=3)"]
CMD ["uvicorn", "dot_browser.main:app_factory", "--factory", "--host", "0.0.0.0", "--port", "8091"]
