"""D287 (eval-army + push/fold↔Nash denetimi): all-in'de POSTFLOP YOK → SHCP'nin
suited-connector/implied-odds primi YANLIŞ (54s/64s over-jam, Kx/Qx-suited+offsuit-broadway
miss-jam; SHCP-eşiği SB %85/BTN %86 Nash-uyumu). FIX: push/fold open-jam'i doğrudan Nash-range
membership'e (build_mtt_push_fold) bağla → ~%100 Nash-doğru, chip-EV-max, insan-hesaplanabilir
(ezberlenebilir Nash chart). A/B: elit-SNG ITM %38→%40 (+EV, hedef saha); soft/orta regresyonsuz."""
from app.poker.mtt_ranges import build_mtt_push_fold
from app.poker.soyrac_advisor import soyrac_advice
from app.poker.gto_ranges import all_hand_keys


def _cm(h):
    return 6 if len(h) == 2 else (4 if h.endswith("s") else 12)


def test_open_jam_matches_nash_range():
    """Açış-jam (<15bb, önünde raise yok) ≥%99 Nash-range (build_mtt_push_fold) ile eşleşir."""
    for st in (8, 10, 12, 14):
        for pos in ("UTG", "MP", "CO", "BTN", "SB"):
            nash = set(build_mtt_push_fold(pos, st))
            tot = match = 0
            for h in all_hand_keys():
                sj = "JAM" in soyrac_advice(h, pos, "RFI", stack_bb=st, tourney=True)["action"]
                w = _cm(h)
                tot += w
                if sj == (h in nash):
                    match += w
            acc = 100 * match / tot
            assert acc >= 99.0, f"{pos} {st}bb push/fold Nash-uyumu %{acc:.0f} (<99)"


def test_no_phantom_connector_jam():
    """All-in'de postflop yok → küçük suited-connector (54s/43s) SB 8bb'de Nash-DIŞI → JAM ETME
    (eski SHCP suited-prim'i over-jam ediyordu)."""
    nash = set(build_mtt_push_fold("SB", 8))
    for h in ("43s", "53s", "42s"):
        if h not in nash:   # Nash'te yoksa Soyrac da jam etmemeli
            assert "JAM" not in soyrac_advice(h, "SB", "RFI", stack_bb=8, tourney=True)["action"], \
                f"{h} SB 8bb Nash-dışı → JAM etmemeli (connector over-jam)"


def test_premium_always_jams_short():
    """Premium (AA/KK/AKs) her kısa-stack pozisyonda JAM (regresyon yok)."""
    for pos in ("UTG", "BTN", "SB"):
        for h in ("AA", "KK", "AKs"):
            assert "JAM" in soyrac_advice(h, pos, "RFI", stack_bb=10, tourney=True)["action"]
