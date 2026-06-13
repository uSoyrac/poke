"""KOÇ == KİTAP güvencesi (D215) — soyrac_advice'ın RFI eşiği, Bible Bölüm 21'deki
EŞİK DENKLEMİ'ni birebir üretmeli. Kullanıcı kitaptan hesaplayınca koç-widget'la AYNI
sonucu almalı; kod sapma yaparsa bu test kırılır.

Denklem (Bölüm 21): EŞİK = baz(8+arkandaki kişi) + masa + stack + turnuva-erken(+2) + ICM + pre-empt
"""
import pytest
from app.poker.soyrac_advisor import soyrac_advice

# Bible Bölüm 21 baz tablo (= 8 + arkandaki kişi; UTG tavan 15, BTN 8, SB 9 istisna)
_BASE = {"UTG": 15, "UTG+1": 15, "MP": 14, "LJ": 13, "HJ": 12, "CO": 11, "BTN": 8, "SB": 9}
_EARLY = ("UTG", "UTG+1", "MP", "LJ", "HJ")
_LATE = ("CO", "BTN", "SB")


def book_threshold(pos, n_active, stack_bb, tourney, icm=False):
    """Bible Bölüm 21 denklemini KAFADAN-hesaplanır biçimde uygular."""
    base = _BASE[pos]
    table = -min(3, (9 - n_active) // 2) if (pos in _EARLY and n_active < 9) else 0
    deep = 2 if stack_bb <= 25 else (1 if stack_bb <= 40 else 0)
    icm_adj = 1 if icm else 0
    tour_early = 2 if (tourney and pos in _EARLY) else 0
    pre = 0
    if tourney and pos in _LATE and n_active > 2:
        pa = 3 + max(0, (9 - n_active) // 2) + {"BTN": 1, "CO": 0, "SB": -1}[pos]
        if n_active <= 3:
            pa += 2
        if stack_bb > 45:
            pa += 1
        elif icm_adj > 0:
            pa -= 1
        pre = -(pa // 2)
    return base + table + deep + icm_adj + tour_early + pre


@pytest.mark.parametrize("tourney", [False, True])
@pytest.mark.parametrize("n_active", [9, 6, 4])
@pytest.mark.parametrize("stack_bb", [100, 40, 25])
@pytest.mark.parametrize("pos", list(_BASE.keys()))
def test_coach_matches_book_equation(pos, stack_bb, n_active, tourney):
    """Koç (soyrac_advice) RFI eşiği = Bible Bölüm 21 denklemi (sapma = kitap-kod desync)."""
    adv = soyrac_advice("A7o", pos, scenario="RFI", stack_bb=stack_bb,
                        tourney=tourney, n_active=n_active)
    expected = book_threshold(pos, n_active, stack_bb, tourney)
    assert adv["threshold"] == expected, (
        f"KOÇ≠KİTAP: {pos} n={n_active} {stack_bb}bb t={tourney} → "
        f"koç {adv['threshold']} vs kitap {expected}")
