"""Leak Finder ↔ Playbook eşlemesi.

Her tespit edilen leak, ihlal ettiği uzun-vade Playbook ilkesine bağlanır;
böylece kullanıcı yalnız 'neyi yanlış yaptım' değil 'hangi prensibi çiğnedim'
ve nereden çalışacağını da görür.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from app.main import prepare_qt_platform_plugins
    prepare_qt_platform_plugins()
except Exception:
    pass

import pytest

from app.poker.playbook import (
    CASH_PLAYBOOK, MTT_PLAYBOOK, playbook_ref_for_leak, section_by_title,
)


# Tespit edilen decision-leak adları (get_decision_leaks formatı)
_DECISION_LEAKS = [
    ("Over-folding (vs 3-bet)", "vs 3-bet"),
    ("Over-folding (vs RFI)", "vs RFI"),
    ("Over-aggression / spew (Postflop)", "Postflop"),
    ("Over-aggression / spew (RFI)", "RFI"),
    ("GTO çizgisinden sapma (Push/Fold)", "Push/Fold"),
    ("GTO çizgisinden sapma (Preflop)", "Preflop"),
]

# Örnek katalog leak adları (EXTENDED_LEAKS)
_CATALOG_LEAKS = [
    ("BB underdefend vs BTN min-raise", "Preflop"),
    ("River overbluff", "Postflop"),
    ("ICM call-off too loose", "ICM"),
    ("Turn overbarrel on paired boards", "Postflop"),
    ("Thin value left on table", "Postflop"),
    ("SB flat-call too wide", "Preflop"),
    ("OOP passivity", "Postflop"),
    ("cbet too high dry boards", "Postflop"),
    ("short stack push/fold", "Push/Fold"),
    ("multiway overbluff", "Postflop"),
]


@pytest.mark.parametrize("name,cat", _DECISION_LEAKS + _CATALOG_LEAKS)
def test_every_leak_maps_to_a_real_playbook_section(name, cat):
    ref = playbook_ref_for_leak(name, cat)
    assert ref is not None, f"'{name}' bir Playbook ilkesine bağlanamadı"
    assert ref["format"] in ("cash", "mtt")
    assert ref["screen"] == "Strategy Playbook"
    # Atıfta bulunduğu bölüm gerçekten var olmalı (tutarlılık)
    sec = section_by_title(ref["section"])
    assert sec is not None, f"hayalet bölüm: {ref['section']}"
    assert ref["principle"] == sec["frame"]


def test_pushfold_maps_to_mtt_stack_phase():
    ref = playbook_ref_for_leak("short stack push/fold", "Push/Fold")
    assert ref["format"] == "mtt"
    assert ref["section"] == MTT_PLAYBOOK[0]["title"]  # Stack Derinliği Fazları


def test_icm_maps_to_mtt_icm_section():
    ref = playbook_ref_for_leak("ICM call-off too loose", "ICM")
    assert ref["format"] == "mtt"
    assert ref["section"] == MTT_PLAYBOOK[2]["title"]  # ICM & Bubble


def test_preflop_defend_maps_to_cash_preflop():
    ref = playbook_ref_for_leak("BB underdefend vs BTN min-raise", "Preflop")
    assert ref["format"] == "cash"
    assert ref["section"] == CASH_PLAYBOOK[1]["title"]  # Preflop İskelet


def test_unknown_leak_returns_none():
    assert playbook_ref_for_leak("zzz totally unrelated", "") is None


# ── UI entegrasyonu ──────────────────────────────────────────────────
def test_normalize_attaches_playbook():
    from app.ui.screens.leak_finder import _normalize_leak
    leak = _normalize_leak({"name": "River overbluff", "category": "Postflop",
                            "severity": "High", "ev_lost": 12.0})
    assert leak["playbook"] is not None
    assert leak["playbook"]["screen"] == "Strategy Playbook"


def test_catalog_leaks_all_have_playbook_after_normalize():
    from app.ui.screens.leak_finder import EXTENDED_LEAKS, _normalize_leak
    for raw in EXTENDED_LEAKS:
        leak = _normalize_leak(raw)
        assert leak["playbook"] is not None, f"{raw['name']} playbook'a bağlanmadı"


def test_leakfinder_select_populates_playbook_label():
    from PySide6.QtWidgets import QApplication
    from app.core.app_state import AppState
    from app.ui.screens.leak_finder import LeakFinderScreen
    app = QApplication.instance() or QApplication([])
    scr = LeakFinderScreen(AppState())
    # En az bir leak olmalı (gerçek veri yoksa katalog)
    assert scr.all_leaks
    scr.table.setProperty("filtered_leaks", scr.all_leaks)
    scr._select_leak(0, 0)
    # Seçilen leak'in playbook'u varsa label dolu + buton aktif
    leak = scr.all_leaks[0]
    if leak.get("playbook"):
        assert "Playbook" in scr.detail_playbook.text()
        assert scr.playbook_btn.isEnabled()


def test_navigation_target_is_valid():
    from app.main import NAV_ITEMS
    assert "Strategy Playbook" in NAV_ITEMS
