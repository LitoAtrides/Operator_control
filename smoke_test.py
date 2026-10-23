"""Проверка настоящего Qt Chromium без обращения к рабочему серверу."""
from __future__ import annotations

import json
import sys
import threading
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from PySide6.QtCore import QSettings, QStandardPaths, QTimer
from PySide6.QtWidgets import QApplication

from config_loader import AppConfig, ConnectionConfig, _resolve_config_path, load_config


def run_smoke_test(report_path: Path, window_class, setup_storage, setup_icon) -> int:
    """Открыть четыре пульта 2×2 на loopback, проверить JS и конфигурацию EXE."""
    report_path = report_path.resolve()
    result = {"success": False, "pages": {}, "errors": []}
    QStandardPaths.setTestModeEnabled(True)
    app = QApplication([sys.argv[0]])
    setup_storage(app)
    setup_icon(app)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            number = parse_qs(urlparse(self.path).query).get("orcnumber", [""])[0]
            body = ("<!doctype html><html><head><title>ORC " + number +
                    "</title></head><body><main id='probe'>operator:" + number + "</main></body></html>").encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    config = AppConfig(ConnectionConfig("http", "127.0.0.1", server.server_port),
                       "orc", None, [11, 12, 13, 14], 2)
    zoom_directory = tempfile.TemporaryDirectory()
    zoom_path = str(Path(zoom_directory.name) / "zoom.ini")
    zoom_settings = QSettings(zoom_path, QSettings.Format.IniFormat)
    window = window_class(config, zoom_settings=zoom_settings)
    finished = False

    def finish(error=None):
        nonlocal finished
        if finished:
            return
        finished = True
        if error:
            result["errors"].append(error)
        result["success"] = not result["errors"] and len(result["pages"]) == len(config.orc_numbers)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        window.close()
        window.deleteLater()
        QTimer.singleShot(100, lambda: app.exit(0 if result["success"] else 1))

    def checked(value, index):
        expected = f"operator:{config.orc_numbers[index]}"
        if value != expected:
            finish(f"Chromium JS result mismatch for pane {index}: {value!r}")
            return
        result["pages"][str(index)] = value
        if len(result["pages"]) == len(config.orc_numbers):
            try:
                verify_zoom()
            except Exception as exc:
                finish(f"Zoom verification failed: {exc}")
            else:
                finish()

    def verify_zoom():
        grid = window._orc_scroll_area.widget().layout()
        first = grid.itemAtPosition(0, 0).widget()
        second = grid.itemAtPosition(0, 1).widget()
        first.plus.click()
        if abs(first.browser.zoomFactor() - 1.1) > 0.001 or second.browser.zoomFactor() != 1:
            raise RuntimeError("Zoom is not independent for each browser")
        first.reset.click()
        if first.browser.zoomFactor() != 1:
            raise RuntimeError("Zoom reset failed")
        first.set_zoom(80)
        second.set_zoom(120)
        restored_settings = QSettings(zoom_path, QSettings.Format.IniFormat)
        restored_settings.sync()
        if restored_settings.status() != QSettings.Status.NoError:
            raise RuntimeError("Zoom settings could not be read from disk")
        for panel, expected in ((first, 0.8), (second, 1.2)):
            panel.set_zoom(100, persist=False)
            panel.settings = restored_settings
            panel.reload_zoom()
            if abs(panel.browser.zoomFactor() - expected) > 0.001:
                raise RuntimeError("Saved zoom was not restored")
        result["zoom"] = {"independent": True, "reset": True, "restored": [80, 120]}

    def loaded(ok, index):
        if not ok:
            finish(f"Failed to load local page in pane {index}")
            return
        window._orc_views[index].page().runJavaScript(
            "document.getElementById('probe').textContent",
            lambda value: checked(value, index))

    try:
        resolved = _resolve_config_path("config.json").resolve()
        load_config(resolved)
        result["configuration_readable"] = True
        if getattr(sys, "frozen", False):
            expected = Path(sys.executable).resolve().parent / "config.json"
            if resolved != expected:
                result["errors"].append("EXE did not select its external config.json")
        result["icon_available"] = not app.windowIcon().isNull()
        if not result["icon_available"]:
            result["errors"].append("Application icon unavailable")
        if len(window._orc_views) != 4:
            result["errors"].append("Expected four simultaneous browser panes")
        grid = window._orc_scroll_area.widget().layout()
        result["grid"] = {"rows": grid.rowCount(), "columns": grid.columnCount()}
        if result["grid"] != {"rows": 2, "columns": 2}:
            result["errors"].append("Expected a 2x2 browser grid")
        for index, view in enumerate(window._orc_views):
            if grid.itemAtPosition(*divmod(index, 2)).widget().browser is not view:
                result["errors"].append(f"Wrong grid position for pane {index}")
        for index, view in enumerate(window._orc_views):
            view.loadFinished.connect(lambda ok, i=index: loaded(ok, i))
        window.show()
        QTimer.singleShot(45000, lambda: finish("Chromium smoke test timed out"))
        code = app.exec()
        return code
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
        zoom_directory.cleanup()
