"""Проверки конфигурации и URL без запуска рабочего сервера."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config_loader import AppConfig, ConfigError, ConnectionConfig, _resolve_config_path, load_config
from url_builder import UrlBuilderError, build_mode_url


class ConfigurationTests(unittest.TestCase):
    def test_operator_columns_validation_and_backward_compatibility(self):
        raw = {"connection": {"protocol": "http", "ip": "host", "port": 8080},
               "mode": "orc", "orcNumbers": list(range(1, 11))}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            self.assertIsNone(load_config(path).orc_columns)
            for value in (None, 1, 5, 20):
                with self.subTest(valid=value):
                    raw["orcColumns"] = value
                    path.write_text(json.dumps(raw), encoding="utf-8")
                    self.assertEqual(load_config(path).orc_columns, value)
            for value in (0, -1, True, False, 2.5, "5", [], {}):
                with self.subTest(invalid=value):
                    raw["orcColumns"] = value
                    path.write_text(json.dumps(raw), encoding="utf-8")
                    with self.assertRaises(ConfigError):
                        load_config(path)

    def test_documented_configuration_ignores_comments(self):
        path = Path(__file__).resolve().parents[1] / "config.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        self.assertIsInstance(raw.pop("_comments"), dict)
        documented = load_config(path)
        with tempfile.TemporaryDirectory() as directory:
            plain = Path(directory) / "config.json"
            plain.write_text(json.dumps(raw), encoding="utf-8")
            self.assertEqual(documented, load_config(plain))

    def test_all_modes_and_encoding(self):
        config = AppConfig(ConnectionConfig(" HTTPS:// ", "server", 443), "orc", "a & b", [1, 2])
        self.assertEqual(build_mode_url(config, "display"), "https://server:443/?app=equeuedisplay&platform=all")
        self.assertIn("segment=a+%26+b", build_mode_url(config, "info"))
        self.assertTrue(build_mode_url(config, "orc", 2).endswith("orcnumber=2"))

    def test_invalid_modes_and_missing_parameters(self):
        config = AppConfig(ConnectionConfig("http", "server", 80), "orc", None, [])
        for mode in ("unknown", "info", "orc"):
            with self.subTest(mode=mode), self.assertRaises(UrlBuilderError):
                build_mode_url(config, mode)

    def test_load_operator_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({"connection": {"protocol": "http", "ip": "host", "port": "8080"},
                "mode": "ORC", "orcNumbers": [1, "2"]}), encoding="utf-8")
            config = load_config(path)
            self.assertEqual(config.orc_numbers, [1, 2])
            self.assertEqual(config.mode, "orc")

    def test_missing_required_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text("{}", encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(path)

    def test_frozen_executable_external_configuration_beats_bundle_and_cwd(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            exe = root / "app"
            bundle = root / "bundle"
            exe.mkdir(); bundle.mkdir()
            (exe / "config.json").write_text("{}")
            (bundle / "config.json").write_text("{}")
            with patch.object(sys, "frozen", True, create=True), \
                 patch.object(sys, "executable", str(exe / "EQueueBrowser.exe")), \
                 patch.object(sys, "_MEIPASS", str(bundle), create=True):
                self.assertEqual(_resolve_config_path("config.json"), (exe / "config.json").resolve())

    def test_explicit_path_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "custom.json"
            path.write_text("{}")
            self.assertEqual(_resolve_config_path(path), path)


if __name__ == "__main__":
    unittest.main()
