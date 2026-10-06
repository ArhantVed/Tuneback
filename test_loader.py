"""Focused synthetic tests for CSV and Spotify Extended History loading."""
import csv
import json
import tempfile
import unittest
import zipfile
from datetime import datetime
from pathlib import Path

from core.loader import load_csv, load_folder, load_json, load_zip


def audio_record(timestamp, artist="Sample Artist", track="Sample Track", ms=60_000, **extra):
    """Synthetic subset of the inspected Spotify Extended History schema."""
    return {
        "ts": timestamp,
        "master_metadata_album_artist_name": artist,
        "master_metadata_track_name": track,
        "ms_played": ms,
        **extra,
    }


class SpotifyJsonLoaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def write_json(self, name, records):
        path = self.root / name
        path.write_text(json.dumps(records), encoding="utf-8")
        return path

    def test_single_record_maps_actual_fields_and_normalizes_utc(self):
        path = self.write_json("Streaming_History_Audio_2024.json", [audio_record(
            "2024-01-02T15:04:05+03:00", "Synthetic Artist", "Synthetic Track", 90_000,
            platform="synthetic device", reason_start="trackdone",
            reason_end="endplay", skipped=False,
        )])
        plays = load_json(str(path))
        self.assertEqual(len(plays), 1)
        play = plays[0]
        self.assertEqual(play.timestamp, datetime(2024, 1, 2, 12, 4, 5))
        self.assertEqual((play.artist, play.track, play.ms_played), ("Synthetic Artist", "Synthetic Track", 90_000))
        self.assertEqual((play.platform, play.reason_start, play.reason_end, play.skipped),
                         ("synthetic device", "trackdone", "endplay", False))

    def test_missing_optional_fields_remain_none(self):
        plays = load_json(str(self.write_json("Streaming_History_Audio_2024.json", [
            audio_record("2024-02-03T10:00:00Z")
        ])))
        self.assertEqual((plays[0].platform, plays[0].reason_start, plays[0].reason_end, plays[0].skipped),
                         (None, None, None, None))

    def test_malformed_and_missing_track_records_are_skipped(self):
        path = self.write_json("Streaming_History_Audio_2024.json", [
            audio_record("not-a-timestamp"),
            audio_record("2024-01-01T00:00:00Z", artist=None),
            audio_record("2024-01-01T00:00:00Z", track=None),
            None,
            audio_record("2024-01-01T00:00:00Z", ms="bad"),
            audio_record("2024-01-01T00:00:00Z", ms=60_000),
        ])
        stats = {}
        plays = load_json(str(path), stats=stats)
        self.assertEqual(len(plays), 1)
        self.assertEqual(stats["raw_records"], 6)
        self.assertEqual(stats["skipped_malformed"], 5)
        self.assertEqual(stats["imported_records"], 1)

    def test_minimum_duration_filter_can_be_disabled(self):
        path = self.write_json("Streaming_History_Audio_2024.json", [
            audio_record("2024-01-01T00:00:00Z", ms=29_999),
            audio_record("2024-01-01T00:01:00Z", track="Long enough", ms=30_000),
        ])
        stats = {}
        plays = load_json(str(path), stats=stats)
        self.assertEqual([play.track for play in plays], ["Long enough"])
        self.assertEqual(stats["filtered_too_short"], 1)
        self.assertEqual(len(load_json(str(path), skip_short=False)), 2)

    def test_split_year_files_merge_sort_deduplicate_and_ignore_video(self):
        common = audio_record("2024-05-01T08:00:00Z", "Shared", "Same play")
        self.write_json("Streaming_History_Audio_2024.json", [
            audio_record("2024-12-01T08:00:00Z", "Later", "Later track"), common
        ])
        self.write_json("Streaming_History_Audio_2024_1.json", [
            common, audio_record("2024-01-01T08:00:00Z", "Earlier", "Earlier track")
        ])
        self.write_json("Streaming_History_Video_2024.json", [
            audio_record("2024-06-01T08:00:00Z", "Video", "Must not import")
        ])
        stats = {}
        plays = load_folder(str(self.root), stats=stats)
        self.assertEqual(len(plays), 3)
        self.assertEqual([play.timestamp for play in plays], sorted(play.timestamp for play in plays))
        self.assertNotIn("Video", {play.artist for play in plays})
        self.assertEqual(stats["audio_json_files"], 2)
        self.assertEqual(stats["raw_records"], 4)
        self.assertEqual(stats["deduplicated"], 1)
        self.assertEqual(stats["imported_records"], 3)

    def test_zip_import_streams_audio_only_and_deduplicates(self):
        archive_path = self.root / "synthetic-export.zip"
        record = audio_record("2024-03-01T08:00:00Z")
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr("Spotify/Streaming_History_Audio_2024.json", json.dumps([record]))
            archive.writestr("Spotify/Streaming_History_Audio_2024_1.json", json.dumps([record]))
            archive.writestr("Spotify/Streaming_History_Video_2024.json", json.dumps([
                audio_record("2024-03-02T08:00:00Z", "Video", "Excluded")
            ]))
            archive.writestr("Spotify/ReadMeFirst.pdf", b"synthetic")
        stats = {}
        plays = load_zip(str(archive_path), stats=stats)
        self.assertEqual(len(plays), 1)
        self.assertEqual(stats["audio_json_files"], 2)
        self.assertEqual(stats["deduplicated"], 1)
        self.assertEqual(stats["imported_records"], 1)

    def test_invalid_json_document_is_skipped(self):
        path = self.root / "Streaming_History_Audio_2024.json"
        path.write_text("[not json", encoding="utf-8")
        stats = {}
        self.assertEqual(load_json(str(path), stats=stats), [])
        self.assertEqual(stats["skipped_malformed"], 1)


class ExistingCsvLoaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_legacy_and_extended_csv_formats_still_load(self):
        legacy = self.root / "legacy.csv"
        with legacy.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["endTime", "artistName", "trackName", "msPlayed"])
            writer.writerow(["2021-03-14 08:00", "Old Format Artist", "Old Format Track", 45_000])
        extended = self.root / "extended.csv"
        with extended.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["ts", "master_metadata_track_artist_name", "master_metadata_track_name", "ms_played", "platform", "reason_start", "reason_end", "skipped"])
            writer.writerow(["2022-04-05T09:00:00Z", "CSV Artist", "CSV Track", 50_000, "device", "playbtn", "endplay", "True"])
        self.assertEqual(load_csv(str(legacy))[0].artist, "Old Format Artist")
        extended_play = load_csv(str(extended))[0]
        self.assertEqual((extended_play.artist, extended_play.track, extended_play.skipped),
                         ("CSV Artist", "CSV Track", True))


if __name__ == "__main__":
    unittest.main(verbosity=2)
