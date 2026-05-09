from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path


def pytest_configure() -> None:
    """Prepare Qt for headless widget smoke tests.

    Some macOS/PySide wheel installs contain valid platform plugins that Qt
    cannot enumerate from the original wheel directory because of filesystem
    metadata. Copying the dylibs without extended attributes into tmp makes
    plain `pytest tests/ -q` work consistently.
    """
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if os.environ.get("QT_QPA_PLATFORM_PLUGIN_PATH"):
        return

    try:
        from PySide6.QtCore import QDir, QLibraryInfo
    except Exception:
        return

    plugin_root = Path(QLibraryInfo.path(QLibraryInfo.PluginsPath))
    platform_dir = plugin_root / "platforms"
    if not platform_dir.exists():
        return

    visible = QDir(str(platform_dir)).entryList(["libq*.dylib", "q*.dll", "libq*.so"], QDir.Files)
    if visible:
        return

    temp_dir = Path(tempfile.gettempdir()) / "champion_poker_training_os_qt_platforms"
    temp_dir.mkdir(parents=True, exist_ok=True)
    for pattern in ("libq*.dylib", "q*.dll", "libq*.so"):
        for plugin in platform_dir.glob(pattern):
            target = temp_dir / plugin.name
            if target.exists():
                target.unlink()
            shutil.copyfile(plugin, target)
            target.chmod(0o755)
    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(temp_dir)

