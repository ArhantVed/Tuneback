"""Focused validation for Music Evolution's analyser inputs."""
from datetime import datetime
import unittest
from unittest.mock import patch

from core.analyser import Analyser
from core.models import Play

try:
    import customtkinter
    import matplotlib.pyplot as plt
    from ui.pages.music_evolution import MusicEvolutionPage, _timeline_series
    from utils.chart_helpers import make_grouped_bar_chart
    UI_IMPORT_ERROR = None
except ImportError as exc:
    customtkinter = None
    plt = None
    MusicEvolutionPage = None
    _timeline_series = None
    make_grouped_bar_chart = None
    UI_IMPORT_ERROR = exc


def many_discovery_plays(artist_count=25):
    plays = []
    for index in range(artist_count):
        plays.append(Play(
            datetime(2021, 1, 1, 0, index), f"Artist {index:02d}",
            f"Track {index:02d}", 60_000,
        ))
    plays.append(Play(datetime(2022, 1, 1), "Later Artist", "Later Track", 60_000))
    return plays


class MusicEvolutionAnalyserTests(unittest.TestCase):
    def setUp(self):
        self.analyser = Analyser([
            Play(datetime(2021, 12, 15), "Cedar", "Track 1", 30_000),
            Play(datetime(2022, 1, 2), "Cedar", "Track 1", 30_000),
            Play(datetime(2022, 1, 3), "Birch", "Track 2", 30_000),
            Play(datetime(2022, 1, 4), "Birch", "Track 3", 30_000),
            Play(datetime(2022, 2, 1), "Aspen", "Track 4", 30_000),
            Play(datetime(2022, 2, 2), "Birch", "Track 2", 30_000),
        ])

    def test_monthly_and_yearly_top_artists(self):
        self.assertEqual(self.analyser.music_evolution_by_period("month"), {
            "2021-12": ["Cedar"],
            "2022-01": ["Birch", "Cedar"],
            "2022-02": ["Aspen", "Birch"],
        })

    def test_monthly_top_artist_counts_match_existing_rankings(self):
        counts = self.analyser.music_evolution_counts_by_period("month", top_n=3)
        self.assertEqual(counts, {
            "2021-12": {"Cedar": 1},
            "2022-01": {"Birch": 2, "Cedar": 1},
            "2022-02": {"Aspen": 1, "Birch": 1},
        })
        self.assertEqual(
            self.analyser.music_evolution_by_period("month", top_n=3),
            {period: list(values) for period, values in counts.items()},
        )

    def test_cached_results_are_returned_as_safe_copies(self):
        first_heard = self.analyser.first_heard_by_artist()
        first_heard.clear()
        counts = self.analyser.music_evolution_counts_by_period("month", top_n=3)
        counts["2022-01"].clear()
        self.assertEqual(len(self.analyser.first_heard_by_artist()), 3)
        self.assertEqual(
            self.analyser.music_evolution_counts_by_period("month", top_n=3)["2022-01"],
            {"Birch": 2, "Cedar": 1},
        )
        self.assertEqual(self.analyser.music_evolution_by_period("year"), {
            "2021": ["Cedar"],
            "2022": ["Birch", "Cedar", "Aspen"],
        })

    def test_first_heard_timestamps_drive_discoveries(self):
        self.assertEqual(self.analyser.first_heard_by_artist(), {
            "Cedar": datetime(2021, 12, 15),
            "Birch": datetime(2022, 1, 3),
            "Aspen": datetime(2022, 2, 1),
        })

    def test_empty_history_returns_empty_evolution_data(self):
        empty = Analyser([])
        self.assertEqual(empty.music_evolution_by_period("month"), {})
        self.assertEqual(empty.first_heard_by_artist(), {})


@unittest.skipUnless(UI_IMPORT_ERROR is None, f"UI dependencies unavailable: {UI_IMPORT_ERROR}")
class MusicEvolutionPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = customtkinter.CTk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def setUp(self):
        self.page = MusicEvolutionPage(self.root)
        self.page.pack(fill="both", expand=True)

    def tearDown(self):
        self.page.destroy()
        plt.close("all")
        self.root.update_idletasks()

    def test_monthly_series_uses_indexed_counts_without_period_rescans(self):
        analyser = self.analyser = Analyser(many_discovery_plays())
        with patch.object(analyser, "top_artists", side_effect=AssertionError("full-period rescan")):
            periods, series = _timeline_series(analyser, "2021")
        self.assertEqual(periods, ["2021-01"])
        self.assertEqual(list(series), ["Artist 00", "Artist 01", "Artist 02"])
        self.assertEqual(list(series.values()), [[1], [1], [1]])

    def test_discoveries_are_paginated_in_existing_chronological_order(self):
        self.page.refresh(Analyser(many_discovery_plays()))
        self.root.update_idletasks()

        self.assertEqual(len(self.page._discoveries), 26)
        self.assertEqual(self.page._discovery_visible_count, 18)
        self.assertEqual(self.page._discovery_summary.cget("text"), "Showing 18 of 26 artists")
        first_rows = self.page._discovery_list.winfo_children()
        self.assertEqual(len(first_rows), 18)
        self.assertEqual(
            [item[0] for item in self.page._visible_discoveries[:18]],
            [item[0] for item in self.page._discoveries[:18]],
        )

        self.page._load_more_button.invoke()
        self.root.update_idletasks()
        self.assertEqual(self.page._discovery_visible_count, 26)
        self.assertEqual(len(self.page._discovery_list.winfo_children()), 26)
        self.assertEqual(self.page._discovery_summary.cget("text"), "Showing 26 of 26 artists")

    def test_year_switch_reuses_controls_and_closes_previous_figure(self):
        analyser = Analyser(many_discovery_plays())
        with patch.object(analyser, "first_heard_by_artist", wraps=analyser.first_heard_by_artist) as first_heard:
            self.page.refresh(analyser)
            menu = self.page._year_menu
            body = self.page._body
            first_heard.assert_called_once()
            self.assertEqual(len(plt.get_fignums()), 1)

            self.page._year_var.set("2022")
            self.page._on_year_changed("2022")
            self.root.update_idletasks()
            self.assertIs(self.page._year_menu, menu)
            self.assertIs(self.page._body, body)
            self.assertEqual(self.page._discovery_count, 1)
            self.assertEqual(self.page._discovery_visible_count, 1)
            self.assertEqual(len(plt.get_fignums()), 1)
            first_heard.assert_called_once()

            self.page._year_var.set("All years")
            self.page._on_year_changed("All years")
            self.root.update_idletasks()
            self.assertEqual(self.page._discovery_visible_count, 18)
            self.assertEqual(len(plt.get_fignums()), 1)

    def test_sparse_chart_only_creates_nonzero_monthly_top_artists(self):
        figure = make_grouped_bar_chart(
            ["Jan", "Feb"],
            {"A": [3, 0], "B": [2, 0], "C": [0, 4], "Unused": [0, 0]},
            sparse=True, show_legend=False, use_tight_layout=False,
        )
        try:
            self.assertEqual(sum(len(container) for container in figure.axes[0].containers), 3)
            self.assertIsNone(figure.axes[0].get_legend())
        finally:
            plt.close(figure)


if __name__ == "__main__":
    unittest.main()
