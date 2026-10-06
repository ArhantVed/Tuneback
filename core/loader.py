"""
core/loader.py — Tuneback CSV ingestion.

Loads Spotify listening-history CSV exports and normalises them into
a flat list of Play objects. Supports two export formats:

  Legacy   — StreamingHistory*.csv produced by older Spotify exports.
             Columns: endTime, artistName, trackName, msPlayed

  Extended — Streaming_History_Audio_*.csv from the newer extended
             streaming history request.
             Columns: ts, master_metadata_track_artist_name,
                      master_metadata_track_name, ms_played
             Plus optional: platform, reason_start, reason_end, skipped

Format detection is automatic based on the header row.

Public API
----------
    load_csv(path, skip_short=True)       -> list[Play]
    load_folder(folder_path, skip_short)  -> list[Play]

Run directly for a quick summary (useful for viva demos):
    python -m core.loader <path-to-csv-or-folder>
"""

from __future__ import annotations

import csv
import glob
import json
import os
import sys
import zipfile
from datetime import datetime, timezone

from core.models import Play

# ---------------------------------------------------------------------------
# Column name constants — the single source of truth for format detection
# ---------------------------------------------------------------------------

# All four must be present for a file to be recognised as legacy format.
_LEGACY_REQUIRED = {"endTime", "artistName", "trackName", "msPlayed"}

# All four must be present for a file to be recognised as extended format.
_EXTENDED_REQUIRED = {
    "ts",
    "master_metadata_track_artist_name",
    "master_metadata_track_name",
    "ms_played",
}

# Optional columns in the extended format — missing columns default gracefully.
_EXTENDED_OPTIONAL = {"platform", "reason_start", "reason_end", "skipped"}

# Minimum milliseconds to keep a row when skip_short=True.
# 30 seconds filters out accidental taps and very short skips.
_MIN_MS = 30_000

_JSON_STATS_DEFAULTS = {
    "audio_json_files": 0,
    "raw_records": 0,
    "valid_records": 0,
    "filtered_too_short": 0,
    "skipped_malformed": 0,
    "deduplicated": 0,
    "imported_records": 0,
}


def _prepare_json_stats(stats: dict | None) -> dict:
    """Initialize optional caller-owned aggregate counters."""
    target = stats if stats is not None else {}
    for name, value in _JSON_STATS_DEFAULTS.items():
        target.setdefault(name, value)
    return target


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

def _detect_format(headers: list[str]) -> str:
    """Detect the Spotify CSV format from the header row.

    Parameters
    ----------
    headers : Column names read from the first row of the CSV file.

    Returns
    -------
    "legacy" or "extended"

    Raises
    ------
    ValueError
        If the headers do not match either recognised format. The error
        message lists both expected column sets so the user can diagnose
        a malformed file.
    """
    header_set = set(headers)

    if _LEGACY_REQUIRED.issubset(header_set):
        return "legacy"

    if _EXTENDED_REQUIRED.issubset(header_set):
        return "extended"

    raise ValueError(
        f"Unrecognised CSV format.\n"
        f"  Headers found   : {sorted(header_set)}\n"
        f"  Legacy requires : {sorted(_LEGACY_REQUIRED)}\n"
        f"  Extended requires: {sorted(_EXTENDED_REQUIRED)}"
    )


# ---------------------------------------------------------------------------
# Timestamp parsers
# ---------------------------------------------------------------------------

def _parse_legacy_timestamp(raw: str) -> datetime:
    """Parse the legacy endTime field: '2021-03-14 08:00'."""
    # Legacy timestamps have no timezone info — treat as naive UTC.
    return datetime.strptime(raw.strip(), "%Y-%m-%d %H:%M")


def _parse_extended_timestamp(raw: str) -> datetime:
    """Parse the extended ts field: ISO 8601 with optional timezone offset.

    Examples handled:
        '2021-03-14T08:00:00Z'
        '2021-03-14T08:00:00+00:00'
        '2021-03-14T08:00:00.000Z'

    The returned datetime is always timezone-naive UTC for consistency
    with legacy timestamps — timezone info is stripped after conversion.
    """
    raw = raw.strip()

    # Replace trailing 'Z' with '+00:00' so fromisoformat handles it on
    # Python 3.10 (fromisoformat gained full ISO 8601 support in 3.11).
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"

    # Remove sub-second precision if present (e.g. ".000") before the offset.
    # Pattern: digits, then '.', then digits, then '+' or end
    dot_pos = raw.find(".")
    if dot_pos != -1:
        # Find where the fractional seconds end ('+' or end of string)
        plus_pos = raw.find("+", dot_pos)
        if plus_pos != -1:
            raw = raw[:dot_pos] + raw[plus_pos:]
        else:
            raw = raw[:dot_pos]

    dt = datetime.fromisoformat(raw)
    # Strip timezone to produce a naive UTC datetime, matching legacy format.
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


