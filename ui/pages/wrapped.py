"""Wrapped listening-story slideshow, rendered inside the Tuneback page."""
from __future__ import annotations

from datetime import datetime
import tkinter

import customtkinter
import matplotlib.pyplot as plt

from ui import theme
from ui.pages.base_page import BasePage
from utils.chart_helpers import embed_figure, make_bar_chart, make_horizontal_bar_chart
from utils.formatting import ms_to_human, short_number


class WrappedPage(BasePage):
    """Present one selected year's listening story as a bounded slideshow."""

    def refresh(self, analyser) -> None:
        self._cancel_transition()
        self._clear()
        plt.close("all")
        self._analyser = analyser
        if analyser is None or not analyser.available_years():
            self.show_placeholder("Load your Spotify data to generate your Wrapped Report")
            return

        self._years = [str(year) for year in analyser.available_years()]
        self._selected_year = self._years[-1]
        self._index = 0
        self._build_shell()
        self._load_story(animate=False)

    def _build_shell(self) -> None:
        header = customtkinter.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=theme.PAD_XL, pady=(theme.PAD_L, theme.PAD_M))
        customtkinter.CTkLabel(
            header, text="Tuneback Wrapped", font=theme.label_style(theme.FONT_XL, True),
            text_color=theme.TEXT,
        ).pack(side="left")
        customtkinter.CTkLabel(
            header, text="A year in your listening", font=theme.label_style(theme.FONT_S),
            text_color=theme.TEXT_MUTED,
        ).pack(side="left", padx=theme.PAD_M, pady=(theme.PAD_S, 0))

        self._year_var = customtkinter.StringVar(value=self._selected_year)
        self._year_menu = customtkinter.CTkOptionMenu(
            header, values=self._years, variable=self._year_var,
            command=self._on_year_changed, width=110,
            fg_color=theme.SURFACE_RAISED, button_color=theme.ACCENT,
            button_hover_color=theme.ACCENT_HOVER, text_color=theme.TEXT,
        )
        self._year_menu.pack(side="right")

        self._slide_host = customtkinter.CTkFrame(self, fg_color="transparent")
        self._slide_host.pack(fill="both", expand=True, padx=theme.PAD_XL, pady=theme.PAD_M)

        footer = customtkinter.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=theme.PAD_XL, pady=(theme.PAD_M, theme.PAD_L))
        self._previous_button = customtkinter.CTkButton(
            footer, text="←  Previous", command=self.previous_slide, width=132,
            fg_color=theme.SURFACE_RAISED, hover_color=theme.BORDER,
            text_color=theme.TEXT,
        )
        self._previous_button.pack(side="left")
        self._indicator = customtkinter.CTkLabel(
            footer, text="", font=theme.label_style(theme.FONT_M, True),
            text_color=theme.TEXT_MUTED,
        )
        self._indicator.pack(side="left", expand=True)
        self._next_button = customtkinter.CTkButton(
            footer, text="Next  →", command=self.next_slide, width=132,
            fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
            text_color=theme.TEXT,
        )
        self._next_button.pack(side="right")

    def _on_year_changed(self, year: str) -> None:
        self._selected_year = year
        self._index = 0
        self._load_story(animate=False)

    def _load_story(self, animate: bool) -> None:
        year = int(self._selected_year)
        start = datetime(year, 1, 1)
        end = datetime(year + 1, 1, 1)
        period = (start, end)
        summary = self._analyser.wrapped_summary(year)
        profile = self._analyser.personality_profile()
        artists = self._analyser.top_artists(5, period)
        tracks = self._analyser.top_tracks(1, period)
        hour_counts = self._analyser.listening_by_hour(period)
        peak_hour = max(hour_counts, key=hour_counts.get)
        peak_hour_text = f"{(peak_hour % 12) or 12} {'AM' if peak_hour < 12 else 'PM'}"
        repeated_track = tracks[0] if tracks else None

        if summary.obsession_artist:
            repeat_title = "A season of one artist"
            repeat_value = summary.obsession_artist
            repeat_subtitle = "Your listening history flagged a concentrated obsession period."
        elif repeated_track and repeated_track[2] > 1:
            repeat_title = "The one you replayed"
            repeat_value = repeated_track[0]
            repeat_subtitle = f"{repeated_track[2]:,} plays · {repeated_track[1]}"
        else:
            repeat_title = "Your repeat-listening highlight"
            repeat_value = "No strong repeat pattern"
            repeat_subtitle = "This year's top track was heard once in the available history."

        self._slides = [
            {"eyebrow": "YOUR YEAR IN SOUND", "title": f"Your {year}", "value": "Wrapped", "subtitle": f"A story made from {short_number(summary.total_plays)} plays."},
            {"eyebrow": "TIME WELL SPENT", "title": "You spent", "value": ms_to_human(summary.total_ms), "subtitle": "with music this year."},
            {"eyebrow": "EVERY PLAY COUNTS", "title": "You listened", "value": short_number(summary.total_plays), "subtitle": "tracks played across the year."},
            {"eyebrow": "A WIDE CATALOG", "title": "Your listening reached", "value": f"{summary.unique_artists:,} artists", "subtitle": f"and {summary.unique_tracks:,} distinct tracks."},
            {"eyebrow": "THE SOUNDTRACK", "title": "Your top artist", "value": summary.top_artist, "subtitle": f"{artists[0][1]:,} plays in {year}." if artists else "No artist plays were recorded for this year.", "chart": "artists", "artists": artists},
            {"eyebrow": "ON REPEAT", "title": "Your top track", "value": summary.top_track, "subtitle": f"by {summary.top_track_artist} · {tracks[0][2]:,} plays" if tracks else f"by {summary.top_track_artist}"},
            {"eyebrow": "YOUR LISTENING RHYTHM", "title": "Your busiest listening hour", "value": peak_hour_text, "subtitle": "Here is how your plays were spread across the day.", "chart": "hours", "hours": hour_counts},
            {"eyebrow": "YOUR LISTENING PERSONALITY", "title": "Your listening archetype", "value": summary.personality_type, "subtitle": profile.description},
            {"eyebrow": "A REPEAT-LISTENING HIGHLIGHT", "title": repeat_title, "value": repeat_value, "subtitle": repeat_subtitle},
            {"eyebrow": "MONTHLY MOMENT", "title": "Your most active month", "value": summary.top_month, "subtitle": f"The month with your most listening time in {year}."},
            {"eyebrow": "UNTIL NEXT YEAR", "title": "Thanks for listening", "value": f"See you in {year + 1}", "subtitle": f"{summary.top_artist}, {summary.top_track}, and {short_number(summary.total_plays)} moments in music."},
        ]
        self.show_slide(self._index, animate=animate)

    def show_slide(self, index: int, animate: bool = True) -> None:
        """Render a bounded slide index, clearing its old chart and widgets."""
        self._cancel_transition()
        self._index = max(0, min(index, len(self._slides) - 1))
        for child in self._slide_host.winfo_children():
            child.destroy()
        plt.close("all")

        slide = self._slides[self._index]
        self._figure = None
        card = customtkinter.CTkFrame(
            self._slide_host, fg_color=theme.SURFACE, corner_radius=18,
            border_width=1, border_color=theme.BORDER,
        )
        card.pack(fill="both", expand=True, padx=theme.PAD_L, pady=theme.PAD_S)
        customtkinter.CTkFrame(card, fg_color=theme.ACCENT, height=5, corner_radius=0).pack(fill="x")
        content = customtkinter.CTkFrame(card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=theme.PAD_XL, pady=theme.PAD_L)
        customtkinter.CTkLabel(
            content, text=slide["eyebrow"], font=theme.label_style(theme.FONT_S, True),
            text_color=theme.ACCENT,
        ).pack(anchor="w", pady=(theme.PAD_M, theme.PAD_S))
        customtkinter.CTkLabel(
            content, text=slide["title"], font=theme.label_style(theme.FONT_L, True),
            text_color=theme.TEXT,
        ).pack(anchor="w")
        self._value_label = customtkinter.CTkLabel(
            content, text=slide["value"], font=theme.label_style(42, True),
            text_color=theme.TEXT, wraplength=900, justify="left", anchor="w",
        )
        self._value_label.pack(anchor="w", pady=(theme.PAD_M, theme.PAD_S))
        customtkinter.CTkLabel(
            content, text=slide["subtitle"], font=theme.label_style(theme.FONT_M),
            text_color=theme.TEXT_MUTED, wraplength=900, justify="left", anchor="w",
        ).pack(anchor="w", pady=(0, theme.PAD_M))

        chart = slide.get("chart")
        if chart == "artists" and slide["artists"]:
            figure = make_horizontal_bar_chart(
                [artist for artist, _, _ in slide["artists"]],
                [count for _, count, _ in slide["artists"]],
                title="Most played artists", color=theme.ACCENT,
                figsize=(8, 2.5),
            )
            embed_figure(figure, content, fill="both", expand=True, pady=theme.PAD_S)
            self._figure = figure
        elif chart == "hours":
            hours = slide["hours"]
            figure = make_bar_chart(
                [str(hour) for hour in hours], list(hours.values()),
                title="Plays by hour", color=theme.ACCENT,
                xlabel="Hour of day", ylabel="Plays", figsize=(9, 2.6),
            )
            embed_figure(figure, content, fill="both", expand=True, pady=theme.PAD_S)
            self._figure = figure

        self._indicator.configure(text=f"{self._index + 1} / {len(self._slides)}")
        self._previous_button.configure(state="normal" if self._index > 0 else "disabled")
        self._next_button.configure(state="normal" if self._index < len(self._slides) - 1 else "disabled")
        if animate:
            self._value_label.configure(text_color=theme.TEXT_MUTED)
            self._transition_job = self.after(90, self._finish_transition)

    def _finish_transition(self) -> None:
        self._transition_job = None
        if self._value_label.winfo_exists():
            self._value_label.configure(text_color=theme.TEXT)

    def _cancel_transition(self) -> None:
        job = getattr(self, "_transition_job", None)
        if job is not None:
            try:
                self.after_cancel(job)
            except (tkinter.TclError, RuntimeError):
                pass
            self._transition_job = None

    def previous_slide(self) -> None:
        self.show_slide(self._index - 1)

    def next_slide(self) -> None:
        self.show_slide(self._index + 1)
