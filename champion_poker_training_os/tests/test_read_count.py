"""D-A (SAYIM-MVP çekirdek read_count): tip-prior + gözlenen dizi → tek-sayı R.
READ-GATED identity + prior-tek-başına-sapma-yok (bot fidelity güvenliği)."""
from app.poker.opponent_typology import HELLMUTH_PRIOR, type_prior
from app.poker.range_narrowing import narrow
from app.poker.read_count import read_count, read_deviation


def test_prior_table():
    assert type_prior("elephant") == 1 and type_prior("mouse") == 1 and type_prior("eagle") == 1
    assert type_prior("lion") == 0 and type_prior("jackal") == -1
    assert type_prior(None) == 0 and type_prior("unknown") == 0
    assert all(-1 <= v <= 1 for v in HELLMUTH_PRIOR.values()), "prior ±1 cap"


def test_identity_no_villain_no_events():
    """READ-GATED: villain yok + dizi yok → R=0, low güven, GTO (bot identity korunur)."""
    rc = read_count(None, [])
    assert rc.R == 0 and rc.confidence == "low" and "GTO" in rc.deviation


def test_prior_alone_no_deviation():
    """Prior TEK BAŞINA (±1) asla sapma açmaz — gözlenen dizi şart."""
    for t in ("elephant", "mouse", "eagle", "jackal"):
        rc = read_count(t, [])           # dizi yok
        assert abs(rc.R) < 2 and "GTO" in rc.deviation, f"{t} prior-tek-başına sapma açmamalı"
        assert rc.confidence == "low"


def test_sequence_opens_value_deviation():
    """Gözlenen dizi (check-raise +2, prior=0 lion) → high güven + value-sapma."""
    rc = read_count("lion", [("flop", "caller", "check_raise")], first_action="open")
    assert rc.R >= 2 and rc.confidence == "high" and "VALUE" in rc.deviation


def test_capped_sequence():
    """flat (−2, prior=0 lion) → capped sapma (R≤−2)."""
    rc = read_count("lion", [("preflop", "facing_raise", "call")], first_action="flat")
    assert rc.R <= -2 and "CAPPED" in rc.deviation and rc.confidence == "high"


def test_scale_single_source():
    """read_count R'si = prior + motor running_count (panel=insan=motor TEK ölçek)."""
    evs = [("flop", "caller", "check_raise")]
    nr = narrow("BTN", evs, "open")
    rc = read_count("jackal", evs, first_action="open")
    assert rc.R == type_prior("jackal") + nr.running_count
    assert rc.steps == list(nr.rc_steps)


# ── read_deviation: D313-validated el-gücü-gate'li sapma ──
def test_deviation_neutral_below_threshold():
    changed, act, _ = read_deviation(1, "HAVA", facing_bet=True)
    assert not changed and act == ""


def test_deviation_value_folds_marginal_keeps_value():
    """R≥+2: MARJİNAL bluff-catch fold, ama VALUE (GÜÇLÜ/NUT) KORU (çift-kritik fidelity dersi)."""
    ch, act, _ = read_deviation(2, "BLUFF-CATCH", facing_bet=True)
    assert ch and act == "FOLD"
    ch2, act2, _ = read_deviation(2, "NUT", facing_bet=True)        # value korunur
    assert not ch2, "value el R≥+2'de bile fold'lanmamalı"
    ch3, _, _ = read_deviation(2, "GÜÇLÜ", facing_bet=True)
    assert not ch3


def test_deviation_value_cuts_own_bluff():
    ch, act, _ = read_deviation(3, "HAVA", facing_bet=False)
    assert ch and act == "CHECK"


def test_deviation_capped_attacks_not_trash():
    """R≤−2: capped'e karşı ince value BET + hafif CALL; ama ÇÖPLE call YOK."""
    ch, act, _ = read_deviation(-2, "ORTA", facing_bet=False)
    assert ch and act == "BET"
    ch2, act2, _ = read_deviation(-2, "BLUFF-CATCH", facing_bet=True, eq=0.40)
    assert ch2 and act2 == "CALL"
    ch3, _, _ = read_deviation(-2, "HAVA", facing_bet=True, eq=0.10)   # çöp → call YOK
    assert not ch3
    ch4, _, _ = read_deviation(-2, "BLUFF-CATCH", facing_bet=True, eq=0.20)  # eq düşük → call YOK
    assert not ch4


