"""SAYIM-MVP +EV DOĞRULAMA (kullanıcı: 'önce +EV doğrula', disiplin: 'kazanmazsa geri al').

Hero soyrac-baz oynar; postflop her kararda villain'in BU-EL aksiyon dizisi + tipi → R hesaplanır.
|R|≥2 ise R-sapması overlay uygulanır. overlay ON vs OFF aynı seed'lerle koşulur → bb/100 (cash)
+ ITM/yer (SNG) farkı = read-count'un GERÇEK +EV katkısı.

Overlay (denetimin en güçlü iddiası 'dizi-kilit' + capped saldırı):
  R≥+2 (value-ağır)  : CALL(facing bet)→FOLD  · bluff BET→CHECK
  R≤−2 (capped/zayıf): CHECK→BET(0.5pot)      · FOLD(facing bet)→CALL
Read-gated kalır (sim sadece DOĞRULAMA için overlay'i açar; advice_from_hand'e dokunulmaz).
"""
import sys, os, statistics as st
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.engine.game_loop import PokerGame
from app.engine.hand_state import ActionType, Street
from app.poker.opponent_typology import classify_hellmuth, type_prior
from app.poker.read_count import read_count
from tools.soyrac_bot_sim import SoyracBrain

_ST = {Street.PREFLOP: "preflop", Street.FLOP: "flop", Street.TURN: "turn", Street.RIVER: "river"}


def _hellmuth_key(profile):
    try:
        return classify_hellmuth(profile.vpip, profile.pfr, profile.aggression)[1].lower()
    except Exception:
        return None


def _preflop_raiser(hand):
    """İlk RAISE/BET eden (preflop aggressor / PFR) seat idx."""
    for a in hand.actions:
        if a.street == Street.PREFLOP and a.action_type in (ActionType.RAISE, ActionType.BET, ActionType.ALL_IN):
            return a.player_idx
    return None


def _main_villain(hand, hero_idx):
    """Hero'nun karşı karşıya olduğu villain: en son agresif aksiyonu yapan non-fold opp;
    yoksa aktif (non-fold) tek opp. Çoklu-pot'ta basitleştirme: son agresör."""
    folded = {a.player_idx for a in hand.actions if a.action_type == ActionType.FOLD}
    active = [i for i, p in enumerate(hand.players)
              if i != hero_idx and i not in folded and not getattr(p, "is_folded", False)]
    if not active:
        return None
    for a in reversed(hand.actions):
        if a.player_idx in active and a.action_type in (ActionType.BET, ActionType.RAISE, ActionType.ALL_IN):
            return a.player_idx
    return active[0]


def _events(hand, vidx):
    """Villain aksiyon dizisi → (first_action, [(street, role, action)]) range_narrowing formatı."""
    pfr = _preflop_raiser(hand)
    role = "aggressor" if vidx == pfr else "caller"
    vacts = [a for a in hand.actions if a.player_idx == vidx]
    first_action = "open"
    events = []
    seen_pre = False
    for a in vacts:
        stn = _ST.get(a.street, "flop")
        at = a.action_type
        if a.street == Street.PREFLOP:
            if not seen_pre:
                seen_pre = True
                if at in (ActionType.RAISE, ActionType.ALL_IN):
                    first_action = "3bet" if vidx != pfr else "open"
                elif at == ActionType.CALL:
                    first_action = "flat"
                    events.append(("preflop", "facing_raise", "call"))   # −2 (capped)
            continue
        # postflop
        if role == "aggressor":
            if at == ActionType.CHECK:
                events.append((stn, "aggressor", "check"))
            elif at in (ActionType.BET, ActionType.ALL_IN):
                events.append((stn, "aggressor", "barrel" if a.street in (Street.TURN, Street.RIVER) else "cbet"))
            elif at == ActionType.RAISE:
                events.append((stn, "aggressor", "barrel"))
            elif at == ActionType.CALL:
                events.append((stn, "aggressor", "call"))
        else:
            if at == ActionType.CHECK:
                events.append((stn, "caller", "check"))
            elif at == ActionType.RAISE:
                events.append((stn, "caller", "check_raise"))     # +2 (dizi-kilit)
            elif at == ActionType.CALL:
                events.append((stn, "caller", "check_call"))
            elif at in (ActionType.BET, ActionType.ALL_IN):
                events.append((stn, "caller", "donk"))
    return first_action, events


def _compute_R(hand, hero_idx, gl):
    vidx = _main_villain(hand, hero_idx)
    if vidx is None or vidx not in gl.bots:
        return 0, None
    vtype = _hellmuth_key(gl.bots[vidx].profile)
    fa, events = _events(hand, vidx)
    pos = "BTN"
    rc = read_count(vtype, events, villain_pos=pos, first_action=fa)
    return rc.R, rc


