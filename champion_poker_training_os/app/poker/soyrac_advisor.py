"""Soyrac HCP danışmanı (D140) — KULLANICI içindir: sen oynarken elini bridge-tarzı
masada-yapılabilir bir puanla değerlendirir ve ne yapman gerektiğini tek satırda
söyler. get_action'a PARALEL bir öğretici katman (onun yerine geçmez; bot kararı
ve grading hep get_action'dan → fidelity korunur).

Doğrulama: 2-ordu workflow, gerçek GTO motoruna karşı %92.35 (RFI/vs-RFI), vs-3bet
B4 blocker %94.4. SHCP açış-range'leri GTO ile eşleşir → sisteme sadık oyuncu
optimal profile (VPIP~23/PFR~19) oturur.
"""
from __future__ import annotations

# Kart puanı (iki kart toplanır) — top-heavy, equity'ye kalibre
_CP = {"A": 10, "K": 8, "Q": 6, "J": 5, "T": 4, "9": 3, "8": 2,
       "7": 1, "6": 1, "5": 1, "4": 1, "3": 0, "2": 0}
_ORD = "23456789TJQKA"

# RFI açış eşikleri @100bb (pozisyon = eşik; puana EKLENMEZ)
_RFI = {"UTG": 15, "UTG+1": 15, "MP": 14, "LJ": 13, "HJ": 12,
        "CO": 11, "BTN": 8, "SB": 9}
# vs RFI çift-eşik (defender: call, 3bet)
_VS_RFI = {"BB": (6, 16), "SB": (9, 17), "BTN": (9, 16), "CO": (10, 16),
           "HJ": (11, 16), "LJ": (12, 17), "MP": (12, 17), "UTG": (13, 18),
           "UTG+1": (13, 18)}
# Açan-pozisyonu savunma eşiğini kaydırır (erken açana sıkı, geç açana geniş).
# 6-max kalibrasyonu: düz BB savunması (%61) erken açışlara aşırı genişti.
_OPENER_ADJ = {"UTG": 4, "UTG+1": 4, "MP": 3, "LJ": 3, "HJ": 2,
               "CO": 1, "BTN": 0, "SB": 0}


def shcp_score(hand_key: str) -> int:
    """Bridge HCP karşılığı: kart puanı + dağılım/oynanabilirlik. 72o=-1 .. AA=40."""
    if not hand_key or len(hand_key) < 2:
        return 0
    r1, r2 = hand_key[0].upper(), hand_key[1].upper()
    if r1 not in _CP or r2 not in _CP:
        return 0
    if r1 == r2:                                   # çift — ayrı taban
        return 16 + 2 * _ORD.index(r1)
    suited = hand_key.endswith("s")
    s = _CP[r1] + _CP[r2]
    if suited:
        s += 4
        if "A" in (r1, r2):                        # nut-flush blocker primi
            s += 2
    gap = abs(_ORD.index(r1) - _ORD.index(r2)) - 1
    s += {0: 3, 1: 2, 2: 1}.get(gap, -2 if gap >= 4 else 0)
    return s


def _b4_blocker(hand_key: str) -> int:
    """vs-3bet blocker skoru (equity sıralaması burada çöker; A5s>AJs)."""
    r1, r2 = hand_key[0].upper(), hand_key[1].upper()
    suited = hand_key.endswith("s")
    val = 0
    if hand_key in ("AA", "KK"):
        val = 3
    elif hand_key in ("QQ", "AKs", "AKo"):
        val = 2
    elif hand_key == "JJ":
        val = 1
    bluff = 0
    if suited and "A" in (r1, r2):                 # Ax-suited tekerlek
        other = r2 if r1 == "A" else r1
        if other in "5432":
            bluff = 2
    elif suited and "K" in (r1, r2):               # Kx-suited düşük
        other = r2 if r1 == "K" else r1
        if other in "98765432":
            bluff = 1
    return val + bluff


