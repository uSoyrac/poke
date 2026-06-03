"""Headless all-bot multi-table MTT — GERÇEK oynatma (varsayım yok).

Her oyuncuya realistic_mtt_mix ile bir arketip atanır; tüm koltuklar GERÇEK
BotBrain kararlarıyla oynar (hero koltuğu da bir bot beyniyle sürülür). Gerçek
el dağıtımı, bahis, eleme, masa-dengeleme ve blind artışı → kim final masaya /
ilk 3'e kalır EMERGENT olarak ölçülür. Skill baştan atanmaz; profilin oyun
mantığı ne yaparsa o olur.

run_mtt(field_size, seed) → {'finish': [arketip...1.den sona], 'final_table':
[son 9 arketip], 'top3': [1,2,3], 'hands': toplam el}.
"""
from __future__ import annotations

import random
from typing import List

from app.engine.bot_brain import BOT_ARCHETYPES, BotBrain, realistic_mtt_mix
from app.engine.game_loop import PokerGame
from app.engine.hand_state import ActionType


# Sıkıştırılmış ama gerçek blind şeması (chip). Hızlı çözülsün diye level'ler
# agresif yükselir; yine de derin→push/fold geçişi gerçek yaşanır.
_LEVELS = [
    (25, 50, 0), (40, 80, 0), (60, 120, 0), (100, 200, 25),
    (150, 300, 40), (250, 500, 60), (400, 800, 100), (600, 1200, 150),
    (1000, 2000, 250), (1500, 3000, 400), (2500, 5000, 600),
    (4000, 8000, 1000), (6000, 12000, 1500), (10000, 20000, 2500),
    (15000, 30000, 4000), (25000, 50000, 6000), (40000, 80000, 10000),
]
_START_CHIPS = 5000          # 100bb @ ilk level
_HANDS_PER_LEVEL = 8         # global el / level
_TABLE_MAX = 9


class _Player:
    __slots__ = ("pid", "arch", "stack")
    def __init__(self, pid: int, arch: str, stack: float):
        self.pid = pid
        self.arch = arch
        self.stack = stack


def _play_one_hand(table: List[_Player], sb: float, bb: float, ante: float,
                   button: int) -> None:
    """Bir masada GERÇEK bir el oynat; stack'leri günceller (yerinde)."""
    n = len(table)
    if n < 2:
        return
    archs = [p.arch for p in table]
    gl = PokerGame(
        num_players=n, starting_stack=_START_CHIPS,
        small_blind=sb, big_blind=bb, ante=ante,
        hero_seat=0, bot_archetypes=archs[1:],
        player_names=[f"p{p.pid}" for p in table[1:]],
        paced_bots=True,
    )
    # Taşınan gerçek stack'leri yükle + butonu ayarla
    for i, p in enumerate(table):
        gl.players[i].stack = p.stack
    gl.dealer_idx = button % n
    hero_brain = BotBrain(BOT_ARCHETYPES.get(archs[0], BOT_ARCHETYPES["Balanced Reg"]))

    gl.start_hand()
    guard = 0
    while guard < 600:
        guard += 1
        h = gl.current_hand
        if h and h.is_complete:
            break
        progressed = gl.step_action()
        if gl.is_waiting_for_hero:
            hh = gl.current_hand
            at, amt = hero_brain.decide(hh, hh.hero_idx)
            gl.hero_act(at, amt)
        elif not progressed:
            break
    # Stack'leri geri yaz
    for i, p in enumerate(table):
        p.stack = max(0.0, gl.players[i].stack)


def run_mtt(field_size: int, seed: int = 0) -> dict:
    rng = random.Random(seed)
    archs = realistic_mtt_mix(field_size, rng=rng)
    alive = [_Player(i, archs[i], float(_START_CHIPS)) for i in range(field_size)]
    finish: List[str] = []          # finish[0] = SON elenen (kazanan en sonda eklenir)
    hands = 0
    level = 0
    buttons: dict = {}              # table-key → button index (kabaca)

    def _rebalance() -> List[List[_Player]]:
        rng.shuffle(alive)
        n_tables = max(1, (len(alive) + _TABLE_MAX - 1) // _TABLE_MAX)
        tables = [alive[i::n_tables] for i in range(n_tables)]  # ~eşit dağıt
        return [t for t in tables if t]

    guard_rounds = 0
    while len(alive) > 1 and guard_rounds < 200000:
        guard_rounds += 1
        sb, bb, ante = _LEVELS[min(level, len(_LEVELS) - 1)]
        tables = _rebalance()
        for ti, table in enumerate(tables):
            if len(alive) <= 1:
                break
            if len(table) < 2:
                continue
            btn = buttons.get(ti, 0)
            _play_one_hand(table, sb, bb, ante, btn)
            buttons[ti] = (btn + 1) % len(table)
            hands += 1
            # Bu masadaki bust'ları işle (place = mevcut alive sayısı)
            busted = [p for p in table if p.stack <= 0]
            for p in busted:
                finish.append(p.arch)      # daha erken elenen → finish'in başında
                alive.remove(p)
        if hands and hands % (_HANDS_PER_LEVEL * max(1, len(tables))) == 0:
            level += 1
    # Kazanan (son kalan) en sona
    if alive:
        finish.append(alive[0].arch)

    # finish: [ilk elenen ... son=kazanan]. Yer numarası: son eleman = 1.
    order_1st_to_last = list(reversed(finish))   # [1., 2., 3., ...]
    final_table = order_1st_to_last[:min(9, len(order_1st_to_last))]
    top3 = order_1st_to_last[:3]
    return {
        "field_size": field_size,
        "hands": hands,
        "finish_1st_to_last": order_1st_to_last,
        "final_table": final_table,
        "top3": top3,
    }
