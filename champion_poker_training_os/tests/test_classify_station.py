"""D330 (kullanıcı yakaladı: 24/7/AF1.5/F-cbet0/Call56 = STATION ama 'Lion solid' etiketleniyordu):
classify_hellmuth VPIP−PFR GAP + F-cbet/call↓ ile station'ı doğru yakalar; mevcut tipler bozulmaz."""
from app.poker.opponent_typology import classify_hellmuth as C


def _k(*a, **kw):
    return C(*a, **kw)[1]


def test_passive_caller_is_station_not_lion():
    """Büyük gap (24/7=17) + düşük AF → Elephant (station), Lion DEĞİL."""
    assert _k(24, 7, 1.5, 48) == "Elephant"
    assert _k(24, 7, 1.5, 48, fold_to_cbet=0, call_down=56) == "Elephant"
    assert _k(28, 8, 1.2) == "Elephant"        # 28/8 gap 20 = station


def test_fcbet_and_calldown_signal_station():
    """F-cbet düşük (öder) ya da call↓ yüksek (öder) + düşük AF → station (gap küçük olsa bile)."""
    assert _k(20, 16, 1.4, fold_to_cbet=18) == "Elephant"   # F-cbet %18 = az fold = öder
    assert _k(20, 16, 1.4, call_down=58) == "Elephant"      # call↓ %58 = öder


def test_existing_types_preserved():
    """Fix mevcut sınıflandırmayı BOZMAZ (fidelity)."""
    assert _k(26, 22, 2.8) in ("Lion", "Eagle")    # TAG (gap 4, agresif)
    assert _k(22, 18, 2.5) == "Lion"               # klasik TAG
    assert _k(12, 9, 1.1) == "Mouse"               # nit
    assert _k(32, 23, 2.0) == "Jackal"             # LAG (gap 9, p>12)
    assert _k(46, 9, 0.8) == "Elephant"            # klasik station


def test_aggressive_small_gap_stays_lion():
    """Agresif + küçük gap (TAG) station'a düşmemeli — yanlış-Elephant riski."""
    assert _k(24, 21, 2.6) in ("Lion", "Eagle")    # gap 3, agresif → TAG