# ---------------------------------------------------------------------------
# Row parsers
# ---------------------------------------------------------------------------

def _parse_legacy_row(row: dict) -> Play:
    """Map one legacy CSV row to a Play.

    All optional fields (platform, reason_start, reason_end, skipped)
    are set to None / False because the legacy format does not provide them.
    """
    return Play(
        timestamp=_parse_legacy_timestamp(row["endTime"]),
        artist=row["artistName"].strip(),
        track=row["trackName"].strip(),
        ms_played=int(row["msPlayed"]),
        # Optional fields — not available in legacy format
        platform=None,
        reason_start=None,
        reason_end=None,
        skipped=None,
    )


def _parse_extended_row(row: dict) -> Play:
    """Map one extended CSV row to a Play.

    Uses row.get() for every optional column so a file that is missing
    one of the optional columns does not raise a KeyError.

    The 'skipped' column is stored as the string 'True'/'False' in the
    CSV — it is converted to a Python bool explicitly.
    """
    # Parse the optional skipped field safely
    raw_skipped = row.get("skipped")
    if raw_skipped is None or raw_skipped == "":
        skipped = None
    else:
        skipped = raw_skipped.strip().lower() == "true"

    # Read other optional string fields, normalising empty strings to None
    def _opt(col: str) -> str | None:
        val = row.get(col, "")
        return val.strip() if val and val.strip() else None

    return Play(
        timestamp=_parse_extended_timestamp(row["ts"]),
        artist=row["master_metadata_track_artist_name"].strip(),
        track=row["master_metadata_track_name"].strip(),
        ms_played=int(row["ms_played"]),
        platform=_opt("platform"),
        reason_start=_opt("reason_start"),
        reason_end=_opt("reason_end"),
        skipped=skipped,
    )


