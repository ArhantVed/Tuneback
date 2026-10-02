"""Focused validation for obsession analysis and page refresh behavior."""
from datetime import datetime
import unittest

from core.analyser import Analyser
from core.models import Play

try:
    import customtkinter
    import matplotlib.pyplot as plt
    from ui.pages.obsessions import ObsessionsPage
    UI_IMPORT_ERROR = None
except ImportError as exc:  # Keep analyzer checks runnable without the UI extras.
    customtkinter = None
    plt = None
    ObsessionsPage = None
    UI_IMPORT_ERROR = exc


def obsession_plays():
    """Two consecutive dominant months, including a late final-day play."""
    return [
        Play(datetime(2022, 1, 5), "Echo", "One", 60_000),
        Play(datetime(2022, 1, 10), "Echo", "Two", 60_000),
        Play(datetime(2022, 1, 20), "Echo", "Three", 60_000),
        Play(datetime(2022, 1, 31, 23, 59), "Echo", "Four", 60_000),
        Play(datetime(2022, 1, 15), "Other", "Support", 60_000),
        Play(datetime(2022, 2, 1), "Echo", "One", 60_000),
        Play(datetime(2022, 2, 10), "Echo", "Two", 60_000),
        Play(datetime(2022, 2, 20), "Echo", "Three", 60_000),
        Play(datetime(2022, 2, 28, 23, 59), "Echo", "Four", 60_000),
        Play(datetime(2022, 2, 11), "Other", "Support", 60_000),
    ]


class ObsessionAnalyserTests(unittest.TestCase):
    def test_no_data_and_single_play_have_no_obsessions(self):
        self.assertEqual(Analyser([]).obsession_periods(), [])
        single = Analyser([Play(datetime(2022, 1, 1), "Solo", "Only", 10_000)])
        self.assertEqual(single.obsession_periods(), [])

    def test_dominant_consecutive_months_produce_full_period(self):
        analyser = Analyser(obsession_plays())
        periods = analyser.obsession_periods(threshold_pct=75)

        self.assertEqual(len(periods), 1)
        period = periods[0]
        self.assertEqual(period.artist, "Echo")
        self.assertEqual(period.start_date, datetime(2022, 1, 1))
        self.assertEqual(period.end_date, datetime(2022, 2, 28))
        self.assertEqual(period.peak_pct, 80.0)
        self.assertEqual(period.total_plays, 8)
        self.assertEqual(analyser.obsession_periods(threshold_pct=85), [])

    def test_month_gap_does_not_count_as_consecutive(self):
        analyser = Analyser([
            Play(datetime(2022, 1, 2), "Echo", "A", 10_000),
            Play(datetime(2022, 1, 3), "Echo", "B", 10_000),
            Play(datetime(2022, 3, 2), "Echo", "A", 10_000),
            Play(datetime(2022, 3, 3), "Echo", "B", 10_000),
        ])
        self.assertEqual(analyser.obsession_periods(threshold_pct=50), [])

    def test_daily_artist_counts_are_scoped_and_fill_zero_days(self):
        analyser = Analyser(obsession_plays())
        daily = analyser.artist_plays_over_time(
            "Echo", granularity="day",
            period=(datetime(2022, 1, 5), datetime(2022, 1, 9)),
        )
        self.assertEqual(daily, {
            "2022-01-05": 1,
            "2022-01-06": 0,
            "2022-01-07": 0,
            "2022-01-08": 0,
        })


@unittest.skipUnless(UI_IMPORT_ERROR is None, f"UI dependencies unavailable: {UI_IMPORT_ERROR}")
class ObsessionPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = customtkinter.CTk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def setUp(self):
        self.page = ObsessionsPage(self.root)
        self.page.pack(fill="both", expand=True)
        self.root.update_idletasks()

    def tearDown(self):
        self.page.destroy()
        plt.close("all")
        self.root.update_idletasks()

    @staticmethod
    def _texts(widget):
        found = []
        for child in widget.winfo_children():
            if isinstance(child, (customtkinter.CTkLabel, customtkinter.CTkButton)):
                found.append(str(child.cget("text")))
            found.extend(ObsessionPageTests._texts(child))
        return found

    @staticmethod
    def _widget_count(widget):
        children = widget.winfo_children()
        return len(children) + sum(ObsessionPageTests._widget_count(child) for child in children)

    def test_page_import_and_no_data_placeholder(self):
        self.assertIsNotNone(ObsessionsPage)
        self.page.refresh(None)
        self.root.update_idletasks()
        self.assertTrue(any("Load your Spotify data" in text for text in self._texts(self.page)))

    def test_normal_data_renders_period_and_daily_chart(self):
        self.page.refresh(Analyser(obsession_plays()))
        self.root.update_idletasks()
        self.assertEqual(len(self.page._periods), 1)
        self.assertTrue(any("Echo" in text and "80.0%" in text for text in self._texts(self.page)))
        line = self.page._detail_figure.axes[0].lines[0]
        self.assertEqual(len(line.get_xdata()), 59)

    def test_single_play_shows_empty_detection_state(self):
        self.page.refresh(Analyser([Play(datetime(2022, 1, 1), "Solo", "Only", 10_000)]))
        self.root.update_idletasks()
        self.assertEqual(self.page._periods, [])
        self.assertTrue(any("No obsession periods found" in text for text in self._texts(self.page)))

    def test_sensitivity_slider_reruns_detection(self):
        self.page.refresh(Analyser(obsession_plays()))
        self.page._on_threshold_changed(85)
        self.assertEqual(self.page._periods, [])
        self.page._on_threshold_changed(75)
        self.assertEqual(len(self.page._periods), 1)
        self.assertEqual(self.page._threshold_label.cget("text"), "75%")

    def test_repeated_refresh_does_not_leak_widgets_or_figures(self):
        analyser = Analyser(obsession_plays())
        counts = []
        figures = []
        for _ in range(3):
            self.page.refresh(analyser)
            self.root.update_idletasks()
            counts.append(self._widget_count(self.page))
            figures.append(len(plt.get_fignums()))
            self.page.refresh(None)
            self.root.update_idletasks()
            self.assertEqual(len(plt.get_fignums()), 0)
        self.assertEqual(counts, [counts[0]] * 3)
        self.assertEqual(figures, [1, 1, 1])


if __name__ == "__main__":
    unittest.main(verbosity=2)
