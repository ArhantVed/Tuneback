# Spotify Time Machine — Implementation Plan

## Top-Level Overview

**Goal:** Build a polished desktop GUI application in Python that lets users import their Spotify listening history (CSV), then explore and visualize that data across several analytical "pages". The app targets a Fundamentals of Python university course, so the implementation must demonstrate core Python concepts clearly and avoid heavy data-science libraries.

**Scope:**
- Single-window CustomTkinter app with a sidebar navigation menu
- Nine feature pages (Dashboard, Time Machine, Statistics, Music Evolution, Listening Personality, Obsession Detection, Abandoned Artists, Period Comparison, Spotify Wrapped Report)
- CSV ingestion that supports both Spotify's legacy `StreamingHistory` format and the newer extended streaming history format
- Matplotlib charts embedded in page frames, with pop-out detail charts on click
- Dark navy/charcoal theme with white text and a green or purple accent colour
- No Spotify API, no AI, no Pandas

**Non-Goals:**
- Real-time data fetching
- User accounts or persistence beyond a single session load
- Mobile or web deployment

---

## Architecture Overview

```
spotify-time-machine/
├── main.py                    # Entry point — creates App window
├── requirements.txt
├── README.md
├── assets/
│   └── logo.png               # Optional app icon
├── data/
│   └── (user CSV files go here — gitignored)
├── core/
│   ├── __init__.py
│   ├── loader.py              # CSV detection and ingestion
│   ├── models.py              # Plain Python dataclasses for a Play record
│   └── analyser.py            # All analytical computations (pure functions / classes)
├── ui/
│   ├── __init__.py
│   ├── app.py                 # App class — root window, sidebar, page container
│   ├── sidebar.py             # Sidebar navigation widget
│   ├── theme.py               # Colour constants and font helpers
│   └── pages/
│       ├── __init__.py
│       ├── base_page.py       # Abstract base page class
│       ├── dashboard.py
│       ├── time_machine.py
│       ├── statistics.py
│       ├── music_evolution.py
│       ├── personality.py
│       ├── obsessions.py
│       ├── abandoned.py
│       ├── comparison.py
│       └── wrapped.py
└── utils/
    ├── __init__.py
    ├── formatting.py          # Duration, date, number formatting helpers
    └── chart_helpers.py       # Reusable Matplotlib figure builders
```

---

## Python Concepts Demonstrated

| Concept | Where |
|---|---|
| Dataclasses | `core/models.py` — `Play` record |
| List comprehensions & generators | `core/analyser.py` — filtering, grouping |
| Dictionaries and sorting | `core/analyser.py` — aggregation without Pandas |
| File I/O and `csv` module | `core/loader.py` |
| OOP — inheritance | `ui/pages/base_page.py` and all page subclasses |
| OOP — encapsulation | `core/analyser.py` — `Analyser` class with methods |
| Exception handling | `core/loader.py` — format detection, bad rows |
| `datetime` module | Throughout — parsing timestamps, grouping by week/month/year |
| `collections.Counter` / `defaultdict` | `core/analyser.py` — frequency counts |
| f-strings and string formatting | `utils/formatting.py` |
| Abstract base classes (`abc`) | `ui/pages/base_page.py` |
| Third-party library integration | CustomTkinter UI, Matplotlib charts |
| Constants / module-level config | `ui/theme.py` |
| Conditional imports and `try/except` | Matplotlib optional pop-out |

---

## Sub-Tasks

---

### Sub-Task 1 — Project Scaffold & Dependencies

**Status:** `[x] done`

**Intent:**
Establish the folder structure, dependency file, and entry point so that every subsequent sub-task has a stable skeleton to build on.

**Expected Outcomes:**
- All directories and `__init__.py` stubs exist
- `requirements.txt` lists `customtkinter`, `matplotlib`
- `main.py` launches a minimal blank window without errors
- `README.md` contains a brief project description and run instructions

**Todo List:**
1. Create the directory tree shown in the Architecture section
2. Write `requirements.txt` with pinned or minimum versions of `customtkinter` and `matplotlib`
3. Write `README.md` with setup and run instructions
4. Write `main.py` as a thin entry point that imports and calls `ui.app.App`
5. Write `ui/app.py` with a bare `App(customtkinter.CTk)` class that opens a 1200×800 window and exits cleanly
6. Add stub `__init__.py` files to `core/`, `ui/`, `ui/pages/`, `utils/`

