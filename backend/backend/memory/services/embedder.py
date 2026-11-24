"""Optional vector search seam. Off by default; no embedding dependency yet."""

from typing import Protocol


class Embedder(Protocol):
    """Turns texts into vectors (e.g. FastEmbed bge-small-en-v1.5, dim 384)."""

    dim: int

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class NullEmbedder:
    """Stand-in used when vector search is off or not installed."""

    dim = 0

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[] for _ in texts]