def _overlay(at, amt, R, hand, hero_idx, pf):
    """|R|≥2 → R-sapması uygula — EL-GÜCÜYLE GATE'li (tasarım: 'MARJİNAL fold, İNCE value';
    value'yu KORU, çöple call ETME). Sadece postflop + gözlenen dizi."""
    if abs(R) < 2 or hand.street == Street.PREFLOP or not pf:
        return at, amt
    tier = pf.get("tier", "") or ""
    eq = pf.get("eq", 0.0) or 0.0
    to_call = hand.to_call(hero_idx)
    pot = getattr(hand, "pot", 0.0) or 0.0
    marginal = tier in ("BLUFF-CATCH", "ZAYIF", "ORTA", "HAVA")
    value = tier in ("GÜÇLÜ", "NUT")
    if R >= 2:   # value-ağır → marjinal bluff-catch'i FOLD + blöf KES (value'yu koru)
        if at == ActionType.CALL and to_call > 0 and marginal and not value:
            return ActionType.FOLD, 0.0
        if at in (ActionType.BET, ActionType.RAISE) and to_call <= 0.01 and tier in ("HAVA", "ZAYIF"):
            return ActionType.CHECK, 0.0
    else:        # R≤−2 capped → saldır: ince value-bet + HAFİF call (çöp DEĞİL)
        if at == ActionType.CHECK and to_call <= 0.01 and tier in ("ORTA", "BLUFF-CATCH", "GÜÇLÜ"):
            return ActionType.BET, max(hand.big_blind, round(0.5 * pot, 1))
        if at == ActionType.FOLD and to_call > 0 and tier in ("BLUFF-CATCH", "ORTA") and eq >= 0.30:
            return ActionType.CALL, to_call
    return at, amt


def run_cash(opponents, hands_n, seed, overlay):
    import random as _rnd; _rnd.seed(seed)
    names = ["Soyrac"] + list(opponents); n = len(names)
    sb, bb, stack = 0.5, 1.0, 100.0
    gl = PokerGame(num_players=n, starting_stack=stack, small_blind=sb, big_blind=bb,
                   ante=0, hero_seat=0, bot_archetypes=names[1:],
                   player_names=[f"a{i}" for i in range(1, n)], paced_bots=True)
    soy = SoyracBrain()
    net = 0.0
    for _h in range(hands_n):
        for p in gl.players:
            p.stack = stack; p.is_eliminated = False
        gl.start_hand()
        guard = 0
        while guard < 400:
            guard += 1
            hh = gl.current_hand
            if hh and hh.is_complete:
                break
            prog = gl.step_action()
            if gl.is_waiting_for_hero:
                h = gl.current_hand; hi = h.hero_idx
                at, amt = soy.decide(h, hi)
                if overlay and h.street != Street.PREFLOP:
                    R, _ = _compute_R(h, hi, gl)
                    if abs(R) >= 2:
                        from app.poker.soyrac_advisor import soyrac_postflop_advice
                        pf = soyrac_postflop_advice(h, hi)
                        at, amt = _overlay(at, amt, R, h, hi, pf)
                gl.hero_act(at, amt)
            elif not prog:
                break
        net += gl.players[0].stack - stack
    return round(100 * net / hands_n, 2)


FIELDS = {
    "soft":  ["Calling Station", "Fish", "Calling Station", "Nit", "TAG"],
    "orta":  ["TAG", "Reg", "Nit", "LAG", "Fish"],
    "tough": ["Reg", "TAG", "Shark", "Reg", "LAG"],
}

if __name__ == "__main__":
    SEEDS = list(range(int(os.environ.get("SEEDS", "6"))))
    HANDS = int(os.environ.get("HANDS", "4000"))
    print(f"=== SAYIM-MVP +EV DOĞRULAMA (cash 6-max, {HANDS} el × {len(SEEDS)} seed) ===")
    print(f"{'alan':6} {'OFF (GTO-baz)':>14} {'ON (R-overlay)':>15} {'Δ bb/100':>10}")
    for fld_name, opps in FIELDS.items():
        off = [run_cash(opps, HANDS, 1000 + s, False) for s in SEEDS]
        on = [run_cash(opps, HANDS, 1000 + s, True) for s in SEEDS]
        mo, mn = st.mean(off), st.mean(on)
        print(f"{fld_name:6} {mo:>+14.1f} {mn:>+15.1f} {mn - mo:>+10.1f}")
