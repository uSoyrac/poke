"""D336 (app-QA: engine 'dead-money çip kaybı' iddiası DOĞRULANDI → abartıydı): toplam çip her el
KORUNUR. Side-pot'lu çoklu-all-in'de ufak float-yuvarlama (<0.05) tolere edilir; SİSTEMATİK çip
kaybı/yaratımı (>0.05) = gerçek bug → test kırılır. Engine muhasebe regresyon-guard'ı."""
import random

from app.engine.game_loop import PokerGame
from app.engine.hand_state import ActionType


def _play_hand(gl, hero_action):
    gl.start_hand()
    g = 0
    while g < 300:
        g += 1
        h = gl.current_hand
        if h and h.is_complete:
            break
        prog = gl.step_action()
        if gl.is_waiting_for_hero:
            gl.hero_act(hero_action)
        elif not prog:
            break


def test_chip_conservation_normal():
    """6-max, çeşitli el — toplam çip her el sabit (float toleransı)."""
    worst = 0.0
    for seed in range(25):
        random.seed(seed)
        gl = PokerGame(num_players=6, starting_stack=100, small_blind=0.5, big_blind=1.0,
                       ante=0, hero_seat=0,
                       bot_archetypes=["Fish", "TAG", "LAG", "Nit", "Maniac"],
                       player_names=list("abcde"))
        for _ in range(20):
            before = sum(p.stack for p in gl.players)
            _play_hand(gl, ActionType.FOLD)
            worst = max(worst, abs(before - sum(p.stack for p in gl.players)))
    assert worst < 0.05, f"çip-korunumu bozuldu: en kötü Δ={worst}"


def test_chip_conservation_sidepots():
    """Kısa+eşit-olmayan stack + all-in → side-pot; toplam çip yine korunur (float-tol)."""
    worst = 0.0
    for seed in range(30):
        random.seed(seed)
        gl = PokerGame(num_players=5, starting_stack=12, small_blind=0.5, big_blind=1.0,
                       ante=0, hero_seat=0,
                       bot_archetypes=["Maniac", "LAG", "Fish", "Maniac"],
                       player_names=list("abcd"))
        gl.players[1].stack = 6; gl.players[2].stack = 20; gl.players[3].stack = 8
        for _ in range(15):
            before = sum(p.stack for p in gl.players)
            _play_hand(gl, ActionType.ALL_IN if random.random() < 0.5 else ActionType.CALL)
            worst = max(worst, abs(before - sum(p.stack for p in gl.players)))
            for p in gl.players:
                if p.stack <= 0:
                    p.stack = 12
    assert worst < 0.05, f"side-pot çip-korunumu bozuldu: en kötü Δ={worst}"
