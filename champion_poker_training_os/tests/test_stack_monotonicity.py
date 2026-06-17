"""D260 (+EV-max audit #6): stack-conditioning regresyon bekçisi (denetim körlüğü kapandı).
IP vs-RFI flat (call) sayısı stack sığlaştıkça ARTAMAZ (SPR çöker → speculative flat azalır).
Eski araçlar ≤25bb test etmiyordu → stack-körlüğü leak'leri '0-ihlal' görünüyordu (D259)."""
import itertools
from app.poker.soyrac_advisor import soyrac_advice

_RANKS = "AKQJT98765432"
# temsili savunma örneklemi (broadway + suited-connector + ax)
_HANDS = []
for i, r1 in enumerate(_RANKS):
    for r2 in _RANKS[i:]:
        if r1 == r2:
            _HANDS.append(r1 + r2)
        else:
            _HANDS.append(r1 + r2 + "s")
            _HANDS.append(r1 + r2 + "o")


def _call_count(pos, vs, stack):
    n = 0
    for hk in _HANDS:
        if soyrac_advice(hk, pos, scenario="vs RFI", vs_position=vs,
                         stack_bb=stack)["action"] == "CALL":
            n += 1
    return n


def test_ip_flat_band_monotone_in_stack():
    """IP (CO/BTN/HJ) flat sayısı: derin ≥ orta ≥ sığ (genişlemek leak'tir)."""
    for pos in ("CO", "BTN", "HJ"):
        deep = _call_count(pos, "MP", 100)
        mid = _call_count(pos, "MP", 30)
        shallow = _call_count(pos, "MP", 18)
        assert deep >= mid >= shallow, f"{pos}: 100bb={deep} 30bb={mid} 18bb={shallow} (monotonluk ihlali)"


def test_shallow_strictly_narrower_somewhere():
    """En az bir IP pozisyonda sığ flat DERİNDEN dar olmalı (D259 etkisi yaşıyor)."""
    diffs = [_call_count(p, "MP", 100) - _call_count(p, "MP", 18) for p in ("CO", "BTN", "HJ")]
    assert max(diffs) > 0, f"hiçbir IP poz sığ'da daralmadı: {diffs}"
