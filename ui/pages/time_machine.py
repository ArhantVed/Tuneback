"""
ui/pages/time_machine.py — Tuneback Time Machine page.

Lets the user pick any month from their history and instantly see what
they were listening to at that moment.

Layout
------
  ┌─────────────────────────────────────────────────────┐
  │  Time Machine      [Year ▾] [Month ▾]  [◀ ▶]        │  ← controls row
  ├────────────────────────────┬────────────────────────┤
  │ ♪ Memory Card              │ Stats strip             │  ← highlight + counts
  │  Most-played track         │  plays / artists /time  │
  ├────────────────────────────┴────────────────────────┤
  │ Top Artists (horizontal bar chart)                   │  ← chart
  ├────────────────────────────┬────────────────────────┤
  │ Top 5 Artists list         │ Top 5 Tracks list       │  ← ranked lists
  └────────────────────────────┴────────────────────────┘

All analysis is delegated to Analyser; formatting to utils.formatting;
charts to utils.chart_helpers.

Python concepts: OOP inheritance, datetime arithmetic, CTkOptionMenu
callbacks, calendar module, f-strings, list comprehension.
"""

from __future__ import annotations

import calendar
from datetime import datetime

import customtkinter
import matplotlib.pyplot as plt

from ui.pages.base_page import BasePage
from ui import theme
from utils.formatting import ms_to_short, short_number, month_label
from utils.chart_helpers import make_horizontal_bar_chart, embed_figure


# Month names used in the dropdown — index 1-12
_MONTH_NAMES = [calendar.month_name[m] for m in range(1, 13)]


