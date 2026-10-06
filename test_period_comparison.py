"""Focused validation for Period Comparison analysis and UI behavior."""
from datetime import datetime
import unittest
import tkinter

from core.analyser import Analyser
from core.models import Play

try:
    import customtkinter
    import matplotlib.pyplot as plt
    from ui.pages.comparison import ComparisonPage
    UI_IMPORT_ERROR = None
except ImportError as exc:
    customtkinter = None
    plt = None
    ComparisonPage = None
    UI_IMPORT_ERROR = exc


def sample_plays():
    return [
        Play(datetime(2022, 1, 2), "Alpha", "A song", 120_000),
        Play(datetime(2022, 1, 2, 13), "Alpha", "A song", 60_000),
        Play(datetime(2022, 2, 8), "Beta", "B song", 180_000),
        Play(datetime(2023, 1, 3), "Beta", "B song", 120_000),
        Play(datetime(2023, 1, 5), "Gamma", "G song", 240_000),
    ]


def many_artist_plays():
    plays = []
    for period, prefix, day in ((2022, "A", 2), (2023, "B", 2)):
        for rank in range(12):
            for play_index in range(12 - rank):
                plays.append(Play(
                    datetime(period, 1, day, play_index // 60, play_index % 60),
                    f"{prefix} Artist {rank:02d}", f"Track {play_index}", 60_000,
                ))
    return plays


class PeriodComparisonAnalyserTests(unittest.TestCase):
    def test_no_data_and_empty_periods(self):
        result = Analyser([]).compare_periods(datetime(2022, 1, 1), datetime(2022, 2, 1), datetime(2023, 1, 1), datetime(2023, 2, 1))
        self.assertEqual(result.period_a.total_plays, 0)
        self.assertEqual(result.period_a.average_daily_ms, 0)
        self.assertEqual(result.only_in_a, [])
        self.assertEqual(result.only_in_b, [])

    def test_comparison_metrics_and_artist_diffs(self):
        analyser = Analyser(sample_plays())
        result = analyser.compare_periods(datetime(2022, 1, 1), datetime(2022, 2, 1), datetime(2023, 1, 1), datetime(2023, 2, 1))
        self.assertEqual((result.period_a.total_plays, result.period_a.total_ms), (2, 180_000))
        self.assertEqual(result.period_a.unique_artists, 1)
        self.assertEqual(result.period_a.top_artist, "Alpha")
        self.assertEqual(result.period_a.top_track, "A song")
        self.assertEqual(result.period_a.active_days, 1)
        self.assertEqual(result.period_a.average_daily_ms, 180_000)
        self.assertEqual(result.period_b.total_plays, 2)
        self.assertEqual(result.period_b.average_daily_ms, 180_000)
        self.assertEqual(result.only_in_a, ["Alpha"])
        self.assertEqual(result.only_in_b, ["Beta", "Gamma"])

    def test_identical_periods_and_end_exclusive_bounds(self):
        analyser = Analyser(sample_plays())
        bounds = (datetime(2022, 1, 1), datetime(2022, 2, 1))
        same = analyser.compare_periods(*bounds, *bounds)
        self.assertEqual(same.shared_artists, ["Alpha"])
        self.assertEqual(same.only_in_a, [])
        self.assertEqual(same.only_in_b, [])
        self.assertEqual(analyser.compare_periods(datetime(2022, 2, 1), datetime(2022, 2, 1), *bounds).period_a.total_plays, 0)


@unittest.skipUnless(UI_IMPORT_ERROR is None, f"UI dependencies unavailable: {UI_IMPORT_ERROR}")
class PeriodComparisonPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = customtkinter.CTk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def setUp(self):
        self.page = ComparisonPage(self.root)
        self.page.pack(fill="both", expand=True)
        self.root.update_idletasks()

    def tearDown(self):
        self.page.destroy()
        plt.close("all")
        self.root.update_idletasks()

    @staticmethod
    def _texts(widget):
        found = []
        for child in widget.winfo_children():
            try:
                value = child.cget("text")
                if value:
                    found.append(str(value))
            except (AttributeError, tkinter.TclError, ValueError):
                pass
            found.extend(PeriodComparisonPageTests._texts(child))
        return found

    def test_import_and_no_data_state(self):
        self.assertIsNotNone(ComparisonPage)
        self.page.refresh(None)
        self.assertTrue(any("Load your Spotify data" in text for text in self._texts(self.page)))

    def test_selectors_metrics_diff_and_grouped_chart(self):
        self.page.refresh(Analyser(sample_plays()))
        self.root.update_idletasks()
        # With the three available months (Jan 2022, Feb 2022, Jan 2023),
        # the default split selects Jan–Feb 2022 for A and Jan 2023 for B.
        # End months are inclusive in the selector; the page converts them
        # to an exclusive first-of-next-month boundary for Analyser.
        self.assertEqual(self.page._selected_month(("Period A", "start")), "2022-01")
        self.assertEqual(self.page._selected_month(("Period A", "end")), "2022-02")
        self.assertEqual(self.page._selected_month(("Period B", "start")), "2023-01")
        self.assertEqual(self.page._selected_month(("Period B", "end")), "2023-01")
        self.assertEqual(self.page._comparison.period_a.total_plays, 3)
        self.assertEqual(self.page._comparison.period_a.unique_artists, 2)
        self.assertEqual(self.page._comparison.period_a.top_artist, "Alpha")
        self.assertIn("Alpha", " ".join(self._texts(self.page._results)))
        self.assertIsNotNone(self.page._figure)
        chart_axis = self.page._figure.axes[0]
        chart_categories = [tick.get_text() for tick in chart_axis.get_xticklabels()]
        rendered_counts = {
            container.get_label(): {
                artist: bar.get_height()
                for artist, bar in zip(chart_categories, container.patches)
            }
            for container in chart_axis.containers
        }
        self.assertEqual(
            rendered_counts,
            {
                "Period A": {"Alpha": 2, "Beta": 1, "Gamma": 0},
                "Period B": {"Alpha": 0, "Beta": 1, "Gamma": 1},
            },
        )
        first_start = self.page._range_vars[("Period A", "start")][1]
        first_start.set("February")
        self.page._selection_changed()
        self.root.update_idletasks()
        self.assertEqual(self.page._comparison.period_a.total_plays, 1)

    def test_top_artist_chart_is_capped_without_truncating_comparison_result(self):
        self.page.refresh(Analyser(many_artist_plays()))
        self.root.update_idletasks()

        self.assertEqual(len(self.page._comparison.only_in_a), 12)
        self.assertEqual(len(self.page._comparison.only_in_b), 12)
        artists_a = self.page._analyser.top_artists(
            5, self.page._period_bounds("Period A"),
        )
        artists_b = self.page._analyser.top_artists(
            5, self.page._period_bounds("Period B"),
        )
        expected = {row[0] for row in artists_a} | {row[0] for row in artists_b}
        categories = [tick.get_text() for tick in self.page._figure.axes[0].get_xticklabels()]
        self.assertLessEqual(len(categories), 10)
        self.assertEqual(set(categories), expected)
        self.assertEqual(self.page._comparison.period_a.total_plays, 78)
        self.assertEqual(self.page._comparison.period_b.total_plays, 78)

    def test_what_changed_initial_batch_and_show_more_keep_full_data(self):
        self.page.refresh(Analyser(many_artist_plays()))
        self.root.update_idletasks()

        expected = (
            [("Only in Period A", artist) for artist in self.page._comparison.only_in_a]
            + [("Only in Period B", artist) for artist in self.page._comparison.only_in_b]
        )
        self.assertEqual(len(expected), 24)
        self.assertEqual(self.page._change_items, expected)
        self.assertEqual(self.page._change_visible_count, 6)
        self.assertEqual(self.page._change_summary.cget("text"), "Showing 6 of 24 changes")
        self.assertEqual(len(self.page._change_content.winfo_children()), 7)
        self.assertEqual(self.page._show_more_button.winfo_manager(), "pack")

        self.page._show_more_button.invoke()
        self.root.update_idletasks()
        self.assertEqual(self.page._change_visible_count, 12)
        self.assertEqual(self.page._change_summary.cget("text"), "Showing 12 of 24 changes")
        self.page._show_more_button.invoke()
        self.root.update_idletasks()
        self.assertEqual(self.page._change_visible_count, 18)
        self.page._show_more_button.invoke()
        self.root.update_idletasks()
        self.assertEqual(self.page._change_visible_count, 24)
        self.assertEqual(self.page._show_more_button.winfo_manager(), "")
        self.assertEqual(len(self.page._comparison.only_in_a), 12)
        self.assertEqual(len(self.page._comparison.only_in_b), 12)

    def test_period_changes_replace_results_and_chart_without_accumulation(self):
        self.page.refresh(Analyser(sample_plays()))
        menus = {key: pair for key, pair in self.page._range_menus.items()}
        shell = self.page._shell
        result_child_count = len(self.page._results.winfo_children())
        self.assertEqual(len(plt.get_fignums()), 1)

        for start_month in ("February", "January", "February", "January"):
            self.page._range_vars[("Period A", "start")][1].set(start_month)
            self.page._selection_changed()
            self.root.update_idletasks()
            self.assertEqual(len(plt.get_fignums()), 1)
            self.assertEqual(len(self.page._results.winfo_children()), result_child_count)
            self.assertIs(self.page._shell, shell)
            for key, pair in menus.items():
                self.assertIs(self.page._range_menus[key][0], pair[0])
                self.assertIs(self.page._range_menus[key][1], pair[1])
        self.assertEqual(self.page._comparison.period_a.total_plays, 3)

    def test_empty_range_chart_and_refresh_have_no_widget_or_figure_leaks(self):
        analyser = Analyser(sample_plays())
        self.page.refresh(analyser)
        initial_children = len(self.page.winfo_children())
        option_menus = {
            key: menus for key, menus in self.page._range_menus.items()
        }
        self.page.refresh(analyser)
        self.page.refresh(analyser)
        self.root.update_idletasks()
        self.assertEqual(len(self.page.winfo_children()), initial_children)
        for key, menus in option_menus.items():
            self.assertIs(self.page._range_menus[key][0], menus[0])
            self.assertIs(self.page._range_menus[key][1], menus[1])
        self.assertEqual(len(plt.get_fignums()), 1)
        self.page._range_vars[("Period A", "start")][1].set("March")
        self.page._range_vars[("Period A", "end")][1].set("February")
        self.page._selection_changed()
        self.assertTrue(any("Choose a start month" in text for text in self._texts(self.page._results)))


if __name__ == "__main__":
    unittest.main(verbosity=2)

