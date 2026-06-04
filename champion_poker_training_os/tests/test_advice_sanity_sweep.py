"""ADVICE INVARIANT SWEEP — kalıcı regresyon kalkanı.

Felsefe: tek tek screenshot'la bug aramak yerine, BÜTÜN (pozisyon × senaryo ×
stack × mod) uzayını SAĞLAM poker gerçeklerine karşı denetle. Bir kanun ihlal
edilirse — daha önce kimsenin görmediği spotlarda bile — test patlar.

Yakalanan bug sınıfları:
  - ALL_RAISE   : grid ~%100 kırmızı (BB all-red bug, D118)
  - ALL_FOLD    : gerçek karar spotunda hiç oynanan el yok (cash BB all-fold)
  - PREMIUM_FOLD: AA/KK fold ediyor (ASLA doğru değil)
  - TRASH_RAISE : erken pozisyon RFI'da 72o/32o pure-raise
  - NON_MONOTONIC: UTG açışı CO'dan / CO açışı BTN'den geniş (sıralama bozuk)
"""
from __future__ import annotations

from app.poker.mtt_ranges import get_ranked_hands
from app.poker.gto_ranges import get_action
from app.ui.components.gto_range_widget import (
    _action_cell_bg, _AC_RAISE, _AC_FOLD_DIM,
)

HANDS = get_ranked_hands()
POS_OPEN = ["UTG", "UTG+1", "MP", "LJ", "HJ", "CO", "BTN", "SB"]
STACKS = [20, 30, 40, 60, 87, 100, 150]
MODES = ["cash", "MTT"]
VS_OPENER = {"BB": "CO", "SB": "BTN", "BTN": "CO", "CO": "MP", "HJ": "MP",
             "LJ": "UTG", "MP": "UTG", "UTG+1": "UTG"}


def _grid(pos, scen, stack, mode, vs=None):
    return {hk: get_action(pos, hk, scenario=scen, stack_depth=stack,
                           mode=mode, vs_position=vs) for hk in HANDS}


def _n_raise(g, thr=90):
    return sum(1 for a in g.values() if a.get("raise", 0) >= thr)


def _n_play(g):
    return sum(1 for a in g.values()
               if a.get("raise", 0) >= 50 or a.get("call", 0) >= 50)


def _sweep_engine():
    """Range motoru (get_action) invariant ihlallerini topla."""
    v = []
    for mode in MODES:
        for stack in STACKS:
            for pos in POS_OPEN + ["BB"]:
                g = _grid(pos, "RFI", stack, mode)
                spot = f"{pos} RFI {stack}bb {mode}"
                if _n_raise(g) >= 152:
                    v.append(f"ALL_RAISE {spot}: {_n_raise(g)}/169 pure-raise")
                if stack > 15 and _n_play(g) == 0:
                    v.append(f"ALL_FOLD {spot}: hiç oynanan el yok")
                for prem in ("AA", "KK"):
                    if g[prem].get("fold", 0) >= 50:
                        v.append(f"PREMIUM_FOLD {spot}: {prem} fold={g[prem]['fold']}")
                if pos in ("UTG", "UTG+1", "MP", "LJ", "HJ", "CO"):
                    for t in ("72o", "32o", "82o", "62o"):
                        if g[t].get("raise", 0) >= 90:
                            v.append(f"TRASH_RAISE {spot}: {t} raise={g[t]['raise']}")
            # monotonik açış genişliği
            ru = _n_raise(_grid("UTG", "RFI", stack, mode), 60)
            rc = _n_raise(_grid("CO", "RFI", stack, mode), 60)
            rb = _n_raise(_grid("BTN", "RFI", stack, mode), 60)
            if ru > rc + 8:
                v.append(f"NON_MONOTONIC RFI {stack}bb {mode}: UTG({ru})>CO({rc})")
            if rc > rb + 8:
                v.append(f"NON_MONOTONIC RFI {stack}bb {mode}: CO({rc})>BTN({rb})")
            # vs 3-bet: dominated offsuit (ATo/KTo/QJo…) DEFEND etmemeli (D121),
            # AA 4-bet etmeli. vs-3bet polarize/value-ağırlıklı domain.
            if stack >= 40:
                for pos in ["BTN", "CO", "MP", "UTG"]:
                    g = _grid(pos, "vs 3-bet", stack, mode, "BB")
                    spot = f"{pos} vs3bet {stack}bb {mode}"
                    if g["AA"].get("raise", 0) < 50:
                        v.append(f"PREMIUM_NO_4BET {spot}: AA raise={g['AA']['raise']}")
                    for dom in ("ATo", "KTo", "QJo", "KJo", "JTo"):
                        d = g[dom]
                        if d.get("call", 0) + d.get("raise", 0) >= 50:
                            v.append(f"DOMINATED_DEFEND {spot}: {dom} "
                                     f"defend (c={d.get('call',0)} r={d.get('raise',0)})")
            # vs RFI defans
            for pos in ["BB", "SB", "BTN", "CO", "HJ", "MP"]:
                vs = VS_OPENER.get(pos)
                g = _grid(pos, "vs RFI", stack, mode, vs)
                spot = f"{pos} vsRFI({vs}) {stack}bb {mode}"
                if _n_raise(g) >= 152:
                    v.append(f"ALL_RAISE {spot}: {_n_raise(g)}/169")
                if stack > 15 and _n_play(g) == 0:
                    v.append(f"ALL_FOLD {spot}: defend yok")
                if g["AA"].get("fold", 0) >= 50:
                    v.append(f"PREMIUM_FOLD {spot}: AA fold={g['AA']['fold']}")
    return v


