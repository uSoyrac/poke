"""Oyuncu klasmanı (Pro/Mid/Hobby) — _SKILL_TIER üstüne kurulu tek kaynak.

Hero kendini Pro'ya karşı geliştirir, Mid'de gerçek seviyesini yaşar, Hobi'de
yumuşak alanda value basar. Klasman preset'leri tournament + cash'te seçilebilir.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.engine.bot_brain import (CLASS_PRESETS, archetype_class,
                                   archetype_skill)


def _qapp():
    from app.main import prepare_qt_platform_plugins
    prepare_qt_platform_plugins()
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_class_maps_from_skill_tier():
    assert archetype_class("Shark") == "pro"
    assert archetype_class("GTO Expert") == "pro"
    assert archetype_class("ICM Expert") == "pro"
    assert archetype_class("TAG") == "mid"
    assert archetype_class("Reg") == "mid"
    assert archetype_class("Fish") == "hobby"
    assert archetype_class("Calling Station") == "hobby"


def test_class_consistent_with_skill():
    skill_to_class = {"strong": "pro", "mid": "mid", "weak": "hobby"}
    for arch in ("Shark", "TAG", "Fish", "Nit", "LAG", "Solver Bot"):
        assert archetype_class(arch) == skill_to_class[archetype_skill(arch)]


def test_class_presets_are_internally_pure():
    for klass, archs in CLASS_PRESETS.items():
        assert archs, f"{klass} preset boş"
        assert all(archetype_class(a) == klass for a in archs), (
            f"{klass} preset'inde yanlış-sınıf arketip: "
            f"{[a for a in archs if archetype_class(a) != klass]}")


def test_pro_preset_has_sharks_and_gto():
    pro = set(CLASS_PRESETS["pro"])
    assert "Shark" in pro and "GTO Expert" in pro and "ICM Expert" in pro


def test_tournament_klasman_preset_populates_picker():
    from app.core.app_state import AppState
    from app.ui.screens.tournament_simulator import TournamentSimulatorScreen
    _qapp()
    s = TournamentSimulatorScreen(AppState())
    items = [s.bot_difficulty.itemText(i) for i in range(s.bot_difficulty.count())]
    assert "🎓 Pro Klasmanı" in items
    s._apply_field_preset("🎓 Pro Klasmanı")
    comp = s.field_picker.get_archetypes()
    assert comp and all(archetype_class(a) == "pro" for a in comp)


def test_cash_klasman_preset_available():
    from app.core.app_state import AppState
    from app.ui.screens.play_session import PlaySessionScreen
    _qapp()
    s = PlaySessionScreen(AppState())
    assert "🎓 Hobi Klasmanı" in s._CASH_PRESETS
    assert all(archetype_class(a) == "hobby"
               for a in s._CASH_PRESETS["🎓 Hobi Klasmanı"])
