"""Uploads and files wiring (F3, F4)."""

from backend.bootstrap.phase5 import Closer, Phase5Deps
from backend.cognition.services.engine.images import ImageSource
from backend.cognition.services.tools.web.fetch_http import SafeFetcher
from backend.sessions.services.browser_view import BrowserView
from backend.sessions.services.workspace.attachments import AttachmentService
from backend.sessions.services.workspace.files import FilesService
from backend.sessions.services.workspace.media import MediaService
from backend.sessions.services.workspace.reminder import make_provider
from backend.vault.wiring import build_vault


async def build_features_d(d: Phase5Deps) -> list[Closer]:
    s = d.settings
    root = str(s.workspace.absolute())
    attachments = AttachmentService(
        d.maker,
        d.sandbox,
        root,
        max_files=s.upload_max_files,
        max_bytes=s.upload_max_bytes,
    )
    d.app.state.attachments = attachments
    d.app.state.files = FilesService(
        d.maker,
        d.react._store,  # noqa: SLF001
        d.sandbox,
        attachments,
        root,
        s.preview_max_bytes,
    )
    fetcher = SafeFetcher(allow_loopback=s.web_unsafe_allow_loopback)
    d.app.state.media = MediaService(d.sandbox, root, fetcher)
    if d.registry.browser is not None:
        d.app.state.browser_view = BrowserView(d.registry.browser, d.gov.audit)
    closers = await build_vault(d)
    closers.append(fetcher.aclose)
    llm_vision = getattr(d.llm, "vision", None)

    async def fetch(session_id: str, path: str) -> bytes | None:
        resp, data = await d.sandbox.get_raw(session_id, path, s.upload_max_bytes)
        return data if resp.ok else None

    async def no_vision() -> bool:
        return False

    images = ImageSource(
        fetch,
        llm_vision or no_vision,
        keep=s.vision_keep_images,
        max_side=s.vision_max_side,
        max_side_text=s.vision_max_side_text,
    )
    d.react.images = images
    d.react.runner.images = images
    d.react.reminder_providers.append(make_provider(attachments, d.gov.taint, images))
    return closers