def _matrix_colors(pos, scen, stack, mode, vs=None):
    """set_action_range mantığını taklit → (kırmızı, koyu, mixed) hücre sayısı."""
    p = pos.upper()
    if p in ("LJ", "UTG+1"):
        p = "MP"
    if p == "HJ":
        p = "CO"
    depth = 100 if stack >= 60 else (40 if stack >= 30 else 20)
    eng = "MTT" if mode == "tournament" else "cash"
    red = dim = other = 0
    for hk in HANDS:
        bg = _action_cell_bg(get_action(p, hk, scenario=scen, stack_depth=depth,
                                        mode=eng, vs_position=vs))
        if bg == _AC_RAISE:
            red += 1
        elif bg == _AC_FOLD_DIM:
            dim += 1
        else:
            other += 1
    return red, dim, other


# ── TESTLER ────────────────────────────────────────────────────────────

def test_engine_invariants_no_violations():
    """Range motoru: 196 spotta 0 invariant ihlali."""
    v = _sweep_engine()
    assert not v, "Range invariant ihlalleri:\n" + "\n".join(v)


def test_matrix_never_all_red_or_all_dark():
    """Kullanıcının GÖRDÜĞÜ matris hiçbir spotta all-red/all-dark olmamalı."""
    bad = []
    for mode in ("cash", "tournament"):
        for stack in (20, 40, 87, 100):
            for pos in ["UTG", "MP", "CO", "BTN", "SB", "BB"]:
                red, dim, other = _matrix_colors(pos, "RFI", stack, mode)
                if red >= 152:
                    bad.append(f"ALL-RED {pos} RFI {stack}bb {mode} (red={red})")
                if red == 0 and other == 0:
                    bad.append(f"ALL-DARK {pos} RFI {stack}bb {mode}")
    assert not bad, "Matris renk anomalileri:\n" + "\n".join(bad)


def test_bb_matrix_is_iso_not_extreme():
    """BB matris: premium iso kümesi (ne all-red ne all-dark) — D118 bug guard."""
    for mode in ("cash", "tournament"):
        red, dim, other = _matrix_colors("BB", "RFI", 87, mode)
        assert 8 <= red <= 50, f"BB {mode} matris red={red} (iso ~16% bekleniyor)"
        assert dim >= 100, f"BB {mode} matris dim={dim} (çoğu el check/fold olmalı)"
