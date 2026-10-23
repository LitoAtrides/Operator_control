"""Проверки масштаба и сохранения в отдельном временном файле настроек."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HAS_QT = importlib.util.find_spec("PySide6") is not None
if HAS_QT:
    from PySide6.QtCore import QSettings, Qt
    from PySide6.QtTest import QTest, QSignalSpy
    from PySide6.QtWidgets import QApplication, QWidget, QHBoxLayout
    from config_loader import AppConfig, ConnectionConfig
    from operator_panel import OperatorPanel, zoom_key

    class Browser(QWidget):
        def __init__(self):
            super().__init__()
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self._zoom = 1.0

        def setZoomFactor(self, value):
            self._zoom = value

        def zoomFactor(self):
            return self._zoom


@unittest.skipUnless(HAS_QT, "Для проверки масштаба нужен PySide6")
class OperatorZoomTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = str(Path(directory.name) / "zoom.ini")
        self.settings = QSettings(self.path, QSettings.Format.IniFormat)
        self.config = AppConfig(ConnectionConfig("http", "server", 8080), "orc", None, [1, 2])

    def panel(self, number=1, config=None, settings=None):
        panel = OperatorPanel(Browser(), number, zoom_key(config or self.config, number),
                              settings if settings is not None else self.settings)
        self.addCleanup(panel.deleteLater)
        self.addCleanup(panel.close)
        return panel

    def test_controls_and_reset(self):
        panel = self.panel()
        self.assertEqual(panel.browser.zoomFactor(), 1)
        panel.plus.click()
        self.assertAlmostEqual(panel.browser.zoomFactor(), 1.1)
        self.assertEqual(panel.reset.text(), "110%")
        panel.minus.click()
        self.assertEqual(panel.browser.zoomFactor(), 1)
        panel.set_zoom(150)
        panel.reset.click()
        self.assertEqual(panel.browser.zoomFactor(), 1)
        self.assertEqual(self.settings.value(panel.key), 100)

    def test_restores_from_disk_without_changing_other_operator(self):
        first, second = self.panel(1), self.panel(2)
        first.set_zoom(70)
        self.assertEqual(second.browser.zoomFactor(), 1)
        second.set_zoom(140)
        fresh_settings = QSettings(self.path, QSettings.Format.IniFormat)
        self.assertAlmostEqual(self.panel(2, settings=fresh_settings).browser.zoomFactor(), 1.4)
        self.assertAlmostEqual(self.panel(1, settings=fresh_settings).browser.zoomFactor(), 0.7)
        self.assertIn("70", Path(self.path).read_text())

    def test_servers_and_protocols_are_isolated(self):
        self.panel().set_zoom(60)
        for connection in (ConnectionConfig("http", "other", 8080),
                           ConnectionConfig("http", "server", 8090),
                           ConnectionConfig("https", "server", 8080)):
            config = AppConfig(connection, "orc", None, [1])
            self.assertEqual(self.panel(config=config).browser.zoomFactor(), 1)

    def test_limits_and_corrupt_settings(self):
        panel = self.panel()
        panel.set_zoom(10)
        self.assertEqual(panel.browser.zoomFactor(), 0.25)
        self.assertFalse(panel.minus.isEnabled())
        panel.set_zoom(1000)
        self.assertEqual(panel.browser.zoomFactor(), 3)
        self.assertFalse(panel.plus.isEnabled())
        for value in ("invalid", "nan", "inf", {}):
            with self.subTest(value=value):
                self.settings.setValue(panel.key, value)
                panel.reload_zoom()
                self.assertEqual(panel.browser.zoomFactor(), 1)

    def test_shortcut_affects_only_focused_panel(self):
        root = QWidget()
        self.addCleanup(root.deleteLater)
        self.addCleanup(root.close)
        layout = QHBoxLayout(root)
        first, second = self.panel(1), self.panel(2)
        layout.addWidget(first)
        layout.addWidget(second)
        root.show()
        root.activateWindow()
        second.browser.setFocus()
        self.app.processEvents()
        QTest.keyClick(second.browser, Qt.Key.Key_Equal, Qt.KeyboardModifier.ControlModifier)
        self.assertAlmostEqual(second.browser.zoomFactor(), 1.1)
        self.assertEqual(first.browser.zoomFactor(), 1)
        QTest.keyClick(second.browser, Qt.Key.Key_0, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(second.browser.zoomFactor(), 1)

    def test_settings_write_error_is_reported(self):
        panel = self.panel()
        spy = QSignalSpy(panel.save_failed)
        with patch.object(self.settings, "status", return_value=QSettings.Status.AccessError):
            with self.assertLogs(level="ERROR"):
                panel.set_zoom(120)
        self.assertEqual(spy.count(), 1)
        self.assertAlmostEqual(panel.browser.zoomFactor(), 1.2)
