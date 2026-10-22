"""Проверка настоящего Qt Chromium без обращения к рабочему серверу."""
from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from PySide6.QtCore import QStandardPaths, QTimer
from PySide6.QtWidgets import QApplication

from config_loader import AppConfig, ConnectionConfig, _resolve_config_path, load_config


def run_smoke_test(report_path: Path, window_class, setup_storage, setup_icon) -> int:
    """Открыть два пульта на loopback, выполнить JS, проверить конфигурацию EXE."""
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
    config = AppConfig(ConnectionConfig("http", "127.0.0.1", server.server_port), "orc", None, [11, 12])
    window = window_class(config)
    finished = False

    def finish(error=None):
        nonlocal finished
        if finished:
            return
        finished = True
        if error:
            result["errors"].append(error)
        result["success"] = not result["errors"] and len(result["pages"]) == 2
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
        if len(result["pages"]) == 2:
            finish()

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
        if len(window._orc_views) != 2:
            result["errors"].append("Expected two simultaneous browser panes")
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