def _parse_spotify_json_record(row: dict) -> Play:
    """Map one Extended Streaming History audio JSON record into Play.

    The field names here match the inspected export schema. Podcast,
    audiobook, and other non-track rows commonly have no track artist/name
    and are rejected because Tuneback's canonical Play represents music.
    """
    if not isinstance(row, dict):
        raise ValueError("record is not an object")

    timestamp = row.get("ts")
    artist = row.get("master_metadata_album_artist_name")
    track = row.get("master_metadata_track_name")
    raw_ms = row.get("ms_played")
    if not isinstance(timestamp, str) or not timestamp.strip():
        raise ValueError("missing timestamp")
    if not isinstance(artist, str) or not artist.strip():
        raise ValueError("missing track artist")
    if not isinstance(track, str) or not track.strip():
        raise ValueError("missing track name")
    if isinstance(raw_ms, bool) or not isinstance(raw_ms, (int, str)):
        raise ValueError("missing played duration")
    try:
        ms_played = int(raw_ms.strip() if isinstance(raw_ms, str) else raw_ms)
    except ValueError as exc:
        raise ValueError("played duration is not an integer") from exc
    if ms_played < 0:
        raise ValueError("played duration is negative")

    def optional_text(field: str) -> str | None:
        value = row.get(field)
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(f"optional field {field} is not text")
        value = value.strip()
        return value or None

    raw_skipped = row.get("skipped")
    if raw_skipped is None:
        skipped = None
    elif isinstance(raw_skipped, bool):
        skipped = raw_skipped
    elif isinstance(raw_skipped, str) and raw_skipped.lower() in {"true", "false"}:
        skipped = raw_skipped.lower() == "true"
    else:
        raise ValueError("optional field skipped is not a boolean")

    return Play(
        timestamp=_parse_extended_timestamp(timestamp),
        artist=artist.strip(),
        track=track.strip(),
        ms_played=ms_played,
        platform=optional_text("platform"),
        reason_start=optional_text("reason_start"),
        reason_end=optional_text("reason_end"),
        skipped=skipped,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _load_spotify_json_stream(stream, source_name: str, skip_short: bool,
                              stats: dict) -> list[Play]:
    """Read one Spotify JSON document while updating aggregate diagnostics."""
    try:
        payload = json.load(stream)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        stats["skipped_malformed"] += 1
        print(f"  [WARNING] Skipping malformed Spotify JSON file '{source_name}': {exc}")
        return []

    if not isinstance(payload, list):
        stats["skipped_malformed"] += 1
        print(f"  [WARNING] Spotify JSON file '{source_name}' does not contain a record list")
        return []

    plays: list[Play] = []
    for row in payload:
        stats["raw_records"] += 1
        try:
            play = _parse_spotify_json_record(row)
        except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
            stats["skipped_malformed"] += 1
            continue

        stats["valid_records"] += 1
        if skip_short and play.ms_played < _MIN_MS:
            stats["filtered_too_short"] += 1
            continue
        plays.append(play)
    return plays


def _deduplicate(plays: list[Play], stats: dict | None = None) -> list[Play]:
    """Apply the loader's established (timestamp, artist, track) key."""
    seen: set[tuple] = set()
    result: list[Play] = []
    for play in plays:
        key = (play.timestamp, play.artist, play.track)
        if key in seen:
            if stats is not None:
                stats["deduplicated"] += 1
            continue
        seen.add(key)
        result.append(play)
    result.sort(key=lambda item: item.timestamp)
    return result


def _is_spotify_audio_json(name: str) -> bool:
    """Recognize Spotify audio export members/files and reject video history."""
    base = os.path.basename(name).lower()
    return (
        base.startswith("streaming_history_audio")
        and base.endswith(".json")
        and "streaming_history_video" not in base
    )


def load_json(path: str, skip_short: bool = True,
              stats: dict | None = None) -> list[Play]:
    """Load one Spotify Extended Streaming History audio JSON file.

    ``stats`` may be a caller-owned dict. When provided it receives counts
    for encountered, valid, filtered, malformed, deduplicated, and imported
    JSON records. JSON record values are never included in warnings.
    """
    diagnostics = _prepare_json_stats(stats)
    if "streaming_history_video" in os.path.basename(path).lower():
        print("  [WARNING] Video history is not imported as music")
        return []
    diagnostics["audio_json_files"] += 1
    try:
        with open(path, "r", encoding="utf-8-sig") as stream:
            plays = _load_spotify_json_stream(
                stream, os.path.basename(path), skip_short, diagnostics
            )
    except OSError:
        raise
    result = _deduplicate(plays, diagnostics)
    diagnostics["imported_records"] += len(result)
    return result


def load_zip(path: str, skip_short: bool = True,
             stats: dict | None = None) -> list[Play]:
    """Load audio JSON members directly from a Spotify export ZIP.

    Files are streamed from the archive; nothing is extracted to disk.
    Video JSON members and PDFs are ignored.
    """
    diagnostics = _prepare_json_stats(stats)
    all_plays: list[Play] = []
    try:
        with zipfile.ZipFile(path) as archive:
            names = [
                name for name in archive.namelist()
                if not name.endswith("/") and _is_spotify_audio_json(name)
            ]
            diagnostics["audio_json_files"] += len(names)
            for name in sorted(names):
                try:
                    with archive.open(name) as stream:
                        all_plays.extend(_load_spotify_json_stream(
                            stream, os.path.basename(name), skip_short, diagnostics
                        ))
                except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
                    diagnostics["skipped_malformed"] += 1
                    print(f"  [WARNING] Skipping unreadable Spotify JSON member '{os.path.basename(name)}': {exc}")
    except zipfile.BadZipFile as exc:
        raise ValueError(f"Cannot load '{path}': not a valid ZIP archive") from exc

    result = _deduplicate(all_plays, diagnostics)
    diagnostics["imported_records"] += len(result)
    if not diagnostics["audio_json_files"]:
        print("  [WARNING] No Spotify audio history JSON files found in ZIP")
    return result

def load_csv(path: str, skip_short: bool = True) -> list[Play]:
    """Load a single Spotify CSV export file and return a list of Play objects.

    Parameters
    ----------
    path       : Absolute or relative path to the CSV file.
    skip_short : If True (default), rows with ms_played < 30 000 are
                 discarded. Set to False to keep all rows including
                 accidental taps and very short skips.

    Returns
    -------
    list[Play], sorted ascending by timestamp.

    Rows that cannot be parsed (bad timestamps, missing required fields,
    non-integer ms_played) are skipped with a warning printed to stdout.
    """
    plays: list[Play] = []

    # Open with UTF-8-sig to transparently strip the BOM that Spotify
    # sometimes writes at the start of its CSV files.
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)

        # DictReader.fieldnames triggers reading the header row.
        headers = list(reader.fieldnames or [])
        try:
            fmt = _detect_format(headers)
        except ValueError as exc:
            raise ValueError(f"Cannot load '{path}': {exc}") from exc

        parse_fn = _parse_legacy_row if fmt == "legacy" else _parse_extended_row

        for line_num, row in enumerate(reader, start=2):  # start=2: row 1 is the header
            try:
                play = parse_fn(row)
            except (KeyError, ValueError, AttributeError) as exc:
                print(f"  [WARNING] Skipping row {line_num} in '{os.path.basename(path)}': {exc}")
                continue

            # Discard very short plays when filtering is enabled
            if skip_short and play.ms_played < _MIN_MS:
                continue

            plays.append(play)

    # Return plays sorted by timestamp (oldest first)
    plays.sort(key=lambda p: p.timestamp)
    return plays


