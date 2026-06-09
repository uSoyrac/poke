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


# ── D132: postflop gerçek-motor grading (MC equity + cbet/defend) ──

from app.db.seed_data import _real_postflop_best_action


def test_postflop_clear_spots():
    """Net postflop spotlar: çöp facing-bet → fold; üst-el hero-act → bet."""
    assert _real_postflop_best_action(
        "flop", "AhKsQd", "MP", "7h2c", 10.0, ("fold", "call", "raise")) == "fold"
    bet = _real_postflop_best_action(
        "flop", "Ah7c2d", "BTN", "AsKh", 8.0,
        ("check", "bet small", "bet medium", "bet large"))
    assert bet in ("bet small", "bet medium", "bet large"), bet


def test_postflop_unsupported_returns_none():
    assert _real_postflop_best_action("preflop", "", "BTN", "AsKh", 5.0, ("fold", "raise")) is None
    assert _real_postflop_best_action("flop", "", "BTN", "AsKh", 5.0, ("fold", "call")) is None


def test_flags_postflop_engine_not_persisted():
    """Postflop gerçek-motor verdict'leri engine_graded=True ama solver_verified=False
    (yaklaşık equity → kalıcı mastery'ye yazılmaz)."""
    drills = generate_spot_drills(120)
    post_engine = [d for d in drills
                   if d["street"] in ("flop", "turn", "river") and d.get("engine_graded")]
    assert len(post_engine) >= 5, "postflop gerçek-motor verdict üretilmeli"
    for d in post_engine:
        assert d.get("solver_verified") is False, "postflop persist edilmemeli (yaklaşık)"
    # preflop gerçek olanlar HEM engine_graded HEM solver_verified
    pre_v = [d for d in drills if d["street"] == "preflop" and d.get("solver_verified")]
    assert all(d.get("engine_graded") for d in pre_v)
