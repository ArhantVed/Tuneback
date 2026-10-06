"""Tuneback Music Evolution page: monthly artist rankings and discoveries."""
from __future__ import annotations

import tkinter as tk

import customtkinter
import matplotlib.pyplot as plt

from ui import theme
from ui.pages.base_page import BasePage
from utils.chart_helpers import embed_figure, make_grouped_bar_chart
from utils.formatting import month_label


DISCOVERY_PAGE_SIZE = 18


def _timeline_series(
    analyser, year: str | None = None,
    first_heard: dict | None = None,
    evolution_counts: dict[str, dict[str, int]] | None = None,
) -> tuple[list[str], dict[str, list[int]]]:
    """Build aligned monthly Top 3 counts from the analyser's month index."""
    evolution_counts = evolution_counts or analyser.music_evolution_counts_by_period(
        "month", top_n=3,
    )
    periods = [key for key in evolution_counts if year is None or key.startswith(year)]
    if first_heard is None:
        first_heard = analyser.first_heard_by_artist()
    artist_order = sorted(first_heard, key=lambda artist: (first_heard[artist], artist.casefold()))
    visible_artists = {
        artist for key in periods for artist in evolution_counts[key]
    }
    series = {
        artist: [evolution_counts[key].get(artist, 0) for key in periods]
        for artist in artist_order if artist in visible_artists
    }
    return periods, series