**Relevant Context:**
- CustomTkinter apps subclass `customtkinter.CTk` for the root window
- The window geometry should be set once here and not overridden by pages

---

### Sub-Task 2 — Theme & Design System

**Status:** `[x] done`

**Intent:**
Define all colours, font sizes, and spacing constants in one place so that every page and widget stays visually consistent without scattering magic values across the codebase.

**Expected Outcomes:**
- `ui/theme.py` exports a `Theme` dataclass or module-level constants covering background, surface, accent, text, and muted colours plus font size constants
- CustomTkinter's global appearance and colour theme are configured from `Theme`
- Developers can change the accent colour in one place and have it propagate everywhere

**Todo List:**
1. Define colour constants: `BG` (dark navy), `SURFACE` (charcoal card), `ACCENT` (green or purple), `TEXT`, `TEXT_MUTED`, `BORDER`
2. Define font size constants: `FONT_XL`, `FONT_L`, `FONT_M`, `FONT_S`
3. Call `customtkinter.set_appearance_mode("dark")` and `customtkinter.set_default_color_theme(...)` from `theme.py` when it is imported
4. Write a small `label_style(size, bold)` helper that returns a font tuple for convenience

**Relevant Context:**
- `ui/app.py` should import `theme.py` before building widgets
- All page files will import from `ui/theme.py`

---

### Sub-Task 3 — Data Models & CSV Loader

**Status:** `[x] done`

**Intent:**
Define the canonical `Play` record and write a loader that detects the Spotify CSV format and normalises both variants into a flat list of `Play` objects. This is the data foundation everything else reads from.

**Expected Outcomes:**
- `core/models.py` defines a `Play` dataclass with fields: `timestamp` (datetime), `artist` (str), `track` (str), `ms_played` (int), `platform` (str, optional), `reason_start` (str, optional), `reason_end` (str, optional), `skipped` (bool, optional)
- `core/loader.py` exports `load_csv(path: str) -> list[Play]`
- Loader auto-detects format by inspecting the CSV header row using documented column names only
- **Legacy format** columns (all required): `endTime`, `artistName`, `trackName`, `msPlayed`
- **Extended format** columns (required): `ts`, `master_metadata_track_artist_name`, `master_metadata_track_name`, `ms_played`; optional: `platform`, `reason_start`, `reason_end`, `skipped`
- All optional fields default to `None` / `False` if absent from the file — no crash on missing columns
- Rows with zero `ms_played` are optionally filtered (configurable `skip_short` flag, default `True`)
- Bad or unparseable rows are skipped with a warning printed to stdout, not a crash
- A `load_folder(folder_path: str) -> list[Play]` helper loads and merges all CSV files in a directory

**Todo List:**
1. Write `core/models.py` with the `Play` dataclass (use `@dataclass` and `field(default=None)` for optionals)
2. Write `core/loader.py` — `_detect_format(headers: list[str]) -> str` returns `"legacy"`, `"extended"`, or raises `ValueError` with a clear message listing recognised column sets
3. Write `_parse_legacy_row(row: dict) -> Play` — maps `endTime`→`timestamp`, `artistName`→`artist`, `trackName`→`track`, `msPlayed`→`ms_played`; fills all optional fields with `None`/`False`
4. Write `_parse_extended_row(row: dict) -> Play` — maps documented extended column names; uses `row.get(col)` for every optional column so missing columns are silently treated as absent
5. Write `load_csv(path, skip_short=True)` that opens the file with UTF-8-sig encoding (handles BOM), detects format, maps rows, returns `list[Play]`
6. Write `load_folder(folder_path)` that globs for `*.csv`, calls `load_csv` for each, deduplicates by `(timestamp, artist, track)`, returns sorted list
7. Write a small `__main__` block in `loader.py` that prints a summary when run directly (good for viva demonstration)

**Relevant Context:**
- Use the standard library `csv` module — no Pandas
- Use `datetime.fromisoformat` or `datetime.strptime` for timestamp parsing; handle both `"2021-03-14 08:00"` (legacy) and full ISO 8601 strings with timezone offset (extended)
- `ms_played` is an int field; convert with `int(row["msPlayed"])` for legacy, `int(row["ms_played"])` for extended
- The `skipped` field in extended format is stored as the string `"True"` / `"False"` in CSV — convert explicitly

