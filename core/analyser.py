"""
core/analyser.py — Tuneback analytical engine.

The Analyser class accepts a list of Play objects and exposes named
methods that return plain Python structures (lists, dicts, dataclasses).
No file I/O, no GUI code, no Pandas — pure Python computation.

Key Python concepts demonstrated
---------------------------------
  collections.defaultdict  — grouping plays by artist / track / month
  collections.Counter      — frequency counting
  list comprehensions      — filtering and transforming play lists
  sorted() with key=       — ranking by arbitrary metrics
  datetime / timedelta     — period filtering and window arithmetic
  set operations           — diff comparisons between periods
  rule-based classification — personality archetype detection

Usage
-----
    from core.analyser import Analyser
    analyser = Analyser(plays)
    print(analyser.top_artists(5))
"""

from __future__ import annotations

import calendar
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Optional

from core.models import (
    AbandonedArtist,
    ComparisonResult,
    ObsessionPeriod,
    PersonalityProfile,
    PeriodStats,
    Play,
    WrappedSummary,
)

# ---------------------------------------------------------------------------
# Type aliases for readability
# ---------------------------------------------------------------------------
_Period = Optional[tuple[datetime, datetime]]   # (start, end) or None = all time


class Analyser:
    """Computes listening statistics from a list of Play records.

    All public methods are pure — they read self._plays and return new
    data structures without modifying any state.  This makes every method
    independently testable from the REPL.

    Parameters
    ----------
    plays : list[Play]
        Normalised play records, typically produced by core.loader.
        An empty list is valid; methods return sensible empty results.
    """

    def __init__(self, plays: list[Play]) -> None:
        # Store sorted ascending by timestamp — most methods depend on order.
        self._plays: list[Play] = sorted(plays, key=lambda p: p.timestamp)

        # ----------------------------------------------------------------
        # Pre-computed indexes — built once, reused by many methods.
        # Using defaultdict(list) so we can do index[key].append() safely.
        # ----------------------------------------------------------------

        # artist name  ->  list[Play]
        self._by_artist: defaultdict[str, list[Play]] = defaultdict(list)
        # (track, artist) -> list[Play]
        self._by_track: defaultdict[tuple[str, str], list[Play]] = defaultdict(list)
        # "YYYY-MM"  ->  list[Play]
        self._by_month: defaultdict[str, list[Play]] = defaultdict(list)
        # year int   ->  list[Play]
        self._by_year: defaultdict[int, list[Play]] = defaultdict(list)
        # Cached query results built from the sorted play/index data.
        self._first_heard_by_artist: dict[str, datetime] = {}
        self._music_evolution_counts_cache: dict[tuple[str, int], dict[str, dict[str, int]]] = {}

        for play in self._plays:
            self._by_artist[play.artist].append(play)
            self._first_heard_by_artist.setdefault(play.artist, play.timestamp)
            self._by_track[(play.track, play.artist)].append(play)
            month_key = f"{play.timestamp.year:04d}-{play.timestamp.month:02d}"
            self._by_month[month_key].append(play)
            self._by_year[play.timestamp.year].append(play)

    # ====================================================================
    # Internal helpers
    # ====================================================================

    def _filter(self, period: _Period = None) -> list[Play]:
        """Return plays that fall within [start, end).

        If period is None, return all plays unchanged.
        This is the central filtering primitive — all period-aware methods
        call this first.
        """
        if period is None:
            return self._plays
        start, end = period
        # List comprehension: keep plays whose timestamp is in [start, end)
        return [p for p in self._plays if start <= p.timestamp < end]

    def _group_by(self, plays: list[Play], key_fn) -> defaultdict:
        """Group a list of plays by an arbitrary key function.

        Returns a defaultdict(list) mapping key -> [Play, ...].

        Example
        -------
            monthly = self._group_by(plays, lambda p: p.timestamp.month)
        """
        groups: defaultdict = defaultdict(list)
        for play in plays:
            groups[key_fn(play)].append(play)
        return groups

    def _period_stats(self, plays: list[Play], label: str) -> PeriodStats:
        """Compute a PeriodStats summary for an arbitrary play list."""
        if not plays:
            return PeriodStats(
                label=label, total_plays=0, total_ms=0,
                unique_artists=0, unique_tracks=0,
                top_artist="—", top_track="—", top_artists=[],
                active_days=0, average_daily_ms=0,
            )
        artist_counts = Counter(p.artist for p in plays)
        track_counts  = Counter((p.track, p.artist) for p in plays)
        top_art  = artist_counts.most_common(1)[0][0]
        top_trk  = track_counts.most_common(1)[0][0][0]
        top5     = [a for a, _ in artist_counts.most_common(5)]
        return PeriodStats(
            label=label,
            total_plays=len(plays),
            total_ms=sum(p.ms_played for p in plays),
            unique_artists=len(artist_counts),
            unique_tracks=len(track_counts),
            top_artist=top_art,
            top_track=top_trk,
            top_artists=top5,
            active_days=len({p.timestamp.date() for p in plays}),
            average_daily_ms=round(
                sum(p.ms_played for p in plays)
                / len({p.timestamp.date() for p in plays})
            ) if plays else 0,
        )

    # ====================================================================
    # Basic counts
    # ====================================================================

    def total_listening_time_ms(self, period: _Period = None) -> int:
        """Total milliseconds played, optionally filtered to a period."""
        return sum(p.ms_played for p in self._filter(period))

    def unique_artists_count(self, period: _Period = None) -> int:
        """Number of distinct artist names in the play history."""
        return len({p.artist for p in self._filter(period)})

    def unique_tracks_count(self, period: _Period = None) -> int:
        """Number of distinct (track, artist) pairs in the play history."""
        return len({(p.track, p.artist) for p in self._filter(period)})

    def active_days_count(self) -> int:
        """Number of calendar dates with at least one recorded play."""
        return len({p.timestamp.date() for p in self._plays})

    def average_daily_listening_time_ms(self) -> int:
        """Average listening time per active calendar day, or zero when empty."""
        active_days = self.active_days_count()
        return round(self.total_listening_time_ms() / active_days) if active_days else 0

    def first_and_last_play(self) -> tuple[Play, Play] | None:
        """Return the (earliest, latest) Play, or None if no plays exist."""
        if not self._plays:
            return None
        return (self._plays[0], self._plays[-1])

    def available_years(self) -> list[int]:
        """Sorted list of years that have at least one play."""
        return sorted(self._by_year.keys())

    def available_months(self, year: int | None = None) -> list[str]:
        """Sorted list of 'YYYY-MM' strings with at least one play.

        If year is given, only return months in that year.
        """
        months = sorted(self._by_month.keys())
        if year is not None:
            months = [m for m in months if m.startswith(f"{year:04d}")]
        return months

    # ====================================================================
    # Top-N rankings
    # ====================================================================

    def top_artists(
        self, n: int = 10, period: _Period = None
    ) -> list[tuple[str, int, int]]:
        """Return the top-N artists by play count.

        Returns
        -------
        list of (artist_name, play_count, total_ms), sorted descending.
        """
        plays = self._filter(period)
        # Group plays by artist, then count and sum ms for each
        by_artist = self._group_by(plays, lambda p: p.artist)
        # Build result tuples and sort by play count descending
        ranked = sorted(
            [
                (artist, len(artist_plays), sum(p.ms_played for p in artist_plays))
                for artist, artist_plays in by_artist.items()
            ],
            key=lambda t: t[1],   # sort by play_count
            reverse=True,
        )
        return ranked[:n]

    def top_tracks(
        self, n: int = 10, period: _Period = None
    ) -> list[tuple[str, str, int, int]]:
        """Return the top-N tracks by play count.

        Returns
        -------
        list of (track_name, artist_name, play_count, total_ms), sorted descending.
        """
        plays = self._filter(period)
        by_track = self._group_by(plays, lambda p: (p.track, p.artist))
        ranked = sorted(
            [
                (track, artist, len(tp), sum(p.ms_played for p in tp))
                for (track, artist), tp in by_track.items()
            ],
            key=lambda t: t[2],   # sort by play_count
            reverse=True,
        )
        return ranked[:n]

    # ====================================================================
    # Time-series aggregations
    # ====================================================================

    def plays_over_time(self, granularity: str = "month") -> dict[str, int]:
        """Count plays grouped by time period.

        Parameters
        ----------
        granularity : "day" | "month" | "year"

        Returns
        -------
        Ordered dict mapping date label -> play count.
        Labels: "2022-03-15" (day), "2022-03" (month), "2022" (year).
        """
        if granularity == "day":
            key_fn = lambda p: p.timestamp.strftime("%Y-%m-%d")
        elif granularity == "year":
            key_fn = lambda p: p.timestamp.strftime("%Y")
        else:  # default: month
            key_fn = lambda p: p.timestamp.strftime("%Y-%m")

        counts: dict[str, int] = {}
        for play in self._plays:
            label = key_fn(play)
            counts[label] = counts.get(label, 0) + 1
        # Return in chronological order (keys are ISO strings, so str sort = chrono)
        return dict(sorted(counts.items()))

    def listening_by_hour(self, period: _Period = None) -> dict[int, int]:
        """Count plays by hour of day (0–23), optionally within a period.

        Returns a complete dict for all 24 hours, with 0 for hours with
        no plays — useful for charts that need a full x-axis.
        """
        counts: dict[int, int] = {h: 0 for h in range(24)}
        for play in self._filter(period):
            counts[play.timestamp.hour] += 1
        return counts

    def listening_by_weekday(self) -> dict[int, int]:
        """Count plays by weekday (0=Monday … 6=Sunday).

        Returns a complete dict for all 7 days.
        """
        counts: dict[int, int] = {d: 0 for d in range(7)}
        for play in self._plays:
            counts[play.timestamp.weekday()] += 1
        return counts

    def listening_by_month(self) -> dict[str, int]:
        """Total ms played per calendar month ('YYYY-MM').

        Returns an ordered dict from earliest to latest month.
        """
        ms_by_month: dict[str, int] = {}
        for month_key, plays in self._by_month.items():
            ms_by_month[month_key] = sum(p.ms_played for p in plays)
        return dict(sorted(ms_by_month.items()))

    # ====================================================================
    # Plays in a specific period (used by Time Machine)
    # ====================================================================

    def plays_in_period(self, start: datetime, end: datetime) -> list[Play]:
        """Return all plays in [start, end)."""
        return self._filter((start, end))

    # ====================================================================
    # Music evolution
    # ====================================================================

    def music_evolution_by_period(
        self, granularity: str = "month", top_n: int = 3
    ) -> dict[str, list[str]]:
        """Return the top-N artists per time period.

        Returns
        -------
        Ordered dict mapping period label -> [artist1, artist2, …].
        """
        counts = self.music_evolution_counts_by_period(granularity, top_n)
        return {period: list(period_counts) for period, period_counts in counts.items()}

    def music_evolution_counts_by_period(
        self, granularity: str = "month", top_n: int = 3,
    ) -> dict[str, dict[str, int]]:
        """Return cached monthly/yearly top-artist names and play counts.

        The existing period indexes avoid rescanning the full history for each
        month. Returned dictionaries are copies so callers cannot mutate the
        analyser's cached values.
        """
        granularity = "year" if granularity == "year" else "month"
        cache_key = (granularity, top_n)
        if cache_key not in self._music_evolution_counts_cache:
            index = self._by_year if granularity == "year" else self._by_month
            result: dict[str, dict[str, int]] = {}
            for period_key in sorted(index):
                period = str(period_key)
                counts = Counter(play.artist for play in index[period_key])
                result[period] = dict(counts.most_common(top_n))
            self._music_evolution_counts_cache[cache_key] = result
        return {
            period: counts.copy()
            for period, counts in self._music_evolution_counts_cache[cache_key].items()
        }

    def first_heard_by_artist(self) -> dict[str, datetime]:
        """Return a copy of the indexed first-ever timestamp for each artist."""
        return self._first_heard_by_artist.copy()

    # ====================================================================
    # Obsession detection
    # ====================================================================

    def obsession_periods(
        self,
        threshold_pct: float = 50.0,
        min_months: int = 2,
    ) -> list[ObsessionPeriod]:
        """Detect periods when one artist dominated listening.

        Algorithm
        ---------
        1. For each calendar month, compute each artist's share of that
           month's total plays (using Counter).
        2. Slide through consecutive months: if the same artist exceeds
           threshold_pct% for min_months or more consecutive months,
           that is an obsession period.
        3. Merge adjacent qualifying months into a single ObsessionPeriod.

        Parameters
        ----------
        threshold_pct : Minimum % of monthly plays for an artist to qualify.
        min_months    : Minimum consecutive months to be called an obsession.

        Returns
        -------
        list[ObsessionPeriod] sorted by start_date descending (most recent first).
        """
        sorted_months = sorted(self._by_month.keys())
        if not sorted_months:
            return []

        # Step 1: for each month, find which artist (if any) exceeds threshold
        # month_label -> (artist, pct) or None
        dominant: dict[str, tuple[str, float] | None] = {}
        for month_key, plays in self._by_month.items():
            total = len(plays)
            if total == 0:
                dominant[month_key] = None
                continue
            artist_counts = Counter(p.artist for p in plays)
            top_artist, top_count = artist_counts.most_common(1)[0]
            pct = (top_count / total) * 100.0
            dominant[month_key] = (top_artist, pct) if pct >= threshold_pct else None

        # Step 2: slide through months to find consecutive runs of the same artist
        obsessions: list[ObsessionPeriod] = []
        i = 0
        while i < len(sorted_months):
            month = sorted_months[i]
            entry = dominant.get(month)
            if entry is None:
                i += 1
                continue

            artist, pct = entry
            # Extend the run as far as the same artist keeps dominating
            run = [month]
            peak_pct = pct
            j = i + 1
            while j < len(sorted_months):
                next_month = sorted_months[j]
                next_entry = dominant.get(next_month)
                prev_year, prev_number = map(int, run[-1].split("-"))
                next_year, next_number = map(int, next_month.split("-"))
                consecutive_month = (
                    next_year * 12 + next_number
                    == prev_year * 12 + prev_number + 1
                )
                if consecutive_month and next_entry and next_entry[0] == artist:
                    run.append(next_month)
                    peak_pct = max(peak_pct, next_entry[1])
                    j += 1
                else:
                    break

            if len(run) >= min_months:
                # Compute start and end dates from the month labels
                start_year, start_mon = map(int, run[0].split("-"))
                end_year,   end_mon   = map(int, run[-1].split("-"))
                start_dt = datetime(start_year, start_mon, 1)
                last_day = calendar.monthrange(end_year, end_mon)[1]
                end_dt   = datetime(end_year, end_mon, last_day)
                end_exclusive = end_dt + timedelta(days=1)

                # Count total plays for this artist across the window
                window_plays = [
                    p for p in self._by_artist[artist]
                    if start_dt <= p.timestamp < end_exclusive
                ]
                obsessions.append(ObsessionPeriod(
                    artist=artist,
                    start_date=start_dt,
                    end_date=end_dt,
                    peak_pct=round(peak_pct, 1),
                    total_plays=len(window_plays),
                ))

            i = j  # skip past the whole run

        return sorted(obsessions, key=lambda o: o.start_date, reverse=True)

    # ====================================================================
    # Abandoned artists
    # ====================================================================

    def abandoned_artists(
        self,
        min_plays: int = 10,
        silence_days: int = 180,
    ) -> list[AbandonedArtist]:
        """Return artists the user used to play but has since gone quiet on.

        An artist is 'abandoned' when:
          - They have >= min_plays total plays, AND
          - Their last play is >= silence_days before the most recent play
            in the entire history (not today, so the result is stable).

        Returns
        -------
        list[AbandonedArtist] sorted by total_plays descending.
        """
        if not self._plays:
            return []

        # Reference point: the last play in the loaded history
        latest_ever = self._plays[-1].timestamp
        cutoff = latest_ever - timedelta(days=silence_days)

        abandoned: list[AbandonedArtist] = []

        for artist, plays in self._by_artist.items():
            if len(plays) < min_plays:
                continue

            last_play  = max(p.timestamp for p in plays)
            first_play = min(p.timestamp for p in plays)

            if last_play > cutoff:
                continue  # Still active — not abandoned

            # Find the peak month (most plays in a single calendar month)
            month_counts = Counter(
                f"{p.timestamp.year:04d}-{p.timestamp.month:02d}" for p in plays
            )
            peak_month = month_counts.most_common(1)[0][0]

            abandoned.append(AbandonedArtist(
                artist=artist,
                total_plays=len(plays),
                first_played=first_play,
                last_played=last_play,
                peak_month=peak_month,
                days_since_last_play=(latest_ever - last_play).days,
            ))

        return sorted(abandoned, key=lambda a: a.total_plays, reverse=True)

    # ====================================================================
    # Period comparison
    # ====================================================================

    def compare_periods(
        self,
        start1: datetime, end1: datetime,
        start2: datetime, end2: datetime,
    ) -> ComparisonResult:
        """Compare listening stats between two user-selected periods.

        Uses set() operations to find shared / exclusive artists —
        a clear demonstration of Python set arithmetic.

        Returns
        -------
        ComparisonResult with stats for each period plus artist diffs.
        """
        plays_a = self._filter((start1, end1))
        plays_b = self._filter((start2, end2))

        stats_a = self._period_stats(plays_a, "Period A")
        stats_b = self._period_stats(plays_b, "Period B")

        # Set operations: find artists unique to each period vs shared
        artists_a = {p.artist for p in plays_a}
        artists_b = {p.artist for p in plays_b}

        shared   = sorted(artists_a & artists_b)
        only_a   = sorted(artists_a - artists_b)
        only_b   = sorted(artists_b - artists_a)

        return ComparisonResult(
            period_a=stats_a,
            period_b=stats_b,
            shared_artists=shared,
            only_in_a=only_a,
            only_in_b=only_b,
        )

    # ====================================================================
    # Personality profile
    # ====================================================================

    def personality_profile(self) -> PersonalityProfile:
        """Classify the user into one of five listening archetypes.

        Classification rules are evaluated in priority order — the first
        matching rule wins.  Rules are intentionally simple thresholds so
        the logic can be read and explained line by line during a viva.

        Archetypes (priority order)
        ---------------------------
        1. Night Owl   — >= 40% of plays between 22:00 and 04:00
        2. Loyalist    — top artist >= 25% of plays AND < 50 unique artists
        3. Repeater    — average plays-per-unique-track >= 5
        4. Discoverer  — >= 60% of artists heard only once
        5. Genre Hopper — default catch-all (top artist < 10%, >= 100 artists)
        """
        if not self._plays:
            return PersonalityProfile(
                archetype="Unknown",
                description="Load some listening history to discover your archetype.",
            )

        total_plays = len(self._plays)

        # ---- Compute raw metrics ----------------------------------------

        # Night score: % of plays between 22:00–03:59 (inclusive)
        night_plays = sum(
            1 for p in self._plays
            if p.timestamp.hour >= 22 or p.timestamp.hour < 4
        )
        night_pct = (night_plays / total_plays) * 100.0

        # Loyalty score: top artist's share of all plays
        artist_counts = Counter(p.artist for p in self._plays)
        top_artist, top_count = artist_counts.most_common(1)[0]
        loyalty_pct = (top_count / total_plays) * 100.0

        # Repetition score: mean plays per unique track
        track_play_counts = [len(plays) for plays in self._by_track.values()]
        mean_plays_per_track = (
            sum(track_play_counts) / len(track_play_counts)
            if track_play_counts else 0.0
        )

        # Discovery score: % of artists heard only once
        unique_artists = len(self._by_artist)
        artists_once = sum(1 for plays in self._by_artist.values() if len(plays) == 1)
        discovery_pct = (artists_once / unique_artists * 100.0) if unique_artists else 0.0

        # Variety score: unique artists / total plays, capped at 100
        variety_score = min((unique_artists / total_plays) * 100.0, 100.0)

        # Additional context for the Personality page. These are computed
        # here so UI code can display them without redoing listening analysis.
        hour_counts = self.listening_by_hour()
        weekday_counts = self.listening_by_weekday()
        peak_hour = max(hour_counts, key=hour_counts.get)
        peak_weekday = max(weekday_counts, key=weekday_counts.get)
        weekend_pct = (sum(weekday_counts[day] for day in (5, 6)) / total_plays) * 100.0
        known_skip_plays = [p for p in self._plays if p.skipped is not None]
        skip_pct = (
            sum(1 for p in known_skip_plays if p.skipped) / len(known_skip_plays) * 100.0
            if known_skip_plays else None
        )

        # ---- Build dimension scores (0–100 ints) for the radar chart ----
        dimension_scores = {
            "night_score":      min(int(night_pct), 100),
            "loyalty_score":    min(int(loyalty_pct), 100),
            # Repetition: cap mean at 20 repeats = score 100
            "repetition_score": min(int((mean_plays_per_track / 20.0) * 100), 100),
            "discovery_score":  min(int(discovery_pct), 100),
            "variety_score":    min(int(variety_score), 100),
            "weekend_score":    min(int(weekend_pct), 100),
        }
        if skip_pct is not None:
            dimension_scores["skip_score"] = min(int(skip_pct), 100)

        key_stats = {
            "night_pct":           round(night_pct, 1),
            "loyalty_pct":         round(loyalty_pct, 1),
            "top_artist":          top_artist,
            "mean_plays_per_track": round(mean_plays_per_track, 2),
            "discovery_pct":       round(discovery_pct, 1),
            "unique_artists":      unique_artists,
            "total_plays":         total_plays,
            "peak_hour":           peak_hour,
            "peak_weekday":        peak_weekday,
            "weekend_pct":         round(weekend_pct, 1),
            "skip_rate":           round(skip_pct, 1) if skip_pct is not None else None,
            "known_skip_plays":    len(known_skip_plays),
            "active_days":         self.active_days_count(),
            "average_daily_ms":    self.average_daily_listening_time_ms(),
        }

        # ---- Archetype classification (priority order) ------------------

        # Rule 1 — Night Owl
        if night_pct >= 40.0:
            return PersonalityProfile(
                archetype="Night Owl",
                description=(
                    f"You do your best listening after dark — "
                    f"{night_pct:.0f}% of your plays happen between 10pm and 4am."
                ),
                dimension_scores=dimension_scores,
                key_stats=key_stats,
            )

        # Rule 2 — Loyalist
        if loyalty_pct >= 25.0 and unique_artists < 50:
            return PersonalityProfile(
                archetype="Loyalist",
                description=(
                    f"When you find an artist you love, you really commit. "
                    f"{top_artist} alone accounts for {loyalty_pct:.0f}% of your plays."
                ),
                dimension_scores=dimension_scores,
                key_stats=key_stats,
            )

        # Rule 3 — Repeater
        if mean_plays_per_track >= 5.0:
            return PersonalityProfile(
                archetype="Repeater",
                description=(
                    f"You play your favourite tracks on repeat — "
                    f"each track gets {mean_plays_per_track:.1f} plays on average."
                ),
                dimension_scores=dimension_scores,
                key_stats=key_stats,
            )

        # Rule 4 — Discoverer
        if discovery_pct >= 60.0:
            return PersonalityProfile(
                archetype="Discoverer",
                description=(
                    f"You're always hunting for something new — "
                    f"{discovery_pct:.0f}% of artists in your history were only heard once."
                ),
                dimension_scores=dimension_scores,
                key_stats=key_stats,
            )

        # Rule 5 — Genre Hopper (default catch-all)
        return PersonalityProfile(
            archetype="Genre Hopper",
            description=(
                f"You range widely across artists and sounds — "
                f"your top artist ({top_artist}) is only {loyalty_pct:.0f}% of your plays "
                f"across {unique_artists} different artists."
            ),
            dimension_scores=dimension_scores,
            key_stats=key_stats,
        )

    # ====================================================================
    # Wrapped summary
    # ====================================================================

    def wrapped_summary(self, year: int | None = None) -> WrappedSummary:
        """Build a pre-computed summary for the Wrapped slideshow.

        Parameters
        ----------
        year : Calendar year to summarise. Defaults to the most recent
               year in the play history.
        """
        if not self._plays:
            raise ValueError("No plays loaded — cannot generate Wrapped summary.")

        if year is None:
            year = self._plays[-1].timestamp.year

        year_plays = self._by_year.get(year, [])
        if not year_plays:
            raise ValueError(f"No plays found for year {year}.")

        # Top artist and track for the year
        artist_counts = Counter(p.artist for p in year_plays)
        track_counts  = Counter((p.track, p.artist) for p in year_plays)

        top_artist = artist_counts.most_common(1)[0][0]
        top_track_tuple = track_counts.most_common(1)[0][0]
        top_track, top_track_artist = top_track_tuple

        # Top month by total ms played
        month_ms: dict[str, int] = {}
        for play in year_plays:
            key = f"{play.timestamp.year:04d}-{play.timestamp.month:02d}"
            month_ms[key] = month_ms.get(key, 0) + play.ms_played
        top_month_key = max(month_ms, key=lambda k: month_ms[k])
        top_month_num = int(top_month_key.split("-")[1])
        top_month_name = calendar.month_name[top_month_num]

        # Personality archetype (computed from the full history for consistency)
        profile = self.personality_profile()

        # Strongest obsession in this year (if any)
        obsessions = self.obsession_periods()
        year_obsessions = [
            o for o in obsessions
            if o.start_date.year == year or o.end_date.year == year
        ]
        obsession_artist = year_obsessions[0].artist if year_obsessions else None

        return WrappedSummary(
            year=year,
            total_ms=sum(p.ms_played for p in year_plays),
            top_artist=top_artist,
            top_track=top_track,
            top_track_artist=top_track_artist,
            top_month=top_month_name,
            personality_type=profile.archetype,
            obsession_artist=obsession_artist,
            unique_artists=len({p.artist for p in year_plays}),
            unique_tracks=len({(p.track, p.artist) for p in year_plays}),
            total_plays=len(year_plays),
        )

    # ====================================================================
    # Additional helpers used by individual pages
    # ====================================================================

    def artist_plays_over_time(
        self, artist: str, granularity: str = "month",
        period: _Period = None,
    ) -> dict[str, int]:
        """Count plays for a single artist, grouped by time period.

        Used by the Statistics, Obsession, and Abandoned pages to draw
        artist timelines.  ``period`` follows the usual [start, end) bounds.
        """
        plays = [p for p in self._filter(period) if p.artist == artist]
        if granularity == "day":
            key_fn = lambda p: p.timestamp.strftime("%Y-%m-%d")
        elif granularity == "year":
            key_fn = lambda p: p.timestamp.strftime("%Y")
        else:
            key_fn = lambda p: p.timestamp.strftime("%Y-%m")

        counts: dict[str, int] = {}
        for play in plays:
            label = key_fn(play)
            counts[label] = counts.get(label, 0) + 1
        if granularity == "day" and period is not None:
            start, end = period
            day = start.date()
            while datetime.combine(day, datetime.min.time()) < end:
                counts.setdefault(day.strftime("%Y-%m-%d"), 0)
                day += timedelta(days=1)
        return dict(sorted(counts.items()))

    def first_heard(self, artist: str) -> datetime | None:
        """Return the timestamp of the first play for an artist, or None."""
        plays = self._by_artist.get(artist)
        return min(p.timestamp for p in plays) if plays else None

    def last_heard(self, artist: str) -> datetime | None:
        """Return the timestamp of the most recent play for an artist, or None."""
        plays = self._by_artist.get(artist)
        return max(p.timestamp for p in plays) if plays else None

    def first_heard_for_track(self, track: str, artist: str) -> datetime | None:
        """Return the timestamp of the first play of a track by an artist."""
        plays = self._by_track.get((track, artist))
        return min(p.timestamp for p in plays) if plays else None

    def last_heard_for_track(self, track: str, artist: str) -> datetime | None:
        """Return the timestamp of the most recent play of a track by an artist."""
        plays = self._by_track.get((track, artist))
        return max(p.timestamp for p in plays) if plays else None

    def track_plays_over_time(
        self, track: str, artist: str, granularity: str = "month"
    ) -> dict[str, int]:
        """Count plays of one track by artist over time, ordered chronologically."""
        plays = self._by_track.get((track, artist), [])
        if granularity == "year":
            key_fn = lambda p: p.timestamp.strftime("%Y")
        elif granularity == "day":
            key_fn = lambda p: p.timestamp.strftime("%Y-%m-%d")
        else:
            key_fn = lambda p: p.timestamp.strftime("%Y-%m")
        counts: dict[str, int] = {}
        for play in plays:
            key = key_fn(play)
            counts[key] = counts.get(key, 0) + 1
        return dict(sorted(counts.items()))
