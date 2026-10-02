# encoding: utf-8
"""Validation script for Sub-Task 7 — Time Machine Page."""
import sys, inspect, calendar
from datetime import datetime
from pathlib import Path

OK = "[OK]"; FAIL = "[FAIL]"
results = []
def check(label, condition, extra=""):
    status = OK if condition else FAIL
    print(f"  {status} {label}" + (f"  ({extra})" if extra else ""))
    results.append(condition)

# ---- 1. Structural checks ----
print("=== Structural checks ===")
from ui.pages.time_machine import TimeMachinePage
from ui.pages.base_page import BasePage

check("TimeMachinePage subclasses BasePage", issubclass(TimeMachinePage, BasePage))
check("concrete (not abstract)", not inspect.isabstract(TimeMachinePage))
check("refresh() defined", "refresh" in TimeMachinePage.__dict__)

# No analysis logic inside the page file
src = Path("ui/pages/time_machine.py").read_text(encoding="utf-8")
check("no Counter/defaultdict in page", "Counter" not in src and "defaultdict" not in src)
check("imports utils.formatting", "formatting" in src)
check("imports utils.chart_helpers", "chart_helpers" in src)
check("uses analyser.plays_in_period", "plays_in_period" in src)
check("uses analyser.top_artists", "top_artists" in src)
check("uses analyser.top_tracks", "top_tracks" in src)
check("uses calendar module", "calendar" in src)
check("uses CTkOptionMenu for dropdowns", "CTkOptionMenu" in src)

# ---- 2. Fixture ----
print()
print("=== Headless render tests ===")
from core.models import Play
from core.analyser import Analyser
import tkinter as tk
import customtkinter as ctk
from ui import theme

# Multi-year, multi-month dataset
plays = []
for year in [2021, 2022]:
    for month in range(1, 7):
        for day in range(1, 11):
            plays.append(Play(
                datetime(year, month, day, 10),
                f"Artist {(year + month + day) % 4}",
                f"Track {(month * day) % 6}",
                180_000,
            ))
analyser = Analyser(plays)

root = tk.Tk(); root.withdraw()
content = ctk.CTkFrame(root, fg_color=theme.BG); content.pack()
page = TimeMachinePage(content); page.pack()

# ---- Test 1: no data ----
page.refresh(None)
root.update_idletasks()
check("no-data: shows placeholder children", len(page.winfo_children()) > 0)

# ---- Test 2: with data — initial render ----
page.refresh(analyser)
root.update_idletasks()
check("with data: page has children", len(page.winfo_children()) > 0)

# _var_year and _var_month must exist
check("_var_year is StringVar", isinstance(page._var_year, ctk.StringVar))
check("_var_month is StringVar", isinstance(page._var_month, ctk.StringVar))

# Default selection must be from 2022 (most recent year)
check("default year is most recent", page._var_year.get() == "2022")
check("default month is populated", page._var_month.get() != "")

# ---- Test 3: available years loaded correctly ----
years_in_data = set(str(y) for y in analyser.available_years())
check("available years match analyser", set(page._years) == years_in_data)

# ---- Test 4: months_by_year populated ----
check("months_by_year has 2022", "2022" in page._months_by_year)
check("months_by_year has 2021", "2021" in page._months_by_year)
check("months_by_year['2022'] non-empty", len(page._months_by_year["2022"]) > 0)

# ---- Test 5: _render_results for a specific month ----
page._set_selection("2022", "March")
root.update_idletasks()
check("after set_selection year=2022", page._var_year.get() == "2022")
check("after set_selection month=March", page._var_month.get() == "March")
# Results frame should have children (chart, memory card, lists)
check("results frame has content", len(page._results_frame.winfo_children()) > 0)

# ---- Test 6: _all_months_ordered returns chronological list ----
all_pairs = page._all_months_ordered()
check("_all_months_ordered returns list of tuples", all_pairs and isinstance(all_pairs[0], tuple))
# Should start with 2021 and end with 2022
check("first pair year is 2021", all_pairs[0][0] == "2021")
check("last pair year is 2022", all_pairs[-1][0] == "2022")
# Pairs should be unique
check("no duplicate pairs", len(all_pairs) == len(set(all_pairs)))

# ---- Test 7: prev/next navigation ----
page._set_selection("2022", "January")
root.update_idletasks()
page._go_next()
root.update_idletasks()
check("go_next from Jan 2022 to Feb 2022", page._var_month.get() == "February")

page._go_prev()
root.update_idletasks()
check("go_prev from Feb 2022 to Jan 2022", page._var_month.get() == "January")

# Can't go before the first month
first_year, first_month = all_pairs[0]
page._set_selection(first_year, first_month)
page._go_prev()
root.update_idletasks()
check("go_prev at first month: stays at first", page._var_year.get() == first_year and
                                                  page._var_month.get() == first_month)

# Can't go past the last month
last_year, last_month = all_pairs[-1]
page._set_selection(last_year, last_month)
page._go_next()
root.update_idletasks()
check("go_next at last month: stays at last", page._var_year.get() == last_year and
                                               page._var_month.get() == last_month)

# ---- Test 8: on_year_changed updates month list ----
page._on_year_changed("2021")
root.update_idletasks()
check("year change updates month dropdown",
      page._var_year.get() == "2021" or page._month_menu.cget("values") != [])

# ---- Test 9: empty month (no plays) shows no-data card ----
# Use a year/month outside the dataset
empty_analyser = Analyser([
    Play(datetime(2020, 1, 1, 10), "Solo", "Song", 180_000)
])
page.refresh(empty_analyser)
root.update_idletasks()
# Select a month with no data — August 2020 (only Jan exists)
page._set_selection("2020", "January")
root.update_idletasks()
check("January 2020 has results", len(page._results_frame.winfo_children()) > 0)

# Now force a month with no data by directly invoking _show_no_data_for_period
for w in page._results_frame.winfo_children():
    w.destroy()
page._show_no_data_for_period("2020", "August")
root.update_idletasks()
check("no-data card rendered for empty month",
      len(page._results_frame.winfo_children()) > 0)

# ---- Test 10: single-play month ----
single_analyser = Analyser([
    Play(datetime(2023, 6, 15, 14), "One Artist", "One Song", 240_000)
])
page.refresh(single_analyser)
root.update_idletasks()
check("single-play month: no crash", True)
check("single-play: _var_year = 2023", page._var_year.get() == "2023")
check("single-play: _var_month = June", page._var_month.get() == "June")

# ---- Test 11: refresh twice — no widget leak ----
page.refresh(analyser)
root.update_idletasks()
count_after_first = len(page.winfo_children())
page.refresh(analyser)
root.update_idletasks()
count_after_second = len(page.winfo_children())
check("double refresh: same child count (no leak)",
      count_after_first == count_after_second)

# ---- Test 12: refresh back to None then data ----
page.refresh(None)
root.update_idletasks()
page.refresh(analyser)
root.update_idletasks()
check("None-to-data cycle: page has children", len(page.winfo_children()) > 0)

root.destroy()

print()
passes = sum(results)
fails  = len(results) - passes
print(f"Results: {passes} passed, {fails} failed out of {len(results)} checks.")
if fails:
    sys.exit(1)
