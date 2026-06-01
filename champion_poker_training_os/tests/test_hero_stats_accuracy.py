"""Hero istatistik DOĞRULUĞU — VPIP/PFR/3bet gerçek poker tanımıyla.

Kullanıcı haklı olarak fark etti: VPIP %70 saçma yüksekti. KÖK NEDEN:
get_player_stats() VPIP'i 'hero_invested > 1bb' (tüm sokaklar boyunca
biriken çip — kör + ante + POSTFLOP) üzerinden türetiyordu. Ante'li
turnuvalarda neredeyse her el > 1bb → VPIP şişiyordu; ayrıca BB'de bedava
flop görüp postflop para koymak da VPIP sayılıyordu (oysa VPIP yalnızca
PREFLOP gönüllü aksiyondur). PFR/3bet ise tamamen uyduruluyordu (vpip*0.7).

Bu paket, gerçek VPIP/PFR/3bet tanımlarını doğrular:
  • VPIP = preflop GÖNÜLLÜ call/raise/bet/all-in (kör yatırma ya da BB
    bedava check SAYILMAZ)
  • PFR  = preflop raise/bet/all-in
  • 3bet = bir açılışa karşı yeniden raise (fırsat varken)
"""
from __future__ import annotations

import random

from app.engine.game_loop import PokerGame, hero_preflop_flags
from app.engine.hand_state import Action, ActionType, Street


# ── Saf birim testi: hero_preflop_flags el-aksiyonlarından doğru türetir ──
class _FakeHand:
    def __init__(self, actions, hero_idx=0):
        self.actions = actions
        self.hero_idx = hero_idx


def _a(idx, at, street=Street.PREFLOP):
    return Action(player_idx=idx, action_type=at, amount=0.0, street=street)


def test_bb_check_free_flop_is_not_vpip():
    """BB'de kimse raise etmedi, hero sadece CHECK etti → VPIP DEĞİL."""
    hand = _FakeHand([_a(0, ActionType.CHECK)])
    f = hero_preflop_flags(hand, 0)
    assert f["vpip"] is False, "bedava flop gören BB check VPIP olmamalı"
    assert f["pfr"] is False


def test_postflop_money_does_not_count_as_vpip():
    """Hero preflop CHECK (BB), sonra flop'ta CALL → yine VPIP DEĞİL
    (VPIP yalnız preflop gönüllü aksiyondur)."""
    hand = _FakeHand([
        _a(0, ActionType.CHECK, Street.PREFLOP),
        _a(0, ActionType.CALL, Street.FLOP),
        _a(0, ActionType.CALL, Street.TURN),
    ])
    f = hero_preflop_flags(hand, 0)
    assert f["vpip"] is False, "postflop para VPIP'i tetiklememeli"


def test_preflop_call_is_vpip_not_pfr():
    hand = _FakeHand([_a(0, ActionType.CALL, Street.PREFLOP)])
    f = hero_preflop_flags(hand, 0)
    assert f["vpip"] is True
    assert f["pfr"] is False


def test_preflop_raise_is_vpip_and_pfr():
    hand = _FakeHand([_a(0, ActionType.RAISE, Street.PREFLOP)])
    f = hero_preflop_flags(hand, 0)
    assert f["vpip"] is True
    assert f["pfr"] is True


def test_3bet_detected_when_facing_open():
    """Villain açtı (RAISE), hero yeniden RAISE → 3bet + fırsat."""
    hand = _FakeHand([
        _a(1, ActionType.RAISE, Street.PREFLOP),
        _a(0, ActionType.RAISE, Street.PREFLOP),
    ])
    f = hero_preflop_flags(hand, 0)
    assert f["threebet_opp"] is True
    assert f["threebet"] is True


def test_no_3bet_opportunity_when_hero_opens():
    """Hero ilk açan (önünde raise yok) → 3bet fırsatı YOK."""
    hand = _FakeHand([_a(0, ActionType.RAISE, Street.PREFLOP)])
    f = hero_preflop_flags(hand, 0)
    assert f["threebet_opp"] is False
    assert f["threebet"] is False


