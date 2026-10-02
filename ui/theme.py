"""
ui/theme.py — Tuneback design system.

All colour constants, font sizes, and spacing values live here.
Importing this module has the immediate side-effect of applying the
CustomTkinter dark appearance mode — so import it before building any
widgets (ui/app.py does this at module level).

Usage
-----
    from ui.theme import BG, SURFACE, ACCENT, TEXT, FONT_L
    from ui.theme import label_style, card_style

Changing the accent colour here propagates to every page automatically.
"""

import customtkinter

# ---------------------------------------------------------------------------
# Apply global CustomTkinter appearance — runs once on first import.
# ---------------------------------------------------------------------------
customtkinter.set_appearance_mode("dark")
# "dark-blue" is the built-in CTk theme closest to our palette; we override
# individual widget colours through constants below rather than a custom JSON.
customtkinter.set_default_color_theme("dark-blue")

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------

# Background — very dark navy, used for the root window and sidebar.
BG = "#0d1117"

# Surface — charcoal, used for cards, frames, and panels inside the content area.
SURFACE = "#161b22"

# Surface raised — slightly lighter card used for nested elements.
SURFACE_RAISED = "#21262d"

# Accent — vivid green, the single brand colour used for highlights,
# active nav buttons, progress bars, and chart bars.
# Change this one value to re-skin the entire application.
ACCENT = "#1db954"          # Spotify-inspired green

# Accent hover — a dimmed version of ACCENT for hover states.
ACCENT_HOVER = "#17a349"

# Text — primary white text.
TEXT = "#e6edf3"

# Text muted — secondary grey for subtitles, captions, and metadata.
TEXT_MUTED = "#8b949e"

# Border — subtle divider line between sections.
BORDER = "#30363d"

# Danger/warning — used for error labels and warning badges.
DANGER = "#f85149"

# Chart colour palette — ordered list for multi-series Matplotlib charts.
# Extended in chart_helpers.py when more than len(CHART_COLORS) series are needed.
CHART_COLORS = [
    "#1db954",  # accent green
    "#58a6ff",  # blue
    "#f78166",  # coral
    "#d2a8ff",  # lavender
    "#ffa657",  # amber
    "#79c0ff",  # sky blue
    "#56d364",  # light green
    "#ff7b72",  # red-orange
]

# ---------------------------------------------------------------------------
# Font family
# ---------------------------------------------------------------------------
FONT_FAMILY = "Segoe UI"          # Windows; falls back gracefully on macOS/Linux

# ---------------------------------------------------------------------------
# Font size constants
# ---------------------------------------------------------------------------
FONT_XL = 28    # Page headings / Wrapped slideshow values
FONT_L  = 20    # Section headings / stat card values
FONT_M  = 14    # Body text / table rows
FONT_S  = 11    # Captions / muted metadata

# ---------------------------------------------------------------------------
# Spacing constants (pixels)
# ---------------------------------------------------------------------------
PAD_XL = 24
PAD_L  = 16
PAD_M  = 10
PAD_S  =  6

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def label_style(size: int = FONT_M, bold: bool = False) -> tuple[str, int, str]:
    """Return a CTk-compatible font tuple for the given size and weight.

    Example
    -------
        widget.configure(font=label_style(FONT_L, bold=True))
    """
    weight = "bold" if bold else "normal"
    return (FONT_FAMILY, size, weight)


def card_style() -> dict:
    """Return a dict of kwargs for a standard surface card frame.

    Example
    -------
        frame = customtkinter.CTkFrame(parent, **card_style())
    """
    return {
        "fg_color": SURFACE,
        "border_color": BORDER,
        "border_width": 1,
        "corner_radius": 8,
    }
