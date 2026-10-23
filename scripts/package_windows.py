"""Собрать Windows x64 EXE, проверить Chromium и подготовить релизные файлы."""
from __future__ import annotations

import hashlib
import importlib.metadata as metadata
import json
import os
import platform
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def collect_licenses(destination: Path) -> None:
    """Сохранить исходные лицензии установленных Qt/Python и сборочных пакетов."""
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    shutil.copytree(ROOT / "third_party_licenses", destination, dirs_exist_ok=True)
    for name in ("PySide6", "PySide6_Addons", "PySide6_Essentials", "shiboken6", "pyinstaller"):
        distribution = metadata.distribution(name)
        for item in distribution.files or []:
            parts = [p.lower() for p in item.parts]
            if (any(p in ("licenses", "license") for p in parts)
                    or item.name.lower().startswith(("license", "notice", "copying"))):
                source = Path(distribution.locate_file(item))
                if source.is_file() and ".." not in item.parts:
                    target = destination / name / item
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
    for name in ("LICENSE.txt", "LICENSE"):
        source = Path(sys.base_prefix) / name
        if source.is_file():
            shutil.copy2(source, destination / "PYTHON-LICENSE.txt")
            break


def main() -> None:
    if sys.platform != "win32" or struct.calcsize("P") != 8:
        raise RuntimeError("Windows x64 Python is required; cross-compilation is unsupported")
    os.chdir(ROOT)
    version = (ROOT / "VERSION").read_text().strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Invalid release version")
    collect_licenses(ROOT / ".build-licenses")
    subprocess.run([sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", "EQueueBrowser.spec"], check=True)
    binary = ROOT / "dist/EQueueBrowser.exe"
    with binary.open("rb") as stream:
        if stream.read(2) != b"MZ":
            raise RuntimeError("Output is not a Windows executable")
        stream.seek(0x3C)
        offset = struct.unpack("<I", stream.read(4))[0]
        stream.seek(offset)
        if stream.read(4) != b"PE\0\0" or struct.unpack("<H", stream.read(2))[0] != 0x8664:
            raise RuntimeError("Output is not a PE x64 executable")
    name = f"EQueueBrowser-{version}-windows-x64"
    stage = ROOT / "dist" / name
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir()
    shutil.copy2(binary, stage / "EQueueBrowser.exe")
    for file in ("config.json", "README.md", "THIRD_PARTY_NOTICES.md"):
        shutil.copy2(ROOT / file, stage / file)
    shutil.copytree(ROOT / ".build-licenses", stage / "third_party_licenses")
    info = {
        "version": version,
        "source_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(), "python": sys.version,
        "dependencies": {key: metadata.version(key) for key in
            ("PySide6", "PySide6_Addons", "PySide6_Essentials", "shiboken6", "pyinstaller")},
        "authenticode_signed": False,
    }
    (stage / "BUILD_INFO.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    report = stage / "smoke-test.json"
    # CI only: offscreen Qt still uses the real packaged Chromium subprocess.
    environment = dict(os.environ, QT_QPA_PLATFORM="offscreen", QTWEBENGINE_CHROMIUM_FLAGS="--disable-gpu")
    with tempfile.TemporaryDirectory() as temporary:
        cwd = Path(temporary)
        launch_dir = cwd / "installed"
        launch_dir.mkdir()
        launch_exe = launch_dir / "EQueueBrowser.exe"
        shutil.copy2(stage / "EQueueBrowser.exe", launch_exe)
        shutil.copy2(stage / "config.json", launch_dir / "config.json")
        subprocess.run([str(launch_exe), "--smoke-test", str(report)],
                       cwd=cwd, env=environment, check=True, timeout=90)
    if not json.loads(report.read_text(encoding="utf-8"))["success"]:
        raise RuntimeError("Packaged Chromium smoke test failed")
    release = ROOT / "release"
    release.mkdir(exist_ok=True)
    standalone = release / f"{name}.exe"
    shutil.copy2(binary, standalone)
    archive = release / f"{name}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        for file in sorted(stage.rglob("*")):
            if file.is_file():
                output.write(file, Path(name) / file.relative_to(stage))
    shutil.copy2(stage / "BUILD_INFO.json", release / "BUILD_INFO.json")
    shutil.copy2(report, release / "smoke-test.json")
    shutil.copy2(stage / "config.json", release / "config.json")
    sums = []
    for file in (standalone, archive, release / "config.json"):
        with file.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        sums.append(f"{digest}  {file.name}\n")
    (release / "SHA256SUMS").write_text("".join(sums), encoding="ascii")
    print(json.dumps(info, indent=2))
    print(f"Release prepared: {archive}")


if __name__ == "__main__":
    main()
