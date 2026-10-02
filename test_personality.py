"""Focused checks for personality metrics consumed by the UI page."""
from datetime import datetime
import unittest

from core.analyser import Analyser
from core.models import Play


class PersonalityAnalyserTests(unittest.TestCase):
    def test_profile_includes_supporting_listening_statistics(self):
        analyser = Analyser([
            Play(datetime(2022, 3, 7, 9), "Artist A", "Track 1", 60_000, skipped=False),
            Play(datetime(2022, 3, 12, 22), "Artist A", "Track 1", 60_000, skipped=True),
            Play(datetime(2022, 3, 13, 14), "Artist B", "Track 2", 60_000, skipped=False),
            Play(datetime(2022, 3, 14, 22), "Artist A", "Track 1", 60_000, skipped=True),
        ])
        profile = analyser.personality_profile()

        self.assertEqual(profile.archetype, "Night Owl")
        self.assertEqual(profile.key_stats["peak_hour"], 22)
        self.assertEqual(profile.key_stats["peak_weekday"], 0)
        self.assertEqual(profile.key_stats["weekend_pct"], 50.0)
        self.assertEqual(profile.key_stats["skip_rate"], 50.0)
        self.assertEqual(profile.key_stats["active_days"], 4)
        self.assertEqual(profile.key_stats["average_daily_ms"], 60_000)
        self.assertEqual(profile.dimension_scores["weekend_score"], 50)
        self.assertEqual(profile.dimension_scores["skip_score"], 50)

    def test_skip_metrics_are_marked_unavailable_for_legacy_data(self):
        profile = Analyser([
            Play(datetime(2022, 1, 1, 10), "Artist", "Track", 30_000),
        ]).personality_profile()

        self.assertIsNone(profile.key_stats["skip_rate"])
        self.assertNotIn("skip_score", profile.dimension_scores)

    def test_empty_history_has_unknown_profile(self):
        profile = Analyser([]).personality_profile()

        self.assertEqual(profile.archetype, "Unknown")
        self.assertEqual(profile.dimension_scores, {})
        self.assertEqual(Analyser([]).average_daily_listening_time_ms(), 0)


if __name__ == "__main__":
    unittest.main()
