"""
ui/pages/base_page.py — Abstract base class for all Tuneback feature pages.

Every page in the application subclasses BasePage.  The two key contracts:

  1. refresh(analyser) — called by App whenever data is loaded or the page
     becomes active.  Receives the Analyser instance (or None before any
     data has been loaded).  Pages must clear their previous content and
     rebuild it from the fresh analyser.

  2. show_placeholder(message) — helper that clears the page and displays a
     centred message string.  Pages call this inside refresh() when analyser
     is None (no data loaded yet) or when an error occurs.

Python concepts: abstract base classes (abc), inheritance, polymorphism.
"""

from __future__ import annotations

import customtkinter
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from ui import theme

# Avoid circular import — Analyser is only needed for the type hint.
if TYPE_CHECKING:
    from core.analyser import Analyser


class BasePage(customtkinter.CTkFrame, ABC):
    """Abstract base for all feature pages.

    Inherits from both CTkFrame (so it IS a widget that can be placed
    in the window) and ABC (so subclasses must implement refresh).

    Parameters
    ----------
    parent : The CTk container that owns this page.
    **kwargs : Forwarded to CTkFrame.__init__.
    """

    def __init__(self, parent: customtkinter.CTkFrame, **kwargs) -> None:
        # Default page background matches the overall window BG
        kwargs.setdefault("fg_color", theme.BG)
        super().__init__(parent, **kwargs)

    # ------------------------------------------------------------------
    # Contract — subclasses must implement this
    # ------------------------------------------------------------------

    @abstractmethod
    def refresh(self, analyser: "Analyser | None") -> None:
        """Rebuild the page content from the given analyser.

        Called by App.show_page() every time the page is navigated to
        and whenever new data is loaded.

        Parameters
        ----------
        analyser : Analyser instance with loaded Play data, or None if
                   no CSV file has been loaded yet.

        Implementations should always start with:
            self._clear()
            if analyser is None:
                self.show_placeholder("Load your data to get started")
                return
            # ... build the page content ...
        """

    # ------------------------------------------------------------------
    # Helpers available to all subclasses
    # ------------------------------------------------------------------

    def _clear(self) -> None:
        """Destroy all child widgets so the page can be rebuilt cleanly."""
        for widget in self.winfo_children():
            widget.destroy()

    def show_placeholder(self, message: str = "No data loaded") -> None:
        """Display a centred placeholder message, clearing any existing content.

        Used when analyser is None or when a page has nothing to show.
        """
        self._clear()

        # Outer frame fills the whole page and centres its content
        container = customtkinter.CTkFrame(self, fg_color="transparent")
        container.place(relx=0.5, rely=0.5, anchor="center")

        # Icon-like large muted text
        customtkinter.CTkLabel(
            container,
            text="♪",
            font=theme.label_style(56),
            text_color=theme.TEXT_MUTED,
        ).pack(pady=(0, theme.PAD_M))

        # Main message
        customtkinter.CTkLabel(
            container,
            text=message,
            font=theme.label_style(theme.FONT_M),
            text_color=theme.TEXT_MUTED,
            wraplength=400,
            justify="center",
        ).pack()
