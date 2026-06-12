"""Duke Resulting-Fallacy aracı (D195) — karar kalitesi ≠ sonuç."""
from app.poker.resulting import resulting_flag, ResultingLedger


def test_good_decision_lost_is_trap():
    f = resulting_flag("A", won=False)
    assert f["trap"] is True and f["quadrant"] == "iyi-karar/kayıp"
    assert "varyans" in f["note"].lower()


def test_bad_decision_won_is_trap():
    f = resulting_flag("F", won=True)
    assert f["trap"] is True and f["quadrant"] == "kötü-karar/kazanç"
    assert "tekrarlama" in f["note"].lower()


def test_aligned_outcomes_not_trap():
    assert resulting_flag("A", True)["trap"] is False
    assert resulting_flag("D", False)["trap"] is False


def test_c_grade_neutral():
    f = resulting_flag("C", True)
    assert f["quadrant"] == "nötr" and f["trap"] is False


def test_ledger_counts_and_traps():
    L = ResultingLedger()
    for g, won in [("A", True), ("A", False), ("A", False), ("F", True),
                   ("B", True), ("D", False), ("C", True)]:
        L.add(g, won)
    assert L.good_won == 2 and L.good_lost == 2 and L.bad_won == 1 and L.bad_lost == 1
    assert L.traps == 3                      # 2 iyi-kayıp + 1 kötü-kazanç
    assert L.neutral == 1


def test_ledger_decision_win_rate_outcome_independent():
    L = ResultingLedger()
    # 3 iyi karar (sonuç ne olursa olsun), 1 kötü → %75 karar-doğruluğu
    for g, won in [("A", False), ("A", False), ("B", True), ("F", True)]:
        L.add(g, won)
    assert L.decision_win_rate == 75.0       # sonuçtan bağımsız (2 kayıp dahil)


def test_ledger_summary_string():
    L = ResultingLedger()
    L.add("A", False)
    L.add("F", True)
    s = L.summary()
    assert "VARYANS" in s and "ŞANS" in s and "Duke" in s
