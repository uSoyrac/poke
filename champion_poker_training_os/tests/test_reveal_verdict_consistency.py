"""El-sonu reveal verdict tutarlılığı — heuristik postflop spotlar
kullanıcının kararını sert 'hata' olarak işaretlememeli (koçla tutarlı).

Senaryo: 55 ile QQT96 board'unda river fold. Sistem eskiden equity
heuristiğine (%39) güvenip 'CALL %100, senin FOLD ✗ sapma' diyordu;
koç ise 'fold doğruydu' diyordu → çelişki. Artık postflop heuristik
spotlarda sert ✗/F verilmez.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.poker.decision_grade import grade_decision


def _qapp():
    from app.main import prepare_qt_platform_plugins
    prepare_qt_platform_plugins()
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


_POSTFLOP = {
    "available": True,
    "scenario": "Postflop (River · paired · IP, eq %39)",
    "tier": "Board-texture model (CONCEPT)",
    "hero_action": "FOLD", "fold": 0, "call": 100, "raise": 0,
}
_CURATED_PRE = {
    "available": True, "scenario": "RFI", "tier": "Curated",
    "hero_action": "FOLD", "fold": 0, "call": 0, "raise": 100,
}


def test_postflop_concept_fold_is_soft_not_mistake():
    _qapp()
    from app.ui.components.gto_range_widget import GTODecisionReveal
    mark, _ = GTODecisionReveal._verdict(_POSTFLOP)
    assert "sapma" not in mark               # sert 'hata' DEĞİL
    assert "heuristik" in mark.lower() or "kesin değil" in mark.lower()


def test_curated_preflop_fold_still_hard_deviation():
    _qapp()
    from app.ui.components.gto_range_widget import GTODecisionReveal
    mark, _ = GTODecisionReveal._verdict(_CURATED_PRE)
    assert "sapma" in mark                   # curated spotta gerçek hata


def test_postflop_concept_grade_capped_at_c():
    g = grade_decision(_POSTFLOP)
    # heuristik → en kötü C (D/F verilmez)
    assert g.letter in ("A", "B", "C")
    assert g.letter not in ("D", "F")


def test_postflop_concept_match_is_heuristik_label():
    _qapp()
    from app.ui.components.gto_range_widget import GTODecisionReveal
    d = dict(_POSTFLOP); d["hero_action"] = "CALL"   # optimal call ile uyumlu
    mark, _ = GTODecisionReveal._verdict(d)
    assert "heuristik" in mark.lower() and "✓" in mark