---

### Sub-Task 4 — Analyser (Core Computations)

**Status:** `[x] done`

**Intent:**
Build all analytical logic as a single `Analyser` class that accepts a `list[Play]` and exposes named methods returning plain Python structures (dicts, lists, tuples). No GUI code touches raw play lists — all computation happens here.

**Expected Outcomes:**
- `core/analyser.py` exports `Analyser`
- All methods return plain Python types (lists, dicts, named tuples) so pages can render them without further computation
- The viva demonstrator can call any method independently from a REPL

**Methods to implement:**

| Method | Returns | Used By |
|---|---|---|
| `top_artists(n, period)` | `list[tuple[artist, play_count, total_ms]]` | Dashboard, Stats |
| `top_tracks(n, period)` | `list[tuple[track, artist, play_count, total_ms]]` | Dashboard, Stats |
| `plays_over_time(granularity)` | `dict[date_label -> count]` | Dashboard, Time Machine |
| `listening_by_hour()` | `dict[hour_int -> count]` | Personality |
| `listening_by_weekday()` | `dict[weekday_int -> count]` | Personality |
| `listening_by_month()` | `dict[month_str -> total_ms]` | Stats |
| `first_and_last_play()` | `tuple[Play, Play]` | Dashboard |
| `total_listening_time_ms()` | `int` | Dashboard, Wrapped |
| `unique_artists_count()` | `int` | Stats |
| `unique_tracks_count()` | `int` | Stats |
| `obsession_periods(threshold_days, threshold_pct)` | `list[ObsessionPeriod]` | Obsessions |
| `abandoned_artists(min_plays, silence_days)` | `list[AbandonedArtist]` | Abandoned |
| `music_evolution_by_period(granularity)` | `dict[period -> list[top artist]]` | Music Evolution |
| `compare_periods(start1, end1, start2, end2)` | `ComparisonResult` | Period Comparison |
| `personality_profile()` | `PersonalityProfile` | Personality |
| `wrapped_summary()` | `WrappedSummary` | Wrapped |

**Todo List:**
1. Define lightweight result dataclasses in `core/models.py`: `ObsessionPeriod`, `AbandonedArtist`, `ComparisonResult`, `PersonalityProfile`, `WrappedSummary`
2. Write `Analyser.__init__(self, plays: list[Play])` — store sorted plays, precompute index structures (artist→plays, track→plays, month→plays) using `collections.defaultdict`
3. Implement aggregation helpers: `_group_by(key_fn)` returns a `defaultdict(list)`
4. Implement all methods listed above using list comprehensions, `sorted()`, `Counter`, and `defaultdict` — no Pandas
5. For `obsession_periods`: slide a rolling window over monthly artist counts, flag when a single artist exceeds `threshold_pct`% of plays in a run of `threshold_days`
6. For `abandoned_artists`: find artists with `>= min_plays` total plays whose last play is `>= silence_days` days ago
7. For `personality_profile`: classify the user into one of 5 archetypes using **explicit, rule-based thresholds** (see archetype definitions below) — no ML, fully explainable
8. Write unit-testable methods (no side effects, no file I/O)

**Personality Archetypes (rule-based classification):**

Classification is evaluated in priority order; the first matching archetype wins.

| Archetype | Primary Rule | Secondary Rule |
|---|---|---|
| **Night Owl** | >= 40% of plays occur between 22:00 and 04:00 | — |
| **Loyalist** | Top artist accounts for >= 25% of all plays | Fewer than 50 unique artists |
| **Repeater** | Average plays-per-track >= 5 (same track played many times) | — |
| **Discoverer** | >= 60% of artists appear only once in the history | High unique-artist count |
| **Genre Hopper** | Top artist accounts for < 10% of all plays AND >= 100 unique artists | Default / catch-all if none above match |

`PersonalityProfile` dataclass fields: `archetype` (str), `description` (str), `dimension_scores` (dict mapping dimension name to 0-100 int), `key_stats` (dict of supporting values used in the classification).

