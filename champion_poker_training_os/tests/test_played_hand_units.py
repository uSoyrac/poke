"""played_hands çip/bb birim tutarlılığı (data-model fix).

Eskiden cash elleri bb-ölçekli, turnuva elleri çip-ölçekli AYNI tabloda
karışıyordu → get_player_stats 'BB/100 +16898' gibi saçma değer veriyordu.
Artık: pot/hero_profit çip saklanır + big_blind ile bb'ye çevrilir; cash
profili yalnız cash ellerini sayar (turnuva çip-ölçeği dışlanır).
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _seed(R):
    # Cash el: bb=1.0, değerler zaten bb-ölçekli (pot 6bb, +2.5bb)
    R.save_played_hand({"hand_id": 1, "hero_cards": "AhKh", "community": "7c2d9s",
                        "pot": 6, "hero_invested": 7, "hero_profit": 2.5,
                        "hero_won": 1, "streets_seen": 2, "big_blind": 1.0,
                        "game_type": "cash"})
    # Turnuva el: bb=20 çip, pot 2000 çip (=100bb), profit 400 çip (=20bb)
    R.save_played_hand({"hand_id": 2, "hero_cards": "QsQd", "community": "",
                        "pot": 2000, "hero_invested": 800, "hero_profit": 400,
                        "hero_won": 1, "streets_seen": 1, "big_blind": 20.0,
                        "game_type": "tournament"})


def test_cash_stats_exclude_tournament_chip_scale(tmp_path, monkeypatch):
    from app.db import repository as R
    monkeypatch.setattr(R, "DB_PATH", tmp_path / "u.db")
    R.initialize_database()
    _seed(R)
    s = R.get_player_stats()
    # Tüm eller sayılır ama profit/bb_per_100 yalnız CASH (turnuva çipi dışlanır)
    assert s["total_hands"] == 2
    assert abs(s["profit_bb"] - 2.5) < 1e-6, f"profit cash-only olmalı: {s['profit_bb']}"
    # bb_per_100 = 100*2.5/1 cash el = 250 — SAÇMA (binlerce) DEĞİL
    assert abs(s["bb_per_100"] - 250.0) < 1.0, s["bb_per_100"]
    assert s["bb_per_100"] < 1000, "çip-ölçekli sızıntı (saçma bb/100) geri geldi"


def test_session_history_carries_big_blind_for_normalization(tmp_path, monkeypatch):
    from app.db import repository as R
    monkeypatch.setattr(R, "DB_PATH", tmp_path / "u2.db")
    R.initialize_database()
    _seed(R)
    hands = {h["hand_id"]: h for h in R.get_session_history(50)}
    # Turnuva eli big_blind=20 taşımalı → tüketici pot/20 = 100bb hesaplayabilsin
    assert hands[2]["big_blind"] == 20.0
    assert hands[2]["pot"] / hands[2]["big_blind"] == 100.0
    assert hands[1]["big_blind"] == 1.0   # cash no-op


def test_missing_big_blind_defaults_to_one(tmp_path, monkeypatch):
    """big_blind/game_type verilmeyen eski-stil kayıt cash bb=1 varsayar."""
    from app.db import repository as R
    monkeypatch.setattr(R, "DB_PATH", tmp_path / "u3.db")
    R.initialize_database()
    R.save_played_hand({"hand_id": 9, "hero_cards": "AhKh", "community": "",
                        "pot": 6, "hero_invested": 2, "hero_profit": 3,
                        "hero_won": 1, "streets_seen": 1})
    s = R.get_player_stats()
    assert abs(s["profit_bb"] - 3.0) < 1e-6
    assert s["bb_per_100"] < 1000