def test_call_facing_open_is_3bet_opp_but_not_3bet():
    hand = _FakeHand([
        _a(1, ActionType.RAISE, Street.PREFLOP),
        _a(0, ActionType.CALL, Street.PREFLOP),
    ])
    f = hero_preflop_flags(hand, 0)
    assert f["threebet_opp"] is True
    assert f["threebet"] is False


# ── Entegrasyon: gerçek oyun + ante → VPIP gerçekçi banttta ──────────
def _play_and_measure(n_hands=300, seed=11, ante=0.15):
    """Hero hep fold/check eden pasif bir oyuncu → VPIP ~0 olmalı.
    Ante VARSA bile VPIP şişmemeli (eski bug: ante VPIP'i ~%100 yapardı)."""
    random.seed(seed)
    gl = PokerGame(
        num_players=6, starting_stack=100.0,
        small_blind=0.5, big_blind=1.0, ante=ante,
        hero_seat=0, bot_archetype="Karma (Mixed)", paced_bots=True,
    )
    vpip = pfr = 0
    played = 0
    for _ in range(n_hands):
        gl.start_hand()
        guard = 0
        while guard < 400:
            guard += 1
            if gl.current_hand and gl.current_hand.is_complete:
                break
            progressed = gl.step_action()
            if gl.is_waiting_for_hero:
                h = gl.current_hand
                tc = h.to_call(h.hero_idx)
                # HER ZAMAN fold (call gerekiyorsa) ya da check → gönüllü para YOK
                gl.hero_act(ActionType.FOLD if tc > 0 else ActionType.CHECK, 0.0)
            elif not progressed:
                break
        if gl.hand_history:
            r = gl.hand_history[-1]
            played += 1
            if getattr(r, "hero_vpip", False):
                vpip += 1
            if getattr(r, "hero_pfr", False):
                pfr += 1
        for p in gl.players:
            p.reset_for_hand(100.0)
    return played, vpip, pfr


def test_always_fold_hero_has_near_zero_vpip_even_with_ante():
    """KÖK NEDEN regresyonu: hep fold/check eden hero, ante VARKEN bile
    VPIP ~0 olmalı (eski bug ante yüzünden ~%100 verirdi)."""
    played, vpip, pfr = _play_and_measure(ante=0.15)
    assert played > 50, f"yeterli el oynanmadı ({played})"
    vpip_pct = 100 * vpip / played
    # BB'de bedava check'ler VPIP DEĞİL; asla call/raise yok → 0 olmalı
    assert vpip_pct <= 2, f"hep-fold hero VPIP %{vpip_pct:.1f} (ante bug?)"
    assert pfr == 0, f"hiç raise etmeyen hero PFR {pfr} olmalı 0"


# ── İçeri alınan eller (CoinPoker/GG/PS) doğru bayrak üretir ──────────
from app.poker.hand_history_import import parse_hands   # noqa: E402

_HAND_WIN = (
    "PokerStars Hand #1: Hold'em No Limit ($0.50/$1.00) - 2024/01/01 12:00:00 ET\n"
    "Table 'T' 6-max Seat #1 is the button\n"
    "Seat 1: Hero ($100 in chips)\n"
    "Seat 2: Villain ($100 in chips)\n"
    "Hero: posts small blind $0.50\n"
    "Villain: posts big blind $1\n"
    "*** HOLE CARDS ***\n"
    "Dealt to Hero [Ah Kh]\n"
    "Hero: raises $2 to $3\n"
    "Villain: calls $2\n"
    "*** FLOP *** [7c 2d 9s]\n"
    "Villain: checks\n"
    "Hero: bets $4\n"
    "Villain: folds\n"
    "Uncalled bet ($4) returned to Hero\n"
    "Hero collected $5.50 from pot\n"
)

