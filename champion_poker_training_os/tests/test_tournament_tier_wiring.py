"""Tournament Simulator ↔ stake-tier alan bağı.

FIELD STRENGTH combo'suna eklenen '🌍 Gerçek: <tier>' seçenekleri hem hero
masasını hem MTTField arka-plan alanını o gerçekçi stake dağılımından besler.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from app.main import prepare_qt_platform_plugins
    prepare_qt_platform_plugins()
except Exception:
    pass


def test_tier_fractions_progress():
    from app.engine.bot_brain import tier_skill_fractions
    micro = tier_skill_fractions("Mikro ($1-5)")
    high = tier_skill_fractions("Yüksek ($530+)")
    assert micro["weak"] > high["weak"]
    assert high["strong"] > micro["strong"]
    assert micro["strong"] < 0.10 and high["strong"] > 0.20


def test_mttfield_tier_sets_buckets():
    from app.simulator.mtt_field import MTTField
    micro = MTTField(field_size=200, tier="Mikro ($1-5)")
    high = MTTField(field_size=200, tier="Yüksek ($530+)")
    assert high.strong_fraction > micro.strong_fraction
    # bucket toplamı arka plan kadar
    assert sum(micro._bg.values()) == micro.bg_players_remaining


def test_combo_has_realistic_tiers():
    from PySide6.QtWidgets import QApplication
    from app.core.app_state import AppState
    from app.ui.screens.tournament_simulator import TournamentSimulatorScreen
    app = QApplication.instance() or QApplication([])
    scr = TournamentSimulatorScreen(AppState())
    items = [scr.bot_difficulty.itemText(i) for i in range(scr.bot_difficulty.count())]
    tiers = [t for t in items if t.startswith("🌍 Gerçek:")]
    assert len(tiers) == 4, f"4 stake tier bekleniyor: {tiers}"


def test_selecting_tier_sets_field_tier_and_composition():
    from PySide6.QtWidgets import QApplication
    from app.core.app_state import AppState
    from app.ui.screens.tournament_simulator import TournamentSimulatorScreen
    from app.engine.bot_brain import BOT_ARCHETYPES
    app = QApplication.instance() or QApplication([])
    scr = TournamentSimulatorScreen(AppState())
    scr._apply_field_preset("🌍 Gerçek: Mikro ($1-5)")
    assert scr._field_tier == "Mikro ($1-5)"
    comp = scr.field_picker.get_archetypes()
    assert len(comp) == 8
    assert all(a in BOT_ARCHETYPES for a in comp)
    # Klasik preset seçince tier sıfırlanır
    scr._apply_field_preset("Tough Field")
    assert scr._field_tier is None
