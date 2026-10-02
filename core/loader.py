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
import os
import sys
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

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


def load_folder(folder_path: str, skip_short: bool = True) -> list[Play]:
    """Load and merge all CSV files in a folder into a single Play list.

    Files are discovered with a case-insensitive *.csv glob. Duplicate
    plays — identical (timestamp, artist, track) tuples — are removed
    to handle the case where users accidentally include the same file
    twice or Spotify exports overlap.

    Parameters
    ----------
    folder_path : Path to the folder containing the CSV files.
    skip_short  : Passed through to load_csv for each file.

    Returns
    -------
    list[Play], deduplicated and sorted ascending by timestamp.
    """
    pattern = os.path.join(folder_path, "*.csv")
    csv_files = sorted(glob.glob(pattern))

    if not csv_files:
        print(f"  [WARNING] No CSV files found in '{folder_path}'")
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

    # Deduplicate by (timestamp, artist, track) — keep the first occurrence
    # which preserves optional-field data from extended files when present.
    seen: set[tuple] = set()
    unique_plays: list[Play] = []
    for play in all_plays:
        key = (play.timestamp, play.artist, play.track)
        if key not in seen:
            seen.add(key)
            unique_plays.append(play)

    unique_plays.sort(key=lambda p: p.timestamp)
    return unique_plays


# ---------------------------------------------------------------------------
# __main__ — quick summary for viva demonstration
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m core.loader <path-to-csv-or-folder>")
        sys.exit(1)

    target = sys.argv[1]

    if os.path.isdir(target):
        print(f"Loading all CSV files from folder: {target}")
        plays = load_folder(target)
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

    # Top 5 artists by play count
    from collections import Counter
    top = Counter(p.artist for p in plays).most_common(5)
    print("  Top 5 artists:")
    for i, (artist, count) in enumerate(top, 1):
        print(f"    {i}. {artist}  ({count:,} plays)")
    print()