class MusicEvolutionPage(BasePage):
    """Explore each month's leading artists and artists first heard by year."""

    DISCOVERY_PAGE_SIZE = DISCOVERY_PAGE_SIZE

    def refresh(self, analyser) -> None:
        self._close_timeline_chart()
        self._clear()
        if analyser is None:
            self.show_placeholder("Load your Spotify data to explore Music Evolution")
            return
        if not analyser.first_and_last_play():
            self.show_placeholder("No listening history found")
            return
        self._analyser = analyser
        self._first_heard = analyser.first_heard_by_artist()
        self._evolution_counts = analyser.music_evolution_counts_by_period(
            "month", top_n=3,
        )
        self._discoveries = sorted(
            self._first_heard.items(),
            key=lambda item: (item[1], item[0].casefold()),
        )
        self._build()

    def _build(self):
        self._scroll = customtkinter.CTkScrollableFrame(
            self, fg_color=theme.BG, corner_radius=0
        )
        self._scroll.pack(fill="both", expand=True)

        header = customtkinter.CTkFrame(self._scroll, fg_color="transparent")
        header.pack(fill="x", padx=theme.PAD_XL, pady=(theme.PAD_XL, theme.PAD_L))
        customtkinter.CTkLabel(
            header, text="Music Evolution", font=theme.label_style(theme.FONT_XL, bold=True),
            text_color=theme.TEXT,
        ).pack(side="left")
        customtkinter.CTkLabel(
            header, text="See which artists shaped each chapter of your listening",
            font=theme.label_style(theme.FONT_S), text_color=theme.TEXT_MUTED,
        ).pack(side="right", pady=(theme.PAD_S, 0))

        controls = customtkinter.CTkFrame(self._scroll, **theme.card_style())
        controls.pack(fill="x", padx=theme.PAD_XL, pady=(0, theme.PAD_L))
        customtkinter.CTkLabel(
            controls, text="Timeline year", font=theme.label_style(theme.FONT_M),
            text_color=theme.TEXT_MUTED,
        ).pack(side="left", padx=theme.PAD_L, pady=theme.PAD_M)
        years = ["All years"] + [str(year) for year in self._analyser.available_years()]
        self._year_var = customtkinter.StringVar(value="All years")
        self._year_menu = customtkinter.CTkOptionMenu(
            controls, values=years, variable=self._year_var,
            fg_color=theme.SURFACE_RAISED, button_color=theme.SURFACE_RAISED,
            button_hover_color=theme.BORDER, text_color=theme.TEXT,
            font=theme.label_style(theme.FONT_M), width=130,
            command=self._on_year_changed,
        )
        self._year_menu.pack(side="left", padx=(0, theme.PAD_L), pady=theme.PAD_M)

        self._body = customtkinter.CTkFrame(self._scroll, fg_color="transparent")
        self._body.pack(fill="both", expand=True, padx=theme.PAD_XL, pady=(0, theme.PAD_XL))
        self._render()

    def _on_year_changed(self, _value: str):
        self._render()

    def _render(self):
        self._close_timeline_chart()
        for child in self._body.winfo_children():
            child.destroy()

        selected = self._year_var.get()
        year = None if selected == "All years" else selected
        periods, series = _timeline_series(
            self._analyser, year, self._first_heard, self._evolution_counts,
        )
        if not periods:
            self._empty_state()
            return

        self._build_timeline(periods, series)
        self._build_discoveries(year)

    def _empty_state(self):
        card = customtkinter.CTkFrame(self._body, **theme.card_style())
        card.pack(fill="x", pady=theme.PAD_M)
        customtkinter.CTkLabel(
            card, text="No listening history is available for this year.",
            font=theme.label_style(theme.FONT_M), text_color=theme.TEXT_MUTED,
        ).pack(padx=theme.PAD_L, pady=theme.PAD_XL)

    def _build_timeline(self, periods, series):
        card = customtkinter.CTkFrame(self._body, **theme.card_style())
        card.pack(fill="x", pady=(0, theme.PAD_L))
        title = "Monthly Top Artists" if self._year_var.get() == "All years" else f"Top Artists in {self._year_var.get()}"
        customtkinter.CTkLabel(
            card, text=title, font=theme.label_style(theme.FONT_M, bold=True),
            text_color=theme.TEXT,
        ).pack(anchor="w", padx=theme.PAD_L, pady=(theme.PAD_L, theme.PAD_S))
        customtkinter.CTkLabel(
            card, text="Grouped bars show monthly play counts for each month's top three artists.",
            font=theme.label_style(theme.FONT_S), text_color=theme.TEXT_MUTED,
        ).pack(anchor="w", padx=theme.PAD_L, pady=(0, theme.PAD_S))

        chart_width = max(9.0, min(0.85 * len(periods), 32.0))
        all_artists = sorted(
            self._first_heard,
            key=lambda artist: (self._first_heard[artist], artist.casefold()),
        )
        color_map = {
            artist: theme.CHART_COLORS[index % len(theme.CHART_COLORS)]
            for index, artist in enumerate(all_artists)
        }
        fig = make_grouped_bar_chart(
            labels=[month_label(period) for period in periods], groups=series,
            title="", ylabel="Plays", figsize=(chart_width, 4.2),
            color_map=color_map, sparse=True, show_legend=False,
            use_tight_layout=False,
        )
        self._timeline_figure = fig
        horizontal = customtkinter.CTkScrollableFrame(
            card, orientation="horizontal", fg_color=theme.BG,
            height=345, corner_radius=6,
        )
        horizontal.pack(fill="x", padx=theme.PAD_S, pady=(0, theme.PAD_S))
        chart_container = customtkinter.CTkFrame(
            horizontal, fg_color=theme.BG, width=int(chart_width * 100), height=330,
        )
        chart_container.pack(fill="y", expand=False)
        chart_container.pack_propagate(False)
        self._timeline_canvas = embed_figure(fig, chart_container, fill="both", expand=True)

    def _build_discoveries(self, year):
        card = customtkinter.CTkFrame(self._body, **theme.card_style())
        card.pack(fill="x")
        heading = "New Discoveries" if year is None else f"New Discoveries in {year}"
        customtkinter.CTkLabel(
            card, text=heading, font=theme.label_style(theme.FONT_M, bold=True),
            text_color=theme.TEXT,
        ).pack(anchor="w", padx=theme.PAD_L, pady=(theme.PAD_L, theme.PAD_S))
        self._visible_discoveries = [
            item for item in self._discoveries
            if year is None or str(item[1].year) == year
        ]
        if not self._visible_discoveries:
            customtkinter.CTkLabel(
                card, text="No new artist discoveries for this year.",
                font=theme.label_style(theme.FONT_S), text_color=theme.TEXT_MUTED,
            ).pack(anchor="w", padx=theme.PAD_L, pady=(0, theme.PAD_L))
            return

        self._discovery_count = len(self._visible_discoveries)
        self._discovery_visible_count = 0
        self._discovery_summary = customtkinter.CTkLabel(
            card, text="", anchor="w", font=theme.label_style(theme.FONT_S),
            text_color=theme.TEXT_MUTED,
        )
        self._discovery_summary.pack(anchor="w", padx=theme.PAD_L, pady=(0, theme.PAD_S))
        list_frame = customtkinter.CTkScrollableFrame(
            card, fg_color=theme.SURFACE, height=190,
        )
        list_frame.pack(fill="x", padx=theme.PAD_S, pady=(0, theme.PAD_S))
        self._discovery_list = list_frame
        self._load_more_button = customtkinter.CTkButton(
            card, text="Load More", command=self._load_more_discoveries,
            fg_color=theme.SURFACE_RAISED, hover_color=theme.BORDER,
            text_color=theme.TEXT, font=theme.label_style(theme.FONT_S),
        )
        self._render_discovery_batch()

    def _render_discovery_batch(self):
        end = min(
            self._discovery_visible_count + self.DISCOVERY_PAGE_SIZE,
            self._discovery_count,
        )
        for artist, heard in self._visible_discoveries[self._discovery_visible_count:end]:
            row = customtkinter.CTkFrame(self._discovery_list, fg_color="transparent")
            row.pack(fill="x", padx=theme.PAD_S, pady=2)
            customtkinter.CTkLabel(
                row, text=artist, anchor="w", font=theme.label_style(theme.FONT_S),
                text_color=theme.TEXT,
            ).pack(side="left", fill="x", expand=True)
            customtkinter.CTkLabel(
                row, text=heard.strftime("%b %d, %Y"), anchor="e",
                font=theme.label_style(theme.FONT_S), text_color=theme.TEXT_MUTED,
            ).pack(side="right")
        self._discovery_visible_count = end
        self._discovery_summary.configure(
            text=(f"Showing {end} of {self._discovery_count} artist"
                  f"{'s' if self._discovery_count != 1 else ''}")
        )
        if end < self._discovery_count:
            self._load_more_button.pack(pady=(0, theme.PAD_M))
        else:
            self._load_more_button.pack_forget()

    def _load_more_discoveries(self):
        self._render_discovery_batch()

    def _close_timeline_chart(self):
        canvas = getattr(self, "_timeline_canvas", None)
        if canvas is not None:
            try:
                canvas.get_tk_widget().destroy()
            except (tk.TclError, AttributeError):
                pass
            self._timeline_canvas = None
        figure = getattr(self, "_timeline_figure", None)
        if figure is not None:
            plt.close(figure)
            self._timeline_figure = None
