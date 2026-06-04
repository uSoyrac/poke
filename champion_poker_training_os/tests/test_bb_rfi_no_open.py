"""BB'nin first-in OPEN range'i yoktur (preflop son oynayan oyuncu).

Bug (canlı test SS1): turnuva GTO matrisi BB için TAMAMEN KIRMIZI çıkıyordu
(157/169 hücre raise). Kök neden: POS_RFI_TARGET_PCT['BB']=100 bir "geniş
DEFEND" işaretiydi ama build_mtt_rfi / build_rfi_range onu açış genişliği
sanıp tüm gridi raise yapıyordu. BB RFI = limp'lenen pottaki iso opsiyonu
(~top %16 polarize), ASLA %100 raise.
"""
from __future__ import annotations

from app.poker.gto_ranges import get_action
from app.poker.mtt_ranges import build_mtt_rfi
from app.poker.gto_generator import heuristic_get_action


def _raise_count(grid):
    return sum(1 for a in grid.values() if a.get("raise", 0) >= 60)


def test_bb_rfi_mtt_not_all_raise():
    """MTT BB RFI matrisi çoğunlukla raise OLMAMALI (eskiden 157/169)."""
    grid = build_mtt_rfi("BB", 87)
    n = _raise_count(grid)
    assert n < 50, f"BB RFI {n}/169 raise — açış range'i yok, all-red olmamalı"
    assert n > 5, "BB iso-raise tamamen boş da olmamalı (limp'e karşı premium iso)"


def test_bb_rfi_premiums_raise_trash_folds():
    """Doğru şekil: premium iso raise, çöp fold."""
    assert get_action("BB", "AA", "RFI", 87, "MTT").get("raise", 0) >= 80
    assert get_action("BB", "AKs", "RFI", 87, "MTT").get("raise", 0) >= 60
    assert get_action("BB", "72o", "RFI", 87, "MTT").get("raise", 0) <= 20
    assert get_action("BB", "J3s", "RFI", 87, "MTT").get("raise", 0) <= 20


def test_bb_rfi_cash_heuristic_no_leak():
    """Cash heuristic'te de aynı sızıntı olmamalı (POS_RFI_TARGET_PCT['BB']=100)."""
    assert heuristic_get_action("BB", "72o", "RFI", 87, "cash", None).get("raise", 0) <= 20
    assert heuristic_get_action("BB", "AA", "RFI", 87, "cash", None).get("raise", 0) >= 80


def test_sb_btn_rfi_unaffected():
    """Regresyon: SB/BTN açış range'leri normal kalmalı (gerçek açış pozisyonları)."""
    assert get_action("SB", "AA", "RFI", 87, "MTT").get("raise", 0) >= 80
    assert get_action("SB", "A7s", "RFI", 87, "MTT").get("raise", 0) >= 60
    assert get_action("SB", "72o", "RFI", 87, "MTT").get("raise", 0) <= 20
    assert get_action("BTN", "AA", "RFI", 87, "MTT").get("raise", 0) >= 80
    assert get_action("BTN", "72o", "RFI", 87, "MTT").get("raise", 0) <= 20
