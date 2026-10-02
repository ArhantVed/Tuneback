"""Focused validation for Music Evolution's analyser inputs."""
from datetime import datetime
import unittest

from core.analyser import Analyser
from core.models import Play


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


if __name__ == "__main__":
    unittest.main()
