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


def _compute_R(hand, hero_idx, gl):
    """TEK-KAYNAK: read_count.villain_sequence (canlı koç ile aynı çıkarım)."""
    from app.poker.read_count import villain_sequence
    vidx, fa, events = villain_sequence(hand, hero_idx)
    if vidx is None or vidx not in gl.bots:
        return 0, None
    vtype = _hellmuth_key(gl.bots[vidx].profile)
    rc = read_count(vtype, events, villain_pos="BTN", first_action=fa,
                    dizi_kilit=(os.environ.get("DIZI", "1") == "1"))
    return rc.R, rc


def _overlay(at, amt, R, hand, hero_idx, pf):
    """TEK-KAYNAK read_count.read_deviation (canlı koç ile aynı VALIDATED kurallar).
    read_deviation R+tier→sapma-aksiyonu verir; biz yalnız base-aksiyon yönle uyumluysa uygularız."""
    from app.poker.read_count import read_deviation
    if abs(R) < 2 or hand.street == Street.PREFLOP or not pf:
        return at, amt
    tier = pf.get("tier", "") or ""
    eq = pf.get("eq", 0.0) or 0.0
    to_call = hand.to_call(hero_idx)
    changed, action, _ = read_deviation(R, tier, facing_bet=(to_call > 0), eq=eq)
    if not changed:
        return at, amt
    # SURVIVAL modu (turnuva hipotezi): yalnız R≥+2 hayatta-kalma sapması (FOLD/CHECK);
    # R≤−2 saldırı (BET/CALL = varyans) ATLA.
    if os.environ.get("SURVIVAL") == "1" and action in ("BET", "CALL"):
        return at, amt
    if action == "FOLD" and at == ActionType.CALL:
        return ActionType.FOLD, 0.0
    if action == "CHECK" and at in (ActionType.BET, ActionType.RAISE):
        return ActionType.CHECK, 0.0
    if action == "BET" and at == ActionType.CHECK:
        pot = getattr(hand, "pot", 0.0) or 0.0
        return ActionType.BET, max(hand.big_blind, round(0.5 * pot, 1))
    if action == "CALL" and at == ActionType.FOLD:
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


_SNG_LEVELS = [(10, 20), (15, 30), (25, 50), (40, 80), (60, 120), (100, 200),
               (150, 300), (250, 500), (400, 800), (600, 1200)]
_SNG_PAYOUT = {1: 0.50, 2: 0.30, 3: 0.20}    # 9-max SNG top-3 (prize pool = 9 buyin)


def run_sng(opponents, seed, overlay):
    """9-max SNG → hero'nun yeri (1=birinci). overlay: postflop |R|≥2 R-sapması."""
    import random as _rnd; _rnd.seed(seed)
    names = ["Soyrac"] + list(opponents); n = len(names)
    gl = PokerGame(num_players=n, starting_stack=1500, small_blind=10, big_blind=20,
                   ante=0, hero_seat=0, bot_archetypes=names[1:],
                   player_names=[f"a{i}" for i in range(1, n)], paced_bots=True)
    soy = SoyracBrain()
    for b in gl.bots.values():
        b.tournament_mode = True
    finish, hands = [], 0
    while sum(1 for p in gl.players if p.stack > 0) > 1:
        sb, bb = _SNG_LEVELS[min(hands // 10, len(_SNG_LEVELS) - 1)]
        gl.small_blind, gl.big_blind = sb, bb
        for p in gl.players:
            if p.stack <= 0:
                p.is_eliminated = True
        gl.start_hand()
        guard = 0
        while guard < 800:
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
        for i, p in enumerate(gl.players):
            if p.stack <= 0 and i not in finish:
                finish.append(i)
        hands += 1
        if hands > 600:
            break
    survivor = [i for i, p in enumerate(gl.players) if p.stack > 0]
    order = survivor + finish[::-1]
    place = {idx: rank + 1 for rank, idx in enumerate(order)}
    return place.get(0, n)        # hero'nun yeri


FIELDS = {
    "soft":  ["Calling Station", "Fish", "Calling Station", "Nit", "TAG"],
    "orta":  ["TAG", "Reg", "Nit", "LAG", "Fish"],
    "tough": ["Reg", "TAG", "Shark", "Reg", "LAG"],
}

def _sng_stats(places, n=9):
    itm = 100 * sum(1 for p in places if p <= 3) / len(places)
    avg = sum(places) / len(places)
    roi = 100 * (sum(_SNG_PAYOUT.get(p, 0.0) * n for p in places) / len(places) - 1)
    return itm, avg, roi


if __name__ == "__main__":
    if os.environ.get("MODE") == "sng":
        N = int(os.environ.get("SNGS", "60"))
        print(f"=== SAYIM-MVP TURNUVA (9-max SNG, {N} adet/alan) ===")
        print(f"{'alan':6} {'OFF ITM/ROI':>18} {'ON ITM/ROI':>18} {'Δ ROI':>8}")
        for fld_name, opps in {"soft": ["Calling Station", "Fish", "Nit", "TAG", "Calling Station", "Fish", "Nit", "Reg"],
                               "orta": ["TAG", "Reg", "Nit", "LAG", "Fish", "TAG", "Reg", "Nit"]}.items():
            off = [run_sng(opps, 2000 + s, False) for s in range(N)]
            on = [run_sng(opps, 2000 + s, True) for s in range(N)]
            io, ao, ro = _sng_stats(off)
            ino, ano, rno = _sng_stats(on)
            print(f"{fld_name:6}  ITM%{io:4.1f} ROI{ro:+6.1f}   ITM%{ino:4.1f} ROI{rno:+6.1f}   {rno - ro:>+7.1f}")
        raise SystemExit(0)
    SEEDS = list(range(int(os.environ.get("SEEDS", "6"))))
    HANDS = int(os.environ.get("HANDS", "4000"))
    print(f"=== SAYIM-MVP +EV DOĞRULAMA (cash 6-max, {HANDS} el × {len(SEEDS)} seed) ===")
    print(f"{'alan':6} {'OFF (GTO-baz)':>14} {'ON (R-overlay)':>15} {'Δ bb/100':>10}")
    for fld_name, opps in FIELDS.items():
        off = [run_cash(opps, HANDS, 1000 + s, False) for s in SEEDS]
        on = [run_cash(opps, HANDS, 1000 + s, True) for s in SEEDS]
        mo, mn = st.mean(off), st.mean(on)
        print(f"{fld_name:6} {mo:>+14.1f} {mn:>+15.1f} {mn - mo:>+10.1f}")