def test_dizi_kilit_floor_optin():
    """Dizi-kilidi floor OPT-IN (A/B EV-nötr → default kapalı): flat(−2)+check-raise(+2)
    naive → R≈0 (trap kaçar); dizi_kilit=True → value-lock floor R≥+2."""
    evs = [("preflop", "facing_raise", "call"), ("flop", "caller", "check_raise")]
    naive = read_count("lion", evs, first_action="flat")              # default KAPALI
    floor = read_count("lion", evs, first_action="flat", dizi_kilit=True)
    assert naive.R < 2, f"naive flat+XR sıfırlanır: {naive.R}"
    assert floor.R >= 2, f"floor value-lock: {floor.R}"


def _build_deviating_hand():
    """Villain flop check-raise (preflop flat YOK) → R≥2 → cash'te sapma (FOLD) tetikler."""
    from app.engine.game_loop import PokerGame
    from app.engine.hand_state import Street, Card, ActionType, Action
    import random as _r
    _r.seed(5)
    gl = PokerGame(num_players=2, starting_stack=100, small_blind=0.5, big_blind=1.0,
                   ante=0, hero_seat=0, bot_archetypes=["Reg"], player_names=["v"])
    gl.start_hand()
    h = gl.current_hand; hi = h.hero_idx; vi = 1 - hi
    h.community = [Card("Q", "d"), Card("7", "c"), Card("2", "h")]
    h.street = Street.FLOP
    h.actions = [Action(player_idx=hi, action_type=ActionType.RAISE, amount=3, street=Street.PREFLOP),
                 Action(player_idx=vi, action_type=ActionType.RAISE, amount=9, street=Street.FLOP)]
    h.current_bet = 9.0
    for p in h.players:
        p.current_bet = 0.0
    return h, hi


# Station (Elephant, prior +1) → check-raise(+2) ile R=3
_VSTATS = {"vpip": 44, "pfr": 7, "aggression": 0.8, "three_bet": 2, "obs_hands": 80}


def test_d319_read_count_fires_with_villain_stats():
    """read_count alanı villain_stats verilince dolar (cash wiring); yoksa None (identity)."""
    from app.poker.soyrac_advisor import soyrac_explain
    h, hi = _build_deviating_hand()
    out = soyrac_explain("8h6c", "BB", scenario="Postflop", hand=h, hero_idx=hi,
                         villain_stats=_VSTATS, tourney=False)
    assert out.get("read_count") and out["read_count"]["context"] == "cash"
    h2, hi2 = _build_deviating_hand()
    out2 = soyrac_explain("8h6c", "BB", scenario="Postflop", hand=h2, hero_idx=hi2)
    assert out2.get("read_count") is None     # villain_stats yok → None (bot identity)


def test_d319_tourney_suppresses_deviation():
    """D319 (SNG kanıtı: SAYIM cash-aracı): AYNI sapan elde cash → deviation_changed True
    (FOLD), tourney → False (R bilgi-amaçlı). Non-vacuous: cash gerçekten sapar."""
    from app.poker.soyrac_advisor import soyrac_explain
    hc, hic = _build_deviating_hand()
    cash = soyrac_explain("8h6c", "BB", scenario="Postflop", hand=hc, hero_idx=hic,
                          villain_stats=_VSTATS, tourney=False)["read_count"]
    ht, hit = _build_deviating_hand()
    trny = soyrac_explain("8h6c", "BB", scenario="Postflop", hand=ht, hero_idx=hit,
                          villain_stats=_VSTATS, tourney=True)["read_count"]
    assert cash["R"] >= 2 and cash["deviation_changed"] is True and cash["context"] == "cash"
    assert trny["deviation_changed"] is False and trny["context"] == "tournament", \
        "turnuvada sapma ÖNERİLMEMELİ (SAYIM cash-aracı)"


def test_read_count_drill():
    """'R tahmin et' drill: doğru R seçeneklerde + skorlama + reveal tally."""
    import random as _r
    from app.poker.read_trainer import generate_read_count_drill, score_read_count
    d = generate_read_count_drill(_r.Random(7))
    assert d.correct_R in d.choices and len(d.choices) == 5
    ok = score_read_count(d.correct_R, d)
    assert ok["correct"] and ok["correct_R"] == d.correct_R and ok["steps"]
    assert not score_read_count(d.correct_R + 1, d)["correct"]
