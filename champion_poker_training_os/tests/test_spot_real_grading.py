"""D131: spot trainer preflop drill'leri GERÇEK GTO motoruyla derecelendirilir.

Eski: best_action = options[(idx*2+1)%len] (sahte rotasyon). D131: preflop
spotlar (SRP→RFI, 3BP→vs 3-bet, limped→RFI) get_action ile gerçek + solver_verified
(kalıcı kayda uygun). Postflop/4BP/multiway → demo (yanlış doğru-cevap üretmemek için).
"""
from __future__ import annotations
from app.db.seed_data import generate_spot_drills, _real_preflop_best_action, _seed_cards_to_key


def test_cards_to_key():
    assert _seed_cards_to_key("AsKh") == "AKo"
    assert _seed_cards_to_key("JhTh") == "JTs"
    assert _seed_cards_to_key("8s8c") == "88"
    assert _seed_cards_to_key("") == ""


def test_preflop_grader_correct_on_known_spots():
    pf = ("fold", "call", "raise", "jam")
    assert _real_preflop_best_action("preflop", "SRP", "UTG", "AsAd", 100, pf) == "raise"
    assert _real_preflop_best_action("preflop", "SRP", "UTG", "7h2c", 100, pf) == "fold"
    assert _real_preflop_best_action("preflop", "3BP", "UTG", "AsAd", 100, ("fold", "call", "raise")) == "raise"
    assert _real_preflop_best_action("preflop", "3BP", "MP", "7h2c", 100, ("fold", "call", "raise")) == "fold"


def test_unsupported_spots_return_none_for_demo():
    # postflop / 4BP / multiway güvenle çözülemez → None (demo fallback)
    assert _real_preflop_best_action("flop", "SRP", "BTN", "AsKh", 100, ("check", "bet small")) is None
    assert _real_preflop_best_action("preflop", "multiway", "BTN", "AsKh", 100, ("fold", "call", "raise")) is None
    assert _real_preflop_best_action("preflop", "4BP", "BTN", "AsKh", 100, ("fold", "call", "raise")) is None


def test_generated_drills_have_verified_flag_and_no_premium_fold():
    drills = generate_spot_drills(120)
    verified = [d for d in drills if d.get("solver_verified")]
    assert len(verified) >= 10, "preflop SRP/3BP/limped drill'leri gerçek olmalı"
    # solver_verified drill'lerde premium el asla fold işaretli olmamalı
    for d in verified:
        if d["hero_cards"] in ("AsAd", "AsKh") and "raise" in d["options"]:
            assert d["best_action"] != "fold", (d["id"], d["hero_cards"])
    # demo (verified değil) drill'lerde de flag tutarlı
    assert all("solver_verified" in d for d in drills)
