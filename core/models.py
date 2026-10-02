"""
core/models.py — Tuneback data models.

Defines the canonical Play dataclass that represents a single song
play event, normalised from either Spotify CSV export format.

All result dataclasses used by the Analyser (Sub-Task 4) are also
defined here so models.py is the single source of truth for data
structures across the application.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


# ---------------------------------------------------------------------------
# Primary record
# ---------------------------------------------------------------------------

@dataclass
class Play:
    """One song play event, normalised from any supported Spotify CSV format.

    Required fields are populated from both legacy and extended exports.
    Optional fields are only available from the extended export; they
    default to None / False when absent so callers must guard with:
        if play.skipped is not None: ...

    Attributes
    ----------
    timestamp   : When the track finished playing (end-of-track time).
    artist      : Artist name string.
    track       : Track title string.
    ms_played   : Milliseconds of audio actually played (>0).
    platform    : Device/platform string, e.g. "android" (extended only).
    reason_start: Why playback started, e.g. "trackdone" (extended only).
    reason_end  : Why playback ended, e.g. "endplay" (extended only).
    skipped     : True if the user skipped the track (extended only).
    """

    # Required — present in every format
    timestamp: datetime
    artist:    str
    track:     str
    ms_played: int

    # Optional — extended format only; default None / False
    platform:     str | None  = field(default=None)
    reason_start: str | None  = field(default=None)
    reason_end:   str | None  = field(default=None)
    skipped:      bool | None = field(default=None)

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def minutes_played(self) -> float:
        """ms_played expressed as fractional minutes."""
        return self.ms_played / 60_000

    @property
    def was_skipped(self) -> bool:
        """True only when skipped data is available AND the track was skipped."""
        return bool(self.skipped)


# ---------------------------------------------------------------------------
# Analyser result dataclasses  (populated in Sub-Task 4)
# ---------------------------------------------------------------------------

@dataclass
class ObsessionPeriod:
    """A window in time when one artist dominated the user's listening.

    Attributes
    ----------
    artist      : Name of the obsession artist.
    start_date  : First day of the obsession window.
    end_date    : Last day of the obsession window.
    peak_pct    : Highest single-month share of total plays (0–100).
    total_plays : Total play count for this artist during the window.
    """
    artist:      str
    start_date:  datetime
    end_date:    datetime
    peak_pct:    float
    total_plays: int


@dataclass
class AbandonedArtist:
    """An artist the user used to listen to but has since stopped playing.

    Attributes
    ----------
    artist      : Artist name.
    total_plays : All-time play count for this artist.
    first_played: Datetime of the very first play of this artist.
    last_played : Datetime of the most recent play of this artist.
    days_since_last_play: Days between this artist's last play and the
                          newest play in the loaded listening history.
    peak_month  : Year-month string ("2022-03") when plays were highest.
    """
    artist:       str
    total_plays:  int
    first_played: datetime
    last_played:  datetime
    peak_month:   str
    days_since_last_play: int


@dataclass
class PeriodStats:
    """Summary stats for a single time period — used inside ComparisonResult."""
    label:          str
    total_plays:    int
    total_ms:       int
    unique_artists: int
    unique_tracks:  int
    top_artist:     str
    top_track:      str
    top_artists:    list[str]   = field(default_factory=list)
    active_days:    int         = 0
    average_daily_ms: int       = 0


@dataclass
class ComparisonResult:
    """Side-by-side stats for two user-selected time periods.

    Attributes
    ----------
    period_a    : Stats for the first period.
    period_b    : Stats for the second period.
    shared_artists : Artists present in both periods.
    only_in_a      : Artists in period A but not B.
    only_in_b      : Artists in period B but not A.
    """
    period_a:       PeriodStats
    period_b:       PeriodStats
    shared_artists: list[str]  = field(default_factory=list)
    only_in_a:      list[str]  = field(default_factory=list)
    only_in_b:      list[str]  = field(default_factory=list)


@dataclass
class PersonalityProfile:
    """The user's listening personality archetype and supporting metrics.

    Attributes
    ----------
    archetype       : Name of the matched archetype, e.g. "Night Owl".
    description     : Human-readable explanation of the archetype.
    dimension_scores: Dict mapping dimension name to a 0–100 int score.
                      Includes night, loyalty, repetition, discovery, variety,
                      and weekend scores; skip_score is present when skip data
                      exists in the source export.
    key_stats       : Raw classification and supporting display metrics,
                      including peak listening time and average per active day.
    """
    archetype:        str
    description:      str
    dimension_scores: dict[str, int]  = field(default_factory=dict)
    key_stats:        dict[str, float | int | str | None] = field(default_factory=dict)


@dataclass
class WrappedSummary:
    """Pre-computed values for the Spotify Wrapped-style slideshow.

    Attributes
    ----------
    year            : The calendar year this summary covers.
    total_ms        : Total milliseconds listened in this year.
    top_artist      : Most-played artist name.
    top_track       : Most-played track title.
    top_track_artist: Artist of the most-played track.
    top_month       : Month with the most listening, e.g. "March".
    personality_type: Archetype name from PersonalityProfile.
    obsession_artist: Artist from the strongest obsession period (or None).
    unique_artists  : Count of distinct artists heard this year.
    unique_tracks   : Count of distinct tracks heard this year.
    total_plays     : Total play count for the year.
    """
    year:             int
    total_ms:         int
    top_artist:       str
    top_track:        str
    top_track_artist: str
    top_month:        str
    personality_type: str
    obsession_artist: str | None
    unique_artists:   int
    unique_tracks:    int
    total_plays:      int
