"""ICM/PKO Trainer GERÇEK aksiyon guard'ı.

Bug (canlı test): best_action = ['fold','jam','call','raise'][idx%4] — ele/stack/
ICM'den BAĞIMSIZ rotasyon. AKo 10bb bubble'a 'FOLD (GTO)' diyordu. Artık gerçek
ICM push/fold motoru (build_icm_push_fold / build_call_vs_jam) kullanılıyor.
"""
from __future__ import annotations

from app.ui.screens.icm_trainer import (
    _cards_to_key, _icm_correct_action, _generate_icm_drills,
)


def test_cards_to_key():
    assert _cards_to_key("AsKh") == "AKo"
    assert _cards_to_key("JhTh") == "JTs"
    assert _cards_to_key("8s8c") == "88"
    assert _cards_to_key("KhAd") == "AKo"   # sıralama düzeltir


def test_ako_10bb_bubble_is_jam_not_fold():
    """KRİTİK: AKo UTG 10bb bubble push/fold = JAM (eskiden 'fold' diyordu)."""
    a = _icm_correct_action("AsKh", "UTG", 10, "bubble", "10bb push/fold", 1.2)
    assert a == "jam", a


def test_premium_jams_trash_folds_push_spot():
    assert _icm_correct_action("AsAd", "UTG", 10, "bubble", "10bb push/fold", 1.2) == "jam"
    assert _icm_correct_action("7h2c", "UTG", 10, "bubble", "10bb push/fold", 1.2) == "fold"


def test_call_spot_returns_call_or_fold_not_jam():
    """Facing-jam (call/fold) spotunda aksiyon call ya da fold — jam değil."""
    a = _icm_correct_action("AsKh", "BB", 12, "bubble", "Bubble call/fold", 1.3)
    assert a in ("call", "fold")
    assert _icm_correct_action("AsAd", "BB", 12, "bubble", "Bubble call/fold", 1.3) == "call"


def test_best_action_not_idx_rotation():
    """best_action artık idx%4 rotasyonu DEĞİL — ele bağlı, premium asla fold değil."""
    drills = _generate_icm_drills(12)
    icm001 = next(d for d in drills if d["id"] == "ICM-001")
    assert icm001["best_action"] == "jam"     # AKo 10bb — eski kod 'fold' derdi
    # push/fold spotunda premium el fold olarak işaretlenmemeli
    for d in drills:
        if "push" in d["spot_type"].lower() and d["hero_cards"] in ("AsAd", "AsKh") \
                and d["hero_stack_bb"] <= 15:
            assert d["best_action"] == "jam", (d["id"], d["hero_cards"], d["best_action"])
