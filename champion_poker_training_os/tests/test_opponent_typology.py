"""Hellmuth hayvan-tipi sınıflandırma (oyun-içi rakip etiketleri)."""
from __future__ import annotations

from app.poker.opponent_typology import classify_hellmuth, classify_label


def _key(vpip, pfr, agg, rb=0.0):
    return classify_hellmuth(vpip, pfr, agg, rb)[1]


def test_five_animal_types():
    assert _key(14, 12, 1.5, 0.08) == "Mouse"          # tight-passive
    assert _key(42, 6, 0.8, 0.05) == "Elephant"        # loose-passive station
    assert _key(50, 32, 1.3, 0.62) == "Jackal"         # maniac (AF düşük ama blöf yüksek)
    assert _key(22, 18, 2.8, 0.25) == "Lion"           # tight-aggressive
    assert _key(24, 22, 3.0, 0.32) == "Eagle"          # elit tight-aggressive


def test_maniac_is_jackal_not_elephant():
    # Maniac'ın AF'si yapısal olarak düşük; river_bluff sinyali onu Jackal yapar
    assert _key(50, 32, 1.3, 0.62) == "Jackal"


def test_label_format():
    lbl = classify_label(22, 18, 2.8, 0.25)
    assert lbl.startswith("🦁") and "Lion" in lbl


def test_river_bluff_percent_or_fraction():
    # Hem 0.62 hem 62 (yüzde) aynı sonucu vermeli
    assert _key(50, 32, 1.3, 0.62) == _key(50, 32, 1.3, 62)
