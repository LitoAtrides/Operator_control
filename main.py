"""Главный модуль запуска desktop-приложения для электронного табло."""
from __future__ import annotations

import logging
import sys

from PySide6.QtCore import Qt, QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QSizePolicy,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from config_loader import AppConfig, ConfigError, load_config
from url_builder import UrlBuilderError, build_mode_url


class OperatorWindow(QMainWindow):
    """Основное окно приложения, устанавливающее нужную разметку."""

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.config = config
        self.setWindowTitle("Электронная очередь")
        self.resize(1280, 720)
        self._setup_ui()

    def _setup_ui(self) -> None:
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setSpacing(12)
        layout.setContentsMargins(8, 8, 8, 8)

        if self.config.mode == "orc":
            layout.addWidget(self._build_orc_panel())
        else:
            browser = self._create_browser(self._mode_url())
            layout.addWidget(browser)

        self.setCentralWidget(central)

    def _build_orc_panel(self) -> QWidget:
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(12)
        container_layout.setContentsMargins(0, 0, 0, 0)

        if not self.config.orc_numbers:
            container_layout.addWidget(
                QLabel("Нет назначенных пультов для режима ORC.")
            )
        for orc_number in self.config.orc_numbers:
            browser = self._create_browser(
                build_mode_url(self.config, "orc", orc_number)
            )
            browser.setMinimumHeight(360)
            container_layout.addWidget(browser)

        container_layout.addStretch(1)
        scroll_area.setWidget(container)
        return scroll_area

    def _create_browser(self, address: str) -> QWebEngineView:
        view = QWebEngineView()
        view.setUrl(QUrl(address))
        view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        return view

    def _mode_url(self) -> str:
        return build_mode_url(self.config, self.config.mode)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )

    try:
        config = load_config()
    except ConfigError as exc:
        logging.error("Не удалось загрузить конфигурацию: %s", exc)
        sys.exit(1)

    app = QApplication(sys.argv)
    window = OperatorWindow(config)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except UrlBuilderError as exc:
        logging.error("Ошибка формирования URL: %s", exc)
        sys.exit(1)
