"""Differential leak-avcısı: _hand_strength (sezgisel advice motoru) KATEGORİSİNİ
oyunun gerçek showdown evaluator'ı (evaluate_best_hand) ile karşılaştırır.

Sistem hero'nun GERÇEK elini (hole kartları katkı sağlıyorken) daha DÜŞÜK kategoriye
sokuyorsa = leak (örn. wheel düzü 'high card' sanması — D219). 'Board oynama' (hero
katkısı yok) durumları elenir (orada _hand_strength'in 'sende yok' demesi doğru).

Çalıştır:  PYTHONPATH=. .venv/bin/python tools/leak_audit_handstrength.py [N]
"""
import sys
import random
from itertools import combinations
from app.engine.hand_state import Card
from app.engine.evaluator import evaluate_best_hand, evaluate_5cards, _compare_hands
from app.engine.bot_brain import BotBrain, BOT_ARCHETYPES

_BB = BotBrain(BOT_ARCHETYPES["GTO Expert"])

# _hand_strength label → gerçek-rank kategorisi (0=royal..9=high card)
_LABEL_CAT = {
    "straight flush": 0,   # royal (0) + straight flush (1) — en üst, asla undervalue sayma
    "quads": 2, "full house": 3, "flush": 4, "straight": 5,
    "set": 6, "trips": 6, "two pair": 7, "top two pair": 7,
    "overpair": 8, "top pair": 8, "middle pair": 8, "underpair": 8,
    "high card": 9,
}
_RANKS = list(range(13))   # 0..12 (2..A)
_SUITS = ["c", "d", "h", "s"]
_DECK = [Card(rank="23456789TJQKA"[r], suit=s) for r in _RANKS for s in _SUITS]


def _board_only_cat(board):
    best = None
    for combo in combinations(board, 5):
        res = evaluate_5cards(list(combo))
        if best is None or _compare_hands(res, best) < 0:
            best = res
    return best[0]


def audit(n):
    random.seed(42)
    leaks = []
    checked = 0
    for _ in range(n):
        cards = random.sample(_DECK, 7)
        hole, board = cards[:2], cards[2:]
        checked += 1
        true_rank, _, true_name = evaluate_best_hand(hole, board)
        _s, _d, label = _BB._hand_strength(hole, board)
        sys_cat = _LABEL_CAT.get(label, 9)
        if sys_cat > true_rank:                 # sistem ZAYIF sınıfladı
            if true_rank < _board_only_cat(board):   # hero kartları GERÇEKTEN katkı sağlıyor
                leaks.append((true_name, label, sys_cat, true_rank,
                              "".join(c.rank + c.suit for c in hole),
                              " ".join(c.rank + c.suit for c in board)))
    # özet — leak tiplerini grupla
    from collections import Counter
    by_type = Counter((l[0], l[1]) for l in leaks)
    print(f"Tarandı: {checked}  ·  LEAK: {len(leaks)}")
    if leaks:
        print("\n=== LEAK TİPLERİ (gerçek-el → sistem-etiketi : adet) ===")
        for (tn, lab), ct in by_type.most_common():
            print(f"  {tn:18s} → {lab:14s} : {ct}")
        print("\n=== ÖRNEKLER ===")
        seen = set()
        for tn, lab, sc, tr, h, b in leaks:
            if (tn, lab) in seen:
                continue
            seen.add((tn, lab))
            print(f"  hole={h:6s} board={b:18s}  GERÇEK={tn}  ama sistem={lab!r}")
    else:
        print("✓ Kategori-leak YOK (sistem hiçbir gerçek eli düşük sınıflamadı).")
    return leaks


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200_000
    audit(n)
