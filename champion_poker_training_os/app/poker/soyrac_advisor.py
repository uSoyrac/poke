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


_JAM_DIST = None


def _jam_threshold_for_pct(pct: float) -> int:
    """Top-pct% el (kombo-ağırlıklı) için SHCP-puan eşiği. Nash jam%'i SHCP
    eşiğine çevirir → push/fold pozisyon+stack-duyarlı (mtt_ranges.mtt_jam_pct)."""
    global _JAM_DIST
    if _JAM_DIST is None:
        items = []
        for i, r1 in enumerate(_ORD[::-1]):
            for j, r2 in enumerate(_ORD[::-1]):
                if i == j:
                    hk, combos = r1 + r1, 6
                elif i < j:
                    hk, combos = r1 + r2 + "s", 4
                else:
                    hk, combos = r2 + r1 + "o", 12
                items.append((shcp_score(hk), combos))
        items.sort(reverse=True)
        _JAM_DIST = items
    target = max(0.0, pct) / 100.0 * 1326
    # puan-kovaları kaba → cum'u HEDEFE EN YAKIN bırakan eşiği seç (over/undershoot
    # değil, en yakın). Yoksa eşik-geçişinde aşırı kombo eklenip jam% şişiyordu.
    by_score = {}
    for s, c in _JAM_DIST:
        by_score[s] = by_score.get(s, 0) + c
    cum, best_s, best_diff = 0, 0, 1e9
    for s in sorted(by_score, reverse=True):
        cum += by_score[s]
        d = abs(cum - target)
        if d < best_diff:
            best_diff, best_s = d, s
    return best_s


