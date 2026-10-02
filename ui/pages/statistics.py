"""Detailed listening statistics with sortable rankings and month chart."""
from __future__ import annotations

from datetime import datetime

import customtkinter
import matplotlib.pyplot as plt

from ui import theme
from ui.pages.base_page import BasePage
from utils.chart_helpers import embed_figure, make_bar_chart, make_line_chart, popup_figure
from utils.formatting import date_label, month_label, ms_to_short, short_number


class RankedTable(customtkinter.CTkFrame):
    """Compact, sortable ranking table; row selection opens its detail chart."""

    def __init__(self, parent, columns, rows, on_select, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._columns = columns
        self._rows = list(rows)
        self._on_select = on_select
        self._sort_column = None
        self._sort_reverse = False
        self._render()

    def _render(self):
        for child in self.winfo_children():
            child.destroy()
        header = customtkinter.CTkFrame(self, fg_color=theme.SURFACE_RAISED)
        header.pack(fill="x")
        for index, (key, label, _) in enumerate(self._columns):
            header.grid_columnconfigure(index, weight=1 if index == 0 else 0)
            customtkinter.CTkButton(
                header, text=label, anchor="w" if index == 0 else "e",
                fg_color="transparent", hover_color=theme.SURFACE,
                text_color=theme.TEXT_MUTED, font=theme.label_style(theme.FONT_S, bold=True),
                command=lambda name=key: self._sort(name),
            ).grid(row=0, column=index, sticky="ew", padx=theme.PAD_S, pady=2)

        body = customtkinter.CTkScrollableFrame(self, fg_color=theme.SURFACE, height=390)
        body.pack(fill="both", expand=True)
        for rank, row in enumerate(self._rows, start=1):
            line = customtkinter.CTkFrame(body, fg_color="transparent")
            line.pack(fill="x", padx=theme.PAD_S, pady=1)
            line.grid_columnconfigure(0, weight=1)
            for index, (key, _, formatter) in enumerate(self._columns):
                value = row[key]
                text = formatter(value) if formatter else str(value)
                if index == 0:
                    text = f"{rank}.  {text}"
                button = customtkinter.CTkButton(
                    line, text=text, anchor="w" if index == 0 else "e",
                    fg_color="transparent", hover_color=theme.SURFACE_RAISED,
                    text_color=theme.TEXT, font=theme.label_style(theme.FONT_S),
                    command=lambda selected=row: self._on_select(selected),
                )
                button.grid(row=0, column=index, sticky="ew", padx=theme.PAD_S)

    def _sort(self, column):
        if self._sort_column == column:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column, self._sort_reverse = column, True
        self._rows.sort(key=lambda row: row[column], reverse=self._sort_reverse)
        self._render()


class StatisticsPage(BasePage):
    """Artists, tracks, and monthly listening breakdown."""

    def refresh(self, analyser) -> None:
        self._clear()
        plt.close("all")
        if analyser is None:
            self.show_placeholder("Load your Spotify data to see your Statistics")
            return
        if not analyser.first_and_last_play():
            self.show_placeholder("No listening history found")
            return

        self._analyser = analyser
        self._active_tab = "Artists"
        self._figures = []
        self._build()

    def _build(self):
        scroll = customtkinter.CTkScrollableFrame(self, fg_color=theme.BG, corner_radius=0)
        scroll.pack(fill="both", expand=True)
        header = customtkinter.CTkFrame(scroll, fg_color="transparent")
        header.pack(fill="x", padx=theme.PAD_XL, pady=(theme.PAD_XL, theme.PAD_L))
        customtkinter.CTkLabel(
            header, text="Statistics", font=theme.label_style(theme.FONT_XL, bold=True),
            text_color=theme.TEXT,
        ).pack(side="left")
        customtkinter.CTkLabel(
            header, text="Rankings and monthly listening time", font=theme.label_style(theme.FONT_S),
            text_color=theme.TEXT_MUTED,
        ).pack(side="right", pady=(theme.PAD_S, 0))

        self._tabs = customtkinter.CTkFrame(scroll, fg_color=theme.SURFACE)
        self._tabs.pack(fill="x", padx=theme.PAD_XL, pady=(0, theme.PAD_M))
        for name in ("Artists", "Tracks", "Monthly Breakdown"):
            customtkinter.CTkButton(
                self._tabs, text=name, width=150, command=lambda tab=name: self._show_tab(tab),
            ).pack(side="left", padx=theme.PAD_S, pady=theme.PAD_S)
        self._content = customtkinter.CTkFrame(scroll, fg_color="transparent")
        self._content.pack(fill="both", expand=True, padx=theme.PAD_XL, pady=(0, theme.PAD_XL))
        self._show_tab("Artists")

    def _show_tab(self, tab):
        self._active_tab = tab
        for child in self._content.winfo_children():
            child.destroy()
        for button in self._tabs.winfo_children():
            active = button.cget("text") == tab
            button.configure(
                fg_color=theme.ACCENT if active else theme.SURFACE_RAISED,
                hover_color=theme.ACCENT_HOVER if active else theme.BORDER,
                text_color=theme.BG if active else theme.TEXT,
            )
        if tab == "Artists":
            self._show_artists()
        elif tab == "Tracks":
            self._show_tracks()
        else:
            self._show_monthly()

    def _show_artists(self):
        rows = []
        for artist, count, total_ms in self._analyser.top_artists(50):
            first = self._analyser.first_heard(artist)
            last = self._analyser.last_heard(artist)
            rows.append({"name": artist, "plays": count, "time": total_ms,
                         "first": first, "last": last})
        self._table(rows, track=False)

    def _show_tracks(self):
        rows = []
        for track, artist, count, total_ms in self._analyser.top_tracks(50):
            first = self._analyser.first_heard_for_track(track, artist)
            last = self._analyser.last_heard_for_track(track, artist)
            rows.append({"name": track, "artist": artist, "plays": count, "time": total_ms,
                         "first": first, "last": last})
        self._table(rows, track=True)

    def _table(self, rows, track):
        if not rows:
            customtkinter.CTkLabel(self._content, text="No plays to show",
                                   text_color=theme.TEXT_MUTED).pack(pady=theme.PAD_XL)
            return
        columns = [("name", "Track" if track else "Artist", None)]
        if track:
            columns.append(("artist", "Artist", None))
        columns.extend([
            ("plays", "Plays", short_number),
            ("time", "Total Time", ms_to_short),
            ("first", "First Heard", lambda value: date_label(value, "day") if value else "—"),
            ("last", "Last Heard", lambda value: date_label(value, "day") if value else "—"),
        ])
        RankedTable(self._content, columns, rows,
                    lambda row: self._show_detail(row, track)).pack(fill="both", expand=True)

    def _show_monthly(self):
        monthly = self._analyser.listening_by_month()
        if not monthly:
            customtkinter.CTkLabel(self._content, text="No monthly listening to show",
                                   text_color=theme.TEXT_MUTED).pack(pady=theme.PAD_XL)
            return
        keys = list(monthly)
        labels = [month_label(key) for key in keys]
        values = [monthly[key] / 3_600_000 for key in keys]
        fig = make_bar_chart(labels, values, title="Listening Time by Month",
                             ylabel="Hours", figsize=(10, 4.2), max_label_len=14)
        self._figures.append(fig)
        card = customtkinter.CTkFrame(self._content, **theme.card_style())
        card.pack(fill="both", expand=True)
        customtkinter.CTkLabel(card, text="Click a month to see its top artists",
                               font=theme.label_style(theme.FONT_S),
                               text_color=theme.TEXT_MUTED).pack(anchor="w", padx=theme.PAD_L,
                                                                 pady=(theme.PAD_M, 0))
        chart_frame = customtkinter.CTkFrame(card, fg_color=theme.BG)
        chart_frame.pack(fill="both", expand=True, padx=theme.PAD_S, pady=theme.PAD_S)
        canvas = embed_figure(fig, chart_frame)
        ax = fig.axes[0]
        month_bars = ax.patches
        canvas.mpl_connect("pick_event", lambda event: None)
        for index, bar in enumerate(month_bars):
            bar.set_picker(True)
            bar._tuneback_month = keys[index]
        canvas.mpl_connect("pick_event", self._on_month_pick)

    def _on_month_pick(self, event):
        key = event.artist._tuneback_month
        year, month = map(int, key.split("-"))
        start = datetime(year, month, 1)
        end = datetime(year + (month == 12), 1 if month == 12 else month + 1, 1)
        artists = self._analyser.top_artists(15, period=(start, end))
        fig = make_bar_chart([name for name, _, _ in artists],
                             [count for _, count, _ in artists],
                             title=f"Top Artists — {month_label(key)}", ylabel="Plays")
        popup_figure(fig, f"{month_label(key)} details")

    def _show_detail(self, row, track):
        if track:
            series = self._analyser.track_plays_over_time(row["name"], row["artist"])
            title = f"{row['name']} — {row['artist']}"
        else:
            series = self._analyser.artist_plays_over_time(row["name"])
            title = row["name"]
        labels = [month_label(key) for key in series]
        fig = make_line_chart(labels, list(series.values()), title=title,
                              ylabel="Plays", xtick_step=max(1, len(labels) // 12),
                              figsize=(9, 4))
        popup_figure(fig, f"{title} listening history")
