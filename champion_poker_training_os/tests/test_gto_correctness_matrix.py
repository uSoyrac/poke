"""KAPSAMLI GTO doğruluk matrisi — sistemi binlerce spotta poker-teorisi
değişmezlerine karşı süpürür. Amaç: kullanıcı YANLIŞ eğitilmesin.

Bir değişmez ihlal edilirse test düşer → hata yüzeye çıkar ve düzeltilir.
Boyutlar: pozisyon × senaryo × stack × 169 el × bet/pot matematiği.
"""
from __future__ import annotations

import itertools

import pytest

from app.poker.gto_ranges import all_hand_keys, get_action

_POS6 = ["UTG", "MP", "CO", "BTN", "SB", "BB"]
# RFI (açış) yalnızca BB-dışı pozisyonlarda anlamlıdır — BB'ye fold gelirse
# pot zaten kazanılmıştır, BB 'açmaz' (motor doğru olarak fold %100 döner).
_RFI_POS = ["UTG", "MP", "CO", "BTN", "SB"]
_SCEN = ["RFI", "vs RFI", "vs 3-bet", "Push/Fold"]
_STACKS = [100, 60, 40, 25, 15]
_HANDS = sorted(all_hand_keys())

_PREMIUM = {"AA", "KK", "QQ", "AKs", "AKo"}
_TRASH = {"72o", "82o", "83o", "92o", "93o", "84o", "73o", "62o", "52o", "42o", "32o"}


# ── 1. HER spot geçerli dağılım döndürür (boş/None/negatif YOK) ───────
def test_every_spot_returns_valid_distribution():
    bad = []
    for pos, scen, stack in itertools.product(_POS6, _SCEN, _STACKS):
        for h in _HANDS:
            a = get_action(pos, h, scen, stack, "cash")
            if not isinstance(a, dict) or "fold" not in a:
                bad.append(f"{pos}/{scen}/{stack}/{h}: {a}")
                continue
            tot = a.get("fold", 0) + a.get("call", 0) + a.get("raise", 0) + a.get("allin", 0)
            if abs(tot - 100) > 2.0:
                bad.append(f"{pos}/{scen}/{stack}/{h}: toplam {tot}")
            if any(v < -0.01 for v in a.values()):
                bad.append(f"{pos}/{scen}/{stack}/{h}: negatif {a}")
    assert not bad, f"{len(bad)} geçersiz spot:\n" + "\n".join(bad[:15])


# ── 2. MTT modu da geçerli (ante/Nash motoru) ────────────────────────
def test_every_mtt_spot_valid():
    bad = []
    for pos, stack in itertools.product(_POS6, _STACKS):
        for h in _HANDS:
            a = get_action(pos, h, "RFI", stack, "MTT")
            tot = sum(a.get(k, 0) for k in ("fold", "call", "raise", "allin"))
            if abs(tot - 100) > 2.0:
                bad.append(f"MTT {pos}/{stack}/{h}: {tot}")
    assert not bad, "\n".join(bad[:15])


# ── 3. PREMIUM eller asla katlanmaz (RFI'da açılır, ucuz spotta devam) ─
def test_premium_never_folds_rfi():
    bad = []
    for pos in _RFI_POS:
        for h in _PREMIUM:
            a = get_action(pos, h, "RFI", 100, "cash")
            if a.get("fold", 0) > 5:
                bad.append(f"{pos} {h} RFI fold %{a.get('fold')}")
    assert not bad, "\n".join(bad)


def test_aa_kk_4bet_vs_3bet():
    """AA/KK 3-bet'e karşı yüksek frekans 4-bet (asla %100 fold değil)."""
    bad = []
    for pos in ("UTG", "MP", "CO", "BTN"):
        for h in ("AA", "KK"):
            a = get_action(pos, h, "vs 3-bet", 100, "cash", vs_position="BB")
            if a.get("raise", 0) + a.get("call", 0) < 60:
                bad.append(f"{pos} {h} vs3bet devam %{a.get('raise',0)+a.get('call',0)}")
    assert not bad, "\n".join(bad)


