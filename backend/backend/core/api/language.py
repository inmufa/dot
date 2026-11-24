from backend.core.error_messages import LANGUAGES

DEFAULT_LANGUAGE = "en"


def _quality(params: list[str]) -> float:
    for p in params:
        name, _, value = p.strip().partition("=")
        if name.strip().lower() == "q":
            try:
                return float(value)
            except ValueError:
                return 0.0
    return 1.0


def resolve_language(header: str | None) -> str:
    """Best supported base tag in an Accept-Language header (by q), else the default."""
    ranked: list[tuple[float, int, str]] = []
    for index, part in enumerate((header or "").split(",")):
        tag, *params = part.split(";")
        base = tag.strip().lower().split("-")[0]
        q = _quality(params)
        if base in LANGUAGES and q > 0:
            ranked.append((-q, index, base))
    return min(ranked)[2] if ranked else DEFAULT_LANGUAGE
