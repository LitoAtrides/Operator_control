"""Главный модуль запуска desktop-приложения для электронного Пульта оператора."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, QRect, QStandardPaths, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QHBoxLayout,
    QMainWindow,
    QSizePolicy,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile

from config_loader import AppConfig, ConfigError, load_config
from url_builder import UrlBuilderError, build_mode_url

APP_DATA_LOCATION = getattr(QStandardPaths, "AppDataLocation", 0)
FORCE_PERSISTENT_COOKIES = getattr(QWebEngineProfile, "ForcePersistentCookies", 0)
SIZE_POLICY_EXPANDING = getattr(QSizePolicy, "Expanding", 0)
SCROLLBAR_AS_NEEDED = getattr(Qt, "ScrollBarAsNeeded", 0)


def _resolve_resource_path(relative: str) -> Path:
    base = Path(__file__).resolve().parent
    candidate = base / relative
    if candidate.exists():
        return candidate

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        alt = Path(meipass) / relative
        if alt.exists():
            return alt

    return candidate


def _setup_application_icon(app: QApplication) -> None:
    icon_path = _resolve_resource_path("assets/EQueueBrowser.ico")
    if not icon_path.exists():
        logging.warning("Иконка приложения не найдена: %s", icon_path)
        return

    icon = QIcon(str(icon_path))
    if icon.isNull():
        logging.warning("Не удалось загрузить иконку: %s", icon_path)
        return

    app.setWindowIcon(icon)
    logging.info("Установлена иконка приложения: %s", icon_path)


_webengine_profile: QWebEngineProfile | None = None


def _setup_webengine_storage(app: QApplication) -> None:
    global _webengine_profile
    profile = QWebEngineProfile("EQueueBrowser", app)
    base_path = Path(
        QStandardPaths.writableLocation(APP_DATA_LOCATION)
        or Path(sys.executable).resolve().parent
    )
    storage_path = base_path / "EQueueBrowser" / "webengine"
    storage_path.mkdir(parents=True, exist_ok=True)
    profile.setPersistentStoragePath(str(storage_path))
    profile.setCachePath(str(storage_path / "cache"))
    profile.setPersistentCookiesPolicy(FORCE_PERSISTENT_COOKIES)
    _webengine_profile = profile
    logging.info("WebEngine storage: %s", storage_path)


# `initial_geometry` определяет точные координаты/размер окна.
class OperatorWindow(QMainWindow):
    """Основное окно приложения, устанавливающее нужную разметку."""

    def __init__(self, config: AppConfig, initial_geometry: QRect | None = None) -> None:
        super().__init__()
        self.config = config
        self.setWindowTitle("Пульт оператора")
        if initial_geometry is None:
            self.resize(1280, 720)
        else:
            self.setGeometry(initial_geometry)
        self._orc_views: list[QWebEngineView] = []
        self._orc_scroll_area: QScrollArea | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 0, 0, 0)

        if self.config.mode == "orc":
            layout.addWidget(self._build_orc_panel(), 1)
        else:
            browser = self._create_browser(self._mode_url())
            layout.addWidget(browser, 1)

        self.setCentralWidget(central)

    def _build_orc_panel(self) -> QWidget:
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setSizePolicy(SIZE_POLICY_EXPANDING, SIZE_POLICY_EXPANDING)
        scroll_area.setHorizontalScrollBarPolicy(SCROLLBAR_AS_NEEDED)
        scroll_area.setVerticalScrollBarPolicy(SCROLLBAR_AS_NEEDED)

        container = QWidget()
        container_layout = QHBoxLayout(container)
        container_layout.setSpacing(2)
        container_layout.setContentsMargins(0, 0, 0, 0)

        self._orc_views.clear()
        if not self.config.orc_numbers:
            container_layout.addWidget(
                QLabel("Нет назначенных пультов для режима ORC.")
            )
        for orc_number in self.config.orc_numbers:
            browser = self._create_browser(
                build_mode_url(self.config, "orc", orc_number)
            )
            browser.setMinimumHeight(360)
            browser.setMinimumWidth(640)
            self._orc_views.append(browser)
            container_layout.addWidget(browser, 1)

        scroll_area.setWidget(container)
        self._orc_scroll_area = scroll_area
        self._fit_orc_browsers()
        return scroll_area

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.config.mode == "orc":
            self._fit_orc_browsers()

    def _fit_orc_browsers(self) -> None:
        if not self._orc_views or self._orc_scroll_area is None:
            return
        viewport_size = self._orc_scroll_area.viewport().size()
        if viewport_size.isEmpty():
            return
        per_width = max(0, viewport_size.width() // len(self._orc_views))
        for view in self._orc_views:
            view.setMinimumSize(QSize(per_width, viewport_size.height()))

    @staticmethod
    def _create_browser(address: str) -> QWebEngineView:
        profile = _webengine_profile or QWebEngineProfile.defaultProfile()
        view = QWebEngineView()
        view.setPage(QWebEnginePage(profile, view))
        view.setUrl(QUrl(address))
        view.setSizePolicy(SIZE_POLICY_EXPANDING, SIZE_POLICY_EXPANDING)
        return view

    def _mode_url(self) -> str:
        return build_mode_url(self.config, self.config.mode)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )

    try:
        config = load_config()
    except ConfigError as config_error:
        logging.error("Не удалось загрузить конфигурацию: %s", config_error)
        sys.exit(1)

    app = QApplication(sys.argv)
    _setup_webengine_storage(app)
    _setup_application_icon(app)
    screen = app.primaryScreen()
    window_geometry: QRect | None = None
    if screen is not None:
        available_geometry = screen.availableGeometry()
        if available_geometry.isValid():
            window_geometry = available_geometry
        else:
            logging.warning(
                "Не удалось получить доступную геометрию экрана, используется размер по умолчанию"
            )
    else:
        logging.warning(
            "Не удалось определить основной экран, используется размер по умолчанию"
        )

    window = OperatorWindow(config, window_geometry)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except UrlBuilderError as url_error:
        logging.error("Ошибка формирования URL: %s", url_error)
        sys.exit(1)
