# Tuneback

A desktop application that lets you explore your Spotify listening history over time.
Import your exported CSV files and navigate rich analytics across nine dedicated pages.

Built with Python, CustomTkinter, and Matplotlib — no Pandas, no Spotify API.

---

## Requirements

- Python 3.10 or later
- pip

## Setup

```bash
# 1. Clone or download the project
cd "Spotify Time Machine"

# 2. (Recommended) Create a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt
```

## Running the App

```bash
python main.py
```

## Loading Your Spotify Data

1. Request your data from Spotify: **Account → Privacy Settings → Download your data**
2. Spotify will email you a ZIP file. Extract it.
3. Inside the app, click **Load Data** in the sidebar and select either:
   - A single `StreamingHistory*.csv` file (legacy format), or
   - The folder containing all your `Streaming_History_*.json`/CSV files (extended format)

Both Spotify export formats are supported and detected automatically.

## Project Structure

```
├── main.py              # Entry point
├── requirements.txt
├── core/
│   ├── loader.py        # CSV ingestion and format detection
│   ├── models.py        # Data model (Play dataclass)
│   └── analyser.py      # All analytical computations
├── ui/
│   ├── app.py           # Root window and page router
│   ├── sidebar.py       # Navigation sidebar
│   ├── theme.py         # Colours and fonts
│   └── pages/           # One file per feature page
└── utils/
    ├── chart_helpers.py  # Reusable Matplotlib figure builders
    └── formatting.py     # Duration, date, number formatting
```

## Pages

| Page | Description |
|---|---|
| Dashboard | Headline stats and listening timeline |
| Time Machine | Pick any past month and see what you played |
| Statistics | Ranked tables of artists and tracks |
| Music Evolution | How your taste changed over time |
| Listening Personality | Your listener archetype and style profile |
| Obsession Detection | Periods when one artist dominated your plays |
| Abandoned Artists | Artists you used to love but stopped playing |
| Period Comparison | Side-by-side view of two time periods |
| Spotify Wrapped | A Wrapped-style slideshow for any year |
