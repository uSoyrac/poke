"""KATEGORİ-LEAK regresyon bekçisi (D221) — _hand_strength'in el-KATEGORİSİ, oyunun
gerçek showdown evaluator'ı (evaluate_best_hand) ile uyumlu olmalı.

Bu test, kullanıcının canlı yakaladığı leak SINIFINI (wheel düz HAVA sanılması, vb.)
proaktif yakalamak için differential audit kullanır: çok sayıda rastgele (el, board)
için sistem hero'nun GERÇEK elini daha düşük kategoriye sokuyorsa = leak. 'Board oynama'
(hero katkısı yok) durumları elenir.

Geçmiş bulgular (hepsi düzeltildi): wheel düz (D219), çift-trips full house + straight/
royal flush 'flush' sanılması (D221).
"""
from app.engine.hand_state import card_from_str
from app.poker.soyrac_advisor import _explain_bb
from tools.leak_audit_handstrength import audit


def _lab(h, b):
    return _explain_bb()._hand_strength([card_from_str(x) for x in h.split()],
                                        [card_from_str(x) for x in b.split()])[2]


def test_straight_flush_detected():
    assert _lab("6d 4d", "5d Ac 7d 3h 3d") == "straight flush"


def test_royal_flush_detected():
    assert _lab("Ks 9c", "Js As Qs Ts Ad") == "straight flush"


def test_steel_wheel_flush_detected():
    """A-2-3-4-5 aynı suit (steel wheel) de straight flush."""
    assert _lab("Ah 4h", "5h 2h 3h Kc Qd") == "straight flush"


def test_double_trips_full_house():
    """22 / 8-8-8-x → 888+22 = full house ('set' DEĞİL)."""
    assert _lab("2d 2h", "2s 6d 8d 8h 8s") == "full house"
    assert _lab("2d 9c", "2c 9d 2h 7h 9h") == "full house"


def test_wheel_straight_still_detected():
    """D219 regresyon: wheel düz hâlâ straight."""
    assert _lab("Ah 4h", "5h Tc 2c Qh 3c") == "straight"


def test_no_category_undervaluation_differential():
    """PROAKTİF bekçi: 40k rastgele (el, board) — sistem hiçbir gerçek eli kategori
    olarak düşük sınıflamamalı (hero kartları katkı sağlıyorken). Yeni kategori-bug
    girerse bu kırılır."""
    leaks = audit(40_000)
    assert not leaks, (
        f"{len(leaks)} kategori-leak: " +
        "; ".join(f"{tn}→{lab!r} (hole={h} board={b})" for tn, lab, sc, tr, h, b in leaks[:5]))
