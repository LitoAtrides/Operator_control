"""Логика загрузки конфигурации из JSON."""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ConfigError(RuntimeError):
    """Ошибка, возникающая при проблемах с конфигурацией."""


@dataclass(frozen=True)
class ConnectionConfig:
    protocol: str
    ip: str
    port: int


@dataclass(frozen=True)
class AppConfig:
    connection: ConnectionConfig
    mode: str
    segment: str | None
    orc_numbers: list[int]


def _ensure_fields(data: dict[str, Any], keys: list[str], source: str) -> None:
    for key in keys:
        if key not in data:
            raise ConfigError(f"В конфигурации '{source}' нет ключа '{key}'")


def _resolve_config_path(path: Path | str) -> Path:
    candidate = Path(path)
    if candidate.exists():
        return candidate

    search_dirs = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        search_dirs.append(Path(meipass))
    exe_parent = Path(sys.executable).resolve().parent
    search_dirs.append(exe_parent)
    search_dirs.append(Path.cwd())

    for base in search_dirs:
        if base == candidate.parent:
            continue
        alt = base / candidate.name
        if alt.exists():
            return alt

    raise ConfigError(f"Файл конфигурации не найден: {candidate}")


def load_config(path: Path | str = "config.json") -> AppConfig:
    """Загружает конфигурацию из JSON-файла и собирает структуры."""

    path = _resolve_config_path(path)

    raw = json.loads(path.read_text(encoding="utf-8"))
    _ensure_fields(raw, ["connection", "mode"], "root")

    connection_data = raw["connection"]
    _ensure_fields(connection_data, ["protocol", "ip", "port"], "connection")

    try:
        connection = ConnectionConfig(
            protocol=str(connection_data["protocol"]),
            ip=str(connection_data["ip"]),
            port=int(connection_data["port"]),
        )
    except (ValueError, TypeError) as exc:
        raise ConfigError("Некорректные данные соединения") from exc

    mode = str(raw["mode"]).lower()
    segment = str(raw.get("segment")) if raw.get("segment") is not None else None
    orc_numbers_raw = raw.get("orcNumbers") or []
    if not isinstance(orc_numbers_raw, list):
        raise ConfigError("Ожидается список orcNumbers")

    orc_numbers: list[int] = []
    for value in orc_numbers_raw:
        try:
            orc_numbers.append(int(value))
        except (ValueError, TypeError) as exc:
            raise ConfigError("orcNumbers должен содержать числовые значения") from exc

    return AppConfig(
        connection=connection,
        mode=mode,
        segment=segment,
        orc_numbers=orc_numbers,
    )
