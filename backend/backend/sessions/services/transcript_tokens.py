def estimate_tokens(text: str) -> int:
    """Rough size: ~4 chars/token for ASCII, ~2 for everything else (cyrillic, CJK)."""
    if not text:
        return 0
    wide = len(text) - len(text.encode("ascii", "ignore"))
    return max(1, (len(text) - wide) // 4 + wide // 2)
