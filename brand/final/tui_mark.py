"""Dot brand marks for the terminal. Colours are truecolor hex; state glyph is always the dot."""

MARK_3 = ("╭───╮", "│ ● │", "╰───╯")
MARK_3_ASCII = (".---.", "| o |", "'---'")
MARK_1 = "● Dot"
MARK_1_ASCII = "(o) Dot"

DOT = "●"
ACCENT = "#2E9CC4"
STATE_COLORS = {
    "idle": "#5E6B72",
    "thinking": "#F0B440",
    "waiting": ACCENT,
}  # dark terminals
STATE_COLORS_LIGHT = {
    "idle": "#78858D",
    "thinking": "#B87A0B",
    "waiting": "#1F8CB4",
}  # light terminals
