"""Focused validation for the Wrapped story page and its analyzer data."""
from datetime import datetime
import inspect
import tkinter
import unittest

from core.analyser import Analyser
from core.models import Play

try:
    import customtkinter
    import matplotlib.pyplot as plt
    from ui.pages.base_page import BasePage
    from ui.pages.wrapped import WrappedPage
    UI_IMPORT_ERROR = None
except ImportError as exc:
    customtkinter = None
    plt = None
    BasePage = None
    WrappedPage = None
    UI_IMPORT_ERROR = exc


def wrapped_plays():
    return [
        Play(datetime(2022, 3, 2, 20), "North Star", "Blue Hour", 210_000),
        Play(datetime(2022, 3, 2, 22), "North Star", "Blue Hour", 210_000),
        Play(datetime(2022, 4, 9, 22), "North Star", "Blue Hour", 210_000),
        Play(datetime(2022, 4, 10, 23), "Juniper", "Quiet Road", 180_000),
        Play(datetime(2023, 1, 5, 9), "Juniper", "Quiet Road", 180_000),
    ]


class WrappedAnalyserTests(unittest.TestCase):
    def test_year_summary_and_scoped_hour_counts(self):
        analyser = Analyser(wrapped_plays())
        summary = analyser.wrapped_summary(2022)
        self.assertEqual(summary.total_plays, 4)
        self.assertEqual(summary.top_artist, "North Star")
        self.assertEqual(summary.top_track, "Blue Hour")
        self.assertEqual(summary.unique_artists, 2)
        self.assertEqual(analyser.listening_by_hour((datetime(2022, 1, 1), datetime(2023, 1, 1)))[22], 2)
        self.assertEqual(sum(analyser.listening_by_hour((datetime(2022, 1, 1), datetime(2023, 1, 1))).values()), summary.total_plays)


@unittest.skipUnless(UI_IMPORT_ERROR is None, f"UI dependencies unavailable: {UI_IMPORT_ERROR}")
class WrappedPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = customtkinter.CTk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def setUp(self):
        self.page = WrappedPage(self.root)
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
            found.extend(WrappedPageTests._texts(child))
        return found

    def test_import_inheritance_concrete_and_no_data(self):
        self.assertIsNotNone(WrappedPage)
        self.assertTrue(issubclass(WrappedPage, BasePage))
        self.assertFalse(inspect.isabstract(WrappedPage))
        self.page.refresh(None)
        self.root.update_idletasks()
        self.assertTrue(any("Load your Spotify data" in text for text in self._texts(self.page)))
        self.assertEqual(plt.get_fignums(), [])

    def test_story_content_is_derived_from_analyser(self):
        analyser = Analyser(wrapped_plays())
        self.page.refresh(analyser)
        summary = analyser.wrapped_summary(2023)
        # Default year is the latest available year, and its story uses the
        # actual year summary returned by the Analyser.
        self.assertEqual(self.page._selected_year, str(summary.year))
        self.assertGreaterEqual(len(self.page._slides), 8)
        self.assertTrue(any(str(summary.total_plays) in slide["subtitle"] for slide in self.page._slides))
        self.assertTrue(any(slide["value"] == summary.top_artist for slide in self.page._slides))
        self.assertTrue(any(slide["value"] == summary.top_track for slide in self.page._slides))
        self.assertTrue(any(slide["value"] == summary.personality_type for slide in self.page._slides))
        self.assertTrue(any(slide["value"] == summary.top_month for slide in self.page._slides))

    def test_forward_backward_navigation_indicator_and_bounds(self):
        self.page.refresh(Analyser(wrapped_plays()))
        self.assertEqual(self.page._index, 0)
        self.assertEqual(self.page._indicator.cget("text"), f"1 / {len(self.page._slides)}")
        self.assertEqual(self.page._previous_button.cget("state"), "disabled")
        self.page.previous_slide()
        self.assertEqual(self.page._index, 0)
        self.page.next_slide()
        self.assertEqual(self.page._index, 1)
        self.assertEqual(self.page._indicator.cget("text"), f"2 / {len(self.page._slides)}")
        self.page.previous_slide()
        self.assertEqual(self.page._index, 0)
        for _ in range(len(self.page._slides) + 2):
            self.page.next_slide()
        self.assertEqual(self.page._index, len(self.page._slides) - 1)
        self.assertEqual(self.page._next_button.cget("state"), "disabled")
        self.page.next_slide()
        self.assertEqual(self.page._index, len(self.page._slides) - 1)
        self.assertEqual(self.page._indicator.cget("text"), f"{len(self.page._slides)} / {len(self.page._slides)}")

    def test_year_selection_rebuilds_story(self):
        self.page.refresh(Analyser(wrapped_plays()))
        self.page._on_year_changed("2022")
        self.root.update_idletasks()
        self.assertEqual(self.page._selected_year, "2022")
        self.assertEqual(self.page._index, 0)
        self.assertEqual(self.page._slides[0]["title"], "Your 2022")
        self.assertEqual(self.page._slides[2]["value"], str(Analyser(wrapped_plays()).wrapped_summary(2022).total_plays))

    def test_charts_render_and_refresh_does_not_leak_widgets_or_figures(self):
        analyser = Analyser(wrapped_plays())
        self.page.refresh(analyser)
        child_count = len(self.page.winfo_children())
        artist_slide = next(i for i, slide in enumerate(self.page._slides) if slide.get("chart") == "artists")
        self.page.show_slide(artist_slide, animate=False)
        self.root.update_idletasks()
        self.assertIsNotNone(self.page._figure)
        self.assertEqual(len(plt.get_fignums()), 1)
        hour_slide = next(i for i, slide in enumerate(self.page._slides) if slide.get("chart") == "hours")
        self.page.show_slide(hour_slide, animate=False)
        self.assertEqual(len(plt.get_fignums()), 1)
        self.page.refresh(analyser)
        self.root.update_idletasks()
        self.assertEqual(len(self.page.winfo_children()), child_count)
        self.assertEqual(plt.get_fignums(), [])

    def test_single_play_history_renders_without_errors(self):
        analyser = Analyser([Play(datetime(2024, 6, 1, 7), "Solo", "Only Track", 30_000)])
        self.page.refresh(analyser)
        self.root.update_idletasks()
        summary = analyser.wrapped_summary(2024)
        self.assertEqual(self.page._slides[0]["title"], "Your 2024")
        self.assertEqual(self.page._slides[2]["value"], str(summary.total_plays))
        self.assertTrue(any("No strong repeat pattern" in slide["value"] for slide in self.page._slides))


if __name__ == "__main__":
    unittest.main(verbosity=2)
