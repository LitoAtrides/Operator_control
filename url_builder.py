"""Генерация URL на основе конфигурации и выбранного режима."""
from __future__ import annotations

from urllib.parse import quote_plus

from config_loader import AppConfig


class UrlBuilderError(RuntimeError):
    """Ошибка при формировании URL."""


def _normalize_protocol(protocol: str) -> str:
    formatted = protocol.strip().lower()
    return formatted.rstrip(":/")


def build_base_url(config: AppConfig) -> str:
    """Собирает базовый адрес по настройкам соединения."""

    proto = _normalize_protocol(config.connection.protocol)
    return f"{proto}://{config.connection.ip}:{config.connection.port}"


def build_mode_url(config: AppConfig, mode: str, orc_number: int | None = None) -> str:
    """
    Формирует окончательный URL с параметрами под требуемый режим.

    :param config: загруженная конфигурация приложения
    :param mode: один из режимов display/info/orc
    :param orc_number: номер пульта (только для orc)
    """

    base = build_base_url(config)
    match mode:
        case "display":
            suffix = "/?app=equeuedisplay&platform=all"
        case "info":
            if not config.segment:
                raise UrlBuilderError("Отсутствует параметр segment для режима info")
            segment = quote_plus(config.segment)
            suffix = (
                "/?app=infopanel"
                f"&widget=map-infopanel-tv&panel=1&segment={segment}"
            )
        case "orc":
            if orc_number is None:
                raise UrlBuilderError("Для режима orc необходим orc_number")
            suffix = f"/?app=equeueorc&platform=all&orcnumber={orc_number}"
        case _:
            raise UrlBuilderError(f"Неизвестный режим '{mode}'")
    return f"{base.rstrip('/')}{suffix}"
