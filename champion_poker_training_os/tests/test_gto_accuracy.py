"""GTO motor DOĞRULUK doğrulaması — '%95 dinamik, yanıltmasın' güvencesi.

Üretilen range'lerin ders-kitabı (Upswing/GTOWizard public konsensus)
bantlarında olduğunu ve poker-mantığı değişmezlerini (monotonluk,
premium asla fold, çöp asla raise) koruduğunu kanıtlar. Bir gün motor
bozulursa bu testler yakalar → kullanıcı yanlış GTO görmez.
"""
from __future__ import annotations

import pytest

from app.poker.gto_ranges import all_hand_keys, get_action


def _range_pct(position, scenario, stack, mode, vs_position=None) -> float:
    """Node'un oynanan (raise+call) range yüzdesi — kombo ağırlıklı."""
    tot = r = c = 0.0
    for h in all_hand_keys():
        cm = 6 if len(h) == 2 else (4 if h.endswith("s") else 12)
        a = get_action(position, h, scenario, stack, mode, vs_position)
        tot += cm
        r += cm * a.get("raise", 0) / 100
        c += cm * a.get("call", 0) / 100
    return 100 * (r + c) / max(tot, 1)


# ── RFI 100bb cash — ders kitabı bantları ────────────────────────────
# Upswing/GTOWizard 6-max 100bb açış range konsensüsü (±birkaç puan tolerans)
RFI_BANDS = {
    "UTG": (13, 20),
    "MP":  (15, 23),
    "CO":  (24, 33),
    "BTN": (40, 52),
    "SB":  (34, 48),
}


@pytest.mark.parametrize("pos,band", RFI_BANDS.items())
def test_rfi_100bb_within_textbook_band(pos, band):
    pct = _range_pct(pos, "RFI", 100, "cash")
    lo, hi = band
    assert lo <= pct <= hi, f"{pos} RFI %{pct:.1f} bandın ({lo}-{hi}) dışında"


def test_rfi_widens_by_position():
    """Geç pozisyon daha geniş açar: UTG < MP < CO < BTN."""
    utg = _range_pct("UTG", "RFI", 100, "cash")
    mp = _range_pct("MP", "RFI", 100, "cash")
    co = _range_pct("CO", "RFI", 100, "cash")
    btn = _range_pct("BTN", "RFI", 100, "cash")
    assert utg < mp < co < btn, f"monotonluk bozuk: {utg:.1f}/{mp:.1f}/{co:.1f}/{btn:.1f}"


def test_rfi_tightens_as_stack_shortens_mtt():
    """MTT'de stack kısaldıkça açış range'i daralır (ICM + ima oranı kaybı)."""
    deep = _range_pct("CO", "RFI", 40, "MTT")
    short = _range_pct("CO", "RFI", 20, "MTT")
    assert short <= deep + 0.5, f"20bb ({short:.1f}) 40bb'den ({deep:.1f}) geniş olamaz"


# ── PUSH/FOLD — pozisyon + stack mantığı ─────────────────────────────
def test_pushfold_sb_wider_than_btn():
    """SB jam range'i BTN'den geniş (sadece BB'yi geçmek yeter)."""
    sb = _range_pct("SB", "Push/Fold", 12, "MTT")
    btn = _range_pct("BTN", "Push/Fold", 12, "MTT")
    assert sb > btn, f"SB ({sb:.1f}) BTN'den ({btn:.1f}) geniş olmalı"


def test_pushfold_shorter_is_wider():
    """Daha kısa stack = daha geniş jam (fold equity + zorunluluk)."""
    bb10 = _range_pct("BTN", "Push/Fold", 10, "MTT")
    bb20 = _range_pct("BTN", "Push/Fold", 20, "MTT")
    assert bb10 > bb20, f"10bb ({bb10:.1f}) 20bb'den ({bb20:.1f}) geniş olmalı"


# ── POKER-MANTIĞI DEĞİŞMEZLERİ (asla bozulmamalı) ────────────────────
@pytest.mark.parametrize("pos", ["UTG", "MP", "CO", "BTN", "SB"])
def test_premiums_always_raised_rfi(pos):
    """AA/KK/AKs her pozisyondan açılır (asla %100 fold değil)."""
    for hand in ("AA", "KK", "AKs"):
        a = get_action(pos, hand, "RFI", 100, "cash")
        assert a.get("raise", 0) + a.get("call", 0) >= 95, \
            f"{pos} {hand} açılmıyor: {a}"


@pytest.mark.parametrize("pos", ["UTG", "MP", "CO"])
def test_trash_always_folded_rfi(pos):
    """72o/82o gibi çöp eller erken/orta pozisyonda asla açılmaz."""
    for hand in ("72o", "82o", "93o"):
        a = get_action(pos, hand, "RFI", 100, "cash")
        assert a.get("fold", 0) >= 95, f"{pos} {hand} fold edilmiyor: {a}"


