"""Turnuva yeniden-başlatma (B bug) + zorluk hero-masası elit oranı (C bug).

B: İkinci turnuva başlatınca SPACE/aksiyon tuşları ölüydü (el ilerlemiyordu).
   Sebep: QShortcut'lar her _start_tournament'ta kalıcı `self`'e tekrar
   bağlanıp Qt 'ambiguous shortcut' durumuna düşürüyordu.
C: Hero masasına elit (GTO/ICM expert, Negreanu...) eklenince zorluk hâlâ
   'KOLAY' diyordu — toughness yalnız alan-geneli strong oranına bakıyordu.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from app.main import prepare_qt_platform_plugins
    prepare_qt_platform_plugins()
except Exception:
    pass


# ── C: zorluk hero masasındaki elit oyuncuları yansıtır ──────────────────

def test_toughness_reflects_hero_table_sharks():
    from app.simulator.mtt_field import MTTField
    soft = MTTField(field_size=200, tier="Mikro ($1-5)",
                    hero_archetypes=["Fish"] * 8)
    sharks = MTTField(field_size=200, tier="Mikro ($1-5)",
                      hero_archetypes=["GTO Expert", "ICM Expert",
                                       "Daniel Negreanu", "Shark", "Solver Bot",
                                       "Phil Ivey", "Fish", "TAG"])
    _, soft_tag = soft.toughness()
    _, sharks_tag = sharks.toughness()
    assert "KOLAY" in soft_tag, soft_tag
    assert "KOLAY" not in sharks_tag, sharks_tag   # 6/8 elit masa kolay olamaz
    assert sharks.hero_strong_fraction > soft.hero_strong_fraction


def test_no_hero_archetypes_keeps_field_only_behaviour():
    from app.simulator.mtt_field import MTTField
    f = MTTField(field_size=200, tier="Mikro ($1-5)")
    assert f.hero_strong_fraction == 0.0   # geriye dönük uyum


# ── B: yeniden başlatma kısayolları çoğaltmaz ────────────────────────────

def test_restart_does_not_duplicate_shortcuts():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QShortcut, QKeySequence
    from PySide6.QtCore import Qt
    from app.core.app_state import AppState
    from app.ui.screens.tournament_simulator import TournamentSimulatorScreen

    QApplication.instance() or QApplication([])
    scr = TournamentSimulatorScreen(AppState())
    # _end_and_restart() canlı turnuvada _confirm_abort() modal QMessageBox açar;
    # offscreen test'te kapatacak kullanıcı yok → exec() sonsuza bloke (hang).
    # Onayı otomatik 'Yes' yap (docstring: 'Test'te monkeypatch'lenebilir').
    scr._confirm_abort = lambda: True
    scr._start_tournament()
    scr._end_and_restart()
    scr._start_tournament()

    space_seq = QKeySequence(Qt.Key_Space)
    space_shortcuts = [s for s in scr.findChildren(QShortcut)
                       if s.key() == space_seq]
    assert len(space_shortcuts) == 1, (
        f"SPACE shortcut çoğaldı ({len(space_shortcuts)}) → ambiguous → ölü tuş")
    scr._end_and_restart()
