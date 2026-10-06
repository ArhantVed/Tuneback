"""Tuneback Abandoned Artists page."""
from __future__ import annotations

import matplotlib.pyplot as plt
import customtkinter

from ui import theme
from ui.pages.base_page import BasePage
from utils.chart_helpers import make_line_chart, popup_figure
from utils.formatting import date_label, month_label, short_number


class AbandonedPage(BasePage):
    """Find long-quiet artists and revisit their monthly listening history."""

    MIN_PLAYS = 10
    MIN_SILENCE_DAYS = 90
    MAX_SILENCE_DAYS = 365
    PAGE_SIZE = 18

    def refresh(self, analyser) -> None:
        """Rebuild page after navigation/data changes without retaining old charts."""
        self._clear()
        plt.close("all")
        if analyser is None:
            self.show_placeholder("Load your Spotify data to find Abandoned Artists")
            return
        if not analyser.first_and_last_play():
            self.show_placeholder("No listening history found")
            return

        self._analyser = analyser
        self._silence_days = 180
        self._build_shell()

    def _build_shell(self):
        self._scroll = customtkinter.CTkScrollableFrame(
            self, fg_color=theme.BG, corner_radius=0,
        )
        self._scroll.pack(fill="both", expand=True)
        self._build_header()
        self._build_threshold_control()
        self._result_summary = customtkinter.CTkLabel(
            self._scroll, text="", anchor="w",
            font=theme.label_style(theme.FONT_S), text_color=theme.TEXT_MUTED,
        )
        self._result_summary.pack(fill="x", padx=theme.PAD_XL, pady=(0, theme.PAD_S))
        self._grid = customtkinter.CTkFrame(self._scroll, fg_color="transparent")
        self._grid.pack(fill="both", expand=True, padx=theme.PAD_XL, pady=(0, theme.PAD_XL))
        for column in range(3):
            self._grid.grid_columnconfigure(column, weight=1, uniform="abandoned_cards")
        self._load_more_button = customtkinter.CTkButton(
            self._scroll, text="Load More", command=self._load_more,
            fg_color=theme.SURFACE_RAISED, hover_color=theme.BORDER,
            text_color=theme.TEXT, font=theme.label_style(theme.FONT_M),
        )
        self._render_artists()

    def _build_header(self):
        header = customtkinter.CTkFrame(self._scroll, fg_color="transparent")
        header.pack(fill="x", padx=theme.PAD_XL, pady=(theme.PAD_XL, theme.PAD_L))
        customtkinter.CTkLabel(
            header, text="Abandoned Artists",
            font=theme.label_style(theme.FONT_XL, bold=True), text_color=theme.TEXT,
        ).pack(side="left")
        customtkinter.CTkLabel(
            header, text="A look back at artists you haven’t played in a while",
            font=theme.label_style(theme.FONT_S), text_color=theme.TEXT_MUTED,
        ).pack(side="right", pady=(theme.PAD_S, 0))

    def _build_threshold_control(self):
        controls = customtkinter.CTkFrame(self._scroll, **theme.card_style())
        controls.pack(fill="x", padx=theme.PAD_XL, pady=(0, theme.PAD_M))
        customtkinter.CTkLabel(
            controls, text="Silence threshold",
            font=theme.label_style(theme.FONT_M, bold=True), text_color=theme.TEXT,
        ).pack(anchor="w", padx=theme.PAD_L, pady=(theme.PAD_M, 0))
        customtkinter.CTkLabel(
            controls,
            text="Days are measured from the newest play in your imported history. Artists need at least 10 plays.",
            font=theme.label_style(theme.FONT_S), text_color=theme.TEXT_MUTED,
        ).pack(anchor="w", padx=theme.PAD_L, pady=(2, 0))

        row = customtkinter.CTkFrame(controls, fg_color="transparent")
        row.pack(fill="x", padx=theme.PAD_L, pady=(theme.PAD_S, theme.PAD_M))
        self._silence_var = customtkinter.DoubleVar(value=self._silence_days)
        self._silence_slider = customtkinter.CTkSlider(
            row, from_=self.MIN_SILENCE_DAYS, to=self.MAX_SILENCE_DAYS,
            number_of_steps=(self.MAX_SILENCE_DAYS - self.MIN_SILENCE_DAYS) // 5,
            variable=self._silence_var, command=self._on_threshold_changed,
            progress_color=theme.ACCENT, button_color=theme.ACCENT,
            button_hover_color=theme.ACCENT_HOVER,
        )
        self._silence_slider.pack(side="left", fill="x", expand=True,
                                  padx=(0, theme.PAD_L))
        self._silence_label = customtkinter.CTkLabel(
            row, text="180 days", width=100,
            font=theme.label_style(theme.FONT_M, bold=True), text_color=theme.ACCENT,
        )
        self._silence_label.pack(side="right")

    def _on_threshold_changed(self, value):
        effective_days = int(round(float(value) / 5) * 5)
        effective_days = min(max(effective_days, self.MIN_SILENCE_DAYS),
                             self.MAX_SILENCE_DAYS)
        if effective_days == self._silence_days:
            return
        self._silence_days = effective_days
        self._silence_var.set(effective_days)
        self._silence_label.configure(text=f"{effective_days} days")
        self._render_artists()

    def _render_artists(self):
        """Analyze all matches, then render only the first page of cards."""
        for child in self._grid.winfo_children():
            child.destroy()
        self._load_more_button.pack_forget()
        self._artists = self._analyser.abandoned_artists(
            min_plays=self.MIN_PLAYS,
            silence_days=self._silence_days,
        )
        self._visible_count = 0
        if not self._artists:
            self._result_summary.configure(
                text=(f"No artists have at least {self.MIN_PLAYS} plays and "
                      f"{self._silence_days} days of silence.")
            )
            return

        count = len(self._artists)
        self._result_summary.configure(
            text=self._summary_text(count)
        )
        self._render_next_batch()

    def _summary_text(self, count: int) -> str:
        shown = min(self._visible_count, count)
        return (
            f"{count} artist{'s' if count != 1 else ''} found · "
            f"Showing {shown} of {count} · sorted by total plays · newest "
            f"history date is "
            f"{date_label(self._analyser.first_and_last_play()[1].timestamp, 'day')}"
        )

    def _render_next_batch(self) -> None:
        start = self._visible_count
        end = min(start + self.PAGE_SIZE, len(self._artists))
        for index in range(start, end):
            self._build_artist_card(index, self._artists[index])
        self._visible_count = end
        self._result_summary.configure(text=self._summary_text(len(self._artists)))
        if end < len(self._artists):
            self._load_more_button.pack(
                padx=theme.PAD_XL, pady=(0, theme.PAD_XL), anchor="center",
            )
        else:
            self._load_more_button.pack_forget()

    def _load_more(self) -> None:
        """Append the next result batch without disturbing existing cards."""
        self._render_next_batch()

    def _build_artist_card(self, index, artist):
        card = customtkinter.CTkFrame(self._grid, **theme.card_style())
        card.grid(row=index // 3, column=index % 3,
                  padx=(0 if index % 3 == 0 else theme.PAD_M, 0),
                  pady=(0, theme.PAD_M), sticky="nsew")
        customtkinter.CTkLabel(
            card, text="◷  LOST IN THE ARCHIVE",
            font=theme.label_style(theme.FONT_S, bold=True), text_color=theme.ACCENT,
            anchor="w",
        ).pack(anchor="w", padx=theme.PAD_L, pady=(theme.PAD_L, theme.PAD_S))
        customtkinter.CTkButton(
            card, text=artist.artist, anchor="w",
            fg_color="transparent", hover_color=theme.SURFACE_RAISED,
            text_color=theme.TEXT, font=theme.label_style(theme.FONT_L, bold=True),
            command=lambda selected=artist: self._open_artist_history(selected),
        ).pack(fill="x", padx=theme.PAD_S)
        customtkinter.CTkLabel(
            card, text=f"{short_number(artist.total_plays)} total plays",
            font=theme.label_style(theme.FONT_M), text_color=theme.TEXT_MUTED,
            anchor="w",
        ).pack(anchor="w", padx=theme.PAD_L, pady=(0, theme.PAD_M))

        details = customtkinter.CTkFrame(card, fg_color=theme.SURFACE_RAISED,
                                         corner_radius=6)
        details.pack(fill="x", padx=theme.PAD_M, pady=(0, theme.PAD_M))
        rows = [
            ("Last played", date_label(artist.last_played, "day")),
            ("Quiet for", f"{artist.days_since_last_play} days"),
            ("Peak month", month_label(artist.peak_month)),
        ]
        for label, value in rows:
            line = customtkinter.CTkFrame(details, fg_color="transparent")
            line.pack(fill="x", padx=theme.PAD_S, pady=3)
            customtkinter.CTkLabel(
                line, text=label, font=theme.label_style(theme.FONT_S),
                text_color=theme.TEXT_MUTED, anchor="w",
            ).pack(side="left")
            customtkinter.CTkLabel(
                line, text=value, font=theme.label_style(theme.FONT_S, bold=True),
                text_color=theme.TEXT, anchor="e",
            ).pack(side="right")

        customtkinter.CTkButton(
            card, text="View listening history  →", anchor="center",
            fg_color=theme.SURFACE_RAISED, hover_color=theme.BORDER,
            text_color=theme.TEXT, font=theme.label_style(theme.FONT_S),
            command=lambda selected=artist: self._open_artist_history(selected),
        ).pack(fill="x", padx=theme.PAD_M, pady=(0, theme.PAD_M))

    def _open_artist_history(self, artist):
        """Show the selected artist's complete monthly history in a pop-out."""
        history = self._analyser.artist_plays_over_time(
            artist.artist, granularity="month",
        )
        labels = [month_label(month) for month in history]
        fig = make_line_chart(
            labels, list(history.values()),
            title=f"{artist.artist} · Listening History",
            ylabel="Plays", xtick_step=max(1, len(labels) // 12),
            figsize=(9, 4),
        )
        popup_figure(fig, f"{artist.artist} listening history")
