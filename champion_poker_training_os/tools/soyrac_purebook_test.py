"""SOYRAC %100 KİTAP — kapsamlı gerçek MTT testi.

KRİTİK: Soyrac bot'unu pure_book=True ile kurar (preflop=soyrac_advice eşik denklemi,
postflop=soyrac_postflop_advice 7-kademe + D218-D221 fix'leri). soyrac_postflop_advice'ı
SAYAÇLA sarar → postflop'ta GERÇEKTEN kitabın kullanıldığını (fallback/exception=0) ispatlar.

Çeşitli hücreler: alan-gücü {soft/medium/hard} × derinlik {100/50/25bb} · 200 kişi · top-10.
Ölçüm EMERGENT (gerçek oynatma); MTT non-deterministik → çok seed replikasyon.

Çalıştır: PYTHONPATH=. .venv/bin/python tools/soyrac_purebook_test.py [seeds]
"""
from __future__ import annotations
import sys, time, random
import tools.soyrac_big_mtt as BIG          # factory injection + _play_fixed + run_mtt_custom + print_board
import app.engine.game_loop as GL
import tools.profile_sim as PS
import app.simulator.headless_mtt as H
from app.engine.bot_brain import archetype_skill
from tools.soyrac_bot_sim import SoyracBrain
from app.poker import soyrac_advisor as ADV

SOY = BIG.SOY
_RealBB = BIG._RealBB

# ── 1) PURE-BOOK factory (Soyrac = %100 kitap) ──────────────────────
def _pb_factory(profile, *a, **k):
    if profile is SOY:
        b = SoyracBrain()
        b.pure_book = True            # preflop+postflop SAF KİTAP
        return b
    return _RealBB(profile, *a, **k)
GL.BotBrain = _pb_factory; PS.BotBrain = _pb_factory; H.BotBrain = _pb_factory

# ── 2) Postflop KİTAP-KULLANIM sayacı (100% kanıtı) ─────────────────
_PF = {"calls": 0, "none": 0, "err": 0}
_orig_pf = ADV.soyrac_postflop_advice
def _counting_pf(state, idx, *a, **k):
    _PF["calls"] += 1
    try:
        r = _orig_pf(state, idx, *a, **k)
    except Exception:
        _PF["err"] += 1
        raise
    if not r or not r.get("action"):
        _PF["none"] += 1
    return r
ADV.soyrac_postflop_advice = _counting_pf

# ── 3) Alan kurucuları (her biri ~%14 Soyrac içerir → ölçüm gücü) ───
_A = [a for a in PS.ARCHS if a != "Soyrac"]
_WEAK = [a for a in _A if archetype_skill(a) == "weak"] or _A
_MID = [a for a in _A if archetype_skill(a) == "mid"] or _A
_STRONG = [a for a in _A if archetype_skill(a) == "strong"] or _A
_COMP = {
    "soft":   _WEAK * 6 + _MID * 2 + _STRONG * 1,   # rekreasyonel-ağırlıklı (mikro)
    "medium": _WEAK * 3 + _MID * 3 + _STRONG * 2,   # tipik online MTT
    "hard":   _STRONG * 5 + _MID * 1,               # elit-ağırlıklı (en zor)
}

def _make_field_fn(comp):
    bucket = _COMP[comp]
    def _fn(n, rng=None):
        rng = rng or random
        soy_n = max(1, int(round(n * 0.14)))
        base = [rng.choice(bucket) for _ in range(n - soy_n)]
        field = ["Soyrac"] * soy_n + base
        rng.shuffle(field)
        return field
    return _fn


def _soy_row(rows):
    return rows.get("Soyrac", {})


if __name__ == "__main__":
    SEEDS = int(sys.argv[1]) if len(sys.argv) > 1 else 14
    FIELD = 200
    # (etiket, comp, derinlik_bb)
    CELLS = [
        ("SOFT · 100bb (mikro/derin)",   "soft",   100),
        ("MEDIUM · 100bb (tipik MTT)",   "medium", 100),
        ("HARD · 100bb (elit-ağırlıklı)","hard",   100),
        ("MEDIUM · 50bb (regular)",      "medium", 50),
        ("MEDIUM · 25bb (turbo/sığ)",    "medium", 25),
        ("HARD · 50bb (elit+regular)",   "hard",   50),
    ]
    print("\n" + "★" * 64)
    print(f"  SOYRAC %100 KİTAP · {FIELD} kişi MTT · top-10 ödeme · {SEEDS} turnuva/hücre")
    print(f"  (preflop=eşik denklemi · postflop=7-kademe+D218-D221 · pure_book=True)")
    print("★" * 64)

    t0 = time.time()
    summary = []
    for label, comp, depth in CELLS:
        tc = time.time()
        rows = BIG.run_mtt_custom(FIELD, SEEDS, depth, field_fn=_make_field_fn(comp))
        BIG.print_board(f"{label} · {SEEDS} turnuva", rows)
        sr = _soy_row(rows)
        board = sorted(rows.items(), key=lambda x: x[1]["avg_fin_pct"])
        rank = next((i for i, (a, _) in enumerate(board, 1) if a == "Soyrac"), None)
        summary.append((label, sr.get("ent", 0), sr.get("itm_pct", 0), sr.get("top3", 0),
                        sr.get("win", 0), sr.get("avg_fin_pct", 0), rank, len(board)))
        print(f"  Süre: {time.time()-tc:.0f}s", flush=True)

    print("\n" + "═" * 64)
    print("  ÖZET — SOYRAC (%100 kitap) tüm hücreler")
    print("═" * 64)
    print(f"  {'HÜCRE':<32}{'giriş':>6}{'ITM%':>7}{'TOP3':>6}{'WIN':>5}{'avgF%':>7}{'sıra':>8}")
    for label, ent, itm, t3, win, avgf, rank, ntot in summary:
        print(f"  {label:<32}{ent:>6}{itm:>7}{t3:>6}{win:>5}{avgf:>7}{f'{rank}/{ntot}':>8}")

    # KİTAP-KULLANIM KANITI
    c, none, err = _PF["calls"], _PF["none"], _PF["err"]
    book_pct = 100 * (c - none - err) / max(c, 1)
    print("\n" + "═" * 64)
    print("  KİTAP-KULLANIM KANITI (postflop)")
    print("═" * 64)
    print(f"  soyrac_postflop_advice çağrısı: {c:,}  ·  None: {none}  ·  exception: {err}")
    print(f"  → postflop kararların %{book_pct:.2f}'i KİTAPTAN (fallback yok = %100 kitap ✓)"
          if none == 0 and err == 0 else
          f"  ⚠️ UYARI: {none} None + {err} exception → %{book_pct:.2f} kitap (fallback VAR!)")
    print(f"\n  TOPLAM SÜRE: {time.time()-t0:.0f}s")