Dimension scores computed for the radar/bar chart:
- `night_score`: % of plays between 22:00-04:00, scaled 0-100
- `loyalty_score`: top-artist share of plays, scaled 0-100
- `repetition_score`: mean plays-per-unique-track, capped and scaled 0-100
- `discovery_score`: % of artists heard only once, scaled 0-100
- `variety_score`: unique artists / total plays x 100, capped at 100

**Relevant Context:**
- `collections.Counter` and `collections.defaultdict` are key — demonstrate both for the viva
- `datetime` arithmetic with `timedelta` is used for window calculations
- All period parameters should default to `None` (meaning "all time")

---

### Sub-Task 5 — App Shell, Sidebar & Page Router

**Status:** `[x] done`

**Intent:**
Build the main window layout — a fixed sidebar on the left with navigation buttons, and a content frame on the right that swaps page widgets in and out. This is the backbone of the UI.

**Expected Outcomes:**
- Running `main.py` shows a 1200×800 dark window with a sidebar listing all nine page names
- Clicking a sidebar button replaces the right-hand content area with the corresponding (initially stub) page
- Active page button is highlighted with the accent colour
- Sidebar shows the app title/logo at the top
- A `load_data` action in the sidebar opens a file dialog to select a CSV file or folder, loads data, and passes the `Analyser` instance to the active page

**Todo List:**
1. Write `ui/pages/base_page.py` — abstract `BasePage(customtkinter.CTkFrame)` with an abstract `refresh(analyser)` method and a `show_placeholder(message)` helper for pages that have no data yet
2. Write `ui/sidebar.py` — `Sidebar(customtkinter.CTkFrame)` with nav buttons and a `Load Data` button at the bottom; buttons call a `navigate_to(page_name)` callback
3. Update `ui/app.py` — split window into sidebar (fixed 220px width) and content frame (fills remaining space); instantiate all nine page classes; implement `show_page(name)` that hides all pages and packs the target one; implement `on_load_data()` that opens a file dialog, calls `loader.load_folder` or `loader.load_csv`, constructs `Analyser`, stores it on `self`, and calls `show_page` which passes the analyser to the active page
4. Wire sidebar button callbacks to `app.show_page`
5. Add stub page classes (subclasses of `BasePage` that just show a placeholder label) for all nine pages so navigation works end-to-end

**Relevant Context:**
- `customtkinter.CTkFrame` for layout containers
- `tkinter.filedialog.askdirectory` and `askopenfilename` for file selection
- Pages should receive the `Analyser` via `refresh(analyser)` so they can be re-rendered when data changes

---

### Sub-Task 6 — Dashboard Page

**Status:** `[x] done`

**Intent:**
Build the first real page — a summary overview that gives the user their headline stats at a glance the moment they load their data.

**Expected Outcomes:**
- Shows total listening time (formatted as "X days, Y hours")
- Shows total unique artists and tracks
- Shows date range of the data
- Shows top 5 artists and top 5 tracks as compact ranked lists
- Shows a small embedded line chart of plays over time (monthly)
- All content appears correctly after `refresh(analyser)` is called

**Todo List:**
1. Layout the page using a grid of `CTkFrame` "stat cards" in the top row
2. Add a scrollable top-artists/top-tracks panel below the cards
3. Embed a Matplotlib figure using `FigureCanvasTkAgg` for the plays-over-time sparkline
4. Wire all widgets to `analyser` methods
5. Use `utils/formatting.py` helpers for duration and number display

**Relevant Context:**
- `FigureCanvasTkAgg` from `matplotlib.backends.backend_tkagg`
- Cards should use `SURFACE` background from `theme.py`
- Dashboard is the default page shown on startup (with a "Load your data to get started" placeholder)

---

### Sub-Task 7 — Time Machine Page

**Status:** `[ ] pending`

**Intent:**
Let the user pick any past date or month and see what they were listening to at that moment — a "what was I obsessed with back then?" feature.

**Expected Outcomes:**
- Date picker controls (year + month dropdowns or a calendar widget) let the user select a period
- On selection, shows top 5 artists and top 5 tracks for that period
- Shows total listening minutes for the period
- Shows an embedded bar chart of top artists for the period
- A "Play Memory" highlight card shows the single most-played track of that period