def test_action_frequencies_sum_to_100():
    """Her aksiyon dağılımı ~%100'e toplanmalı (eksik/fazla olasılık yok)."""
    bad = []
    for pos in ("UTG", "CO", "BTN"):
        for scen in ("RFI", "vs 3-bet"):
            for h in ("AA", "KQs", "T9s", "54s", "72o"):
                a = get_action(pos, h, scen, 100, "cash")
                total = a.get("raise", 0) + a.get("call", 0) + a.get("fold", 0) \
                    + a.get("allin", 0)
                if abs(total - 100) > 1.5:
                    bad.append(f"{pos}/{scen}/{h}={total}")
    assert not bad, "Dağılım 100'e toplanmıyor: " + ", ".join(bad)


def test_vs_3bet_is_polarized():
    """vs-3bet polarize: çoğu el fold, premium 4-bet, bazıları flat."""
    # AA/KK value 4-bet (raise yüksek)
    aa = get_action("BTN", "AA", "vs 3-bet", 100, "cash")
    assert aa.get("raise", 0) >= 50, f"AA vs 3-bet 4-bet etmeli: {aa}"
    # Zayıf el çoğunlukla fold
    weak = get_action("BTN", "J8o", "vs 3-bet", 100, "cash")
    assert weak.get("fold", 0) >= 60, f"J8o vs 3-bet çoğunlukla fold: {weak}"


def test_every_grid_spot_returns_valid_action():
    """169 el × kritik node grid'i — her spot geçerli dağılım döndürür
    (hiçbir spot 'boş'/None değil → kullanıcı her zaman cevap görür)."""
    nodes = [
        ("UTG", "RFI", 100, "cash"), ("BTN", "RFI", 100, "cash"),
        ("CO", "RFI", 40, "MTT"), ("BTN", "Push/Fold", 12, "MTT"),
        ("BTN", "vs 3-bet", 100, "cash"), ("BB", "vs RFI", 100, "cash"),
    ]
    for pos, scen, stack, mode in nodes:
        for h in all_hand_keys():
            a = get_action(pos, h, scen, stack, mode)
            assert isinstance(a, dict) and "fold" in a, f"{pos}/{scen}/{h}: {a}"


# ── KANONİK 'gerçek-optimal' spot kontrolleri (well-established) ──────
def test_ako_opens_every_position():
    """AKo her pozisyondan açılır (premium — asla fold/limp)."""
    for pos in ("UTG", "MP", "CO", "BTN", "SB"):
        a = get_action(pos, "AKo", "RFI", 100, "cash")
        assert a.get("raise", 0) + a.get("call", 0) >= 95, f"{pos} AKo: {a}"


def test_btn_rfi_is_wide_includes_speculative():
    """BTN açılışı GENİŞ — suited connector + tüm pair'ler dahil."""
    for h in ("76s", "65s", "54s", "22", "44", "A2s", "K9s"):
        a = get_action("BTN", h, "RFI", 100, "cash")
        assert a.get("raise", 0) + a.get("call", 0) >= 50, f"BTN {h} dışarıda: {a}"


def test_utg_rfi_excludes_weak_suited_gappers():
    """UTG açılışı SIKI — zayıf suited gapper'lar (J8s, 96s, 85s) açılmaz."""
    for h in ("J8s", "96s", "85s", "74s"):
        a = get_action("UTG", h, "RFI", 100, "cash")
        assert a.get("fold", 0) >= 80, f"UTG {h} açılmamalı: {a}"


def test_bb_defends_wide_vs_btn_open():
    """BB, BTN açılışına KARŞI geniş savunur (call+raise yüksek)."""
    tot = defend = 0.0
    for h in all_hand_keys():
        cm = 6 if len(h) == 2 else (4 if h.endswith("s") else 12)
        a = get_action("BB", h, "vs RFI", 100, "cash", vs_position="BTN")
        tot += cm
        defend += cm * (a.get("call", 0) + a.get("raise", 0)) / 100
    pct = 100 * defend / tot
    assert pct >= 40, f"BB vs BTN savunma %{pct:.0f} — çok dar (geniş olmalı)"


def test_premium_pairs_always_continue_vs_3bet():
    """QQ+ 3-bet'e karşı asla %100 fold değil (devam: 4-bet veya call)."""
    for pos in ("UTG", "MP", "CO", "BTN"):
        for h in ("AA", "KK", "QQ"):
            a = get_action(pos, h, "vs 3-bet", 100, "cash", vs_position="BB")
            assert a.get("raise", 0) + a.get("call", 0) >= 70, f"{pos} {h}: {a}"


def test_bb_defends_widest_vs_btn_and_sb():
    """BB en GENİŞ BTN/SB açılışına karşı savunur (geç poz = geniş açılış).
    Ölçülen tight'lık düzeltildi (D72): vs BTN ≥%52, vs SB ≥%58 (blind-vs-blind)."""
    btn = _range_pct("BB", "vs RFI", 100, "cash", vs_position="BTN")
    sb = _range_pct("BB", "vs RFI", 100, "cash", vs_position="SB")
    utg = _range_pct("BB", "vs RFI", 100, "cash", vs_position="UTG")
    assert btn >= 52, f"BB vs BTN savunma %{btn:.0f} — çok dar"
    assert sb >= 58, f"BB vs SB savunma %{sb:.0f} — blind-vs-blind çok dar"
    # Defend monotonluğu: SB (blind-vs-blind) > BTN > UTG (sıkı açan)
    assert sb > btn > utg, f"monotonluk bozuk: SB{sb:.0f} BTN{btn:.0f} UTG{utg:.0f}"
