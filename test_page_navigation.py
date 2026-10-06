"""Regression checks for page routing and persistent Comparison menus."""
import unittest
from unittest.mock import Mock, patch

try:
    import customtkinter
    from core.analyser import Analyser
    from core.models import Play
    from datetime import datetime
    from ui.app import App
    from ui.pages.abandoned import AbandonedPage
    from ui.pages.comparison import ComparisonPage
    from ui.sidebar import NAV_ITEMS
    UI_IMPORT_ERROR = None
except ImportError as exc:
    customtkinter = None
    App = None
    AbandonedPage = None
    ComparisonPage = None
    NAV_ITEMS = []
    UI_IMPORT_ERROR = exc


@unittest.skipUnless(UI_IMPORT_ERROR is None, f"UI dependencies unavailable: {UI_IMPORT_ERROR}")
class PageNavigationTests(unittest.TestCase):
    def setUp(self):
        self.app = App()
        self.app.withdraw()
        self._analyser = Analyser([
            Play(datetime(2022, 1, 2), "Artist A", "Track A", 60_000),
            Play(datetime(2022, 2, 2), "Artist B", "Track B", 60_000),
            Play(datetime(2023, 1, 2), "Artist A", "Track A", 60_000),
        ])

    def tearDown(self):
        if not self.app._is_closing:
            self.app._on_close()

    def _load_test_data(self, app=None):
        app = app or self.app
        app._analyser = self._analyser
        app.show_page("dashboard")
        return app

    @staticmethod
    def _assert_orderly_close(test_case, app, scheduled_callback=None):
        callback_errors = []
        app.report_callback_exception = lambda *args: callback_errors.append(args)
        with patch.object(app, "after_cancel", wraps=app.after_cancel) as cancel:
            app._on_close()
            app._on_close()  # shutdown must be idempotent
        test_case.assertTrue(app._is_closing)
        test_case.assertEqual(callback_errors, [])
        if scheduled_callback is not None:
            test_case.assertIn(
                scheduled_callback,
                [call.args[0] for call in cancel.call_args_list],
            )

    def test_sidebar_routes_abandoned_and_comparison_to_their_pages(self):
        self._load_test_data()
        routes = dict(NAV_ITEMS)
        self.assertEqual(routes["Abandoned Artists"], "abandoned")
        self.assertEqual(routes["Period Comparison"], "comparison")
        self.assertIsInstance(self.app._pages["abandoned"], AbandonedPage)
        self.assertIsInstance(self.app._pages["comparison"], ComparisonPage)

        comparison_page = self.app._pages["comparison"]
        comparison_refresh = Mock(wraps=comparison_page.refresh)
        comparison_page.refresh = comparison_refresh
        for _ in range(3):
            self.app.show_page("abandoned")
        comparison_refresh.assert_not_called()
        self.assertEqual(self.app._current_page_key, "abandoned")

        self.app.show_page("comparison")
        comparison_refresh.assert_called_once_with(self.app._analyser)

    def test_switching_repeatedly_keeps_comparison_option_menus(self):
        self._load_test_data()
        self.app.show_page("comparison")
        page = self.app._pages["comparison"]
        initial_menus = {
            key: menu_pair for key, menu_pair in page._range_menus.items()
        }
        for _ in range(5):
            self.app.show_page("abandoned")
            self.app.show_page("comparison")
        for key, menu_pair in initial_menus.items():
            self.assertIs(page._range_menus[key][0], menu_pair[0])
            self.assertIs(page._range_menus[key][1], menu_pair[1])
        self.assertEqual(len(page._range_menus), 4)

    def test_shutdown_is_safe_from_launch_loaded_pages_and_navigation(self):
        scenarios = (
            (self.app, None, False),
            (None, "dashboard", True),
            (None, "comparison", True),
            (None, "music_evolution", True),
            (None, "abandoned", True),
            (None, "switch", True),
        )
        for existing_app, page_key, load_data in scenarios:
            with self.subTest(page=page_key or "launch"):
                app = existing_app or App()
                app.withdraw()
                if load_data:
                    self._load_test_data(app)
                if page_key == "switch":
                    for key in ("dashboard", "comparison", "music_evolution", "abandoned"):
                        app.show_page(key)
                elif page_key:
                    app.show_page(page_key)
                scheduled = app.after(60_000, lambda: None)
                self._assert_orderly_close(self, app, scheduled)

    def test_comparison_keeps_customtkinter_canvas_separate_from_figure_canvas(self):
        self._load_test_data()
        page = self.app._pages["comparison"]
        self.app.show_page("comparison")
        ctk_canvas = page._canvas
        self.assertIsNotNone(page._figure_canvas)

        self.app.show_page("abandoned")
        self.app.show_page("comparison")
        self.assertIs(page._canvas, ctk_canvas)
        self.assertIsNot(page._figure_canvas, ctk_canvas)

    def test_root_is_destroyed_even_if_callback_cleanup_raises(self):
        with patch.object(App, "_cancel_pending_after_callbacks", side_effect=AttributeError("simulated cleanup race")):
            with self.assertRaisesRegex(AttributeError, "simulated cleanup race"):
                self.app._on_close()
        self.assertEqual(int(self.app.tk.call("winfo", "exists", self.app._w)), 0)



if __name__ == "__main__":
    unittest.main(verbosity=2)
