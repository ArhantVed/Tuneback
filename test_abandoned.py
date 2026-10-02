"""Focused validation for Abandoned artist analysis and page behavior."""
from datetime import datetime, timedelta
import unittest
from unittest.mock import patch

from core.analyser import Analyser
from core.models import Play

try:
    import customtkinter
    import matplotlib.pyplot as plt
    from ui.pages.abandoned import AbandonedPage
    UI_IMPORT_ERROR = None
except ImportError as exc:  # Keep analyzer checks runnable without optional UI packages.
    customtkinter = None
    plt = None
    AbandonedPage = None
    UI_IMPORT_ERROR = exc


def abandoned_plays():
    latest = datetime(2024, 1, 1, 12)
    plays = [
        Play(datetime(2022, 1, day), "Old A", f"Track {day}", 60_000)
        for day in range(1, 13)
    ]
    plays.extend(
        Play(datetime(2022, 2, day), "Old B", f"Song {day}", 60_000)
        for day in range(1, 11)
    )
    plays.extend(
        Play(latest - timedelta(days=200 - index), "Quiet 200", f"Track {index}", 60_000)
        for index in range(10)
    )
    plays.append(Play(latest, "Recently Played", "Now", 60_000))
    return plays


class AbandonedAnalyserTests(unittest.TestCase):
    def test_no_data_and_minimal_history(self):
        self.assertEqual(Analyser([]).abandoned_artists(), [])
        one_play = Analyser([Play(datetime(2024, 1, 1), "Solo", "Only", 10_000)])
        self.assertEqual(one_play.abandoned_artists(), [])

    def test_abandoned_artists_are_ranked_and_include_silence_age(self):
        results = Analyser(abandoned_plays()).abandoned_artists(
            min_plays=10, silence_days=180,
        )
        self.assertEqual([item.artist for item in results], ["Old A", "Old B", "Quiet 200"])
        self.assertEqual(results[0].total_plays, 12)
        self.assertEqual(results[0].last_played, datetime(2022, 1, 12))
        self.assertEqual(
            results[0].days_since_last_play,
            (datetime(2024, 1, 1, 12) - datetime(2022, 1, 12)).days,
        )
        self.assertEqual(results[0].peak_month, "2022-01")

    def test_silence_threshold_and_play_count_edges(self):
        analyser = Analyser(abandoned_plays())
        self.assertEqual(len(analyser.abandoned_artists(silence_days=180)), 3)
        self.assertEqual(len(analyser.abandoned_artists(silence_days=365)), 2)
        self.assertEqual(analyser.abandoned_artists(min_plays=13, silence_days=180), [])
        self.assertEqual(analyser.abandoned_artists(min_plays=0, silence_days=0)[0].artist,
                         "Old A")


@unittest.skipUnless(UI_IMPORT_ERROR is None, f"UI dependencies unavailable: {UI_IMPORT_ERROR}")
class AbandonedPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = customtkinter.CTk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def setUp(self):
        self.page = AbandonedPage(self.root)
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
            found.extend(AbandonedPageTests._texts(child))
        return found

    @staticmethod
    def _widget_count(widget):
        children = widget.winfo_children()
        return len(children) + sum(AbandonedPageTests._widget_count(child) for child in children)

    def test_page_import_and_no_data_state(self):
        self.assertIsNotNone(AbandonedPage)
        self.page.refresh(None)
        self.root.update_idletasks()
        self.assertTrue(any("Load your Spotify data" in text for text in self._texts(self.page)))

    def test_artist_cards_show_sorted_abandoned_results(self):
        self.page.refresh(Analyser(abandoned_plays()))
        self.root.update_idletasks()
        self.assertEqual([artist.artist for artist in self.page._artists],
                         ["Old A", "Old B", "Quiet 200"])
        texts = self._texts(self.page)
        self.assertTrue(any("Old A" in text for text in texts))
        self.assertTrue(any("Quiet for" in text for text in texts))

    def test_single_play_shows_no_matching_artist_state(self):
        self.page.refresh(Analyser([Play(datetime(2024, 1, 1), "Solo", "Only", 10_000)]))
        self.root.update_idletasks()
        self.assertEqual(self.page._artists, [])
        self.assertTrue(any("No artists have at least 10 plays" in text
                            for text in self._texts(self.page)))

    def test_silence_slider_refreshes_results(self):
        self.page.refresh(Analyser(abandoned_plays()))
        self.assertEqual(len(self.page._artists), 3)
        self.page._on_threshold_changed(365)
        self.assertEqual(len(self.page._artists), 2)
        self.assertEqual(self.page._silence_label.cget("text"), "365 days")

    def test_artist_history_opens_monthly_popout(self):
        self.page.refresh(Analyser(abandoned_plays()))
        with patch("ui.pages.abandoned.popup_figure") as popup:
            self.page._open_artist_history(self.page._artists[0])
        figure, title = popup.call_args.args
        self.assertEqual(title, "Old A listening history")
        self.assertEqual(figure.axes[0].get_ylabel(), "Plays")
        plt.close(figure)

    def test_repeated_refresh_does_not_leak_widgets(self):
        analyser = Analyser(abandoned_plays())
        counts = []
        for _ in range(3):
            self.page.refresh(analyser)
            self.root.update_idletasks()
            counts.append(self._widget_count(self.page))
            self.page.refresh(None)
            self.root.update_idletasks()
            self.assertEqual(plt.get_fignums(), [])
        self.assertEqual(counts, [counts[0]] * 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
