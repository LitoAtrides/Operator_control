"""Управление масштабом отдельного пульта и сохранение настроек пользователя."""
import hashlib
import logging
import math

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from url_builder import build_base_url


def zoom_key(config, number: int) -> str:
    server = build_base_url(config).lower()
    identifier = hashlib.sha256(server.encode("utf-8")).hexdigest()
    return f"operatorZoom/{identifier}/{number}"


class OperatorPanel(QWidget):
    """Пульт с независимым масштабом 25–300%, записываемым сразу после изменения."""

    save_failed = Signal(str)

    def __init__(self, browser, number, key, settings, parent=None):
        super().__init__(parent)
        self.browser = browser
        self.key = key
        self.settings = settings
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(4, 2, 4, 2)
        toolbar.setSpacing(4)
        toolbar.addWidget(QLabel(f"Пульт {number}"))
        toolbar.addStretch()
        self.minus = QPushButton("−")
        self.reset = QPushButton()
        self.plus = QPushButton("+")
        for button in (self.minus, self.reset, self.plus):
            button.setMinimumWidth(0)
            toolbar.addWidget(button)
        self.minus.setFixedWidth(26)
        self.plus.setFixedWidth(26)
        self.reset.setFixedWidth(52)
        self.minus.setToolTip("Уменьшить масштаб (Ctrl+-)")
        self.plus.setToolTip("Увеличить масштаб (Ctrl++)")
        self.reset.setToolTip("Вернуть масштаб 100% (Ctrl+0)")
        self.minus.setAccessibleName(f"Уменьшить масштаб пульта {number}")
        self.plus.setAccessibleName(f"Увеличить масштаб пульта {number}")
        self.reset.setAccessibleName(f"Сбросить масштаб пульта {number}")
        layout.addLayout(toolbar)
        layout.addWidget(browser, 1)
        self.minus.clicked.connect(lambda: self.change_zoom(-10))
        self.plus.clicked.connect(lambda: self.change_zoom(10))
        self.reset.clicked.connect(lambda: self.set_zoom(100))
        self._shortcuts = []
        for sequence, callback in (("Ctrl++", lambda: self.change_zoom(10)),
                                   ("Ctrl+=", lambda: self.change_zoom(10)),
                                   ("Ctrl+-", lambda: self.change_zoom(-10)),
                                   ("Ctrl+0", lambda: self.set_zoom(100))):
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(callback)
            self._shortcuts.append(shortcut)
        self.reload_zoom()

    def reload_zoom(self):
        try:
            percent = float(self.settings.value(self.key, 100))
            if not math.isfinite(percent):
                percent = 100
        except (TypeError, ValueError):
            percent = 100
        self.set_zoom(percent, persist=False)

    def change_zoom(self, delta):
        self.set_zoom(round(self.browser.zoomFactor() * 100) + delta)

    def set_zoom(self, percent, persist=True):
        percent = max(25, min(300, round(percent)))
        self.browser.setZoomFactor(percent / 100)
        self.reset.setText(f"{percent}%")
        self.minus.setEnabled(percent > 25)
        self.plus.setEnabled(percent < 300)
        if persist:
            self.settings.setValue(self.key, percent)
            self.settings.sync()
            if self.settings.status() != QSettings.Status.NoError:
                logging.error("Не удалось сохранить масштаб пульта: %s", self.key)
                self.save_failed.emit("Не удалось сохранить масштаб. Проверьте права записи настроек.")
