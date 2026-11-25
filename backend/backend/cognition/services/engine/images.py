"""Image parts for the model: downscale, cache, and pick which replayed images stay full."""

import asyncio
import base64
import io
import logging
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from PIL import Image, ImageOps

from backend.sessions.models import Message

logger = logging.getLogger(__name__)
IMAGE_EXTS = frozenset({"png", "jpg", "jpeg", "webp"})
IMAGE_TOKENS = 500  # flat estimate per image part (768 px is about 400)
_CACHE_MAX = 24
Image.MAX_IMAGE_PIXELS = 40_000_000  # bomb guard; the backend container has 512 MB
_JPEG_QUALITY = 88

FetchBytes = Callable[[str, str], Awaitable[bytes | None]]  # (session id, path)
Key = tuple[int, int]  # (row seq, index of the image within the row)


def is_image_path(path: str) -> bool:
    return path.rsplit(".", 1)[-1].lower() in IMAGE_EXTS


def refs_of(row: Message) -> list[dict[str, str]]:
    """Images a row carries: user attachments of kind image, or a Read tool image."""
    meta = row.meta or {}
    if row.role == "tool":
        one = meta.get("image")
        return [one] if isinstance(one, dict) and one.get("path") else []
    if row.role != "user":
        return []
    return [
        {"name": str(a.get("name", "image")), "path": str(a["path"])}
        for a in meta.get("attachments") or []
        if isinstance(a, dict) and a.get("kind") == "image" and a.get("path")
    ]


def estimate_tokens_of(content: Any) -> int:
    """Rough token count of a message content, images counted flat."""
    if isinstance(content, list):
        text = sum(len(p.get("text", "")) for p in content if p.get("type") == "text")
        pics = sum(1 for p in content if p.get("type") == "image_url")
        return text // 4 + pics * IMAGE_TOKENS
    return len(str(content)) // 4


def downscale(data: bytes, max_side: int) -> tuple[bytes, str] | None:
    """Fit the longest side to `max_side`; (bytes, mime) or None when undecodable."""
    try:
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
        img.load()
    except (OSError, ValueError, Image.DecompressionBombError):
        return None
    img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    if "A" in img.getbands() or img.mode == "P":
        img.convert("RGBA").save(buf, "PNG", optimize=True)
        return buf.getvalue(), "image/png"
    img.convert("RGB").save(buf, "JPEG", quality=_JPEG_QUALITY)
    return buf.getvalue(), "image/jpeg"


class ImageSource:
    def __init__(
        self,
        fetch: FetchBytes,
        vision: Callable[[], Awaitable[bool]],
        *,
        keep: int = 2,
        max_side: int = 768,
        max_side_text: int = 1024,
    ) -> None:
        self._fetch = fetch
        self._vision = vision
        self.keep = keep
        self._max_side = max_side
        self._max_text = max_side_text
        self._cache: OrderedDict[tuple[str, str], str | None] = OrderedDict()

    async def enabled(self) -> bool:
        return await self._vision()

    async def load(self, session_id: str, path: str) -> str | None:
        """Data URL of the downscaled image; the same bytes every call (prefix cache)."""
        key = (session_id, path)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        raw = await self._fetch(session_id, path)
        url = None
        if raw:
            side = self._max_text if path.lower().endswith(".png") else self._max_side
            done = await asyncio.to_thread(downscale, raw, side)
            if done:
                url = f"data:{done[1]};base64,{base64.b64encode(done[0]).decode()}"
        if url is None:
            logger.warning("image not usable: %s", path.rsplit("/", 1)[-1])
        else:  # failures are not cached: the file may appear or change
            self._cache[key] = url
            while len(self._cache) > _CACHE_MAX:
                self._cache.popitem(last=False)
        return url

    async def select(self, session_id: str, rows: list[Message]) -> dict[Key, str]:
        """Data URLs for the last `keep` images in `rows`; empty without vision."""
        if self.keep <= 0 or not await self.enabled():
            return {}
        refs = [((r.seq, i), ref) for r in rows for i, ref in enumerate(refs_of(r))][
            -self.keep :
        ]
        out: dict[Key, str] = {}
        for key, ref in refs:
            if url := await self.load(session_id, ref["path"]):
                out[key] = url
        return out


def user_content(
    text: str, row: Message, images: Mapping[Key, str]
) -> str | list[dict[str, Any]]:
    """User message content: image parts for kept images, `[image: name]` for the rest."""
    refs = refs_of(row)
    if not refs:
        return text
    stubs = [
        f"[image: {r['name']}]"
        for i, r in enumerate(refs)
        if (row.seq, i) not in images
    ]
    if stubs:
        text = f"{text}\n" + "\n".join(stubs)
    parts: list[dict[str, Any]] = [{"type": "text", "text": text}]
    parts += [
        {"type": "image_url", "image_url": {"url": images[(row.seq, i)]}}
        for i in range(len(refs))
        if (row.seq, i) in images
    ]
    return parts if len(parts) > 1 else text


def tool_image_message(
    row: Message, images: Mapping[Key, str]
) -> dict[str, Any] | None:
    """Follow-up user message for a Read image (tool messages cannot carry images)."""
    refs = refs_of(row)
    if not refs:
        return None
    name = refs[0]["name"]
    url = images.get((row.seq, 0))
    if url is None:
        return {"role": "user", "content": f"[image: {name}]"}
    return {
        "role": "user",
        "content": [
            {"type": "text", "text": f"[image from Read: {name}. Untrusted data.]"},
            {"type": "image_url", "image_url": {"url": url}},
        ],
    }