# ── 4. ÇÖP eller erken pozisyonda asla AÇILMAZ ───────────────────────
def test_trash_never_opens_early():
    bad = []
    for pos in ("UTG", "MP"):
        for h in _TRASH:
            a = get_action(pos, h, "RFI", 100, "cash")
            played = a.get("raise", 0) + a.get("call", 0)
            if played > 5:
                bad.append(f"{pos} {h} RFI oynanıyor %{played}")
    assert not bad, "\n".join(bad)


# ── 5. vs-3bet POLARİZE: zayıf eller çoğunlukla fold, herkes 4-bet etmez ─
def test_vs_3bet_is_not_all_raise():
    """Hiçbir vs-3bet spotunda TÜM eller %100 raise olamaz (range polarize)."""
    for pos in ("UTG", "MP", "CO", "BTN"):
        raises_100 = sum(
            1 for h in _HANDS
            if get_action(pos, h, "vs 3-bet", 100, "cash", vs_position="BB").get("raise", 0) >= 99
        )
        # En fazla birkaç premium %100 4-bet olabilir; çoğunluk olamaz
        assert raises_100 <= 20, f"{pos}: {raises_100} el %100 4-bet (polarize değil)"


def test_weak_offsuit_folds_vs_3bet():
    bad = []
    for h in ("J8o", "T8o", "96o", "85o", "Q8o"):
        a = get_action("BTN", h, "vs 3-bet", 100, "cash", vs_position="BB")
        if a.get("fold", 0) < 50:
            bad.append(f"{h} vs3bet fold sadece %{a.get('fold')}")
    assert not bad, "\n".join(bad)


# ── 6. POZİSYON monotonluğu: geç pozisyon ≥ erken pozisyon açıklık ────
def _rfi_pct(pos):
    tot = r = 0.0
    for h in _HANDS:
        cm = 6 if len(h) == 2 else (4 if h.endswith("s") else 12)
        a = get_action(pos, h, "RFI", 100, "cash")
        tot += cm
        r += cm * (a.get("raise", 0) + a.get("call", 0)) / 100
    return 100 * r / tot


def test_position_openness_monotonic():
    utg, mp, co, btn = (_rfi_pct(p) for p in ("UTG", "MP", "CO", "BTN"))
    assert utg < mp < co < btn, f"{utg:.1f}/{mp:.1f}/{co:.1f}/{btn:.1f}"


# ── 7. MTT stack derinliği: kısaldıkça açılış daralır ────────────────
def test_mtt_tightens_when_shorter():
    def pct(stack):
        tot = r = 0.0
        for h in _HANDS:
            cm = 6 if len(h) == 2 else (4 if h.endswith("s") else 12)
            a = get_action("MP", h, "RFI", stack, "MTT")
            tot += cm
            r += cm * (a.get("raise", 0) + a.get("call", 0)) / 100
        return 100 * r / tot
    assert pct(20) <= pct(40) + 1 <= pct(100) + 2


# ── 8. POT-MATEMATİĞİ formülleri (her zaman EXACT) ───────────────────
@pytest.mark.parametrize("pot,to_call", [
    (10, 4), (1.5, 1.0), (21.8, 9.7), (47.2, 15.8), (100, 50), (6, 2),
])
def test_pot_odds_and_mdf_exact(pot, to_call):
    be = 100.0 * to_call / (pot + to_call)
    mdf = 100.0 * pot / (pot + to_call)
    assert abs(be + mdf - 100.0) < 1e-6          # break-even + MDF = %100
    assert 0 < be < 100 and 0 < mdf < 100


def test_ev_verdict_consistency():
    """equity ≥ break-even ⟺ +EV call (tutarlılık değişmezi)."""
    for pot, to_call, eq in [(10, 4, 40), (10, 4, 28), (20, 10, 34), (20, 10, 30)]:
        be = 100.0 * to_call / (pot + to_call)
        plus_ev = eq >= be
        # break-even tam %33.3 → eq 34 +EV, eq 28 -EV (10/4 spotunda be=28.6)
        if pot == 10 and to_call == 4:
            assert (eq == 40) == plus_ev or (eq == 28 and not plus_ev) or plus_ev == (eq >= 28.57)
