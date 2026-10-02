"""Focused checks for the data methods used by the Statistics page."""
from datetime import datetime
import unittest

from core.analyser import Analyser
from core.models import Play


class StatisticsAnalyserTests(unittest.TestCase):
    def test_track_dates_and_timeline(self):
        analyser = Analyser([
            Play(datetime(2022, 1, 2), "Artist", "Song", 60_000),
            Play(datetime(2022, 2, 3), "Artist", "Song", 120_000),
            Play(datetime(2022, 2, 4), "Artist", "Other Song", 30_000),
        ])

        self.assertEqual(analyser.first_heard("Artist"), datetime(2022, 1, 2))
        self.assertEqual(analyser.last_heard("Artist"), datetime(2022, 2, 4))
        self.assertEqual(analyser.first_heard_for_track("Song", "Artist"), datetime(2022, 1, 2))
        self.assertEqual(analyser.last_heard_for_track("Song", "Artist"), datetime(2022, 2, 3))
        self.assertIsNone(analyser.first_heard_for_track("Missing", "Artist"))
        self.assertEqual(analyser.track_plays_over_time("Song", "Artist"), {
            "2022-01": 1, "2022-02": 1,
        })
        self.assertEqual(analyser.track_plays_over_time("Missing", "Artist"), {})

    def test_rankings_and_monthly_totals(self):
        analyser = Analyser([
            Play(datetime(2022, 1, 2), "Artist", "Song", 60_000),
            Play(datetime(2022, 1, 3), "Artist", "Song", 120_000),
            Play(datetime(2022, 2, 4), "Other", "Tune", 30_000),
        ])

        self.assertEqual(analyser.top_artists(50)[0], ("Artist", 2, 180_000))
        self.assertEqual(analyser.top_tracks(50)[0], ("Song", "Artist", 2, 180_000))
        self.assertEqual(analyser.listening_by_month(), {
            "2022-01": 180_000, "2022-02": 30_000,
        })


if __name__ == "__main__":
    unittest.main()
