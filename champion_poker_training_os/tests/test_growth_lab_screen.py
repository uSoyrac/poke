"""Growth & Edge Lab ekranı — kurulum + mod toggle + nav kaydı smoke."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from app.main import prepare_qt_platform_plugins
    prepare_qt_platform_plugins()
except Exception:
    pass


def test_screen_builds_and_toggles():
    from PySide6.QtWidgets import QApplication
    from app.core.app_state import AppState
    from app.ui.screens.growth_lab import GrowthLabScreen
    app = QApplication.instance() or QApplication([])
    scr = GrowthLabScreen(AppState())
    assert scr._mode == "bankroll"
    # isHidden() açık-gizli bayrağını yansıtır (ekran show() edilmese de)
    assert not scr._bankroll_box.isHidden()
    assert scr._edge_box.isHidden()
    # Edge moduna geç
    scr._set_mode("edge")
    assert scr._mode == "edge"
    assert not scr._edge_box.isHidden()
    assert scr._bankroll_box.isHidden()
    # Geri
    scr._set_mode("bankroll")
    assert not scr._bankroll_box.isHidden()


def test_recompute_reacts_to_inputs():
    from PySide6.QtWidgets import QApplication
    from app.core.app_state import AppState
    from app.ui.screens.growth_lab import GrowthLabScreen
    app = QApplication.instance() or QApplication([])
    scr = GrowthLabScreen(AppState())
    # Kayıp eden winrate → sonuç host yine dolu (kart üretilir)
    scr._winrate.setValue(-2.0)
    scr._recompute()
    assert scr._results_host.count() >= 1


def test_registered_in_nav():
    from app.main import NAV_ITEMS
    assert "Growth & Edge Lab" in NAV_ITEMS


def test_edge_mode_renders_for_botlike_input():
    from PySide6.QtWidgets import QApplication
    from app.core.app_state import AppState
    from app.ui.screens.growth_lab import GrowthLabScreen
    app = QApplication.instance() or QApplication([])
    scr = GrowthLabScreen(AppState())
    scr._set_mode("edge")
    scr._winp.setValue(58.0)
    scr._payoff.setValue(1.2)
    scr._lossf.setValue(1.0)
    scr._recompute()
    assert scr._results_host.count() >= 1