def soyrac_advice(hand_key: str, position: str, scenario: str = "RFI",
                  vs_position: str = "", stack_bb: float = 100,
                  icm: bool = False, n_active: int = 9, tourney: bool = False) -> dict:
    """SENİN elin için masada-yapılabilir değerlendirme → {score, action, line, ...}.

    n_active<=2 → HEADS-UP modu: range'ler çok genişler (HU'da BTN/SB ~%85 açar,
    BB ~%70 savunur). Full-ring eşikleri HU'da çok sıkıdır (turnuvayı kapatamazsın)."""
    score = shcp_score(hand_key)
    pos = (position or "BTN").upper()
    icm_adj = 1 if icm else 0
    # STACK-DERİNLİĞİ (D181): GTO sığlaştıkça SIKILAŞIR (ölçüldü: ~75bb plato; 40bb
    # +1; 25bb +2 — get_action stack-aware doğrulamasıyla kalibre). Eski binary
    # (≤40→+1) 25 ile 40'ı eşitliyordu; kademeli daha iyi eşleşir. <15bb → push/fold
    # (ayrı dal, D177 Nash). İNSAN-DENKLEMİ: derin=baz, sığlaştıkça +1/+2.
    deep_adj = 2 if stack_bb <= 25 else (1 if stack_bb <= 40 else 0)
    hu = n_active <= 2
    # TURNUVA SIKILAŞTIRMA (D173 POZİSYON-DUYARLI): erken pozisyon SIKI (survival,
    # reload yok), GEÇ pozisyon (CO/BTN/SB) SIKMA — turnuvada steal +EV (blind'lar
    # değerli). Eski düz +2 over-tight'tı (gerçek-oyun post-mortem: VPIP %13.6, steal
    # kaçtı, chip-EV −8.2). Late'te sıkma → steal'ler geri → accumulation.
    _late_pos = pos in ("CO", "BTN", "SB")
    tourney_adj = 2 if (tourney and not hu and not _late_pos) else 0
    sc = (scenario or "RFI").lower()

    if "push" in sc or stack_bb < 15:              # kısa stack → equity ekseni
        # POZİSYON-AWARE NASH (D177): jam eşiği pozisyon+stack'e göre (mtt_jam_pct,
        # HRC/SnapShove-kalibre). Eski sabit-16 her yerden %17 jam'liyordu — BTN
        # 7bb Nash ~%54! Geç pozisyon ÇOK daha geniş jam'lemeli (arkanda az kişi).
        if hu:
            jam_thr = 10
        else:
            try:
                from app.poker.mtt_ranges import mtt_jam_pct
                jp = mtt_jam_pct(pos, stack_bb) * 0.83   # puan-kova dönüşüm-aşımını telafi
                if icm:
                    jp *= 0.82                     # ICM: elenme pahalı → biraz sıkı
                jam_thr = _jam_threshold_for_pct(jp)
            except Exception:
                jam_thr = 16
        jam = score >= jam_thr
        return {"score": score, "action": "JAM" if jam else "FOLD",
                "scenario": "Push/Fold", "threshold": jam_thr,
                "line": f"🧮 SHCP {score} ≥ jam-eşik {jam_thr} ({pos})"
                        f"{' HU' if hu else ''} → {'JAM' if jam else 'FOLD'}"
                        if jam else
                        f"🧮 SHCP {score} < jam-eşik {jam_thr} ({pos}) → FOLD"}

    if "3-bet" in sc or "3bet" in sc or "vs 3" in sc:   # blocker ekseni
        b4 = _b4_blocker(hand_key)
        # LEAK FIX: 3-bet pot'ta GTO ÇOĞU eli folder (sadece JJ+/AQs+/KQs flat,
        # premium 4-bet). Eski call_t (~8) %53 over-call sızdırıyordu (22-88/broadway).
        call_t = (10 if hu else 22) + icm_adj
        # DENEY (D175, GERİ ALINDI): "suited broadway (iki kart T+) → CALL" eklendi
        # (JTs/KQs FOLD'a düşmesin) ama vs-3bet accuracy %93.8→%92.6 DÜŞTÜ — blanket
        # kural fazla geniş (QTs/KTs sıkı-açana GTO-fold, call'landı). Doğru cevap
        # 3-bettor-pozisyonuna bağlı (opener-aware range gerekir = tam GTO). Basit-
        # sistem sınırı: T9s gibi net spot doğru, JTs sınır spot yaklaşık. Eşik korundu.
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
    # MASA-BOYUTU (D180): kısa masada ERKEN pozisyonlar daha az kişiyle karşılaşır →
    # GENİŞLE (6-max UTG 5 arkada, 9-max UTG 8 arkada gibi sıkı olmamalı). Geç pozisyon
    # (CO/BTN/SB) behind SABİT → dokunma. Gevşet: ~2 eksik oyuncu/-1, max -3. (Teori-
    # sağlam; GTO'da masa-boyutu verisi yok → temkinli faktör.)
    _early = pos in ("UTG", "UTG+1", "MP", "LJ", "HJ")
    table_adj = -min(3, (9 - n_active) // 2) if (not hu and _early and n_active < 9) else 0
    thr = (3 if hu else _RFI.get(pos, 13)) + icm_adj + deep_adj + tourney_adj + table_adj
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


# ════════════════════════════════════════════════════════════════════
# CANLI KOÇ — ÖĞRETİCİ KATMAN (saf, Qt'siz; soyrac_advice/grading DEĞİŞMEZ)
# Tasarım: LXD+ID+UX workflow. Kullanıcı oynarken "nasıl düşün" öğretir.
# ════════════════════════════════════════════════════════════════════

def shcp_breakdown(hand_key: str) -> str:
    """Puanın adım-adım kırılımı: 'A=10 + K=8 + suited+4 + As-blocker+2 = 27'."""
    if not hand_key or len(hand_key) < 2:
        return ""
    r1, r2 = hand_key[0].upper(), hand_key[1].upper()
    if r1 not in _CP or r2 not in _CP:
        return ""
    sc = shcp_score(hand_key)
    if r1 == r2:                                   # çift
        return f"{r1}{r1} çifti = 16+{2 * _ORD.index(r1)} = {sc}"
    parts = [f"{r1}={_CP[r1]}", f"{r2}={_CP[r2]}"]
    if hand_key.endswith("s"):
        parts.append("suited+4")
        if "A" in (r1, r2):
            parts.append("As-blocker+2")
    gap = abs(_ORD.index(r1) - _ORD.index(r2)) - 1
    gb = {0: 3, 1: 2, 2: 1}.get(gap, -2 if gap >= 4 else 0)
    if gb:
        lbl = "bitişik" if gap == 0 else (f"{gap}-gap" if gb > 0 else "uzak")
        parts.append(f"{lbl}{'+' if gb > 0 else ''}{gb}")
    return " + ".join(parts) + f" = {sc}"


def _tone_for_action(action: str) -> str:
    a = (action or "").upper()
    if any(k in a for k in ("RAISE", "3-BET", "4-BET", "JAM", "BET", "AÇ")):
        return "go"
    if "CALL" in a or "CHECK" in a:
        return "caution"
    return "stop"


def soyrac_explain(hand_key: str, position: str, scenario: str = "RFI",
                   vs_position: str = "", stack_bb: float = 100, icm: bool = False,
                   n_active: int = 9, tourney: bool = False, *,
                   hand=None, hero_idx=None, advice=None) -> dict:
    """ÖĞRETİCİ çıktı — soyrac_advice'i sarar, üstüne 'nasıl düşün' katmanı serer.
    Panel bunu okur; soyrac_advice/grading AYNEN korunur (fidelity 0-sapma)."""
    # POSTFLOP dalı — board varsa 7-kademe + altın kural öğreticisi
    if hand is not None and hero_idx is not None:
        comm = getattr(hand, "community", None)
        if comm and len(comm) >= 3:
            pf = soyrac_postflop_advice(hand, hero_idx, advice)
            if pf:
                stn = {1: "Flop", 2: "Turn", 3: "River"}.get(len(comm) - 2, "Postflop")
                return {
                    "phase": "postflop", "scenario": "Postflop",
                    "scenario_label": f"{stn} · {pf['board_label']}",
                    "action": pf["action"], "tone": _tone_for_action(pf["action"]),
                    "line": pf["line"], "score": None, "threshold": None,
                    "call_t": None, "raise_t": None, "b4": None, "scale_max": 40,
                    "why": pf["golden_rule"] or f"El gücün {pf['tier']} → {pf['action']}",
                    "chain_steps": pf["chain_steps"], "format_note": "",
                    "card_breakdown": "", "tier": pf["tier"],
                    "board_label": pf["board_label"], "wetness": pf["wetness"],
                    "golden_rule": pf["golden_rule"], "size_frac": pf["size_frac"],
                    "flow_nodes": pf["flow_nodes"],
                    "terms": ["7-kademe", "commit-gate", "pot-odds", "wetness"],
                    "quiz_prompt": f"Sen ne yapardın? ({stn} {pf['board_label']} · {pf['tier']})",
                    "quiz_correct": pf["action"],
                    "quiz_options": ["FOLD", "CHECK/CALL", "BET/RAISE"],
                }
    base = soyrac_advice(hand_key, position, scenario=scenario, vs_position=vs_position,
                         stack_bb=stack_bb, icm=icm, n_active=n_active, tourney=tourney)
    action = base.get("action", "FOLD")
    score = base.get("score")
    pos = (position or "BTN").upper()
    vp = (vs_position or "").upper()
    hu = n_active <= 2
    fmt = "🎯 Cash: loose-aggressive — balığı ez" if not tourney \
        else "🏆 Turnuva: ICM-sıkı, survival"
    out = {
        "phase": "preflop", "scenario": base.get("scenario", scenario),
        "action": action, "tone": _tone_for_action(action), "line": base.get("line", ""),
        "score": score, "threshold": base.get("threshold"),
        "call_t": base.get("call_t"), "raise_t": base.get("raise_t"), "b4": base.get("b4"),
        "scale_max": 40, "format_note": fmt, "card_breakdown": shcp_breakdown(hand_key),
        "tier": None, "board_label": None, "wetness": None, "golden_rule": None,
        "size_frac": None, "flow_nodes": None, "terms": ["SHCP", "eşik"],
    }
    sc = base.get("scenario", scenario)
    h = hand_key

    if "Push" in str(sc):                          # PUSH/FOLD
        out["scenario_label"] = f"Push/Fold · {pos}"
        out["why"] = (f"Kısa stack ({stack_bb:.0f}bb) → equity ekseni. Puan {score} "
                      f"{'≥ jam eşiği → JAM' if action == 'JAM' else '< eşik → FOLD'}")
        _jthr = base.get("threshold", 16)
        out["threshold"] = _jthr
        out["chain_steps"] = [
            f"🃏 {h}: {out['card_breakdown']}",
            f"♟ Stack {stack_bb:.0f}bb → push/fold modu (Nash, pozisyon-duyarlı)",
            f"📍 {pos} jam-eşiği {_jthr} (geç poz → düşük eşik = geniş jam)",
            f"{'≥' if action == 'JAM' else '<'} Puan {score} {'≥' if action == 'JAM' else '<'} {_jthr} → {action}",
        ]
        out["terms"] = ["SHCP", "push/fold", "Nash", "ICM"]
    elif "3-bet" in str(sc) or "3bet" in str(sc):  # vs 3-BET
        b4 = base.get("b4", 0)
        out["scenario_label"] = f"vs 3-bet · 3BP"
        if action == "4-BET":
            out["why"] = f"B4 blocker {b4}≥2 → AA/AK bloklar, premium baskı → 4-BET"
        elif action == "CALL":
            out["why"] = "Çok güçlü (JJ+/AQs+/KQs) → düz çağır"
        else:
            out["why"] = "Premium değil → KATLA. 3-bet pot pahalı, marjinal el para yakar"
        _tb_early = (vs_position or "").upper() in ("UTG", "UTG+1", "MP", "LJ", "HJ")
        _tb_read = (f"♟ 3-bettor {vp or '?'}: " + ("ERKEN → sıkı range, premium-only (daha çok katla)"
                    if _tb_early else "GEÇ/blind → geniş/squeeze (suited-broadway da devam okunabilir)"))
        out["chain_steps"] = [
            f"🃏 {h}: {out['card_breakdown']} · B4 blocker {b4}",
            "🔒 3-bet pot: saf equity sıralaması ÇÖKER → blocker ekseni",
            f"{'B4≥2 → 4-BET' if action == '4-BET' else 'Premium değil → ' + action}",
            _tb_read,
            "💡 Kural: premium değilse KATLA (3-bettor pozisyonunu OKU)",
        ]
        out["terms"] = ["B4 blocker", "3BP", "blocker"]
    elif "vs" in str(sc).lower() and "rfi" in str(sc).lower() or "vs RFI" in str(sc):
        ct, rt = base.get("call_t"), base.get("raise_t")
        out["scenario_label"] = f"vs RFI · {vp or '?'} açtı"
        if action == "3-BET":
            out["why"] = f"Puan {score} ≥ 3bet eşiği {rt} → değer yükselt"
        elif action == "CALL":
            out["why"] = f"Orta bölge ({ct}≤{score}<{rt}) → düz çağır"
        else:
            out["why"] = f"İki eşiğin altı ({score}<{ct}) → negatif-EV bırak"
        out["chain_steps"] = [
            f"🃏 {h}: {out['card_breakdown']}",
            f"📍 {vp or '?'} açtı · call≥{ct} / 3bet≥{rt}",
            f"→ {action}",
            "♠ Açan ERKEN→sıkı savun, GEÇ→geniş",
        ]
        out["terms"] = ["SHCP", "eşik", "RFI"]
    else:                                          # RFI (açış)
        thr = base.get("threshold")
        out["scenario_label"] = f"RFI · {pos}"
        rel = "≥" if action.startswith("RAISE") else "<"
        out["why"] = (f"{pos} eşiği {thr}, puanın {score} → "
                      f"{'güvenle aç' if action.startswith('RAISE') else 'altında, para yakar → katla'}")
        out["chain_steps"] = [
            f"🃏 {h}: {out['card_breakdown']}",
            f"📍 {pos} eşiği {thr} (pozisyon PUANA eklenmez)",
            f"{rel} Puan {score} {rel} eşik {thr} → {action}",
            fmt,
        ]
        out["terms"] = ["SHCP", "eşik", "RFI"]

    # QUIZ metinleri
    out["quiz_prompt"] = f"Sen ne yapardın? ({out.get('scenario_label', '')} · {h})"
    out["quiz_correct"] = action
    out["quiz_options"] = ["FOLD", "CALL", "RAISE/3-BET"]
    return out


_BOARD_TR = {"dry": "KURU", "wet/dynamic": "ISLAK", "semi-wet": "SEMİ-ISLAK",
             "paired": "EŞLİ", "monotone": "TEK-RENK", "preflop": "—"}
_EXPLAIN_BB = None


def _explain_bb():
    """_hand_strength için cache'li board-aware evaluator (GTO Expert beyni)."""
    global _EXPLAIN_BB
    if _EXPLAIN_BB is None:
        from app.engine.bot_brain import BotBrain, BOT_ARCHETYPES
        _EXPLAIN_BB = BotBrain(BOT_ARCHETYPES["GTO Expert"])
    return _EXPLAIN_BB


def _tier_from(strength: float, draws: float) -> str:
    if strength >= 0.85:
        return "NUT"
    if strength >= 0.62:
        return "GÜÇLÜ"
    if strength >= 0.55:
        return "ORTA"
    if draws >= 0.30 and strength < 0.55:
        return "DRAW"
    if strength >= 0.40:
        return "ZAYIF"
    if strength >= 0.28:
        return "BLUFF-CATCH"
    return "HAVA"


def soyrac_postflop_advice(hand, hero_idx, advice=None) -> "dict | None":
    """Postflop ÖĞRETİCİ — board-aware _hand_strength → 7-kademe + 3 altın kural
    + sizing. Saf (Qt'siz); postflop_gto/bot kararı DEĞİŞMEZ."""
    try:
        from app.poker.postflop_gto import classify_board
        from app.engine.hand_state import Street
        hero = hand.players[hero_idx]
        board = list(getattr(hand, "community", []) or [])
        if len(board) < 3 or len(getattr(hero, "hole_cards", []) or []) < 2:
            return None
        strength, draws, _lbl = _explain_bb()._hand_strength(hero.hole_cards, board)
        eq = min(1.0, strength + 0.45 * draws)
        tex = classify_board(board)
        tier = _tier_from(strength, draws)
        blab = _BOARD_TR.get(tex.label, tex.label.upper())
        to_call = hand.to_call(hero_idx)
        pot = max(getattr(hand, "pot", 0.0), 0.01)
        stack = max(getattr(hero, "stack", 0.0), 0.01)
        street = getattr(hand, "street", Street.FLOP)
        wet = tex.wetness
        size = 0.33 if wet < 0.35 else (0.55 if wet < 0.6 else 0.75)
        # 3 ALTIN KURAL — ilk tetikleyen
        gr = None
        if to_call > 0 and to_call / stack > 0.70 and strength < 0.60 and draws < 0.30:
            gr = "⛔ Commit-gate: yığının %70'i riskte — sadece GÜÇLÜ+/çekme ile devam"
        elif street == Street.FLOP and tex.label == "dry" and to_call <= 0.01:
            gr = "🎯 Kuru board + agresör → range-cbet (her şeyle küçük bas, 1/3)"
        elif to_call > 0:
            be = to_call / (pot + to_call)
            if eq < be:
                gr = f"📉 Pot-odds: gereken %{be*100:.0f}, equity %{eq*100:.0f} → FOLD"
            else:
                gr = f"✅ Pot-odds: equity %{eq*100:.0f} ≥ gereken %{be*100:.0f} → call uygun"
        # AKSİYON (tier-uyumlu, öğretici)
        if to_call <= 0.01:
            if tier in ("NUT", "GÜÇLÜ"):
                action = "BET (value)"
            elif tier == "DRAW":
                action = "BET (semi-blöf)"
            elif tier == "ORTA" and street == Street.FLOP and tex.label == "dry":
                action = "BET (range)"
            else:
                action = "CHECK"
        else:
            be = to_call / (pot + to_call)
            if tier == "NUT":
                action = "RAISE"
            elif eq >= be:
                action = "CALL"
            else:
                action = "FOLD"
        # AYRI RANGE-DEĞERLENDİRMESİ: pot-odds el-vs-board equity kullanır (range-naif).
        # A/broadway board açan-range'ini (sıkı/erken) VURUR → gerçek equity şişik.
        # Range-ayarlı equity = generic − haircut(board-korkutuculuğu). İkisini de göster.
        range_note = None
        range_adj_eq = None
        if to_call > 0 and tier in ("ZAYIF", "BLUFF-CATCH", "HAVA", "ORTA"):
            ranks = [getattr(c, "rank", "") for c in board]
            bro = sum(1 for r in ranks if r in "AKQJT")
            has_ace = "A" in ranks
            if has_ace or bro >= 2:
                haircut = 0.20 if (has_ace and bro >= 2) else (0.15 if has_ace else 0.12)
                range_adj_eq = max(0.0, eq - haircut)
                be = to_call / (pot + to_call)
                verdict = "KATLA" if range_adj_eq < be - 0.02 else (
                    "marjinal (sıkıya fold, loose'a call)" if range_adj_eq < be + 0.04 else "call OK")
                range_note = (f"⚖ Range-aware: açan-range'i board'u vurur → gerçek eq "
                              f"~%{range_adj_eq*100:.0f} (generic %{eq*100:.0f}), gereken "
                              f"%{be*100:.0f} → {verdict}")
        line = f"🎴 {blab} · {tier} → {action}"
        chain = [
            f"🎴 Board {blab} (ıslaklık {wet:.2f})",
            f"📊 El gücün: {tier} (7-kademe)",
            gr or f"💡 {tier} → {action}",
        ]
        if range_note:
            chain.append(range_note)
        chain.append(f"📏 Sizing: pot×{size:.2f} ({'kuru→küçük' if wet < 0.35 else 'ıslak→büyük'})")
        flow = [("Board", blab, True), ("El", tier, True),
                ("Karar", action.split()[0], True)]
        return {"tier": tier, "board_label": blab, "wetness": round(wet, 2),
                "golden_rule": gr, "size_frac": size, "action": action, "line": line,
                "range_note": range_note, "range_adj_eq": range_adj_eq,
                "chain_steps": chain, "flow_nodes": flow,
                "strength": round(strength, 2), "draws": round(draws, 2), "eq": round(eq, 2)}
    except Exception:
        return None


def soyrac_leak_category(explain: dict, hero_action: str) -> "str | None":
    """Kullanıcı aksiyonu Soyrac önerisinden saparsa LEAK kategorisi (ders + leak-takibi).
    None = uyuşma veya önemsiz. explain = soyrac_explain çıktısı."""
    if not explain:
        return None

    def _n(a):
        a = (a or "").upper()
        if any(k in a for k in ("RAISE", "3-BET", "4-BET", "BET", "JAM")):
            return "R"
        if "CALL" in a or "CHECK" in a:
            return "C"
        if "FOLD" in a:
            return "F"
        return "?"

    hs, hh = _n(explain.get("action")), _n(hero_action)
    if hs == hh or hh == "?":
        return None
    sc = str(explain.get("scenario", "")).lower()
    if explain.get("phase") == "preflop":
        if "3-bet" in sc:
            if hh == "C" and hs == "F":
                return "3-bet pot over-call (premium değilken call → para yakar)"
            if hh == "R" and hs == "F":
                return "Aşırı 4-bet (premium/blocker yok)"
        elif "vs" in sc:                              # vs RFI
            if hh == "R" and hs != "R":
                return "Aşırı 3-bet (premium değilken yükseltme)"
            if hh == "C" and hs == "F":
                return "Over-defend — çöp/spekülatif savunma (GTO'da bile -EV)"
        else:                                          # RFI
            if hh == "R" and hs == "F":
                return "Çok geniş açış (eşik altı raise)"
            if hh == "F" and hs == "R":
                return "Çok sıkı — değer açışı kaçtı"
    else:                                              # postflop
        gr = explain.get("golden_rule", "") or ""
        if "Commit-gate" in gr and hh == "R":
            return "Commit-gate ihlali (zayıf elle %70+ stack riski)"
        if "Pot-odds" in gr and "FOLD" in gr and hh == "C":
            return "Pot-odds ihmali (negatif-EV call)"
        if "range-cbet" in gr and hh == "C":
            return "Range-cbet kaçırma (kuru board'da agresörken check)"
    return f"Sapma: sen {hh}, Soyrac {hs}"
