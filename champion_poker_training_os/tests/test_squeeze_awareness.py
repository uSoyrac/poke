"""D298 (audit yakaladı: squeeze spot'u "vs RFI" sanılıyordu, ölü-para kör): SQUEEZE-farkındalık.
limper(ler)+açan varken hero = squeeze; cold-call flat multiway/inisiyatifsiz/sık-OOP → −EV →
3bet-or-fold lean (FLAT'i call_t+2 sıkılaştır). En-zayıf cold-call'lar (skor 10-11) FOLD;
oynanabilir flat (skor 12+) ve value-3bet (squeeze) KORUNUR. Multiway-disiplini (D278) + kullanıcı
tezi ("multiway büyük call olmamalı") ile tutarlı. ADVICE-only (n_squeeze default 0 → fidelity 0)."""
from types import SimpleNamespace

from app.engine.hand_state import ActionType, Street
from app.poker.soyrac_advisor import soyrac_advice, _limpers_before_raiser


def _act(idx, at):
    return SimpleNamespace(player_idx=idx, action_type=at, street=Street.PREFLOP)


def _adv(hk, n_squeeze=0, stack_bb=40):
    # SIĞ (≤50bb): squeeze-fold disiplini burada +EV (A/B); derin'de implied-odds flati haklı kılar.
    return soyrac_advice(hk, "BTN", "vs RFI", vs_position="CO", stack_bb=stack_bb,
                         n_active=6, n_squeeze=n_squeeze)


def test_limpers_before_raiser_counts_dead_money():
    """limp + raise → 1 ölü-para limp (raise olsa bile raise-ÖNCESİ limp'i sayar)."""
    h = SimpleNamespace(actions=[_act(1, ActionType.CALL), _act(2, ActionType.RAISE)])
    assert _limpers_before_raiser(h, hero_idx=3) == 1
    h2 = SimpleNamespace(actions=[_act(1, ActionType.CALL), _act(2, ActionType.CALL),
                                  _act(3, ActionType.RAISE)])
    assert _limpers_before_raiser(h2, hero_idx=4) == 2


def test_no_limper_before_raise():
    """Limp yok, sadece raise → 0 (squeeze değil, düz vs-RFI)."""
    h = SimpleNamespace(actions=[_act(2, ActionType.RAISE)])
    assert _limpers_before_raiser(h, hero_idx=3) == 0


def test_squeeze_bumps_call_threshold():
    """Squeeze → flat eşiği +2 (3bet-or-fold lean)."""
    base = _adv("KTs")
    sq = _adv("KTs", n_squeeze=1)
    assert sq["call_t"] == base["call_t"] + 2
    assert "SQUEEZE" in sq["line"] and "SQUEEZE" not in base["line"]


def test_squeeze_folds_weakest_flats():
    """Sığ (40bb) squeeze: en-zayıf cold-call'lar (T8s/98s/K9o/QTo) CALL→FOLD (3bet-or-fold lean)."""
    for hk in ("T8s", "98s", "K9o", "QTo"):
        assert _adv(hk)["action"] == "CALL", f"{hk} base CALL olmalı"
        assert _adv(hk, n_squeeze=1)["action"] == "FOLD", f"{hk} squeeze FOLD olmalı"


def test_squeeze_keeps_playable_flats_and_value():
    """Oynanabilir flat (J9s/KTo) CALL kalır; value-3bet (AKs/A9s) 3-BET (squeeze) kalır."""
    for hk in ("J9s", "KTo"):
        assert _adv(hk, n_squeeze=1)["action"] == "CALL", f"{hk} oynanabilir flat kalmalı"
    for hk in ("AKs", "A9s"):
        assert _adv(hk, n_squeeze=1)["action"] == "3-BET", f"{hk} value-squeeze 3-BET kalmalı"


def test_squeeze_deep_no_change():
    """DERİN (100bb): squeeze gate kapalı (IP implied-odds flati haklı kılar) → identity."""
    for hk in ("T8s", "98s", "K9o"):
        d0 = _adv(hk, n_squeeze=0, stack_bb=100)
        d1 = _adv(hk, n_squeeze=1, stack_bb=100)
        assert d0["action"] == d1["action"], f"{hk} derin squeeze değişmemeli (gate ≤50bb)"


def test_no_squeeze_identity():
    """n_squeeze=0 → hiçbir değişiklik (mevcut davranış, fidelity/sim korunur)."""
    for hk in ("T8s", "K9o", "J9s", "AKs"):
        b0 = _adv(hk, n_squeeze=0)
        b1 = soyrac_advice(hk, "BTN", "vs RFI", vs_position="CO", stack_bb=40, n_active=6)
        assert b0["action"] == b1["action"] and b0["call_t"] == b1["call_t"]
