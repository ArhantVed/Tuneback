"""
ui/app.py — Tuneback root window, sidebar, and page router.

The App class owns:
  - The CustomTkinter root window (1200 × 800)
  - The Sidebar widget (fixed 220 px left panel)
  - The content area (right panel, fills remaining space)
  - All nine page instances, stacked in the content area
  - The Analyser instance (None until the user loads data)
  - The data-loading workflow (file dialog → loader → Analyser → refresh)

Navigation model
----------------
  show_page(key) hides every page frame, then places the chosen one via
  pack().  The active page's refresh(analyser) is called so it always
  renders fresh data whenever it becomes visible.

Python concepts: OOP encapsulation, callback pattern, tkinter layout.
"""

from __future__ import annotations

import os
from tkinter import filedialog, messagebox

import customtkinter

import ui.theme as theme  # side-effect: sets CTk appearance mode
from core.analyser import Analyser
from core.loader import load_csv, load_folder
from ui.sidebar import Sidebar
from ui.pages.dashboard import DashboardPage
from ui.pages.time_machine import TimeMachinePage
from ui.pages.statistics import StatisticsPage
from ui.pages.music_evolution import MusicEvolutionPage
from ui.pages.personality import PersonalityPage
from ui.pages.obsessions import ObsessionsPage
from ui.pages.abandoned import AbandonedPage
from ui.pages.comparison import ComparisonPage
from ui.pages.wrapped import WrappedPage


class App(customtkinter.CTk):
    """Root window for Tuneback.

    Subclasses customtkinter.CTk so it IS the Tk root — only one
    instance should ever be created (in main.py).
    """

    # Window dimensions — set once here, never overridden by pages.
    WIDTH  = 1200
    HEIGHT = 800

    # Default page shown at startup.
    DEFAULT_PAGE = "dashboard"

    def __init__(self) -> None:
        super().__init__()

        self.title("Tuneback")
        self.geometry(f"{self.WIDTH}x{self.HEIGHT}")
        self.minsize(900, 600)
        self.configure(fg_color=theme.BG)

        # The Analyser instance — None until data is loaded.
        self._analyser: Analyser | None = None

        # Track which page key is currently visible.
        self._current_page_key: str = self.DEFAULT_PAGE

        self._build_layout()
        self._build_pages()

        # Show the default page with no data (triggers placeholder state).
        self.show_page(self.DEFAULT_PAGE)

    # ====================================================================
    # Layout construction
    # ====================================================================

    def _build_layout(self) -> None:
        """Divide the window into a fixed sidebar and a fluid content area."""

        # ---- Sidebar (left, fixed width) --------------------------------
        self._sidebar = Sidebar(
            parent=self,
            on_navigate=self.show_page,
            on_load_data=self._on_load_data,
        )
        self._sidebar.pack(side="left", fill="y")

        # Thin vertical divider between sidebar and content
        customtkinter.CTkFrame(
            self, width=1, fg_color=theme.BORDER, corner_radius=0
        ).pack(side="left", fill="y")

        # ---- Content area (right, fills remaining width) ----------------
        self._content = customtkinter.CTkFrame(
            self, fg_color=theme.BG, corner_radius=0
        )
        self._content.pack(side="left", fill="both", expand=True)

    def _build_pages(self) -> None:
        """Instantiate every page and store them in a dict keyed by page name.

        Pages are created once and reused — navigation swaps which one is
        visible; refresh() is called to update the content.
        """
        page_classes = {
            "dashboard":      DashboardPage,
            "time_machine":   TimeMachinePage,
            "statistics":     StatisticsPage,
            "music_evolution": MusicEvolutionPage,
            "personality":    PersonalityPage,
            "obsessions":     ObsessionsPage,
            "abandoned":      AbandonedPage,
            "comparison":     ComparisonPage,
            "wrapped":        WrappedPage,
        }

        # Instantiate each page inside the content area.
        # All pages are placed in the same cell — only one is visible at a time.
        self._pages: dict[str, object] = {
            key: cls(self._content) for key, cls in page_classes.items()
        }

    # ====================================================================
    # Navigation (public — called by Sidebar callbacks)
    # ====================================================================

    def show_page(self, key: str) -> None:
        """Make the named page visible and call its refresh() method.

        Steps:
          1. Unpack (hide) every page that is currently visible.
          2. Pack (show) the target page so it fills the content area.
          3. Tell the sidebar to highlight the correct nav button.
          4. Call refresh(analyser) on the target page so it can render
             fresh content (or its no-data placeholder).

        Parameters
        ----------
        key : One of the page keys defined in page_classes above.
        """
        if key not in self._pages:
            return

        # Hide all pages
        for page in self._pages.values():
            page.pack_forget()

        # Show and refresh the target page
        target_page = self._pages[key]
        target_page.pack(fill="both", expand=True)
        target_page.refresh(self._analyser)

        # Update sidebar highlight
        self._sidebar.set_active_page(key)
        self._current_page_key = key

    # ====================================================================
    # Data loading (triggered by sidebar Load Data button)
    # ====================================================================

    def _on_load_data(self) -> None:
        """Open a file dialog, load CSVs, build Analyser, refresh current page.

        The user can select either:
          - A folder containing one or more Spotify CSV export files, OR
          - A single CSV file.

        A folder dialog is shown first; if cancelled, a file dialog is shown.
        """
        # Try folder selection first
        folder = filedialog.askdirectory(
            title="Select folder containing Spotify CSV exports",
            mustexist=True,
        )

        if folder:
            # Folder selected — load all CSVs inside it
            try:
                plays = load_folder(folder)
            except Exception as exc:
                messagebox.showerror("Load Error", str(exc))
                return
            source_label = os.path.basename(folder) or folder
        else:
            # Folder dialog cancelled — try a single file instead
            filepath = filedialog.askopenfilename(
                title="Select a Spotify CSV export file",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            )
            if not filepath:
                return  # Both dialogs cancelled — do nothing

            try:
                plays = load_csv(filepath)
            except Exception as exc:
                messagebox.showerror("Load Error", str(exc))
                return
            source_label = os.path.basename(filepath)

        if not plays:
            messagebox.showwarning(
                "No Data",
                f"No valid play records were found in:\n{source_label}\n\n"
                "Make sure the file is a Spotify StreamingHistory CSV export.",
            )
            return

        # Build the Analyser and store it on self so all pages can use it
        self._analyser = Analyser(plays)

        # Refresh the currently visible page with the new analyser
        self.show_page(self._current_page_key)

        # Update the window title to show how much data was loaded
        self.title(
            f"Tuneback  —  {len(plays):,} plays  |  {source_label}"
        )
