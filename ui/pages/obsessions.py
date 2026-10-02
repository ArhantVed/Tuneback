"""Tuneback Obsession Detection page."""
from __future__ import annotations

from datetime import datetime, timedelta

import customtkinter
import matplotlib.pyplot as plt

from ui import theme
from ui.pages.base_page import BasePage
from utils.chart_helpers import embed_figure, make_line_chart
from utils.formatting import date_label


class ObsessionsPage(BasePage):
    """Find artist-dominant periods and inspect their daily play history."""

    def refresh(self, analyser) -> None:
        """Rebuild this page safely after navigation or a data reload."""
        self._clear()
        plt.close("all")
        self._detail_figure = None
        if analyser is None:
            self.show_placeholder("Load your Spotify data to detect Obsession periods")
            return

        if not analyser.first_and_last_play():
            self.show_placeholder("No listening history found")
            return

        self._analyser = analyser
        self._threshold = 50
        self._build_shell()

    def _build_shell(self):
        self._scroll = customtkinter.CTkScrollableFrame(
            self, fg_color=theme.BG, corner_radius=0
        )
        self._scroll.pack(fill="both", expand=True)
        self._build_header()
        self._build_controls()
        self._build_panels()
        self._render_periods()

    def _build_header(self):
        header = customtkinter.CTkFrame(self._scroll, fg_color="transparent")
        header.pack(fill="x", padx=theme.PAD_XL, pady=(theme.PAD_XL, theme.PAD_L))
        customtkinter.CTkLabel(
            header, text="Obsession Detection",
            font=theme.label_style(theme.FONT_XL, bold=True), text_color=theme.TEXT,
        ).pack(side="left")
        customtkinter.CTkLabel(
            header, text="Find the stretches when one artist took over",
            font=theme.label_style(theme.FONT_S), text_color=theme.TEXT_MUTED,
        ).pack(side="right", pady=(theme.PAD_S, 0))

    def _build_controls(self):
        controls = customtkinter.CTkFrame(self._scroll, **theme.card_style())
        controls.pack(fill="x", padx=theme.PAD_XL, pady=(0, theme.PAD_L))
        customtkinter.CTkLabel(
            controls, text="Dominance threshold",
            font=theme.label_style(theme.FONT_M, bold=True), text_color=theme.TEXT,
        ).pack(anchor="w", padx=theme.PAD_L, pady=(theme.PAD_M, 0))
        customtkinter.CTkLabel(
            controls, text="An artist must account for this share of plays in each month of a period.",
            font=theme.label_style(theme.FONT_S), text_color=theme.TEXT_MUTED,
        ).pack(anchor="w", padx=theme.PAD_L, pady=(2, 0))

        slider_row = customtkinter.CTkFrame(controls, fg_color="transparent")
        slider_row.pack(fill="x", padx=theme.PAD_L, pady=(theme.PAD_S, theme.PAD_M))
        self._threshold_var = customtkinter.DoubleVar(value=self._threshold)
        self._threshold_slider = customtkinter.CTkSlider(
            slider_row, from_=20, to=100, number_of_steps=16,
            variable=self._threshold_var, command=self._on_threshold_changed,
            progress_color=theme.ACCENT, button_color=theme.ACCENT,
            button_hover_color=theme.ACCENT_HOVER,
        )
        self._threshold_slider.pack(side="left", fill="x", expand=True, padx=(0, theme.PAD_L))
        self._threshold_label = customtkinter.CTkLabel(
            slider_row, text="50%", width=55,
            font=theme.label_style(theme.FONT_M, bold=True), text_color=theme.ACCENT,
        )
        self._threshold_label.pack(side="right")

    def _build_panels(self):
        panels = customtkinter.CTkFrame(self._scroll, fg_color="transparent")
        panels.pack(fill="both", expand=True, padx=theme.PAD_XL, pady=(0, theme.PAD_XL))
        panels.grid_columnconfigure(0, weight=2, uniform="obsession_panels")
        panels.grid_columnconfigure(1, weight=3, uniform="obsession_panels")

        self._list_panel = customtkinter.CTkFrame(panels, **theme.card_style())
        self._list_panel.grid(row=0, column=0, sticky="nsew", padx=(0, theme.PAD_M))
        customtkinter.CTkLabel(
            self._list_panel, text="Detected Periods",
            font=theme.label_style(theme.FONT_M, bold=True), text_color=theme.TEXT,
        ).pack(anchor="w", padx=theme.PAD_L, pady=(theme.PAD_L, theme.PAD_S))
        customtkinter.CTkFrame(
            self._list_panel, height=1, fg_color=theme.BORDER, corner_radius=0,
        ).pack(fill="x", padx=theme.PAD_L)
        self._period_list = customtkinter.CTkScrollableFrame(
            self._list_panel, fg_color="transparent", height=430,
        )
        self._period_list.pack(fill="both", expand=True, padx=theme.PAD_S, pady=theme.PAD_S)

        self._detail_panel = customtkinter.CTkFrame(panels, **theme.card_style())
        self._detail_panel.grid(row=0, column=1, sticky="nsew")

    def _on_threshold_changed(self, value):
        self._threshold = int(round(float(value) / 5) * 5)
        self._threshold_var.set(self._threshold)
        self._threshold_label.configure(text=f"{self._threshold}%")
        self._render_periods()

    def _render_periods(self):
        for child in self._period_list.winfo_children():
            child.destroy()
        self._clear_detail()
        self._periods = self._analyser.obsession_periods(
            threshold_pct=self._threshold,
        )
        if not self._periods:
            customtkinter.CTkLabel(
                self._period_list,
                text="No obsession periods found at this threshold.",
                font=theme.label_style(theme.FONT_S), text_color=theme.TEXT_MUTED,
                wraplength=240, justify="left",
            ).pack(anchor="w", padx=theme.PAD_M, pady=theme.PAD_L)
            self._show_detail_placeholder("Lower the threshold to explore more periods.")
            return

        for index, period in enumerate(self._periods):
            self._build_period_card(index, period)
        self._show_period_detail(0)

    def _build_period_card(self, index, period):
        card = customtkinter.CTkFrame(self._period_list, **theme.card_style())
        card.pack(fill="x", padx=theme.PAD_S, pady=theme.PAD_S)
        end_date = date_label(period.end_date, "day")
        start_date = date_label(period.start_date, "day")
        button = customtkinter.CTkButton(
            card,
            text=(f"{period.artist}\n{start_date} – {end_date}\n"
                  f"Peak monthly share: {period.peak_pct:.1f}%  ·  {period.total_plays} plays"),
            anchor="w", height=76,
            fg_color="transparent", hover_color=theme.SURFACE_RAISED,
            text_color=theme.TEXT, font=theme.label_style(theme.FONT_S),
            command=lambda selected=index: self._show_period_detail(selected),
        )
        button.pack(fill="x", padx=theme.PAD_S, pady=(theme.PAD_S, 2))
        intensity = customtkinter.CTkProgressBar(
            card, progress_color=theme.ACCENT, fg_color=theme.SURFACE_RAISED,
            height=7,
        )
        intensity.set(min(max(period.peak_pct / 100.0, 0.0), 1.0))
        intensity.pack(fill="x", padx=theme.PAD_M, pady=(0, theme.PAD_M))

    def _show_detail_placeholder(self, message):
        customtkinter.CTkLabel(
            self._detail_panel, text="Select an obsession period",
            font=theme.label_style(theme.FONT_L, bold=True), text_color=theme.TEXT,
        ).pack(anchor="w", padx=theme.PAD_L, pady=(theme.PAD_L, theme.PAD_S))
        customtkinter.CTkLabel(
            self._detail_panel, text=message,
            font=theme.label_style(theme.FONT_S), text_color=theme.TEXT_MUTED,
            wraplength=480, justify="left",
        ).pack(anchor="w", padx=theme.PAD_L, pady=(0, theme.PAD_L))

    def _clear_detail(self):
        for child in self._detail_panel.winfo_children():
            child.destroy()
        if self._detail_figure is not None:
            plt.close(self._detail_figure)
            self._detail_figure = None

    def _show_period_detail(self, index):
        self._clear_detail()
        period = self._periods[index]
        customtkinter.CTkLabel(
            self._detail_panel, text=f"{period.artist} over time",
            font=theme.label_style(theme.FONT_L, bold=True), text_color=theme.TEXT,
        ).pack(anchor="w", padx=theme.PAD_L, pady=(theme.PAD_L, theme.PAD_S))
        customtkinter.CTkLabel(
            self._detail_panel,
            text=(f"{date_label(period.start_date, 'day')} – "
                  f"{date_label(period.end_date, 'day')}  ·  "
                  f"{period.total_plays} plays during this period"),
            font=theme.label_style(theme.FONT_S), text_color=theme.TEXT_MUTED,
        ).pack(anchor="w", padx=theme.PAD_L, pady=(0, theme.PAD_S))

        end_exclusive = period.end_date + timedelta(days=1)
        daily_counts = self._analyser.artist_plays_over_time(
            period.artist, granularity="day",
            period=(period.start_date, end_exclusive),
        )
        days = [datetime.strptime(key, "%Y-%m-%d") for key in daily_counts]
        labels = [date_label(day, "day") for day in days]
        self._detail_figure = make_line_chart(
            labels, list(daily_counts.values()),
            title=f"Daily Plays · Peak {period.peak_pct:.1f}%",
            ylabel="Plays", xtick_step=max(1, len(labels) // 12),
            figsize=(8, 3.8),
        )
        chart_frame = customtkinter.CTkFrame(self._detail_panel, fg_color=theme.BG)
        chart_frame.pack(fill="both", expand=True, padx=theme.PAD_S,
                         pady=(theme.PAD_S, theme.PAD_M))
        self._detail_canvas = embed_figure(self._detail_figure, chart_frame)
