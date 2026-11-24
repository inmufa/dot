from typing import Any


class DomainException(Exception):  # noqa: N818
    """Services raise only this; the handler maps `code` to the catalog."""

    def __init__(
        self,
        code: int,
        ctx: dict[str, Any] | None = None,
        *,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.ctx = ctx or {}
        self.retry_after = retry_after