**Todo List:**
1. Add `plays_in_period(start, end)` and `top_tracks(n, period)` / `top_artists(n, period)` period-filtering to `Analyser` if not already present
2. Build year/month dropdown widgets using `CTkOptionMenu` populated from available years/months in the data
3. Build the results panel that updates when the user changes the date selection
4. Embed a horizontal bar chart for top artists using `chart_helpers.py`
5. Build the "Memory Card" highlight widget

**Relevant Context:**
- Use `datetime` to compute `start = datetime(year, month, 1)` and `end` as last day of month
- Dropdowns should only show years/months present in the loaded data

---

### Sub-Task 8 — Statistics Page

**Status:** `[ ] pending`

**Intent:**
A detailed numerical breakdown of listening habits — deeper than the dashboard, with sortable tables and multiple charts.

**Expected Outcomes:**
- Tabs or toggle buttons for: Artists, Tracks, Monthly Breakdown
- Each tab shows a ranked table (artist/track name, play count, total time, first heard, last heard)
- Monthly breakdown shows a bar chart of total listening time per month
- Charts are embedded; clicking a bar or row opens a pop-out detail chart

**Todo List:**
1. Build a reusable `RankedTable` widget (scrollable frame with header row and data rows) in `ui/` or the page file
2. Populate Artists and Tracks tabs from `analyser.top_artists(50)` and `analyser.top_tracks(50)`
3. Build the monthly bar chart embedded via `FigureCanvasTkAgg`
4. Implement click handler on bars/rows to open a `Toplevel` pop-out window with a more detailed chart for the selected artist or track
5. Add `first_heard(artist)` and `last_heard(artist)` methods to `Analyser` if not already present

**Relevant Context:**
- `customtkinter.CTkScrollableFrame` for the table
- Pop-out windows use `tkinter.Toplevel` styled with theme colours

---

### Sub-Task 9 — Music Evolution Page

**Status:** `[ ] pending`

**Intent:**
Show how the user's taste changed over time — which artists dominated each month or year, and how genres of artists shifted.

**Expected Outcomes:**
- A timeline chart (horizontal stacked or grouped bars) showing top 3 artists per month/quarter
- A "New Discoveries" panel listing artists first heard in each selected year
- Navigation controls to zoom into a specific year

**Todo List:**
1. Call `analyser.music_evolution_by_period("month")` to get per-period top artists
2. Build a stacked bar chart using Matplotlib with one segment per top-3 artist per period; embed it via `FigureCanvasTkAgg`
3. Add a year selector to filter the timeline
4. Build the "New Discoveries" list panel: filter plays to find each artist's first-ever occurrence, then group by year
5. Add `first_heard_by_artist()` method to `Analyser` returning `dict[artist -> datetime]`

**Relevant Context:**
- Keep artist colours consistent across the chart by assigning a colour from a fixed palette using a `dict` keyed on artist name
- The chart will be wide — use a scrollable canvas if many months are present

---

### Sub-Task 10 — Listening Personality Page

**Status:** `[ ] pending`

**Intent:**
Give the user a fun personality archetype based on their listening patterns — "Night Owl", "Morning Commuter", "Obsessive Repeater", etc.

**Expected Outcomes:**
- A large archetype card showing the user's personality type name, description, and a relevant icon/emoji
- A radar or bar chart showing the underlying dimensions (night vs day, variety vs repetition, skip rate, weekend vs weekday)
- Supporting stats that justify the classification

**Todo List:**
1. Define 5 archetypes in a Python dict or list-of-dicts constant in the page or `analyser.py`
2. Call `analyser.personality_profile()` to get the computed profile
3. Build the archetype card widget displaying name + description
4. Build the supporting dimension chart (horizontal bar chart showing each dimension score 0-100)
5. Display supporting stats: peak listening hour, most active day, average daily listening time

**Relevant Context:**
- `PersonalityProfile` dataclass (defined in Sub-Task 4) holds archetype name, dimension scores dict, and key stats
- Dimensions computed from `listening_by_hour()`, `listening_by_weekday()`, skip rate from extended-format data

---

### Sub-Task 11 — Obsession Detection Page

**Status:** `[ ] pending`

**Intent:**
Identify periods when the user was clearly obsessed with a single artist — streaming them far more than anything else for a stretch of time.

**Expected Outcomes:**
- A list of detected obsession periods: artist name, start date, end date, percentage of plays during that window
- Clicking an obsession period shows an embedded line chart of that artist's daily play count during the obsession window
- An "Intensity" bar visualises how strong each obsession was

