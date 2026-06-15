"""VALUE-LAYER leak audit: sistemin el-DEĞERİni (eq + threat-haircut + tier/aksiyon)
gerçek Monte-Carlo equity'yle (showdown evaluator, vs gerçekçi devam-range'i) karşılaştır.
Kategori-audit (leak_audit_handstrength) doğru SINIF'ı test eder; bu DEĞER'i test eder
(D218/D220 sınıfı: within-category over/under-valuation, threat mis-calibration).

Çalıştır: PYTHONPATH=. .venv/bin/python tools/leak_audit_value.py [N]
"""
import sys, random
from collections import defaultdict
from itertools import combinations
from app.engine.hand_state import Card
from app.poker.mc_equity import calculate_equity
from app.poker.mtt_ranges import get_ranked_hands
from app.poker.soyrac_advisor import _explain_bb, _draw_equity, soyrac_postflop_advice
from app.poker.postflop_gto import classify_board
import types

_RANKS = "23456789TJQKA"
_SUITS = "cdhs"
_DECK = [Card(rank=r, suit=s) for r in _RANKS for s in _SUITS]
_TOP40 = get_ranked_hands()[:68]   # gerçekçi devam-range (~top %40)


def _spot_advice(hole, board, to_call):
    hero = types.SimpleNamespace(hole_cards=hole, stack=80.0, is_folded=False, is_eliminated=False)
    v = types.SimpleNamespace(hole_cards=[], stack=80.0, is_folded=False, is_eliminated=False)
    hand = types.SimpleNamespace(players=[hero, v], community=board, street=None,
                                 pot=10.0, active_count=2, to_call=lambda i: to_call)
    return soyrac_postflop_advice(hand, 0)


def audit(n):
    random.seed(7)
    flags = []
    bias = defaultdict(lambda: {"n": 0, "sys": 0.0, "true": 0.0})
    checked = 0
    for _ in range(n):
        ncomm = random.choice([3, 4, 5])
        cards = random.sample(_DECK, 2 + ncomm)
        hole, board = cards[:2], cards[2:]
        strength, _d, label = _explain_bb()._hand_strength(hole, board)
        draws, _ = _draw_equity(hole, board)
        sys_eq = min(1.0, strength + draws)
        try:
            true = calculate_equity([(hole[0], hole[1])], _TOP40, board=board,
                                    iterations=1500, seed=11).a_equity / 100.0
        except Exception:
            continue
        checked += 1
        tex = classify_board(board).label
        b = bias[tex]; b["n"] += 1; b["sys"] += sys_eq; b["true"] += true
        # FACING-BET aksiyonu (to_call>0) — sistem ne diyor
        adv = _spot_advice(hole, board, 4.0)
        tier = (adv or {}).get("tier", "?"); action = (adv or {}).get("action", "?")
        # LEAK bayrakları: aksiyon ↔ gerçek-equity çelişkisi
        over = tier in ("NUT", "GÜÇLÜ") and true < 0.45      # güçlü diyor ama range'e karşı zayıf
        under = tier in ("HAVA", "BLUFF-CATCH") and true > 0.62  # zayıf diyor ama aslında önde
        if over or under:
            flags.append((("OVER" if over else "UNDER"), tex, label, tier, action,
                          round(sys_eq, 2), round(true, 2),
                          "".join(c.rank + c.suit for c in hole),
                          " ".join(c.rank + c.suit for c in board)))
    return flags, bias, checked


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
    flags, bias, checked = audit(n)
    print(f"\n{'='*68}\n  VALUE-LAYER AUDIT · {checked} spot · sistem-eq vs gerçek-MC(vs top%40)\n{'='*68}")
    print("\n[1] DOKU bazında ortalama sapma (sistem_eq − gerçek_eq):")
    print(f"  {'doku':<12}{'n':>5}{'sys_eq':>9}{'true_eq':>9}{'fark':>8}")
    for tex, b in sorted(bias.items(), key=lambda x: -abs(x[1]['sys']/max(x[1]['n'],1) - x[1]['true']/max(x[1]['n'],1))):
        if b["n"] < 8: continue
        s, t = b["sys"]/b["n"], b["true"]/b["n"]
        print(f"  {tex:<12}{b['n']:>5}{s:>9.2f}{t:>9.2f}{s-t:>+8.2f}")
    print(f"\n[2] AKSİYON-ÇELİŞKİSİ bayrakları: {len(flags)} (over-value tier güçlü ama eq<45; under tier zayıf ama eq>62)")
    from collections import Counter
    by = Counter((f[0], f[1], f[3]) for f in flags)
    for (kind, tex, tier), c in by.most_common(12):
        print(f"   {c:>3} × {kind:5s} · {tex:<10} · tier={tier}")
    print("\n   örnekler:")
    seen = set()
    for f in flags:
        k = (f[0], f[1], f[3])
        if k in seen: continue
        seen.add(k)
        print(f"   {f[0]:5s} {f[1]:<9} {f[7]:6s}/{f[8]:<16} tier={f[3]:11s} sys_eq={f[5]} true={f[6]} → {f[4][:24]}")
        if len(seen) >= 10: break
