"""SOYRAC ↔ GTO DOĞRULUK ölçümü: soyrac_advice (insan-kitap) vs get_action (GTO referans),
tüm 169 el × pozisyon × senaryo. Kombo-ağırlıklı uyum %. Cash 100bb (GTO referans derinliği).
Uyum = soyrac'ın seçtiği aksiyon, GTO'nun ÇOĞUNLUK aksiyonuyla eşleşiyor mu (binary, kombo-ağırlıklı).
Ek: 'GTO-bu-aksiyonu-oynar' (lenient) — soyrac'ın aksiyonunu GTO ≥%25 oynuyorsa kabul.

PYTHONPATH=. .venv/bin/python tools/soyrac_gto_accuracy.py
"""
from __future__ import annotations

from app.poker.gto_ranges import all_hand_keys, get_action
from app.poker.soyrac_advisor import soyrac_advice

POS_OPEN = ["UTG", "UTG+1", "MP", "LJ", "HJ", "CO", "BTN", "SB"]
VS_OPENER = {"BB": "CO", "SB": "BTN", "BTN": "CO", "CO": "MP", "HJ": "MP",
             "LJ": "UTG", "MP": "UTG", "UTG+1": "UTG"}
# vs-3bet: hero açar, arkadan 3-bet'çi (temsili)
VS_3BETTOR = {"UTG": "CO", "MP": "BTN", "LJ": "BTN", "HJ": "BTN", "CO": "BTN", "BTN": "SB"}


def _cm(h):
    return 6 if len(h) == 2 else (4 if h.endswith("s") else 12)


def _gto_primary(a):
    r, c, f = a.get("raise", 0), a.get("call", 0), a.get("fold", 0)
    m = max(r, c, f)
    return "raise" if r == m else ("call" if c == m else "fold")


def _soy_map(act):
    a = (act or "").upper()
    if "CALL" in a:                       # ÖNCE: 'CALL' içinde 'ALL' geçer → raise'e kaçmasın
        return "call"
    if any(k in a for k in ("RAISE", "3-BET", "4-BET", "JAM", "ALL_IN", "ALL-IN", "AÇ", "BET")):
        return "raise"
    if "CHECK" in a:
        return "call"
    return "fold"


def _score(pos, scenario, vs):
    tot = match = lenient = 0.0
    for h in all_hand_keys():
        cm = _cm(h)
        g = get_action(pos, h, scenario=scenario, stack_depth=100, mode="cash", vs_position=vs)
        gp = _gto_primary(g)
        adv = soyrac_advice(h, pos, scenario=scenario, vs_position=vs or "",
                            stack_bb=100, n_active=6, tourney=False)
        sm = _soy_map(adv.get("action"))
        tot += cm
        if sm == gp:
            match += cm
        # lenient: soyrac'ın aksiyonunu GTO ≥%25 oynuyor mu
        if g.get({"raise": "raise", "call": "call", "fold": "fold"}[sm], 0) >= 25:
            lenient += cm
    return match, lenient, tot


def main():
    print("=== SOYRAC ↔ GTO DOĞRULUK (cash 100bb, 169 el, kombo-ağırlıklı) ===\n")
    print(f"{'SENARYO':<12}{'spot':>6}{'UYUM%':>8}{'lenient%':>10}")
    print("-" * 38)
    grand_m = grand_l = grand_t = 0.0
    scen_rows = []
    # RFI
    m = l = t = 0.0
    for pos in POS_OPEN:
        a, b, c = _score(pos, "RFI", None)
        m += a; l += b; t += c
    scen_rows.append(("RFI", len(POS_OPEN), m, l, t)); grand_m += m; grand_l += l; grand_t += t
    # vs RFI
    m = l = t = 0.0
    for pos, opener in VS_OPENER.items():
        a, b, c = _score(pos, "vs RFI", opener)
        m += a; l += b; t += c
    scen_rows.append(("vs RFI", len(VS_OPENER), m, l, t)); grand_m += m; grand_l += l; grand_t += t
    # vs 3-bet
    m = l = t = 0.0
    for pos, tb in VS_3BETTOR.items():
        a, b, c = _score(pos, "vs 3-bet", tb)
        m += a; l += b; t += c
    scen_rows.append(("vs 3-bet", len(VS_3BETTOR), m, l, t)); grand_m += m; grand_l += l; grand_t += t

    for name, n, m, l, t in scen_rows:
        print(f"{name:<12}{n:>6}{100*m/max(t,1):>7.1f}{100*l/max(t,1):>9.1f}")
    print("-" * 38)
    print(f"{'GENEL':<12}{'':>6}{100*grand_m/max(grand_t,1):>7.1f}{100*grand_l/max(grand_t,1):>9.1f}")
    print("\nUYUM% = soyrac aksiyonu == GTO çoğunluk aksiyonu (binary). lenient% = soyrac aksiyonunu")
    print("GTO ≥%25 oynuyor (mixed spot'ta da doğru sayılır). Sapmaların çoğu +EV-max yargı (read/exploit).")


if __name__ == "__main__":
    main()