**Todo List:**
1. Call `analyser.obsession_periods()` to get the list of `ObsessionPeriod` objects
2. Build a scrollable list of obsession cards (one per period) with artist, date range, intensity bar
3. Implement click handler: clicking a card shows a detail chart (embedded or pop-out) of daily plays for that artist during the window
4. Add a sensitivity slider (threshold percentage) that re-runs the detection and updates the list in real time

**Relevant Context:**
- `ObsessionPeriod` dataclass: `artist`, `start_date`, `end_date`, `peak_pct`, `total_plays`
- The sensitivity slider uses `CTkSlider`

---

### Sub-Task 12 — Abandoned Artists Page

**Status:** `[ ] pending`

**Intent:**
Surface artists the user used to listen to a lot but hasn't played in a long time — a nostalgic "who did you forget about?" feature.

**Expected Outcomes:**
- A list of abandoned artists sorted by total historical plays descending
- Each card shows: artist name, total plays, last played date, "abandoned X days ago" label
- A "silence threshold" slider lets the user adjust what counts as abandoned (e.g. 90, 180, 365 days)
- Clicking an artist shows their full play history as a line chart in a pop-out

**Todo List:**
1. Call `analyser.abandoned_artists(min_plays=10, silence_days=180)` to get the list
2. Build a scrollable grid of artist cards
3. Implement the silence-threshold slider that calls `analyser.abandoned_artists(silence_days=slider_value)` and re-renders
4. Implement click handler to open a pop-out line chart of plays per month for that artist

**Relevant Context:**
- `AbandonedArtist` dataclass: `artist`, `total_plays`, `last_played` (datetime), `first_played` (datetime), `peak_month`
- The slider can trigger a full re-render of the list — keep the render function separate from the build function

---

### Sub-Task 13 — Period Comparison Page

**Status:** `[ ] pending`

**Intent:**
Let the user compare two time periods side-by-side — e.g. "summer 2022 vs summer 2023" — to see how their taste changed.

**Expected Outcomes:**
- Two date-range selectors (start + end for Period A and Period B)
- Side-by-side stat cards: total plays, unique artists, top artist, top track, avg daily listening
- A grouped bar chart comparing top 5 artists across both periods
- A "What Changed" panel listing artists that appear in one period but not the other

**Todo List:**
1. Build two date-range selector widgets (year + month start/end dropdowns)
2. Call `analyser.compare_periods(...)` and display the `ComparisonResult`
3. Build the side-by-side stat card layout (two columns)
4. Build the grouped bar chart using Matplotlib
5. Build the "What Changed" diff panel using set operations on the two top-artist lists

**Relevant Context:**
- `ComparisonResult` dataclass: `period_a_stats`, `period_b_stats`, `shared_artists`, `only_in_a`, `only_in_b`
- Use `set()` operations for the diff — a clear Fundamentals of Python concept to demonstrate

---

### Sub-Task 14 — Spotify Wrapped Report Page

**Status:** `[ ] pending`

**Intent:**
A fun full-screen "slideshow" of cards summarising the user's year in music — modelled on Spotify Wrapped. Each card has a bold stat or story, with forward/back navigation.

**Expected Outcomes:**
- Full-screen content area (no sidebar scroll) with previous/next arrow buttons
- At least 8 slide cards: intro, total time, top artist, top track, listening personality, obsession highlight, most active month, closing card
- Each card has a large colourful graphic or Matplotlib chart
- Animated or styled transitions between cards (fade or slide using `after()`)
- A year selector at the top so the user can generate a Wrapped for any year in their data

**Todo List:**
1. Call `analyser.wrapped_summary(year)` to get the `WrappedSummary` dataclass with all needed values pre-computed
2. Define a list of slide specification dicts: `[{"title": ..., "value": ..., "subtitle": ..., "chart_fn": ...}, ...]`
3. Build a `WrappedSlide` widget that renders one card with large title/value text and an optional embedded chart
4. Implement `show_slide(index)` that destroys the previous `WrappedSlide` and creates a new one
5. Add prev/next buttons and keyboard left/right arrow bindings
6. Implement a simple fade transition using `after()` and widget `configure(fg_color=...)`
7. Add a year selector `CTkOptionMenu` that regenerates the slide list for the selected year

