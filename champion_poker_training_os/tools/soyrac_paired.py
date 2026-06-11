"""Soyrac DETERMİNİSTİK PAIRED-tester — cash tweak'lerini DOĞRU ölç.

Sorun: harness deck-shuffle'ı seedsiz (hand_state global random) → tek-koşu
bb/100 ±20-25 gürültü taşır. ÇÖZÜM: her koşudan önce random.seed(S); baseline
ve tweak AYNI seed → aynı deste/kararlar, tek fark tweak → TEMİZ delta. N seed
ortalaması alınır. KURAL (memory): bb/100 gürültülü; paired + çok-seed şart.

Kullanım: PYTHONPATH=. .venv/bin/python tools/soyrac_paired.py
"""
from __future__ import annotations
import random
import tools.soyrac_canonical          # enjeksiyon (Soyrac arketip + tournament_mode=False)
import tools.profile_sim as PS
import app.poker.soyrac_advisor as SA

SEEDS = [11, 22, 33, 44, 55]


def _run(seed: int, n_tables: int = 110):
    random.seed(seed)                  # GLOBAL → deck + bot kararları deterministik
    res = PS.run_cash(n_tables=n_tables, hands_per=250, depth_bb=100)
    rows = res["rows"]
    board = sorted(rows.items(), key=lambda x: -x[1]["bb_per_100"])
    rank = next(i for i, (a, _) in enumerate(board, 1) if a == "Soyrac")
    return rows["Soyrac"]["bb_per_100"], rank


def paired_test(apply_tweak, revert_tweak, label: str, seeds=SEEDS, n_tables=110) -> float:
    """apply_tweak()/revert_tweak() in-process mutasyon; aynı seed paired delta."""
    deltas = []
    print(f"\nPAIRED: {label}")
    for s in seeds:
        revert_tweak(); b, br = _run(s, n_tables)
        apply_tweak();  t, tr = _run(s, n_tables)
        revert_tweak()
        deltas.append(t - b)
        print(f"  seed {s}: base {b:+.1f}(#{br}) · tweak {t:+.1f}(#{tr}) · Δ {t - b:+.1f}")
    avg = sum(deltas) / len(deltas)
    verdict = "GERÇEK KAZANÇ" if avg >= 3 else ("ZARARLI" if avg <= -3 else "NÖTR/gürültü")
    print(f"  → ORT Δ {avg:+.1f} bb/100 → {verdict}")
    return avg


if __name__ == "__main__":
    import time
    t0 = time.time()
    _BASE = dict(SA._VS_RFI)
    print("=== SOYRAC PAIRED-OPTİMİZASYON (deterministik) ===")
    # örnek: h2 (BB savunması +1 geniş) — DOĞRULANDI: nötr (+1.5), uygulanmadı
    paired_test(lambda: SA._VS_RFI.__setitem__("BB", (5, 16)),
                lambda: SA._VS_RFI.update(_BASE), "h2: BB call 6→5")
    print(f"\nDONE {time.time()-t0:.0f}s")