def load_folder(folder_path: str, skip_short: bool = True,
                stats: dict | None = None) -> list[Play]:
    """Load and merge CSV and Spotify audio JSON files in a folder.

    JSON files are limited to Spotify ``Streaming_History_Audio*.json``;
    video history is ignored. Duplicate plays — identical (timestamp,
    artist, track) tuples — are removed across supported files.

    Parameters
    ----------
    folder_path : Path containing CSVs and/or Spotify audio JSON files.
    skip_short  : Passed through to each file loader.
    stats       : Optional caller-owned aggregate diagnostics for JSON files.

    Returns
    -------
    list[Play], deduplicated and sorted ascending by timestamp.
    """
    diagnostics = _prepare_json_stats(stats)
    csv_files = sorted(glob.glob(os.path.join(folder_path, "*.csv")))
    json_files = sorted(
        path for path in glob.glob(os.path.join(folder_path, "*.json"))
        if _is_spotify_audio_json(path)
    )

    if not csv_files and not json_files:
        print(f"  [WARNING] No supported CSV or Spotify audio JSON files found in '{folder_path}'")
        return []

    all_plays: list[Play] = []
    for csv_path in csv_files:
        try:
            batch = load_csv(csv_path, skip_short=skip_short)
            print(f"  Loaded {len(batch):>5} plays from '{os.path.basename(csv_path)}'")
            all_plays.extend(batch)
        except ValueError as exc:
            print(f"  [WARNING] Skipping '{os.path.basename(csv_path)}': {exc}")
            continue

    for json_path in json_files:
        try:
            batch = load_json(json_path, skip_short=skip_short, stats=diagnostics)
            print(f"  Loaded {len(batch):>5} plays from Spotify audio JSON")
            all_plays.extend(batch)
        except (OSError, ValueError) as exc:
            diagnostics["skipped_malformed"] += 1
            print(f"  [WARNING] Skipping unreadable Spotify JSON file '{os.path.basename(json_path)}': {exc}")

    unique_plays = _deduplicate(all_plays, diagnostics)
    diagnostics["imported_records"] = len(unique_plays)
    return unique_plays


# ---------------------------------------------------------------------------
# __main__ — quick summary for viva demonstration
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m core.loader <path-to-csv-json-zip-or-folder>")
        sys.exit(1)

    target = sys.argv[1]

    if os.path.isdir(target):
        print(f"Loading supported history files from folder: {target}")
        plays = load_folder(target)
    elif target.lower().endswith(".zip"):
        print("Loading Spotify audio JSON history from ZIP")
        plays = load_zip(target)
    elif target.lower().endswith(".json"):
        print("Loading Spotify audio JSON history")
        plays = load_json(target)
    else:
        print(f"Loading CSV file: {target}")
        plays = load_csv(target)

    if not plays:
        print("No plays loaded.")
        sys.exit(0)

    # Summary statistics
    total_ms = sum(p.ms_played for p in plays)
    total_hours = total_ms / 3_600_000
    artists = {p.artist for p in plays}
    tracks = {p.track for p in plays}

    print()
    print("=" * 40)
    print("  Tuneback — Loaded Data Summary")
    print("=" * 40)
    print(f"  Total plays    : {len(plays):,}")
    print(f"  Unique artists : {len(artists):,}")
    print(f"  Unique tracks  : {len(tracks):,}")
    print(f"  Listening time : {total_hours:.1f} hours  ({total_ms / 86_400_000:.1f} days)")
    print(f"  Date range     : {plays[0].timestamp:%Y-%m-%d}  →  {plays[-1].timestamp:%Y-%m-%d}")
    print()

    # Keep ZIP based validation summaries aggregate-only so personal names
    # are not printed when checking a real Spotify export.
    if not target.lower().endswith(".zip"):
        from collections import Counter
        top = Counter(p.artist for p in plays).most_common(5)
        print("  Top 5 artists:")
        for i, (artist, count) in enumerate(top, 1):
            print(f"    {i}. {artist}  ({count:,} plays)")
        print()
