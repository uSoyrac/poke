"""ICM Trainer layout (F revizyonu) — masa küçük pencerede çökmemeli.

SS4: LivePokerTable yüzde-mutlak konumlu seat'leri alan daralınca pot/hero
kartlarının üstüne biniyordu ('iç içe' kaos). Min boyut çökmeyi engeller.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from app.main import prepare_qt_platform_plugins
    prepare_qt_platform_plugins()
except Exception:
    pass


def test_icm_table_has_collapse_proof_minimum():
    from PySide6.QtWidgets import QApplication
    from app.core.app_state import AppState
    from app.ui.screens.icm_trainer import IcmTrainerScreen
    QApplication.instance() or QApplication([])
    s = IcmTrainerScreen(AppState())
    ms = s.table.minimumSize()
    # Seat'lerin örtüşmeden yerleşmesi için yeterli min alan
    assert ms.width() >= 800 and ms.height() >= 500, (
        f"masa min boyutu yetersiz → küçük pencerede overlap riski: {ms}")


def test_icm_table_stays_at_minimum_when_squeezed():
    from PySide6.QtWidgets import QApplication
    from app.core.app_state import AppState
    from app.ui.screens.icm_trainer import IcmTrainerScreen
    QApplication.instance() or QApplication([])
    s = IcmTrainerScreen(AppState())
    s.resize(900, 600)
    QApplication.processEvents()
    # Dar pencerede bile masa min boyutun altına SIKIŞMAZ (scroll devreye girer)
    assert s.table.width() >= 800 and s.table.height() >= 500
