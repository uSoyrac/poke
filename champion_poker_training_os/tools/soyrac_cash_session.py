"""CASH BANKROLL SESSION sim: $10 ile masaya otur (NL10 = $0.05/$0.10, 100bb), 1000 el oyna,
stack DEVREDER (gerçek cash; rebuy YOK — $10 hepsi bu), bust → biter. 100 bağımsız oturum.
Her oturumun 1000-el sonu final $'ı + özet dağılım. pure_book Soyrac vs gerçekçi soft NL10 alanı.
SİMÜLASYON = GERÇEK OYNATMA (winrate+varyans uydurma YOK; her el gerçekten oynanır).

PYTHONPATH=. QT_QPA_PLATFORM=offscreen .venv/bin/python tools/soyrac_cash_session.py
"""
from __future__ import annotations
import random
import sys
import statistics as st

from app.engine.game_loop import PokerGame
from app.engine.hand_state import ActionType
from tools.soyrac_bot_sim import SoyracBrain
from tools.soyrac_matrix_sim import sample_field, PROFILES

SESSIONS = 100
HANDS = 1000
START_BB = 100.0          # 1 buy-in = $10 @ NL10 (1bb=$0.10, 100bb)
BB_USD = 0.10
TABLE = 6                 # 6-max NL10
BUYINS = int(sys.argv[1]) if len(sys.argv) > 1 else 1   # bankroll = BUYINS × $10


def session(seed, buyins=1):
    random.seed(seed)
    field = sample_field(PROFILES["soft"], TABLE - 1, 7000)   # gerçekçi soft NL10 (balık-ağır)
    gl = PokerGame(num_players=TABLE, starting_stack=START_BB, small_blind=0.5, big_blind=1.0,
                   ante=0, hero_seat=0, bot_archetypes=field,
                   player_names=[f"a{i}" for i in range(1, TABLE)], paced_bots=True)
    soy = SoyracBrain(); soy.tournament_mode = False
    for b in gl.bots.values():
        b.tournament_mode = False
    hero = gl.players[0]
    hero.stack = START_BB
    rebuys_left = buyins - 1          # ilki masada; kalanlar bankroll'da
    ruined = False
    for h in range(HANDS):
        if hero.stack < 1.0:                          # mevcut stack battı
            if rebuys_left > 0:
                rebuys_left -= 1
                hero.stack = START_BB                  # bankroll'dan rebuy
            else:
                ruined = True                          # tüm buy-in'ler bitti = RUİN
                break
        for i, p in enumerate(gl.players):             # rakipler her el 100bb; HERO DEVREDER
            if i != 0:
                p.stack = START_BB
            p.is_eliminated = False
        hero.is_eliminated = False
        gl.start_hand()
        guard = 0
        while guard < 800:
            guard += 1
            hh = gl.current_hand
            if hh and hh.is_complete:
                break
            prog = gl.step_action()
            if gl.is_waiting_for_hero:
                at, amt = soy.decide(gl.current_hand, gl.current_hand.hero_idx)
                gl.hero_act(at, amt)
            elif not prog:
                break
    total_bb = max(0.0, hero.stack) + rebuys_left * START_BB   # masadaki + kullanılmamış buy-in'ler
    return total_bb, ruined


def main():
    cap = BUYINS * 10.0
    print(f"=== CASH SESSION: ${cap:.0f} bankroll ({BUYINS} buy-in × $10 NL10) × 1000 el × "
          f"{SESSIONS} oturum (soft alan) ===\n")
    rows = []
    for s in range(SESSIONS):
        tb, ruined = session(600 + s, BUYINS)
        rows.append((s + 1, tb, ruined))
    print(f"  her oturumun 1000-el sonu TOPLAM BAKİYE ($):  (R=ruin/tüm bankroll bitti)")
    line = ""
    for i, (sn, tb, ruined) in enumerate(rows):
        usd = tb * BB_USD
        tag = "R" if ruined else " "
        line += f"#{sn:>3}:${usd:7.2f}{tag}  "
        if (i + 1) % 5 == 0:
            print("   " + line.rstrip()); line = ""
    if line:
        print("   " + line.rstrip())
    usds = [tb * BB_USD for _, tb, _ in rows]
    profit = [u - cap for u in usds]
    n_ruin = sum(1 for _, _, r in rows if r)
    n_win = sum(1 for p in profit if p > 0)
    n_2x = sum(1 for u in usds if u >= 2 * cap)
    print("\n  ───────── ÖZET ─────────")
    print(f"  Başlangıç: ${cap:.0f} ({BUYINS} buy-in) × {SESSIONS} oturum, her biri 1000 el")
    print(f"  Ortalama final : ${st.mean(usds):.2f}   (ort. kâr/oturum ${st.mean(profit):+.2f})")
    print(f"  Medyan  final  : ${st.median(usds):.2f}")
    print(f"  En iyi / en kötü: ${max(usds):.2f} / ${min(usds):.2f}")
    print(f"  Kârlı oturum   : {n_win}/{SESSIONS} (%{100*n_win/SESSIONS:.0f})")
    print(f"  2×+ (${2*cap:.0f}+)   : {n_2x}/{SESSIONS} (%{100*n_2x/SESSIONS:.0f})")
    print(f"  RUİN (tüm bankroll battı): {n_ruin}/{SESSIONS} (%{100*n_ruin/SESSIONS:.0f})")
    total = sum(profit)
    print(f"  Toplam net ({SESSIONS} oturum, ${cap*SESSIONS:.0f} yatırım): ${total:+.2f}"
          f"  → ROI %{100*total/(cap*SESSIONS):+.1f}")
    print(f"\n  Not: NL10, 1bb=$0.10. {BUYINS} buy-in bankroll (stack battıkça rebuy; tümü bitince ruin).")


if __name__ == "__main__":
    main()
