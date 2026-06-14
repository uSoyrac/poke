"""OUT-DISCOUNTING güvencesi (D227) — kitap-madenciliği "dirty outs" kuralı.

Kanon (Chen/Ankenman, Janda, Hardin): ham out say AMA rakibin DAHA İYİ elini tamamlayan
out'ları ÇIKAR. (a) eşli board → floş/düz hit etse bile DOLU'ya kaybedebilir; (b) alt-floş-
çekme → üst floş mümkün. Coach-katmanı (_draw_equity); standart-bot _hand_strength kullanır
→ fidelity etkilenmez.
"""
from app.engine.hand_state import card_from_str
from app.poker.soyrac_advisor import _draw_equity


def _eq(h, b):
    return _draw_equity([card_from_str(x) for x in h.split()],
                        [card_from_str(x) for x in b.split()])


def test_clean_board_no_discount():
    """Temiz (eşsiz) board + nut-floş-çekme → tam 9 out, indirim yok."""
    eq, notes = _eq("Ah Kh", "Qh 7h 2c")
    assert abs(eq - 0.36) < 0.01, f"nut FD flop 9-out=0.36 beklenir: {eq}"
    assert not any("kirli" in n for n in notes)


def test_paired_board_discounts_flush_draw():
    """Eşli board → floş-çekme dirty (dolu riski): 9→7 out."""
    eq, notes = _eq("Ah Kh", "Qh 7h 7c")
    assert any("kirli" in n for n in notes), f"eşli board indirim notu yok: {notes}"
    clean, _ = _eq("Ah Kh", "Qh 7h 2c")
    assert eq < clean, f"eşli board ({eq}) temizden ({clean}) düşük olmalı"


def test_paired_board_discounts_straight_draw():
    """Eşli board → OESD dirty: 8→6 out."""
    eq, notes = _eq("Jh Td", "9c 8s 8d")
    clean, _ = _eq("Jh Td", "9c 8s 2d")
    assert eq < clean and any("kirli" in n for n in notes)


def test_low_flush_draw_discounted():
    """Alt-floş-çekme (üst floş mümkün) → −1 out."""
    eq, notes = _eq("7h 2h", "Ah Kh 3c")
    nut, _ = _eq("Ah 2h", "Kh Qh 3c")   # A-yüksek floş-çekme = nut
    assert eq < nut, f"alt-floş ({eq}) nut-floştan ({nut}) düşük olmalı"
    assert any("kirli" in n for n in notes)


def test_nut_flush_draw_not_discounted_for_height():
    """A'lı floş-çekme (temiz board) → üst-floş indirimi YEMEZ."""
    eq, notes = _eq("Ah 5h", "Kh Qh 2c")
    assert not any("kirli" in n for n in notes), f"nut-FD indirim yememeli: {notes}"


def test_river_no_draw():
    """River → çekme yok (regresyon)."""
    eq, notes = _eq("Ah Kh", "Qh 7h 2c 3d 4s")
    assert eq == 0.0
