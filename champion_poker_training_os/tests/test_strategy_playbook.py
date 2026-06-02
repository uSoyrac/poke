"""Strateji Planı (Playbook) ekranı — içerik bütünlüğü + smoke + nav.

Playbook bir EĞİTİM kaynağı; içerik kalitesi (her ilkenin 'neden'i olması,
ilgili trainer'a geçerli bağlantı) ve ekranın hatasız kurulması doğrulanır.
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

from app.ui.screens.strategy_playbook import (
    CASH_PLAYBOOK, MTT_PLAYBOOK, StrategyPlaybookScreen,
)
from app.main import NAV_ITEMS


# Playbook bağlantılarının gösterdiği ekranlar gerçekten nav'da olmalı
_VALID_TARGETS = set(NAV_ITEMS)


@pytest.mark.parametrize("book,name", [(CASH_PLAYBOOK, "cash"), (MTT_PLAYBOOK, "mtt")])
def test_every_section_well_formed(book, name):
    assert len(book) >= 5, f"{name} playbook çok kısa ({len(book)} bölüm)"
    for sec in book:
        assert sec["title"].strip()
        assert len(sec["frame"]) > 30, f"{name}/{sec['title']}: çerçeve zayıf"
        assert sec["rules"], f"{name}/{sec['title']}: ilke yok"
        for rule, why in sec["rules"]:
            # Her ilke 'neden'iyle gelmeli (ezber değil anlayış)
            assert len(rule) > 15, f"kısa kural: {rule}"
            assert len(why) > 20, f"'{rule}' için neden zayıf: {why}"


@pytest.mark.parametrize("book", [CASH_PLAYBOOK, MTT_PLAYBOOK])
def test_links_point_to_real_screens(book):
    for sec in book:
        link = sec.get("link")
        if link:
            _, target = link
            assert target in _VALID_TARGETS, f"geçersiz nav hedefi: {target}"


def test_cash_and_mtt_cover_core_themes():
    cash_text = " ".join(s["title"] + s["frame"] for s in CASH_PLAYBOOK).lower()
    mtt_text = " ".join(s["title"] + s["frame"] for s in MTT_PLAYBOOK).lower()
    # Cash: bankroll/masa seçimi, preflop, postflop, sömürü, mental
    for kw in ("bankroll", "preflop", "postflop", "sömürü", "mental"):
        assert kw in cash_text, f"cash playbook '{kw}' içermiyor"
    # MTT: stack derinliği, ante, icm/bubble, final table, varyans
    for kw in ("stack", "ante", "icm", "final table", "varyans"):
        assert kw in mtt_text, f"mtt playbook '{kw}' içermiyor"


def test_screen_builds_and_toggles():
    from PySide6.QtWidgets import QApplication
    from app.core.app_state import AppState
    app = QApplication.instance() or QApplication([])
    scr = StrategyPlaybookScreen(AppState())
    # Varsayılan cash
    assert scr._mode == "cash"
    n_cash = scr._content.count()
    assert n_cash == len(CASH_PLAYBOOK)
    # MTT'ye geç
    scr._set_mode("mtt")
    assert scr._mode == "mtt"
    assert scr._content.count() == len(MTT_PLAYBOOK)
    # Geri cash
    scr._set_mode("cash")
    assert scr._content.count() == len(CASH_PLAYBOOK)


def test_navigation_signal_emits():
    from PySide6.QtWidgets import QApplication
    from app.core.app_state import AppState
    app = QApplication.instance() or QApplication([])
    scr = StrategyPlaybookScreen(AppState())
    got = []
    scr.navigate_requested.connect(got.append)
    scr._goto("Math Lab")
    assert got == ["Math Lab"]
