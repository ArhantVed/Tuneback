"""Tuneback Listening Personality page."""
from __future__ import annotations

import calendar

import customtkinter
import matplotlib.pyplot as plt

from ui import theme
from ui.pages.base_page import BasePage
from utils.chart_helpers import embed_figure, make_horizontal_bar_chart
from utils.formatting import ms_to_short, pct_label, short_number


_ARCHETYPES = {
    "Night Owl": "🌙",
    "Loyalist": "💚",
    "Repeater": "🔁",
    "Discoverer": "🧭",
    "Genre Hopper": "🎧",
    "Unknown": "♪",
}

_DIMENSION_LABELS = {
    "night_score": "Night listening",
    "loyalty_score": "Artist loyalty",
    "repetition_score": "Repetition",
    "discovery_score": "Discovery",
    "variety_score": "Artist variety",
    "weekend_score": "Weekend listening",
    "skip_score": "Skip rate",
}


class PersonalityPage(BasePage):
    """Display the analyzer's listening archetype, dimensions, and evidence."""

    def refresh(self, analyser) -> None:
        self._clear()
        plt.close("all")
        if analyser is None:
            self.show_placeholder("Load your Spotify data to discover your Personality")
            return

        self._analyser = analyser
        self._profile = analyser.personality_profile()
        if self._profile.archetype == "Unknown":
            self.show_placeholder(self._profile.description)
            return
        self._build()

    def _build(self):
        scroll = customtkinter.CTkScrollableFrame(self, fg_color=theme.BG, corner_radius=0)
        scroll.pack(fill="both", expand=True)

        header = customtkinter.CTkFrame(scroll, fg_color="transparent")
        header.pack(fill="x", padx=theme.PAD_XL, pady=(theme.PAD_XL, theme.PAD_L))
        customtkinter.CTkLabel(
            header, text="Listening Personality",
            font=theme.label_style(theme.FONT_XL, bold=True), text_color=theme.TEXT,
        ).pack(side="left")
        customtkinter.CTkLabel(
            header, text="A portrait of how you listen", font=theme.label_style(theme.FONT_S),
            text_color=theme.TEXT_MUTED,
        ).pack(side="right", pady=(theme.PAD_S, 0))

        self._build_archetype_card(scroll)
        self._build_supporting_stats(scroll)
        self._build_dimensions(scroll)

    def _build_archetype_card(self, parent):
        icon = _ARCHETYPES.get(self._profile.archetype, "♪")
        card = customtkinter.CTkFrame(parent, **theme.card_style())
        card.pack(fill="x", padx=theme.PAD_XL, pady=(0, theme.PAD_L))
        content = customtkinter.CTkFrame(card, fg_color="transparent")
        content.pack(fill="x", padx=theme.PAD_L, pady=theme.PAD_L)
        customtkinter.CTkLabel(
            content, text=icon, font=theme.label_style(42), text_color=theme.ACCENT,
        ).pack(side="left", padx=(0, theme.PAD_L))
        text = customtkinter.CTkFrame(content, fg_color="transparent")
        text.pack(side="left", fill="x", expand=True)
        customtkinter.CTkLabel(
            text, text=self._profile.archetype,
            font=theme.label_style(theme.FONT_XL, bold=True), text_color=theme.TEXT,
            anchor="w",
        ).pack(anchor="w")
        customtkinter.CTkLabel(
            text, text=self._profile.description,
            font=theme.label_style(theme.FONT_M), text_color=theme.TEXT_MUTED,
            anchor="w", justify="left", wraplength=850,
        ).pack(anchor="w", pady=(theme.PAD_S, 0))

    def _build_supporting_stats(self, parent):
        stats = self._profile.key_stats
        peak_hour = stats.get("peak_hour")
        peak_day = stats.get("peak_weekday")
        hour_label = f"{int(peak_hour) % 12 or 12} {'AM' if int(peak_hour) < 12 else 'PM'}" if peak_hour is not None else "—"
        day_label = calendar.day_name[int(peak_day)] if peak_day is not None else "—"
        skip_rate = stats.get("skip_rate")
        cards = [
            ("Peak Listening Hour", hour_label, "🕒"),
            ("Most Active Day", day_label, "📅"),
            ("Avg. per Active Day", ms_to_short(int(stats.get("average_daily_ms", 0))), "⏱"),
            ("Weekend Listening", pct_label(stats.get("weekend_pct", 0), 100), "🎉"),
            ("Skip Rate", pct_label(skip_rate, 100) if skip_rate is not None else "No skip data", "⏭"),
        ]
        row = customtkinter.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=theme.PAD_XL, pady=(0, theme.PAD_L))
        for col in range(len(cards)):
            row.columnconfigure(col, weight=1)
        for col, (label, value, icon) in enumerate(cards):
            card = customtkinter.CTkFrame(row, **theme.card_style())
            card.grid(row=0, column=col, padx=(0 if col == 0 else theme.PAD_S, 0), sticky="nsew")
            customtkinter.CTkLabel(
                card, text=icon, font=theme.label_style(20), text_color=theme.ACCENT,
            ).pack(anchor="w", padx=theme.PAD_M, pady=(theme.PAD_M, 0))
            customtkinter.CTkLabel(
                card, text=value, font=theme.label_style(theme.FONT_M, bold=True),
                text_color=theme.TEXT, anchor="w", wraplength=150,
            ).pack(anchor="w", padx=theme.PAD_M, pady=(theme.PAD_S, 0))
            customtkinter.CTkLabel(
                card, text=label, font=theme.label_style(theme.FONT_S),
                text_color=theme.TEXT_MUTED, anchor="w", wraplength=150,
            ).pack(anchor="w", padx=theme.PAD_M, pady=(2, theme.PAD_M))

    def _build_dimensions(self, parent):
        card = customtkinter.CTkFrame(parent, **theme.card_style())
        card.pack(fill="both", expand=True, padx=theme.PAD_XL, pady=(0, theme.PAD_XL))
        customtkinter.CTkLabel(
            card, text="What shapes your listening?",
            font=theme.label_style(theme.FONT_M, bold=True), text_color=theme.TEXT,
        ).pack(anchor="w", padx=theme.PAD_L, pady=(theme.PAD_L, theme.PAD_S))
        customtkinter.CTkLabel(
            card, text="Scores are based on your full listening history. Skip rate appears when the export includes skip data.",
            font=theme.label_style(theme.FONT_S), text_color=theme.TEXT_MUTED,
        ).pack(anchor="w", padx=theme.PAD_L)

        dimensions = self._profile.dimension_scores
        keys = [key for key in _DIMENSION_LABELS if key in dimensions]
        labels = [_DIMENSION_LABELS[key] for key in keys]
        values = [dimensions[key] for key in keys]
        fig = make_horizontal_bar_chart(
            labels, values, title="", xlabel="Score (0–100)",
            figsize=(8.5, max(3.2, len(labels) * 0.55)), max_label_len=24,
        )
        self._dimension_figure = fig
        chart_frame = customtkinter.CTkFrame(card, fg_color=theme.BG)
        chart_frame.pack(fill="both", expand=True, padx=theme.PAD_S,
                         pady=(theme.PAD_S, theme.PAD_M))
        self._dimension_canvas = embed_figure(fig, chart_frame)

        key_stats = self._profile.key_stats
        evidence = (
            f"{short_number(int(key_stats.get('total_plays', 0)))} plays  ·  "
            f"{short_number(int(key_stats.get('unique_artists', 0)))} artists  ·  "
            f"Top artist: {key_stats.get('top_artist', '—')} "
            f"({key_stats.get('loyalty_pct', 0):.1f}% of plays)"
        )
        customtkinter.CTkLabel(
            card, text=evidence, font=theme.label_style(theme.FONT_S),
            text_color=theme.TEXT_MUTED, anchor="w",
        ).pack(anchor="w", padx=theme.PAD_L, pady=(0, theme.PAD_L))
