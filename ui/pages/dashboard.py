"""
ui/pages/dashboard.py — Tuneback Dashboard page.

The first page the user sees after loading data. Provides an at-a-glance
summary of their entire listening history:

  ┌─────────────────────────────────────────────────────┐
  │  [Total Time] [Artists] [Tracks] [Date Range]        │  ← stat cards
  ├──────────────────────────────┬──────────────────────┤
  │  Plays Over Time (line chart)│  Top 5 Artists       │  ← main content
  │                              │  Top 5 Tracks        │
  └──────────────────────────────┴──────────────────────┘

Layout uses CTkFrame grid cells — no raw tkinter grid manager so it stays
consistent with the rest of the CustomTkinter codebase.

All analysis is delegated to Analyser; all formatting to utils.formatting;
all chart building to utils.chart_helpers.  This page contains zero
computation logic.

Python concepts demonstrated: OOP (inheritance), composition, f-strings,
list comprehension (top-artist loop), conditional rendering.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import customtkinter

from ui.pages.base_page import BasePage
from ui import theme
from utils.formatting import ms_to_human, ms_to_short, short_number, month_label
from utils.chart_helpers import make_line_chart, embed_figure, clear_frame_charts


class DashboardPage(BasePage):
    """Headline statistics overview page.

    Rebuilds itself from scratch on every refresh() call so stale
    widgets never accumulate.  All child widgets are destroyed by
    _clear() before the new layout is constructed.
    """

    def refresh(self, analyser) -> None:
        """Rebuild the Dashboard from the given analyser.

        Parameters
        ----------
        analyser : Analyser instance, or None if no data is loaded yet.
        """
        self._clear()
        plt.close("all")   # release any previously embedded figures

        if analyser is None:
            self._show_welcome()
            return

        self._build(analyser)

    # ------------------------------------------------------------------
    # No-data state
    # ------------------------------------------------------------------

    def _show_welcome(self) -> None:
        """Centred welcome card shown before any data is loaded."""
        container = customtkinter.CTkFrame(self, fg_color="transparent")
        container.place(relx=0.5, rely=0.5, anchor="center")

        customtkinter.CTkLabel(
            container,
            text="♪",
            font=theme.label_style(64),
            text_color=theme.ACCENT,
        ).pack(pady=(0, theme.PAD_M))

        customtkinter.CTkLabel(
            container,
            text="Welcome to Tuneback",
            font=theme.label_style(theme.FONT_L, bold=True),
            text_color=theme.TEXT,
        ).pack()

        customtkinter.CTkLabel(
            container,
            text="Click  ⬆  Load Data  in the sidebar to import your Spotify history.",
            font=theme.label_style(theme.FONT_M),
            text_color=theme.TEXT_MUTED,
            wraplength=420,
            justify="center",
        ).pack(pady=(theme.PAD_M, 0))

    # ------------------------------------------------------------------
    # Main build
    # ------------------------------------------------------------------

    def _build(self, analyser) -> None:
        """Construct the full dashboard layout with real data."""
        # ---- outer scroll container ----
        scroll = customtkinter.CTkScrollableFrame(
            self, fg_color=theme.BG, corner_radius=0
        )
        scroll.pack(fill="both", expand=True)

        self._build_header(scroll)
        self._build_stat_cards(scroll, analyser)
        self._build_main_content(scroll, analyser)

    def _build_header(self, parent) -> None:
        """Page title row."""
        header = customtkinter.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", padx=theme.PAD_XL, pady=(theme.PAD_XL, theme.PAD_M))

        customtkinter.CTkLabel(
            header,
            text="Dashboard",
            font=theme.label_style(theme.FONT_XL, bold=True),
            text_color=theme.TEXT,
            anchor="w",
        ).pack(side="left")

        customtkinter.CTkLabel(
            header,
            text="Your complete listening history at a glance",
            font=theme.label_style(theme.FONT_S),
            text_color=theme.TEXT_MUTED,
            anchor="e",
        ).pack(side="right", pady=(theme.PAD_S, 0))

    def _build_stat_cards(self, parent, analyser) -> None:
        """Top row of 4 headline stat cards."""
        # Gather values from the analyser (no computation here)
        total_ms      = analyser.total_listening_time_ms()
        n_artists     = analyser.unique_artists_count()
        n_tracks      = analyser.unique_tracks_count()
        pair = analyser.first_and_last_play()
        if pair:
            first_dt = pair[0].timestamp
            last_dt  = pair[1].timestamp
        else:
            first_dt = last_dt = None

        date_range = (
            f"{first_dt:%d %b %Y}  →  {last_dt:%d %b %Y}"
            if first_dt and last_dt
            else "No data"
        )

        cards_data = [
            ("Listening Time",   ms_to_human(total_ms),     "⏱"),
            ("Artists",          short_number(n_artists),    "🎤"),
            ("Tracks",           short_number(n_tracks),     "🎵"),
            ("Date Range",       date_range,                 "📅"),
        ]

        row = customtkinter.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=theme.PAD_XL, pady=(0, theme.PAD_L))

        # Give all 4 columns equal weight so cards are evenly spaced
        for col in range(4):
            row.columnconfigure(col, weight=1)

        for col, (label, value, icon) in enumerate(cards_data):
            card = customtkinter.CTkFrame(row, **theme.card_style())
            card.grid(row=0, column=col, padx=(0 if col == 0 else theme.PAD_M, 0), sticky="nsew")

            # Icon
            customtkinter.CTkLabel(
                card,
                text=icon,
                font=theme.label_style(22),
                text_color=theme.ACCENT,
            ).pack(anchor="w", padx=theme.PAD_L, pady=(theme.PAD_L, 0))

            # Main value
            customtkinter.CTkLabel(
                card,
                text=value,
                font=theme.label_style(theme.FONT_L, bold=True),
                text_color=theme.TEXT,
                anchor="w",
                wraplength=220,
            ).pack(anchor="w", padx=theme.PAD_L, pady=(theme.PAD_S, 0))

            # Sub-label
            customtkinter.CTkLabel(
                card,
                text=label,
                font=theme.label_style(theme.FONT_S),
                text_color=theme.TEXT_MUTED,
                anchor="w",
            ).pack(anchor="w", padx=theme.PAD_L, pady=(2, theme.PAD_L))

    def _build_main_content(self, parent, analyser) -> None:
        """Two-column area: plays-over-time chart (left) + top lists (right)."""
        row = customtkinter.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="both", expand=True, padx=theme.PAD_XL, pady=(0, theme.PAD_XL))
        row.columnconfigure(0, weight=3)   # chart gets 3/5 of the width
        row.columnconfigure(1, weight=2)   # lists get 2/5

        self._build_timeline_chart(row, analyser)
        self._build_top_lists(row, analyser)

    # ------------------------------------------------------------------
    # Timeline chart (left column)
    # ------------------------------------------------------------------

    def _build_timeline_chart(self, parent, analyser) -> None:
        """Plays-over-time line chart embedded in the left column."""
        card = customtkinter.CTkFrame(parent, **theme.card_style())
        card.grid(row=0, column=0, padx=(0, theme.PAD_M), sticky="nsew", pady=0)

        # Section heading
        customtkinter.CTkLabel(
            card,
            text="Plays Over Time",
            font=theme.label_style(theme.FONT_M, bold=True),
            text_color=theme.TEXT,
            anchor="w",
        ).pack(anchor="w", padx=theme.PAD_L, pady=(theme.PAD_L, theme.PAD_S))

        # Thin separator
        customtkinter.CTkFrame(card, height=1, fg_color=theme.BORDER, corner_radius=0).pack(
            fill="x", padx=theme.PAD_L
        )

        # Build the chart from analyser data
        pot = analyser.plays_over_time("month")    # dict[YYYY-MM -> count]
        x_labels = [month_label(k) for k in pot.keys()]
        y_values  = list(pot.values())

        # Auto-compute xtick_step so we never show more than ~12 labels
        n = len(x_labels)
        step = max(1, n // 12)

        fig = make_line_chart(
            x=x_labels,
            y=y_values,
            title="",
            ylabel="Plays",
            fill=True,
            xtick_step=step,
            figsize=(7, 3.2),
        )

        # Chart frame that expands to fill the card
        chart_frame = customtkinter.CTkFrame(card, fg_color=theme.BG, corner_radius=0)
        chart_frame.pack(fill="both", expand=True, padx=theme.PAD_S, pady=theme.PAD_S)

        self._timeline_canvas = embed_figure(fig, chart_frame)

    # ------------------------------------------------------------------
    # Top artists / tracks lists (right column)
    # ------------------------------------------------------------------

    def _build_top_lists(self, parent, analyser) -> None:
        """Stacked cards: Top 5 Artists and Top 5 Tracks."""
        col = customtkinter.CTkFrame(parent, fg_color="transparent")
        col.grid(row=0, column=1, sticky="nsew")

        # Top 5 artists
        top_artists = analyser.top_artists(5)
        self._build_ranked_card(
            col, "Top 5 Artists", top_artists,
            row_fn=lambda i, item: (f"#{i+1}  {item[0]}", f"{short_number(item[1])} plays"),
        )

        spacer = customtkinter.CTkFrame(col, height=theme.PAD_M, fg_color="transparent")
        spacer.pack(fill="x")

        # Top 5 tracks  — item: (track, artist, play_count, total_ms)
        top_tracks = analyser.top_tracks(5)
        self._build_ranked_card(
            col, "Top 5 Tracks", top_tracks,
            row_fn=lambda i, item: (f"#{i+1}  {item[0]}", f"{item[1]}  ·  {short_number(item[2])} plays"),
        )

    def _build_ranked_card(self, parent, title, items, row_fn) -> None:
        """Generic ranked-list card used for both artists and tracks."""
        card = customtkinter.CTkFrame(parent, **theme.card_style())
        card.pack(fill="x")

        # Heading
        customtkinter.CTkLabel(
            card,
            text=title,
            font=theme.label_style(theme.FONT_M, bold=True),
            text_color=theme.TEXT,
            anchor="w",
        ).pack(anchor="w", padx=theme.PAD_L, pady=(theme.PAD_L, theme.PAD_S))

        customtkinter.CTkFrame(card, height=1, fg_color=theme.BORDER, corner_radius=0).pack(
            fill="x", padx=theme.PAD_L
        )

        # List rows — each row is a left label + right muted count
        for i, item in enumerate(items):
            name_text, meta_text = row_fn(i, item)

            row_frame = customtkinter.CTkFrame(card, fg_color="transparent")
            row_frame.pack(fill="x", padx=theme.PAD_L, pady=(theme.PAD_S, 0))

            # Rank + name (truncated to avoid overflow)
            max_chars = 28
            if len(name_text) > max_chars:
                name_text = name_text[:max_chars] + "…"

            customtkinter.CTkLabel(
                row_frame,
                text=name_text,
                font=theme.label_style(theme.FONT_M),
                text_color=theme.TEXT,
                anchor="w",
            ).pack(side="left")

            # Meta info on the right
            customtkinter.CTkLabel(
                row_frame,
                text=meta_text,
                font=theme.label_style(theme.FONT_S),
                text_color=theme.TEXT_MUTED,
                anchor="e",
            ).pack(side="right")

        # Bottom padding
        customtkinter.CTkFrame(card, height=theme.PAD_M, fg_color="transparent").pack()