class TimeMachinePage(BasePage):
    """Pick any month in history and replay what you were listening to.

    The page is split into two logical areas:
      - Controls (year/month dropdowns + prev/next arrows)  — rebuilt once
        per data load, then updated in-place on navigation.
      - Results panel — destroyed and rebuilt every time the selection changes.

    This keeps the dropdown state alive across result refreshes so the UI
    feels responsive rather than flickering on every change.
    """

    def refresh(self, analyser) -> None:
        """Called by App whenever this page becomes active or data changes."""
        self._clear()
        plt.close("all")

        if analyser is None:
            self.show_placeholder("Load your Spotify data to use the Time Machine")
            return

        # Cache the analyser so _on_selection_changed() can access it
        self._analyser = analyser

        self._build_shell(analyser)

    # ------------------------------------------------------------------
    # Shell build  (controls + results container)
    # ------------------------------------------------------------------

    def _build_shell(self, analyser) -> None:
        """Construct the page shell: header, controls, and results area."""
        # Main scroll wrapper
        self._scroll = customtkinter.CTkScrollableFrame(
            self, fg_color=theme.BG, corner_radius=0
        )
        self._scroll.pack(fill="both", expand=True)

        self._build_header(self._scroll)
        self._build_controls(self._scroll, analyser)

        # Results container — cleared and rebuilt on each selection change
        self._results_frame = customtkinter.CTkFrame(
            self._scroll, fg_color="transparent"
        )
        self._results_frame.pack(fill="both", expand=True,
                                 padx=theme.PAD_XL, pady=(0, theme.PAD_XL))

        # Render initial results for the default selection
        self._render_results()

    def _build_header(self, parent) -> None:
        header = customtkinter.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", padx=theme.PAD_XL, pady=(theme.PAD_XL, theme.PAD_M))

        customtkinter.CTkLabel(
            header,
            text="Time Machine",
            font=theme.label_style(theme.FONT_XL, bold=True),
            text_color=theme.TEXT,
            anchor="w",
        ).pack(side="left")

        customtkinter.CTkLabel(
            header,
            text="Travel back to any month in your listening history",
            font=theme.label_style(theme.FONT_S),
            text_color=theme.TEXT_MUTED,
            anchor="e",
        ).pack(side="right", pady=(theme.PAD_S, 0))

    def _build_controls(self, parent, analyser) -> None:
        """Year dropdown + Month dropdown + prev/next navigation buttons."""
        bar = customtkinter.CTkFrame(parent, fg_color=theme.SURFACE,
                                     corner_radius=8)
        bar.pack(fill="x", padx=theme.PAD_XL, pady=(0, theme.PAD_L))

        # ---- Determine available year/month options from loaded data ----
        self._years  = [str(y) for y in analyser.available_years()]
        self._months_by_year: dict[str, list[str]] = {}
        for y in self._years:
            # available_months returns "YYYY-MM" strings — extract month names
            raw = analyser.available_months(int(y))
            self._months_by_year[y] = [_MONTH_NAMES[int(m.split("-")[1]) - 1] for m in raw]

        # Default selection: most recent year and its most recent month
        default_year  = self._years[-1]
        default_month = self._months_by_year[default_year][-1]

        # Tkinter string variables so we can read and write them programmatically
        self._var_year  = customtkinter.StringVar(value=default_year)
        self._var_month = customtkinter.StringVar(value=default_month)

        inner = customtkinter.CTkFrame(bar, fg_color="transparent")
        inner.pack(padx=theme.PAD_L, pady=theme.PAD_M)

        # Label
        customtkinter.CTkLabel(
            inner,
            text="Select a month:",
            font=theme.label_style(theme.FONT_M),
            text_color=theme.TEXT_MUTED,
        ).pack(side="left", padx=(0, theme.PAD_M))

        # Year dropdown
        self._year_menu = customtkinter.CTkOptionMenu(
            inner,
            values=self._years,
            variable=self._var_year,
            fg_color=theme.SURFACE_RAISED,
            button_color=theme.SURFACE_RAISED,
            button_hover_color=theme.BORDER,
            text_color=theme.TEXT,
            font=theme.label_style(theme.FONT_M),
            width=90,
            command=self._on_year_changed,
        )
        self._year_menu.pack(side="left", padx=(0, theme.PAD_S))

        # Month dropdown
        self._month_menu = customtkinter.CTkOptionMenu(
            inner,
            values=self._months_by_year[default_year],
            variable=self._var_month,
            fg_color=theme.SURFACE_RAISED,
            button_color=theme.SURFACE_RAISED,
            button_hover_color=theme.BORDER,
            text_color=theme.TEXT,
            font=theme.label_style(theme.FONT_M),
            width=120,
            command=self._on_month_changed,
        )
        self._month_menu.pack(side="left", padx=(0, theme.PAD_L))

        # Prev / Next navigation buttons
        nav_frame = customtkinter.CTkFrame(inner, fg_color="transparent")
        nav_frame.pack(side="left", padx=(theme.PAD_M, 0))

        customtkinter.CTkButton(
            nav_frame,
            text="◀",
            width=36, height=32,
            fg_color=theme.SURFACE_RAISED,
            hover_color=theme.BORDER,
            text_color=theme.TEXT,
            font=theme.label_style(theme.FONT_M),
            command=self._go_prev,
        ).pack(side="left", padx=(0, theme.PAD_S))

        customtkinter.CTkButton(
            nav_frame,
            text="▶",
            width=36, height=32,
            fg_color=theme.SURFACE_RAISED,
            hover_color=theme.BORDER,
            text_color=theme.TEXT,
            font=theme.label_style(theme.FONT_M),
            command=self._go_next,
        ).pack(side="left")

    # ------------------------------------------------------------------
    # Navigation helpers
    # ------------------------------------------------------------------

    def _all_months_ordered(self) -> list[tuple[str, str]]:
        """Return all (year, month_name) pairs in chronological order."""
        pairs: list[tuple[str, str]] = []
        for y in self._years:
            for m in self._months_by_year[y]:
                pairs.append((y, m))
        return pairs

    def _go_prev(self) -> None:
        """Navigate one month backward."""
        pairs = self._all_months_ordered()
        current = (self._var_year.get(), self._var_month.get())
        if current in pairs:
            idx = pairs.index(current)
            if idx > 0:
                prev_y, prev_m = pairs[idx - 1]
                self._set_selection(prev_y, prev_m)

    def _go_next(self) -> None:
        """Navigate one month forward."""
        pairs = self._all_months_ordered()
        current = (self._var_year.get(), self._var_month.get())
        if current in pairs:
            idx = pairs.index(current)
            if idx < len(pairs) - 1:
                next_y, next_m = pairs[idx + 1]
                self._set_selection(next_y, next_m)

    def _set_selection(self, year: str, month: str) -> None:
        """Programmatically set the year+month dropdowns and refresh results."""
        self._var_year.set(year)
        # Update available months for this year
        self._month_menu.configure(values=self._months_by_year[year])
        self._var_month.set(month)
        self._render_results()

    def _on_year_changed(self, new_year: str) -> None:
        """When year changes, update month options and default to last month."""
        months = self._months_by_year[new_year]
        self._month_menu.configure(values=months)
        self._var_month.set(months[-1])
        self._render_results()

    def _on_month_changed(self, _: str) -> None:
        self._render_results()

    # ------------------------------------------------------------------
    # Results rendering
    # ------------------------------------------------------------------

    def _render_results(self) -> None:
        """Destroy and rebuild the results panel for the current selection."""
        # Clear previous results and figure memory
        for widget in self._results_frame.winfo_children():
            widget.destroy()
        plt.close("all")

        year_str  = self._var_year.get()
        month_str = self._var_month.get()

        # Convert selection to a (start, end) datetime window
        year  = int(year_str)
        month = _MONTH_NAMES.index(month_str) + 1  # 1-based month number
        start = datetime(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end   = datetime(year, month, last_day, 23, 59, 59)

        # Fetch data via analyser — all analysis happens here
        plays  = self._analyser.plays_in_period(start, end)
        period = (start, end)

        if not plays:
            self._show_no_data_for_period(year_str, month_str)
            return

        top_artists = self._analyser.top_artists(5, period=period)
        top_tracks  = self._analyser.top_tracks(5, period=period)
        total_ms    = sum(p.ms_played for p in plays)
        n_artists   = len({p.artist for p in plays})

        self._build_memory_row(period, top_tracks, total_ms, n_artists, len(plays))
        self._build_chart(top_artists)
        self._build_lists_row(top_artists, top_tracks)

    def _show_no_data_for_period(self, year: str, month: str) -> None:
        """Empty-state card when the selected month has no plays."""
        card = customtkinter.CTkFrame(self._results_frame, **theme.card_style())
        card.pack(fill="x", pady=theme.PAD_L)
        customtkinter.CTkLabel(
            card,
            text=f"No plays found in {month} {year}",
            font=theme.label_style(theme.FONT_M),
            text_color=theme.TEXT_MUTED,
        ).pack(pady=theme.PAD_XL)

    # ------------------------------------------------------------------
    # Memory card + stats strip
    # ------------------------------------------------------------------

    def _build_memory_row(self, period, top_tracks, total_ms, n_artists, n_plays) -> None:
        """Memory card (most-played track) + stats strip side by side."""
        row = customtkinter.CTkFrame(self._results_frame, fg_color="transparent")
        row.pack(fill="x", pady=(0, theme.PAD_L))
        row.columnconfigure(0, weight=2)
        row.columnconfigure(1, weight=3)

        self._build_memory_card(row, top_tracks)
        self._build_stats_strip(row, total_ms, n_artists, n_plays, period)

    def _build_memory_card(self, parent, top_tracks) -> None:
        """Highlight card showing the single most-played track of the period."""
        card = customtkinter.CTkFrame(parent, **theme.card_style())
        card.grid(row=0, column=0, sticky="nsew", padx=(0, theme.PAD_M))

        customtkinter.CTkLabel(
            card,
            text="♪  Memory",
            font=theme.label_style(theme.FONT_S, bold=True),
            text_color=theme.ACCENT,
            anchor="w",
        ).pack(anchor="w", padx=theme.PAD_L, pady=(theme.PAD_L, theme.PAD_S))

        customtkinter.CTkFrame(card, height=1, fg_color=theme.BORDER,
                               corner_radius=0).pack(fill="x", padx=theme.PAD_L)

        if top_tracks:
            track, artist, play_count, _ = top_tracks[0]

            # Truncate long track names
            display_track  = track[:32]  + ("…" if len(track)  > 32 else "")
            display_artist = artist[:28] + ("…" if len(artist) > 28 else "")

            customtkinter.CTkLabel(
                card,
                text=display_track,
                font=theme.label_style(theme.FONT_L, bold=True),
                text_color=theme.TEXT,
                anchor="w",
                wraplength=260,
            ).pack(anchor="w", padx=theme.PAD_L, pady=(theme.PAD_M, 0))

            customtkinter.CTkLabel(
                card,
                text=display_artist,
                font=theme.label_style(theme.FONT_M),
                text_color=theme.TEXT_MUTED,
                anchor="w",
            ).pack(anchor="w", padx=theme.PAD_L)

            customtkinter.CTkLabel(
                card,
                text=f"played {play_count}× this month",
                font=theme.label_style(theme.FONT_S),
                text_color=theme.ACCENT,
                anchor="w",
            ).pack(anchor="w", padx=theme.PAD_L, pady=(theme.PAD_S, theme.PAD_L))
        else:
            customtkinter.CTkLabel(
                card,
                text="No tracks found",
                font=theme.label_style(theme.FONT_M),
                text_color=theme.TEXT_MUTED,
            ).pack(pady=theme.PAD_XL)

    def _build_stats_strip(self, parent, total_ms, n_artists, n_plays, period) -> None:
        """Three mini-stats: total time, plays, unique artists."""
        card = customtkinter.CTkFrame(parent, **theme.card_style())
        card.grid(row=0, column=1, sticky="nsew")

        customtkinter.CTkLabel(
            card,
            text="Month at a Glance",
            font=theme.label_style(theme.FONT_S, bold=True),
            text_color=theme.TEXT_MUTED,
            anchor="w",
        ).pack(anchor="w", padx=theme.PAD_L, pady=(theme.PAD_L, theme.PAD_S))

        customtkinter.CTkFrame(card, height=1, fg_color=theme.BORDER,
                               corner_radius=0).pack(fill="x", padx=theme.PAD_L)

        stats = [
            ("⏱  Listening Time", ms_to_short(total_ms)),
            ("▶  Plays",          short_number(n_plays)),
            ("🎤  Artists",       short_number(n_artists)),
        ]

        stats_row = customtkinter.CTkFrame(card, fg_color="transparent")
        stats_row.pack(fill="x", padx=theme.PAD_L, pady=theme.PAD_L)

        for i, (label, value) in enumerate(stats):
            cell = customtkinter.CTkFrame(stats_row, fg_color=theme.SURFACE_RAISED,
                                          corner_radius=6)
            cell.pack(side="left", padx=(0 if i == 0 else theme.PAD_M, 0),
                      fill="x", expand=True)

            customtkinter.CTkLabel(
                cell,
                text=value,
                font=theme.label_style(theme.FONT_L, bold=True),
                text_color=theme.TEXT,
            ).pack(pady=(theme.PAD_M, 0))

            customtkinter.CTkLabel(
                cell,
                text=label,
                font=theme.label_style(theme.FONT_S),
                text_color=theme.TEXT_MUTED,
            ).pack(pady=(0, theme.PAD_M))

    # ------------------------------------------------------------------
    # Top artists bar chart
    # ------------------------------------------------------------------

    def _build_chart(self, top_artists) -> None:
        """Horizontal bar chart of top artists for the selected month."""
        if not top_artists:
            return

        card = customtkinter.CTkFrame(self._results_frame, **theme.card_style())
        card.pack(fill="x", pady=(0, theme.PAD_L))

        customtkinter.CTkLabel(
            card,
            text="Top Artists This Month",
            font=theme.label_style(theme.FONT_M, bold=True),
            text_color=theme.TEXT,
            anchor="w",
        ).pack(anchor="w", padx=theme.PAD_L, pady=(theme.PAD_L, theme.PAD_S))

        customtkinter.CTkFrame(card, height=1, fg_color=theme.BORDER,
                               corner_radius=0).pack(fill="x", padx=theme.PAD_L)

        labels = [item[0] for item in top_artists]
        values = [item[1] for item in top_artists]   # play counts

        fig = make_horizontal_bar_chart(
            labels=labels,
            values=values,
            xlabel="Plays",
            figsize=(7, 2.6),
        )

        chart_frame = customtkinter.CTkFrame(card, fg_color=theme.BG, corner_radius=0)
        chart_frame.pack(fill="x", padx=theme.PAD_S, pady=theme.PAD_S)

        self._chart_canvas = embed_figure(fig, chart_frame,
                                          fill="x", expand=False)

    # ------------------------------------------------------------------
    # Top artists + tracks ranked lists
    # ------------------------------------------------------------------

    def _build_lists_row(self, top_artists, top_tracks) -> None:
        """Side-by-side Top 5 Artists and Top 5 Tracks lists."""
        row = customtkinter.CTkFrame(self._results_frame, fg_color="transparent")
        row.pack(fill="x")
        row.columnconfigure(0, weight=1)
        row.columnconfigure(1, weight=1)

        # Artists list — item: (artist, play_count, total_ms)
        self._build_list_card(
            row, col=0,
            title="Top 5 Artists",
            items=top_artists,
            row_fn=lambda i, item: (
                f"#{i+1}  {item[0]}",
                f"{short_number(item[1])} plays",
            ),
        )

        # Tracks list — item: (track, artist, play_count, total_ms)
        self._build_list_card(
            row, col=1,
            title="Top 5 Tracks",
            items=top_tracks,
            row_fn=lambda i, item: (
                f"#{i+1}  {item[0]}",
                f"{item[1]}  ·  {short_number(item[2])}×",
            ),
        )

    def _build_list_card(self, parent, col, title, items, row_fn) -> None:
        """Reusable ranked list card (mirrors Dashboard's _build_ranked_card)."""
        card = customtkinter.CTkFrame(parent, **theme.card_style())
        card.grid(row=0, column=col,
                  padx=(0 if col == 0 else theme.PAD_M, 0),
                  sticky="nsew")

        customtkinter.CTkLabel(
            card,
            text=title,
            font=theme.label_style(theme.FONT_M, bold=True),
            text_color=theme.TEXT,
            anchor="w",
        ).pack(anchor="w", padx=theme.PAD_L, pady=(theme.PAD_L, theme.PAD_S))

        customtkinter.CTkFrame(card, height=1, fg_color=theme.BORDER,
                               corner_radius=0).pack(fill="x", padx=theme.PAD_L)

        max_chars = 26
        for i, item in enumerate(items):
            name_text, meta_text = row_fn(i, item)
            if len(name_text) > max_chars:
                name_text = name_text[:max_chars] + "…"

            row_frame = customtkinter.CTkFrame(card, fg_color="transparent")
            row_frame.pack(fill="x", padx=theme.PAD_L, pady=(theme.PAD_S, 0))

            customtkinter.CTkLabel(
                row_frame,
                text=name_text,
                font=theme.label_style(theme.FONT_M),
                text_color=theme.TEXT,
                anchor="w",
            ).pack(side="left")

            customtkinter.CTkLabel(
                row_frame,
                text=meta_text,
                font=theme.label_style(theme.FONT_S),
                text_color=theme.TEXT_MUTED,
                anchor="e",
            ).pack(side="right")

        customtkinter.CTkFrame(card, height=theme.PAD_M,
                               fg_color="transparent").pack()
