"""D334 (app-QA agent-denetimi): app her-anlamda sağlam mı.
(1) icm.malmuth_harville O(n!) → büyük alanda DONMA; bubble_factor/icm_ft_guidance defensive-cap.
(2) soyrac_advice geçersiz stack (negatif/NaN/inf) → saçma öneri yerine güvenli."""
import math
import time

from app.poker.icm import bubble_factor, icm_ft_guidance, malmuth_harville
from app.poker.soyrac_advisor import soyrac_advice


def test_bubble_factor_large_field_no_hang():
    """25 oyuncu → exact O(n!) ÇALIŞTIRMA (donma); yaklaşık hızlı döner (<0.1s)."""
    t0 = time.time()
    bf = bubble_factor([100.0] * 25, [100.0] + [0.0] * 24, 0)
    assert time.time() - t0 < 0.1 and bf > 0


def test_icm_ft_guidance_large_field_no_hang():
    t0 = time.time()
    g = icm_ft_guidance("bubble", 9, 40, 25, [100.0] * 25, [50.0] + [0.0] * 24, 0)
    assert time.time() - t0 < 0.1 and g.get("active") is True


def test_malmuth_small_field_still_exact():
    """Küçük alan (≤10) hâlâ exact ICM hesaplar (toplam $ = pot)."""
    eq = malmuth_harville([100.0, 100.0, 100.0], [50.0, 30.0, 20.0])
    assert abs(sum(eq) - 100.0) < 0.01     # tüm equity = toplam payout (4-ondalık yuvarlama toleransı)
    assert all(abs(x - 100.0 / 3) < 0.01 for x in eq)   # simetrik stack → eşit pay


def test_soyrac_advice_invalid_stack_safe():
    """Negatif/NaN/inf/0 stack → güvenli öneri (saçma 'JAM size=-50bb' YOK)."""
    for s in (-50.0, float("nan"), float("inf"), 0.0):
        r = soyrac_advice("AKs", "BTN", "RFI", stack_bb=s, n_active=9)
        sz = r.get("size", {})
        szbb = sz.get("size_bb") if isinstance(sz, dict) else None
        assert szbb is None or (math.isfinite(szbb) and szbb >= 0), f"stack={s} saçma size {szbb}"
    # normal davranış korunur
    assert soyrac_advice("72o", "UTG", "RFI", stack_bb=100, n_active=9)["action"] == "FOLD"