_HAND_3BET_CALL = (
    "PokerStars Hand #2: Hold'em No Limit ($0.50/$1.00) - 2024/01/01 12:05:00 ET\n"
    "Table 'T' 6-max Seat #2 is the button\n"
    "Seat 1: Hero ($100 in chips)\n"
    "Seat 2: Villain ($100 in chips)\n"
    "Villain: posts small blind $0.50\n"
    "Hero: posts big blind $1\n"
    "*** HOLE CARDS ***\n"
    "Dealt to Hero [Qd Jc]\n"
    "Villain: raises $2 to $3\n"
    "Hero: calls $2\n"
    "*** FLOP *** [Ah 7c 2d]\n"
    "Hero: checks\n"
    "Villain: bets $4\n"
    "Hero: calls $4\n"
    "*** TURN *** [Ah 7c 2d] [8s]\n"
    "Hero: checks\n"
    "Villain: bets $10\n"
    "Hero: folds\n"
    "Uncalled bet ($10) returned to Villain\n"
    "Villain collected $14 from pot\n"
)


def test_import_open_raise_flags():
    """Hero RFI açtı (önünde raise yok): VPIP+PFR, 3bet fırsatı YOK; flop bet."""
    h = parse_hands(_HAND_WIN)[0]
    assert h["hero_vpip"] == 1 and h["hero_pfr"] == 1
    assert h["hero_3bet_opp"] == 0 and h["hero_3bet"] == 0
    assert h["hero_postflop_aggr"] == 1 and h["hero_postflop_passive"] == 0


def test_import_call_vs_open_flags():
    """Villain açtı, hero call: VPIP ama PFR değil; 3bet fırsatı VAR, 3bet YOK;
    postflop 1 call (passive)."""
    h = parse_hands(_HAND_3BET_CALL)[0]
    assert h["hero_vpip"] == 1 and h["hero_pfr"] == 0
    assert h["hero_3bet_opp"] == 1 and h["hero_3bet"] == 0
    assert h["hero_postflop_passive"] == 1 and h["hero_postflop_aggr"] == 0


def test_db_stats_use_real_flags(tmp_path, monkeypatch):
    """get_player_stats artık bayraklardan sayar: 1 RFI + 1 call+fold-pre →
    VPIP %... PFR yalnız RFI. Kör-yatıran insta-fold VPIP'i şişirmez."""
    from app.db import repository as R
    monkeypatch.setattr(R, "DB_PATH", tmp_path / "stats.db")
    R.initialize_database()
    # 1) RFI raise (vpip+pfr)
    R.save_played_hand({"hand_id": 1, "hero_cards": "AhKh", "community": "7c2d9s",
                        "pot": 6, "hero_invested": 7, "hero_profit": 2.5,
                        "hero_won": 1, "streets_seen": 2,
                        "hero_vpip": 1, "hero_pfr": 1, "hero_3bet_opp": 0,
                        "hero_3bet": 0, "hero_postflop_aggr": 1,
                        "hero_postflop_passive": 0})
    # 2) BB bedava check, sonra preflop fold-yok ama postflop yatırım YOK → vpip 0
    R.save_played_hand({"hand_id": 2, "hero_cards": "9h4c", "community": "",
                        "pot": 1.5, "hero_invested": 1.0, "hero_profit": -1.0,
                        "hero_won": 0, "streets_seen": 1,
                        "hero_vpip": 0, "hero_pfr": 0, "hero_3bet_opp": 0,
                        "hero_3bet": 0, "hero_postflop_aggr": 0,
                        "hero_postflop_passive": 0})
    # 3) Ante'li el — invested>1 ama gönüllü değil (eski bug: VPIP sayardı)
    R.save_played_hand({"hand_id": 3, "hero_cards": "7d2c", "community": "",
                        "pot": 2, "hero_invested": 1.3, "hero_profit": -1.3,
                        "hero_won": 0, "streets_seen": 1,
                        "hero_vpip": 0, "hero_pfr": 0, "hero_3bet_opp": 0,
                        "hero_3bet": 0, "hero_postflop_aggr": 0,
                        "hero_postflop_passive": 0})
    s = R.get_player_stats()
    assert s["total_hands"] == 3
    assert abs(s["vpip"] - round(100 / 3, 1)) < 0.2, f"VPIP {s['vpip']} (1/3 olmalı)"
    assert abs(s["pfr"] - round(100 / 3, 1)) < 0.2, f"PFR {s['pfr']}"
    # Ante eli VPIP'i ŞİŞİRMEDİ (eski bug ~%66 verirdi)
    assert s["vpip"] < 40, f"VPIP {s['vpip']} ante bug regresyonu"
