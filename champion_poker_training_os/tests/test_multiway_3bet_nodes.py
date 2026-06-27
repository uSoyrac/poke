"""D331 (kullanıcı: 'çok-yollu/sıralı preflop node'larını sistem ayırmıyor'):
vs-3bet MULTIWAY (3bet'e caller) → sıkı + blöf-blocker-4bet YOK; SQUEEZE-bana (hero önce call,
sonra 3bet) → range capped (blöf-4bet YOK) + ölü-para odds (set-mine call HAKLI). AK premium korunur."""
from app.poker.soyrac_advisor import soyrac_advice as A


def _act(hk, **kw):
    return A(hk, "BTN", "vs 3-bet", vs_position="CO", stack_bb=kw.pop("s", 100),
             n_active=6, **kw)["action"]


def test_squeeze_against_hero_setmine():
    """Hero önce call → 3bet yedi (squeeze): küçük çift FOLD yerine set-mine CALL (ölü-para odds)."""
    assert _act("44") == "FOLD"                      # normal vs-3bet @100bb (D310 gate)
    assert _act("44", hero_pre_called=True) == "CALL"  # squeeze-bana → set-mine açılır
    assert _act("66", hero_pre_called=True) == "CALL"


def test_multiway_3bet_tightens():
    """vs-3bet'e caller (n_committed≥1): marjinal call FOLD'a, blöf-blocker-4bet FOLD'a."""
    assert _act("KJs") == "CALL" and _act("KJs", n_committed=1) == "FOLD"     # flat sıkılaşır
    assert _act("A5s", s=60) == "4-BET" and _act("A5s", s=60, n_committed=1) == "FOLD"  # blocker-4bet kapanır


def test_premium_preserved_all_nodes():
    """Gerçek premium (AK) tüm node'larda devam eder (4-BET) — over-fold riski yok."""
    for kw in ({}, {"n_committed": 1}, {"hero_pre_called": True}):
        assert _act("AKo", **kw) == "4-BET", kw
        assert _act("AKs", **kw) == "4-BET", kw


def test_default_unchanged_fidelity():
    """Bayrak yok → eski davranış (advice-only, fidelity)."""
    assert _act("KJs") == "CALL" and _act("44") == "FOLD" and _act("AKo") == "4-BET"