**Relevant Context:**
- `WrappedSummary` dataclass: `year`, `total_ms`, `top_artist`, `top_track`, `top_month`, `personality_type`, `obsession_artist`, `unique_artists`, `unique_tracks`
- The slideshow should feel celebratory — use large fonts and the accent colour prominently

---

### Sub-Task 15 — Chart Helpers & Formatting Utilities

**Status:** `[x] done`

**Intent:**
Consolidate all reusable Matplotlib figure-building code and all display-formatting helpers into dedicated utility modules so no page file contains raw Matplotlib setup boilerplate. This sub-task must be completed **before** Sub-Task 6 (Dashboard) and all subsequent page sub-tasks.

**Expected Outcomes:**
- `utils/chart_helpers.py` provides functions: `make_bar_chart(labels, values, title, color)`, `make_line_chart(x, y, title, color)`, `make_grouped_bar_chart(...)`, `make_radar_chart(...)`, `embed_figure(fig, parent_frame)` (returns the canvas), `popup_figure(fig, title)` (opens a `Toplevel`)
- `utils/formatting.py` provides: `ms_to_human(ms)` → `"3 days, 2 hours"`, `short_number(n)` → `"1.2k"`, `date_label(dt, granularity)` → `"Jan 2022"` etc.
- All Matplotlib figures use the dark theme (dark background, white axes text, accent colour bars)

**Todo List:**
1. Write `utils/formatting.py` with the three format helpers
2. Write `utils/chart_helpers.py` with all figure-builder functions; each function accepts data and returns a `plt.Figure` (not displayed yet)
3. Write `embed_figure(fig, parent_frame)` that creates `FigureCanvasTkAgg`, calls `draw()`, and packs the canvas widget
4. Write `popup_figure(fig, title)` that opens a styled `Toplevel` and embeds the figure in it
5. Apply dark Matplotlib style: `plt.style.use("dark_background")` plus override face/edge colours to match `theme.py`

**Relevant Context:**
- All pages import from these utilities — implement this sub-task strictly before any page sub-task (6 onwards)
- Keeping chart code here means the viva demonstrator can show Matplotlib knowledge in one focused file

---

## Development Phase Summary

| Phase | Sub-Tasks | Description |
|---|---|---|
| 1 — Foundation | 1, 2, 3, 4 | Scaffold, theme, data layer, analysis engine |
| 2 — UI Shell | 5, 15 | App window + navigation first, then chart utilities before any pages |
| 3 — Core Pages | 6, 7, 8 | Dashboard, Time Machine, Statistics |
| 4 — Insight Pages | 9, 10, 11, 12 | Evolution, Personality, Obsessions, Abandoned |
| 5 — Advanced Pages | 13, 14 | Period Comparison, Spotify Wrapped slideshow |

**Required sub-task order within Phase 2:** Sub-Task 5 must be complete before Sub-Task 15, and Sub-Task 15 must be complete before Sub-Task 6 onwards.

---

## Implementation Notes

- **Recommended implementation order:** Follow phases 1→2→3→4→5. Do not start a phase until the previous phase is complete and working. Within Phase 2, Sub-Task 15 (chart helpers) must be complete before any page sub-task begins.
- **Data safety:** Never modify the user's CSV files. All operations are read-only.
- **Viva readiness:** Each module should have a descriptive docstring and at least one method with a clear inline comment explaining the algorithm. Personality classification rules must be readable inline — no opaque scoring functions.
- **No global mutable state:** The `Analyser` instance lives on `App` and is passed to pages via `refresh(analyser)`. Pages do not store the analyser as a module-level variable.
- **Error states:** Every page's `refresh` method must handle `analyser=None` gracefully by showing a placeholder message.
- **No Spotify API, no AI/LLM, no authentication** — out of scope for this project.
- **Optional fields:** Any `Play` field sourced only from the extended format must never be assumed present. All analyser methods that use optional fields (e.g. `skipped`, `platform`) must check for `None` before using the value.
- **Personality archetypes are evaluated in priority order** (Night Owl → Loyalist → Repeater → Discoverer → Genre Hopper). The first matching rule wins. This deterministic logic is intentional and should be clearly commented for the viva.
