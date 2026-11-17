"""Reqless design co. palette and type, shared by the app and the exported report."""

# Colours from reqless.design
DEAD_AIR = "#141419"   # page background
NOISE = "#282832"      # cards and panels
SNOW = "#f5f7fa"       # main text
GLITCH = "#ff00be"     # primary accent (magenta)
CARRIER = "#1a41ff"    # secondary accent (blue)
PHOSPHOR = "#00d7a9"   # good / positive (teal)
LIVE = "#ff4b00"       # warning (orange)

# Blends of SNOW over DEAD_AIR / NOISE for text and lines, pre-mixed because Tk has no transparency
MUTED = "#b5b7bd"      # ~72% snow
FAINT = "#94959c"      # ~58% snow
LINE = "#2f2f37"       # ~12% snow on dead air
LINE_STRONG = "#41414b"
NOISE_HOVER = "#33333f"
DEAD_AIR_DEEP = "#0e0e12"

GLITCH_HOVER = "#d6009f"
CARRIER_HOVER = "#1534cc"

# Verdict colours
LEVEL_COLORS = {
    "good": PHOSPHOR,
    "warn": LIVE,
    "poor": GLITCH,
    "info": MUTED,
    "na": FAINT,
}

# Font stacks: the brand font first, then the fallbacks reqless.design itself uses, then system fonts.
DISPLAY_FONTS = ["apotek-extrawide", "Unbounded", "Bahnschrift SemiBold", "Segoe UI Black", "Helvetica Neue", "Arial Black"]
BODY_FONTS = ["aktiv-grotesk", "Instrument Sans", "Segoe UI", "Helvetica Neue", "Helvetica", "Arial"]
MONO_FONTS = ["Space Mono", "Cascadia Mono", "Consolas", "Menlo", "Courier New"]


def pick_font(candidates, available):
    """First installed font from a stack (Tk can't fall back by itself)."""
    lowered = {name.lower(): name for name in available}
    for name in candidates:
        if name.lower() in lowered:
            return lowered[name.lower()]
    return candidates[-1]

# Glitch at ~15% over NOISE, for the selected sidebar item
GLITCH_TINT = "#482247"
