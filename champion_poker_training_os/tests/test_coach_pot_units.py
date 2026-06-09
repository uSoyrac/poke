"""S2 guard: AI koç 'El Analizi' pot'u bb-normalize + el-sonu etiketi (D126).

Bug (canlı test): analiz 'potun 500BB' diyordu ama o pota el SONUNDA ulaşıldı +
turnuva çip-pot'u (500 çip) bb sanılıp '500bb' gösteriliyordu (tablo /bb böler,
analiz bölmüyordu). Fix: big_blind ile normalize + 'El sonu pot (showdown)' etiketi.
"""
from __future__ import annotations

from app.ai.coach_engine import analyze_played_hand


def test_tournament_pot_bb_normalized():
    """500 çip pot, bb=20 → 25.0bb gösterilmeli, '500bb' DEĞİL."""
    txt = analyze_played_hand({
        "hero_cards": "AsKh", "community": "Ah7c2d",
        "pot": 500.0, "hero_invested": 100.0, "hero_profit": 200.0,
        "hero_won": True, "big_blind": 20.0, "winner_hand_name": "Pair",
    })
    assert "25.0bb" in txt, txt          # 500/20
    assert "500.0bb" not in txt          # çip değeri bb sanılmamalı
    assert "5.0bb" in txt                # invested 100/20
    assert "10.0bb" in txt               # profit 200/20


def test_pot_labeled_as_showdown_not_decision():
    """Pot 'El sonu pot (showdown)' diye etiketlenmeli (karar-anı izlenimi vermesin)."""
    txt = analyze_played_hand({
        "hero_cards": "QdQs", "community": "", "pot": 30.0,
        "hero_invested": 10.0, "hero_profit": -10.0, "hero_won": False,
        "big_blind": 1.0,
    })
    assert "El sonu pot (showdown)" in txt
    assert "📊 Pot:" not in txt           # eski yanıltıcı etiket kaldı mı


def test_cash_bb1_unchanged():
    """Cash bb=1.0 → değerler aynen (bölme no-op)."""
    txt = analyze_played_hand({
        "hero_cards": "JhTh", "community": "", "pot": 12.0,
        "hero_invested": 3.0, "hero_profit": 9.0, "hero_won": True,
        "big_blind": 1.0,
    })
    assert "12.0bb" in txt
