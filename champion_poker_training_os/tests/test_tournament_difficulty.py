"""Turnuva zorluk göstergesi + hero ICM-koç uyarısı.

toughness(): alan sertliği (strong oranı) + bubble/ICM baskısı → 0..1 + etiket.
_maybe_icm_coach: faz geçişinde (bubble/ITM) hero'ya BİR KEZ uyarı (spam yok).
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from app.main import prepare_qt_platform_plugins
    prepare_qt_platform_plugins()
except Exception:
    pass

import random

from app.simulator.mtt_field import MTTField


def test_toughness_higher_for_high_stake():
    """Yüksek-stake (reg-ağır) alan, düşük-stake'ten daha ZOR skor verir."""
    low = MTTField(field_size=500, tier="Düşük ($11-33)")
    high = MTTField(field_size=500, tier="Yüksek ($530+)")
    assert high.toughness()[0] > low.toughness()[0]


def test_toughness_rises_on_bubble():
    """Bubble'a yaklaşınca zorluk artar (ICM baskısı)."""
    f = MTTField(field_size=100, tier="Düşük ($11-33)")
    early = f.toughness()[0]
    # Alanı bubble'a yaklaştır (paid+1'e indir)
    paid = f.paid_places
    # tüm arka planı boşalt, hero masasını paid+1'e çek
    f._bg = {"weak": 0, "mid": 0, "strong": 0}
    f.update_hero_table(paid + 1)
    bubble = f.toughness()[0]
    assert bubble >= early


def test_toughness_label_bands():
    f = MTTField(field_size=200, tier="Mikro ($1-5)")
    score, tag = f.toughness()
    assert 0.0 <= score <= 1.0
    assert any(k in tag for k in ("KOLAY", "ORTA", "ZOR"))


def test_icm_coach_fires_once_per_phase():
    from PySide6.QtWidgets import QApplication
    from app.core.app_state import AppState
    from app.ui.screens.tournament_simulator import TournamentSimulatorScreen
    app = QApplication.instance() or QApplication([])
    scr = TournamentSimulatorScreen(AppState())
    msgs = []
    scr.coach_message.connect(msgs.append)
    # Bubble baskısı (yüksek icm) → bir kez uyarı
    scr._maybe_icm_coach(0.9, alive=51, paid=50)
    scr._maybe_icm_coach(0.9, alive=51, paid=50)   # aynı faz → tekrar YOK
    bubble_msgs = [m for m in msgs if "BUBBLE" in m]
    assert len(bubble_msgs) == 1, f"bubble uyarısı tam 1 kez olmalı: {len(bubble_msgs)}"
    # ITM fazına geç → yeni uyarı
    scr._maybe_icm_coach(0.45, alive=40, paid=50)
    assert any("ITM" in m for m in msgs)


def test_closing_eval_includes_field_tier():
    """Turnuva-sonu post-mortem prompt'u alan tier/zorluk bağlamını içerir."""
    from PySide6.QtWidgets import QApplication
    from app.core.app_state import AppState
    from app.ui.screens.tournament_simulator import TournamentSimulatorScreen
    from app.simulator.tournament_runner import TournamentConfig
    app = QApplication.instance() or QApplication([])
    scr = TournamentSimulatorScreen(AppState())
    prompts = []
    scr.tournament_advice_requested.connect(prompts.append)
    cfg = TournamentConfig(field_size=500)
    scr._emit_closing_evaluation(
        finish=3, field_size=500, prize=400, profit=378, roi=1718,
        won=False, itm=True, pct_rank=99.4, total_hands=120,
        stats={"vpip": 22, "pfr": 18}, leaks=[], config=cfg,
        field_tier="Yüksek ($530+)")
    assert prompts, "post-mortem prompt emit edilmedi"
    assert "Yüksek ($530+)" in prompts[0]
    assert "Alan profili" in prompts[0]


def test_icm_coach_silent_early():
    from PySide6.QtWidgets import QApplication
    from app.core.app_state import AppState
    from app.ui.screens.tournament_simulator import TournamentSimulatorScreen
    app = QApplication.instance() or QApplication([])
    scr = TournamentSimulatorScreen(AppState())
    msgs = []
    scr.coach_message.connect(msgs.append)
    scr._maybe_icm_coach(0.0, alive=500, paid=50)   # erken → sessiz
    assert msgs == []