def soyrac_advice(hand_key: str, position: str, scenario: str = "RFI",
                  vs_position: str = "", stack_bb: float = 100,
                  icm: bool = False, n_active: int = 9, tourney: bool = False) -> dict:
    """SENİN elin için masada-yapılabilir değerlendirme → {score, action, line, ...}.

    n_active<=2 → HEADS-UP modu: range'ler çok genişler (HU'da BTN/SB ~%85 açar,
    BB ~%70 savunur). Full-ring eşikleri HU'da çok sıkıdır (turnuvayı kapatamazsın)."""
    score = shcp_score(hand_key)
    pos = (position or "BTN").upper()
    icm_adj = 1 if icm else 0
    deep_adj = 1 if stack_bb <= 40 else 0
    # TURNUVA SIKILAŞTIRMA (D150): turnuvada reload yok → survival için açış/savunma
    # eşiklerini +2 sık (cash'te tourney=False → loose-optimal korunur, #1). MTT'de
    # daha az el = daha uzun yaşam (nit/ICM-Expert gibi ladder).
    tourney_adj = 2 if (tourney and not n_active <= 2) else 0
    hu = n_active <= 2
    sc = (scenario or "RFI").lower()

    if "push" in sc or stack_bb < 15:              # kısa stack → equity ekseni
        jam = score >= (10 if hu else 16)          # HU'da çok geniş jam
        return {"score": score, "action": "JAM" if jam else "FOLD",
                "scenario": "Push/Fold",
                "line": f"🧮 SHCP {score} · kısa stack{' HU' if hu else ''} → {'JAM' if jam else 'FOLD'}"}

    if "3-bet" in sc or "3bet" in sc or "vs 3" in sc:   # blocker ekseni
        b4 = _b4_blocker(hand_key)
        # LEAK FIX: 3-bet pot'ta GTO ÇOĞU eli folder (sadece JJ+/AQs+/KQs flat,
        # premium 4-bet). Eski call_t (~8) %53 over-call sızdırıyordu (22-88/broadway).
        call_t = (10 if hu else 22) + icm_adj
        act = "4-BET" if b4 >= 2 else ("CALL" if score >= call_t else "FOLD")
        return {"score": score, "b4": b4, "action": act, "scenario": "vs 3-bet",
                "line": f"🧮 SHCP {score} · B4 blocker {b4} → {act}  (vs 3-bet)"}

    if "vs rfi" in sc or "vs açış" in sc or "vs_rfi" in sc:
        call_t, raise_t = (2, 14) if hu else _VS_RFI.get(pos, (9, 16))
        call_t += icm_adj + tourney_adj
        raise_t += icm_adj
        # 6-max FIX: savunma açanın pozisyonuna göre kayar (erken açana sıkı,
        # geç açana geniş). Düz BB savunması VPIP'i şişiriyordu (%61 → GTO-uyumlu).
        if not hu:
            call_t += _OPENER_ADJ.get((vs_position or "").upper(), 1)
        act = "3-BET" if score >= raise_t else ("CALL" if score >= call_t else "FOLD")
        # 6-max AGRESYON (D148): geç açana karşı suited-wheel-As (A2s-A5s) 3-BET BLÖF.
        # Bu eller AA/AK'yı bloklar + nut-floş yedek-equity'si var; 3bet'i %5→~%10'a
        # çıkarır (6-max GTO hedefi), expert'e karşı sömürülmeyi azaltır.
        bluff3 = ""
        if not hu and act in ("CALL", "FOLD") and \
                (vs_position or "").upper() in ("CO", "BTN", "SB", "HJ") and \
                _b4_blocker(hand_key) >= 2:
            act = "3-BET"
            bluff3 = " (blocker blöf)"
        return {"score": score, "call_t": call_t, "raise_t": raise_t,
                "action": act, "scenario": "vs RFI",
                "line": f"🧮 SHCP {score} · {pos}{' HU' if hu else ''} call≥{call_t}/3bet≥{raise_t} → {act}{bluff3}"}

    # RFI (açış) — pozisyon eşiği (puana eklenmez); HU'da çok düşük (geniş aç)
    thr = (3 if hu else _RFI.get(pos, 13)) + icm_adj + deep_adj + tourney_adj
    rel = "≥" if score >= thr else "<"
    act = "RAISE (AÇ)" if score >= thr else "FOLD"
    return {"score": score, "threshold": thr, "action": act, "scenario": "RFI",
            "line": f"🧮 SHCP {score} {rel} {pos}{' HU' if hu else ''} eşik {thr} → {act}"}


def advice_from_hand(hand, hero_idx: int, stack_bb: float = 100,
                     icm: bool = False, tourney: bool = False) -> "dict | None":
    """Canlı HandState'ten doğrudan: senaryoyu live_gto_advice ile aynı tespit edip
    SHCP satırı üret (gerçek motorla TUTARLI scenario)."""
    try:
        from app.engine.bot_brain import hand_key as _hk
        from app.poker.gto_live_advice import live_gto_advice
        hero = hand.players[hero_idx]
        if not hero.hole_cards or len(hero.hole_cards) < 2:
            return None
        hk = _hk(hero.hole_cards[0], hero.hole_cards[1])
        adv = live_gto_advice(hand, hero_idx, mode="MTT")
        n_active = getattr(hand, "active_count", None)
        if not n_active:
            n_active = sum(1 for pl in hand.players
                           if not getattr(pl, "is_folded", False)
                           and not getattr(pl, "is_eliminated", False))
        return soyrac_advice(hk, hero.position,
                             scenario=getattr(adv, "scenario_key", "RFI") or "RFI",
                             vs_position=getattr(adv, "vs_position", "") or "",
                             stack_bb=stack_bb, icm=icm, n_active=n_active or 9,
                             tourney=tourney)
    except Exception:
        return None
