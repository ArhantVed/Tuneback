"""Period Comparison page for comparing two month-based date ranges."""
from __future__ import annotations

import calendar
from datetime import datetime

import customtkinter
import matplotlib.pyplot as plt

from ui import theme
from ui.pages.base_page import BasePage
from utils.chart_helpers import embed_figure, make_grouped_bar_chart
from utils.formatting import ms_to_short, short_number


class ComparisonPage(BasePage):
    """Compare listening metrics and artists across two selected periods."""

    def refresh(self, analyser) -> None:
        self._clear()
        plt.close("all")
        self._analyser = analyser
        if analyser is None or not analyser.available_months():
            self.show_placeholder("Load your Spotify data to compare periods")
            return
        self._years = [str(year) for year in analyser.available_years()]
        self._months = analyser.available_months()
        self._build_page()

    def _build_page(self) -> None:
        shell = customtkinter.CTkScrollableFrame(self, fg_color=theme.BG, corner_radius=0)
        shell.pack(fill="both", expand=True)
        header = customtkinter.CTkFrame(shell, fg_color="transparent")
        header.pack(fill="x", padx=theme.PAD_XL, pady=(theme.PAD_XL, theme.PAD_M))
        customtkinter.CTkLabel(header, text="Period Comparison", font=theme.label_style(theme.FONT_XL, True), text_color=theme.TEXT).pack(anchor="w")
        customtkinter.CTkLabel(header, text="Compare listening patterns across two date ranges", font=theme.label_style(theme.FONT_S), text_color=theme.TEXT_MUTED).pack(anchor="w", pady=(2, 0))

        self._range_vars = {}
        self._range_menus = {}
        controls = customtkinter.CTkFrame(shell, fg_color="transparent")
        controls.pack(fill="x", padx=theme.PAD_XL, pady=theme.PAD_M)
        indexes = [0, max(0, (len(self._months) - 1) // 2), min(len(self._months) - 1, (len(self._months) - 1) // 2 + 1), len(self._months) - 1]
        for period_index, name in enumerate(("Period A", "Period B")):
            card = customtkinter.CTkFrame(controls, **theme.card_style())
            card.pack(side="left", fill="x", expand=True, padx=(0 if period_index == 0 else theme.PAD_M, 0))
            customtkinter.CTkLabel(card, text=name, font=theme.label_style(theme.FONT_M, True), text_color=theme.ACCENT).pack(anchor="w", padx=theme.PAD_M, pady=(theme.PAD_M, 0))
            row = customtkinter.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=theme.PAD_M, pady=theme.PAD_M)
            for endpoint, month_index in (("start", indexes[period_index * 2]), ("end", indexes[period_index * 2 + 1])):
                group = customtkinter.CTkFrame(row, fg_color="transparent")
                group.pack(side="left", fill="x", expand=True, padx=(0, theme.PAD_M))
                customtkinter.CTkLabel(group, text=endpoint.title(), font=theme.label_style(theme.FONT_S), text_color=theme.TEXT_MUTED).pack(anchor="w")
                value = self._months[month_index]
                year, month = value.split("-")
                key = (name, endpoint)
                year_var = customtkinter.StringVar(value=year)
                month_var = customtkinter.StringVar(value=calendar.month_name[int(month)])
                self._range_vars[key] = (year_var, month_var)
                year_menu = customtkinter.CTkOptionMenu(group, values=self._years, variable=year_var, command=lambda _v, k=key: self._year_changed(k), width=100)
                year_menu.pack(anchor="w", pady=(3, 2))
                month_values = self._month_names_for(year)
                month_menu = customtkinter.CTkOptionMenu(group, values=month_values, variable=month_var, command=lambda _v: self._selection_changed(), width=130)
                month_menu.pack(anchor="w")
                self._range_menus[key] = (year_menu, month_menu)

        self._results = customtkinter.CTkFrame(shell, fg_color="transparent")
        self._results.pack(fill="both", expand=True, padx=theme.PAD_XL, pady=(0, theme.PAD_XL))
        self._render_results()

    def _month_names_for(self, year: str) -> list[str]:
        return [calendar.month_name[int(value[-2:])] for value in self._analyser.available_months(int(year))]

    def _selected_month(self, key) -> str:
        year_var, month_var = self._range_vars[key]
        month_num = list(calendar.month_name).index(month_var.get())
        return f"{int(year_var.get()):04d}-{month_num:02d}"

    def _year_changed(self, key) -> None:
        year_var, month_var = self._range_vars[key]
        months = self._month_names_for(year_var.get())
        menu = self._range_menus[key][1]
        menu.configure(values=months)
        if month_var.get() not in months:
            month_var.set(months[0])
        self._selection_changed()

    def _selection_changed(self) -> None:
        self._render_results()

    def _period_bounds(self, period_name: str) -> tuple[datetime, datetime] | None:
        start_key = (period_name, "start")
        end_key = (period_name, "end")
        start_month = self._selected_month(start_key)
        end_month = self._selected_month(end_key)
        if start_month > end_month:
            return None
        end_year, end_number = map(int, end_month.split("-"))
        next_year, next_month = (end_year + 1, 1) if end_number == 12 else (end_year, end_number + 1)
        return datetime.strptime(start_month, "%Y-%m"), datetime(next_year, next_month, 1)

    def _render_results(self) -> None:
        for widget in self._results.winfo_children():
            widget.destroy()
        plt.close("all")
        bounds_a = self._period_bounds("Period A")
        bounds_b = self._period_bounds("Period B")
        if bounds_a is None or bounds_b is None:
            customtkinter.CTkLabel(self._results, text="Choose a start month on or before the end month for each period.", text_color=theme.TEXT_MUTED, font=theme.label_style()).pack(anchor="w", pady=theme.PAD_M)
            return
        result = self._analyser.compare_periods(*bounds_a, *bounds_b)
        self._comparison = result
        columns = customtkinter.CTkFrame(self._results, fg_color="transparent")
        columns.pack(fill="x", pady=(0, theme.PAD_M))
        metrics = (("Total plays", "total_plays", short_number), ("Unique artists", "unique_artists", short_number), ("Top artist", "top_artist", str), ("Top track", "top_track", str), ("Avg daily listening", "average_daily_ms", ms_to_short))
        for stat, name in ((result.period_a, "Period A"), (result.period_b, "Period B")):
            card = customtkinter.CTkFrame(columns, **theme.card_style())
            card.pack(side="left", fill="both", expand=True, padx=(0 if name == "Period A" else theme.PAD_M, 0))
            customtkinter.CTkLabel(card, text=f"{name}  ·  {stat.label}", font=theme.label_style(theme.FONT_M, True), text_color=theme.ACCENT).pack(anchor="w", padx=theme.PAD_M, pady=(theme.PAD_M, 3))
            for label, attr, formatter in metrics:
                raw = getattr(stat, attr)
                shown = formatter(raw)
                customtkinter.CTkLabel(card, text=f"{label}:  {shown}", font=theme.label_style(theme.FONT_S), text_color=theme.TEXT).pack(anchor="w", padx=theme.PAD_M, pady=2)

        chart_row = customtkinter.CTkFrame(self._results, fg_color="transparent")
        chart_row.pack(fill="both", expand=True)
        chart_card = customtkinter.CTkFrame(chart_row, **theme.card_style())
        chart_card.pack(side="left", fill="both", expand=True, padx=(0, theme.PAD_M))
        customtkinter.CTkLabel(chart_card, text="Top Artists", font=theme.label_style(theme.FONT_M, True), text_color=theme.TEXT).pack(anchor="w", padx=theme.PAD_M, pady=(theme.PAD_M, 0))
        artists_a = self._analyser.top_artists(5, bounds_a)
        artists_b = self._analyser.top_artists(5, bounds_b)
        count_a = {artist: count for artist, count, _ in artists_a}
        count_b = {artist: count for artist, count, _ in artists_b}
        labels = sorted(set(count_a) | set(count_b), key=lambda artist: count_a.get(artist, 0) + count_b.get(artist, 0), reverse=True)
        if labels:
            fig = make_grouped_bar_chart(labels, {"Period A": [count_a.get(a, 0) for a in labels], "Period B": [count_b.get(a, 0) for a in labels]}, title="Top 5 Artists by Plays", ylabel="Plays", figsize=(8, 3.5), color_map={"Period A": theme.ACCENT, "Period B": "#58a6ff"})
            embed_figure(fig, chart_card, fill="both", expand=True, padx=theme.PAD_S, pady=theme.PAD_S)
            self._figure = fig
        else:
            customtkinter.CTkLabel(chart_card, text="No plays in either selected period.", text_color=theme.TEXT_MUTED, font=theme.label_style()).pack(padx=theme.PAD_M, pady=theme.PAD_L)

        diff = customtkinter.CTkFrame(chart_row, **theme.card_style())
        diff.pack(side="left", fill="both", expand=True)
        customtkinter.CTkLabel(diff, text="What Changed", font=theme.label_style(theme.FONT_M, True), text_color=theme.TEXT).pack(anchor="w", padx=theme.PAD_M, pady=(theme.PAD_M, 0))
        if result.only_in_a:
            customtkinter.CTkLabel(diff, text="Only in Period A", font=theme.label_style(theme.FONT_S, True), text_color=theme.ACCENT).pack(anchor="w", padx=theme.PAD_M, pady=(theme.PAD_M, 2))
            customtkinter.CTkLabel(diff, text="\n".join(result.only_in_a), font=theme.label_style(theme.FONT_S), text_color=theme.TEXT, justify="left", anchor="w").pack(anchor="w", padx=theme.PAD_M)
        if result.only_in_b:
            customtkinter.CTkLabel(diff, text="Only in Period B", font=theme.label_style(theme.FONT_S, True), text_color="#58a6ff").pack(anchor="w", padx=theme.PAD_M, pady=(theme.PAD_M, 2))
            customtkinter.CTkLabel(diff, text="\n".join(result.only_in_b), font=theme.label_style(theme.FONT_S), text_color=theme.TEXT, justify="left", anchor="w").pack(anchor="w", padx=theme.PAD_M)
        if not result.only_in_a and not result.only_in_b:
            message = "The periods have the same artists." if result.shared_artists else "No artists to compare yet."
            customtkinter.CTkLabel(diff, text=message, font=theme.label_style(theme.FONT_S), text_color=theme.TEXT_MUTED).pack(anchor="w", padx=theme.PAD_M, pady=theme.PAD_M)
