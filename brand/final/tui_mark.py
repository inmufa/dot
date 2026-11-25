"""Dot brand marks for the terminal. Colours are truecolor hex; state glyph is always the dot."""

MARK_3 = ("╭───╮", "│ ● │", "╰───╯")
MARK_3_ASCII = (".---.", "| o |", "'---'")
MARK_1 = "● Dot"
MARK_1_ASCII = "(o) Dot"

DOT = "●"
ACCENT = "#93BFA3"  # sage on dark
STATE_COLORS = {
    "idle": "#7A766D",
    "thinking": "#D9A03A",
    "waiting": "#7FA6C6",
}  # dark terminals
STATE_COLORS_LIGHT = {
    "idle": "#7B776E",
    "thinking": "#A8700A",
    "waiting": "#4F7CA3",
}  # light terminals
