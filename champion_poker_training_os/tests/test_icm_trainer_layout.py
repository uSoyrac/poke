"""Poker masası RESPONSIVE ölçekleme + ICM trainer yerleşimi (G / responsive).

Eskiden masa büyük katı min-size'a (820×520) sahipti → küçük pencerede yan
paneli/aksiyonu ekran dışına itiyordu (responsive değil). Artık kart+koltuk
boyutu _scale() ile tablo boyutuna göre küçülür → masa dar alana sığar,
seat'ler örtüşmez. Min küçük tutulur.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from app.main import prepare_qt_platform_plugins
    prepare_qt_platform_plugins()
except Exception:
    pass


def test_table_scale_shrinks_when_small_and_unity_at_baseline():
    from PySide6.QtWidgets import QApplication
    from app.ui.components.poker_table import LivePokerTable
    QApplication.instance() or QApplication([])
    t = LivePokerTable()
    t.resize(760, 420)          # baseline → ~1.0
    assert abs(t._scale() - 1.0) < 0.05
    t.resize(480, 320)          # küçük → belirgin küçülme (responsive)
    assert t._scale() < 0.85, t._scale()
    # Genişlik DE dikkate alınır: dar-ama-uzun alanda da küçülür
    t.resize(520, 900)
    assert t._scale() < 0.8, "dar genişlikte ölçek küçülmeli (genişlik-duyarlı)"


def test_icm_table_has_small_responsive_minimum():
    from PySide6.QtWidgets import QApplication
    from app.core.app_state import AppState
    from app.ui.screens.icm_trainer import IcmTrainerScreen
    QApplication.instance() or QApplication([])
    s = IcmTrainerScreen(AppState())
    # Büyük instance min KOYULMAMALI → dar pencerede tablo küçülüp yan panele
    # yer açabilsin (responsive). Bileşen alt sınırı 480×320.
    assert s.table.minimumWidth() <= 600, s.table.minimumWidth()


def test_cards_scale_down_at_small_table_size():
    """Hole/back kartları küçük masada base boyutun altına iner (örtüşmeyi önler)."""
    from PySide6.QtWidgets import QApplication
    from app.ui.components.poker_table import LivePokerTable, SeatState
    QApplication.instance() or QApplication([])
    t = LivePokerTable()
    seats = [SeatState(pos="BTN", name="Hero", stack=100.0, is_hero=True,
                       hole="AsKh")]
    for p in ("SB", "BB", "UTG", "CO"):
        seats.append(SeatState(pos=p, name="Bot", stack=100.0))
    t.render_state(seats, 0, 0, street="preflop", board=[], pot=1.5)
    t.resize(500, 330)
    t._layout_children()
    holes = [w for w in t._hole_widgets if hasattr(w, "_base_w")]
    assert holes, "hole widget yok"
    assert any(w.width() < w._base_w for w in holes), "kartlar küçük masada ölçeklenmiyor"
