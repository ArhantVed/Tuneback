"""
ui/sidebar.py — Tuneback navigation sidebar.

A fixed-width panel on the left of the window containing:
  - App branding (title at the top)
  - Navigation buttons for each feature page
  - A "Load Data" button at the bottom

The sidebar is purely presentational — it calls callbacks provided by
App rather than performing any data loading itself.

Python concepts: OOP composition, callback pattern, list iteration.
"""

from __future__ import annotations

import customtkinter
from typing import Callable

from ui import theme

# Navigation items — (display label, internal page key)
# Order here determines the order buttons appear in the sidebar.
NAV_ITEMS: list[tuple[str, str]] = [
    ("Dashboard",           "dashboard"),
    ("Time Machine",        "time_machine"),
    ("Statistics",          "statistics"),
    ("Music Evolution",     "music_evolution"),
    ("Personality",         "personality"),
    ("Obsessions",          "obsessions"),
    ("Abandoned Artists",   "abandoned"),
    ("Period Comparison",   "comparison"),
    ("Wrapped Report",      "wrapped"),
]


class Sidebar(customtkinter.CTkFrame):
    """Left-hand navigation sidebar.

    Parameters
    ----------
    parent          : Parent widget (the root App window).
    on_navigate     : Callback(page_key: str) — called when a nav button
                      is clicked.
    on_load_data    : Callback() — called when the Load Data button is clicked.
    """

    # Width of the sidebar in pixels — fixed, never changes.
    WIDTH = 220

    def __init__(
        self,
        parent,
        on_navigate: Callable[[str], None],
        on_load_data: Callable[[], None],
    ) -> None:
        super().__init__(
            parent,
            width=self.WIDTH,
            fg_color=theme.BG,
            corner_radius=0,
        )
        # Prevent the sidebar from shrinking when its children are small
        self.pack_propagate(False)

        self._on_navigate = on_navigate
        self._on_load_data = on_load_data

        # Keep a reference to every nav button so we can update their
        # active/inactive colour when the selected page changes.
        self._nav_buttons: dict[str, customtkinter.CTkButton] = {}

        self._build()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self) -> None:
        """Construct all sidebar widgets once at startup."""
        self._build_header()
        self._build_nav_buttons()
        self._build_footer()

    def _build_header(self) -> None:
        """App title / branding at the top of the sidebar."""
        header = customtkinter.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=theme.PAD_L, pady=(theme.PAD_XL, theme.PAD_L))

        customtkinter.CTkLabel(
            header,
            text="Tuneback",
            font=theme.label_style(theme.FONT_L, bold=True),
            text_color=theme.TEXT,
            anchor="w",
        ).pack(fill="x")

        customtkinter.CTkLabel(
            header,
            text="Spotify History Explorer",
            font=theme.label_style(theme.FONT_S),
            text_color=theme.TEXT_MUTED,
            anchor="w",
        ).pack(fill="x", pady=(2, 0))

        # Thin separator line below the header
        customtkinter.CTkFrame(
            self, height=1, fg_color=theme.BORDER, corner_radius=0
        ).pack(fill="x", pady=(theme.PAD_M, 0))

    def _build_nav_buttons(self) -> None:
        """One button per page, stacked vertically."""
        nav_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        nav_frame.pack(fill="x", pady=(theme.PAD_M, 0))

        for label, page_key in NAV_ITEMS:
            btn = customtkinter.CTkButton(
                nav_frame,
                text=label,
                anchor="w",
                height=40,
                corner_radius=6,
                border_spacing=10,
                fg_color="transparent",
                text_color=theme.TEXT_MUTED,
                hover_color=theme.SURFACE_RAISED,
                font=theme.label_style(theme.FONT_M),
                # Use a closure to capture the page_key for this iteration
                command=lambda key=page_key: self._on_navigate(key),
            )
            btn.pack(fill="x", padx=theme.PAD_M, pady=2)
            self._nav_buttons[page_key] = btn

    def _build_footer(self) -> None:
        """Load Data button pinned to the bottom of the sidebar."""
        # Push the footer to the bottom using a spacer that expands
        spacer = customtkinter.CTkFrame(self, fg_color="transparent")
        spacer.pack(fill="both", expand=True)

        # Thin separator above the footer
        customtkinter.CTkFrame(
            self, height=1, fg_color=theme.BORDER, corner_radius=0
        ).pack(fill="x")

        footer = customtkinter.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=theme.PAD_M, pady=theme.PAD_L)

        customtkinter.CTkButton(
            footer,
            text="⬆  Load Data",
            height=40,
            corner_radius=6,
            fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER,
            text_color="#000000",
            font=theme.label_style(theme.FONT_M, bold=True),
            command=self._on_load_data,
        ).pack(fill="x")

    # ------------------------------------------------------------------
    # Public API called by App
    # ------------------------------------------------------------------

    def set_active_page(self, page_key: str) -> None:
        """Highlight the button for the active page; dim all others.

        Called by App.show_page() after navigation so the sidebar always
        reflects which page is currently visible.
        """
        for key, btn in self._nav_buttons.items():
            if key == page_key:
                btn.configure(
                    fg_color=theme.SURFACE_RAISED,
                    text_color=theme.ACCENT,
                    font=theme.label_style(theme.FONT_M, bold=True),
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=theme.TEXT_MUTED,
                    font=theme.label_style(theme.FONT_M),
                )
