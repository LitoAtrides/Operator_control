"""Проверки геометрии настоящих Qt-виджетов без запуска Chromium и сервера."""
import importlib.util
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HAS_QT = importlib.util.find_spec("PySide6") is not None
if HAS_QT:
    from PySide6.QtWidgets import QApplication, QWidget
    from config_loader import AppConfig, ConnectionConfig
    from main import OperatorWindow

    class FakeBrowser(QWidget):
        def setZoomFactor(self, value):
            self._zoom = value

        def zoomFactor(self):
            return self._zoom


@unittest.skipUnless(HAS_QT, "Для проверки Qt-разметки нужен PySide6")
class OperatorLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_window(self, numbers, columns=None, mode="orc"):
        config = AppConfig(ConnectionConfig("http", "localhost", 8080), mode, "1", numbers, columns)
        with patch.object(OperatorWindow, "_create_browser", side_effect=lambda address: FakeBrowser()):
            window = OperatorWindow(config)
        self.addCleanup(window.close)
        self.addCleanup(window.deleteLater)
        window.resize(1500, 900)
        window.show()
        self.app.processEvents()
        return window

    def test_ten_operators_in_two_equal_rows(self):
        window = self.make_window(list(range(1, 11)), 5)
        grid = window._orc_scroll_area.widget().layout()
        self.assertEqual((grid.rowCount(), grid.columnCount()), (2, 5))
        for index, view in enumerate(window._orc_views):
            self.assertIs(grid.itemAtPosition(*divmod(index, 5)).widget().browser, view)
        sizes = [(v.width(), v.height()) for v in window._orc_views]
        self.assertLessEqual(max(w for w, h in sizes) - min(w for w, h in sizes), 1)
        self.assertLessEqual(max(h for w, h in sizes) - min(h for w, h in sizes), 1)
        old_height = window._orc_views[0].height()
        window.resize(1000, 600)
        self.app.processEvents()
        self.assertLess(window._orc_views[0].height(), old_height)

    def test_default_single_row(self):
        window = self.make_window([1, 2, 3])
        grid = window._orc_scroll_area.widget().layout()
        self.assertEqual((grid.rowCount(), grid.columnCount()), (1, 3))

    def test_incomplete_row_keeps_empty_cell(self):
        window = self.make_window([1, 2, 3, 4, 5], 3)
        grid = window._orc_scroll_area.widget().layout()
        self.assertEqual((grid.rowCount(), grid.columnCount()), (2, 3))
        self.assertIsNone(grid.itemAtPosition(1, 2))

    def test_single_column_and_excess_columns(self):
        for columns, expected in ((1, (3, 1)), (10, (1, 3))):
            with self.subTest(columns=columns):
                window = self.make_window([1, 2, 3], columns)
                grid = window._orc_scroll_area.widget().layout()
                self.assertEqual((grid.rowCount(), grid.columnCount()), expected)

    def test_no_operators(self):
        window = self.make_window([], 5)
        self.assertEqual(window._orc_views, [])
        self.assertIsNotNone(window._orc_scroll_area.widget().layout().itemAtPosition(0, 0))

    def test_other_modes_unchanged(self):
        for mode in ("display", "info"):
            with self.subTest(mode=mode):
                window = self.make_window([1, 2], 1, mode)
                self.assertIsNone(window._orc_scroll_area)
                self.assertEqual(window.centralWidget().layout().count(), 1)
