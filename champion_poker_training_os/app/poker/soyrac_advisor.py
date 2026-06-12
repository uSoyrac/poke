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
# Defender-pozisyon vs-RFI ince ayarı (call_delta, raise_delta) — D184 greedy
# kalibrasyon (defender×opener tam grid, %83.6→%91.0). Blind: opener_adj + bu;
# IP: opener_adj YOK + bu. BB over-call kıs, SB/HJ flat aç, CO/HJ 3bet sıkı.
_VSRFI_ADJ = {"BB": (1, 1), "SB": (-1, 1),
              "BTN": (1, 1), "CO": (0, 2), "HJ": (-1, 2)}


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


def _preflop_size(action: str, position: str, stack_bb: float,
                  ante: bool, hu: bool) -> "dict | None":
    """Preflop bet-sizing önerisi (D188, A9) — sizing_advice._open_size_bb'i bağlar.
    KRİTİK ayrım: aynı '4-BET' derin'de küçük (~2.2× 3bet) ama sığ'da JAM olmalı;
    eski advisor bu farkı hiç göstermiyordu (size_frac=None hardcode)."""
    a = (action or "").upper()
    st = round(stack_bb, 1)
    if "JAM" in a:
        return {"size_bb": st, "text": f"all-in ({st}bb)"}
    if "RAISE" in a:                                   # RFI açış
        try:
            from app.poker.sizing_advice import _open_size_bb
            sz = _open_size_bb(position, stack_bb, ante)
        except Exception:
            sz = round(stack_bb, 1) if stack_bb <= 15 else (2.3 if ante else 2.5)
        if sz >= stack_bb - 0.1:
            return {"size_bb": sz, "text": f"jam ({sz}bb — sığ)"}
        return {"size_bb": sz, "text": f"{sz}bb aç"}
    if "3-BET" in a:
        if stack_bb <= 25:
            return {"size_bb": st, "text": f"3bet-jam ({st}bb — sığ, fold-equity)"}
        ip = (position or "").upper() in ("BTN", "CO", "HJ")
        return {"size_bb": None,
                "text": "≈3× açış (IP)" if ip else "≈4× açış (OOP — pozisyon yok, denial)"}
    if "4-BET" in a:
        if stack_bb <= 40:
            return {"size_bb": st, "text": f"4bet-jam ({st}bb — sığ, commit)"}
        return {"size_bb": None, "text": "≈2.2× 3bet (küçük 4bet — derin, jam değil)"}
    return None


def _threshold_count_line(b: dict) -> str:
    """True-count tarzı eşik kırılımı (D186): 'baz 15 · ICM +1 · sığ +2 → efektif 18'.
    Blackjack running→true count gibi: baz eşik + yalnız SIFIR-OLMAYAN düzeltmeler.
    Kullanıcı 'neden bu eşik'i refleks okur; davranış değişmez, sadece görünür."""
    parts = [f"baz {b.get('base', 0)}"]
    for key, lbl in (("icm_adj", "ICM"), ("deep_adj", "sığ-stack"),
                     ("tourney_adj", "turnuva"), ("table_adj", "masa"),
                     ("preempt_adj", "pre-empt")):
        v = b.get(key, 0)
        if v:
            parts.append(f"{lbl} {v:+d}")
    return " · ".join(parts) + f" → efektif eşik {b.get('effective', 0)}"


def soyrac_advice(hand_key: str, position: str, scenario: str = "RFI",
                  vs_position: str = "", stack_bb: float = 100,
                  icm: bool = False, n_active: int = 9, tourney: bool = False,
                  bot_mode: bool = False, stage: str = "",
                  avg_stack_bb: float = 0.0) -> dict:
    """SENİN elin için masada-yapılabilir değerlendirme → {score, action, line, ...}.

    n_active<=2 → HEADS-UP modu: range'ler çok genişler (HU'da BTN/SB ~%85 açar,
    BB ~%70 savunur). Full-ring eşikleri HU'da çok sıkıdır (turnuvayı kapatamazsın).

    bot_mode=True (D184): SADECE bot-sim (advice_from_hand) için vs-RFI'yi eski
    cash-optimal (sıkı IP flat) tutar. Sebep: GTO-doğru geniş IP flat ADVICE için
    doğru (insan postflop'ta equity realize eder) ama bot postflop'u marjinal
    flopları sızdırır → cash −16bb/100 (5/5 seed, paired). Default False = insan-
    advice = GTO-accurate vs-RFI %91 (D169 deseni: GTO-genişlik advice katmanı)."""
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
    _facing = ("vs" in sc) or ("3-bet" in sc) or ("3bet" in sc)   # önünde raise/jam var

    # CALL-vs-JAM ekseni (D185, A1): kısa stack + ÖNÜNDE jam/raise var → re-jam çoğu
    # zaman imkânsız (rakip all-in); tek eksen CALL/FOLD. Eski kod stack<15'i kör
    # açış-jam dalına atıp "JAM" döndürüyordu = all-in'e re-jam öğretmek (yanlış-eğitim).
    # call_vs_jam_pct: Nash call-off range (jam'den DAR — call'lamak daha çok equity ister).
    if stack_bb < 15 and _facing:
        if hu:
            cj_thr = 12                            # HU: aksiyonu kapatıyorsun, fiyat var → geniş
        else:
            try:
                from app.poker.mtt_ranges import call_vs_jam_pct
                cp = call_vs_jam_pct(stack_bb) * 0.83
                if icm:
                    from app.poker.icm import cube_pressure_factor
                    cp *= cube_pressure_factor(stage or "bubble", stack_bb, avg_stack_bb)  # tavla-cube ICM
                cj_thr = _jam_threshold_for_pct(cp)
            except Exception:
                cj_thr = 18
        callit = score >= cj_thr
        return {"score": score, "action": "CALL" if callit else "FOLD",
                "scenario": "Call vs Jam", "threshold": cj_thr,
                "line": f"🧮 SHCP {score} {'≥' if callit else '<'} call-vs-jam eşik {cj_thr}"
                        f" ({pos}){' HU' if hu else ''} → {'CALL' if callit else 'FOLD'} (jam'e karşı)"}

    if "push" in sc or (stack_bb < 15 and not _facing):    # AÇIŞ-jam (önünde raise yok)
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
                    from app.poker.icm import cube_pressure_factor
                    jp *= cube_pressure_factor(stage or "bubble", stack_bb, avg_stack_bb)  # tavla-cube ICM
                jam_thr = _jam_threshold_for_pct(jp)
            except Exception:
                jam_thr = 16
        jam = score >= jam_thr
        return {"score": score, "action": "JAM" if jam else "FOLD",
                "scenario": "Push/Fold", "threshold": jam_thr,
                "size": _preflop_size("JAM" if jam else "FOLD", pos, stack_bb, bool(tourney), hu),
                "line": f"🧮 SHCP {score} ≥ jam-eşik {jam_thr} ({pos})"
                        f"{' HU' if hu else ''} → {'JAM' if jam else 'FOLD'}"
                        if jam else
                        f"🧮 SHCP {score} < jam-eşik {jam_thr} ({pos}) → FOLD"}

    if "3-bet" in sc or "3bet" in sc or "vs 3" in sc:   # blocker + üç-kademe eksen
        b4 = _b4_blocker(hand_key)
        # ÜÇ-KADEME (D182) — eski "b4≥2→4bet, score≥22→call, gerisi FOLD" mantığı
        # premium suited/offsuit broadway'i (KQs/KJs/QJs/JTs/AQo) ÇÖPE atıyordu:
        # GTO bunları CONTINUE eder (KQs 4-bet value, KJs/QJs/AQo flat) → 48 spot
        # kaçtı. Yeni: get_action'ın merged yapısını taklit et —
        #   4-BET VALUE: premium (skor≥v4_t: AQs+/JJ+/TT) — sığ-derin value/jam.
        #   4-BET BLUFF: wheel-ace blocker (b4≥2) ama SADECE DERİN (≤40bb GTO bluff-
        #     4bet'i folder; fold-equity realize olmaz, dominated call'lanır).
        #   FLAT/CONTINUE: broadway tier (skor≥flat_t) — eski 22 eşiği bunları fold'a
        #     düşürüyordu; flat_t=18 ile KQs/KJs/QJs/AQo continue (GTO call'lar).
        # Parametreler vs-3bet accuracy sweep'iyle kalibre: %90.4→%93.0 (943/1014).
        # STACK-AWARE value-4bet (D187, A2/A7): pair-ladder (16+2×rank) küçük/orta
        # çiftleri (TT-66 skor 24-32) şişiriyor → DERİN'de (cash 100bb) GTO bunları
        # set-mine için CALL/FOLD eder, 4-bet=domine spew. Derin: yüksek eşik (27) +
        # blocker-gate (b4≥2 = QQ+/AKs); JJ-TT-99-88 CALL'a düşer. Sığ (≤45bb): GTO
        # merged, geniş value (TT+ jam) → eski eşik (23, gate yok). flat_t değişmez.
        flat_t = (10 if hu else 18) + icm_adj
        if bot_mode or stack_bb <= 45:
            # BOT (her stack) + sığ advice: geniş value-4bet. Bot için cash-optimal —
            # GTO-doğru daraltma (derin çift→CALL) botu −16bb/100 düşürdü (D184 emsali,
            # paired); zayıf sahada agresif 4-bet +EV. Sığ'da GTO de geniş (merged).
            v4_t = 23 + icm_adj
            value4 = score >= v4_t
        else:
            # ADVICE + derin (>45bb): GTO polarize → SADECE QQ+/AKs value-4bet (b4≥2);
            # JJ-TT-99-88 set-mine için CALL (pair-ladder spew'ünü kapat, A2/A7).
            v4_t = 27 + icm_adj
            value4 = (score >= v4_t) and (b4 >= 2)
        bluff4 = (b4 >= 2 and stack_bb >= 60)
        if value4 or bluff4:
            act = "4-BET"
        elif score >= flat_t:
            act = "CALL"
        else:
            act = "FOLD"
        return {"score": score, "b4": b4, "action": act, "scenario": "vs 3-bet",
                "size": _preflop_size(act, pos, stack_bb, bool(tourney), hu),
                "line": f"🧮 SHCP {score} · B4 blocker {b4} · 4bet≥{v4_t}/call≥{flat_t}"
                        f" → {act}  (vs 3-bet)"}

    if "vs rfi" in sc or "vs açış" in sc or "vs_rfi" in sc:
        call_t, raise_t = (2, 14) if hu else _VS_RFI.get(pos, (9, 16))
        call_t += icm_adj + tourney_adj
        raise_t += icm_adj
        if tourney:   # D208: MTT facing over-call leak (sim: book BB CALL nerede ICM FOLD ×835)
            call_t += 3   # disiplinli savunma — pre-empt geniş açışıyla DENGE (tek-yön sıkmak zarar)
        # POZİSYON-DUYARLI SAVUNMA (D184): açan-pozisyonu (opener_adj) SADECE
        # OOP blind savunmasında önemli (squeeze riski + dominate). IP (BTN/CO/HJ)
        # flat'i açan-pozisyonundan AZ etkilenir → opener_adj UYGULANMAZ. Eski düz
        # opener_adj IP'de call_t'yi şişirip AŞIRI FOLD ettiriyordu (HJ 139 over-fold:
        # QJo/Q9s/T9s/suited-conn GTO-call'larını atıyordu). Yerine per-pozisyon
        # (call_delta, raise_delta) kalibrasyonu (defender×opener tam grid greedy):
        # IP'de 3bet sıkı/flat geniş; HJ en çok over-fold'du → flat'i aç (call−1).
        # vs-RFI accuracy %83.6→%91.0. Blocker-3bet-blöf SADECE IP (blind'da değil).
        if not hu:
            if bot_mode:                # BOT: eski cash-optimal (sıkı IP flat)
                call_t += _OPENER_ADJ.get((vs_position or "").upper(), 1)
            else:                       # ADVICE: GTO-accurate per-pozisyon (D184)
                cd, rd = _VSRFI_ADJ.get(pos, (0, 0))
                if pos in ("BB", "SB"):
                    call_t += _OPENER_ADJ.get((vs_position or "").upper(), 1)
                call_t += cd
                raise_t += rd
        act = "3-BET" if score >= raise_t else ("CALL" if score >= call_t else "FOLD")
        # 6-max AGRESYON (D148): geç açana karşı suited-wheel-As (A2s-A5s) 3-BET BLÖF.
        # Bu eller AA/AK'yı bloklar + nut-floş yedek-equity'si var. ADVICE'ta SADECE IP
        # defender (blind'da GTO flat/call'lar); bot_mode'da eski davranış (tüm pozisyon).
        bluff3 = ""
        _bluff_pos_ok = bot_mode or pos not in ("BB", "SB")
        if not hu and act in ("CALL", "FOLD") and _bluff_pos_ok and \
                (vs_position or "").upper() in ("CO", "BTN", "SB", "HJ") and \
                _b4_blocker(hand_key) >= 2:
            act = "3-BET"
            bluff3 = " (blocker blöf)"
        return {"score": score, "call_t": call_t, "raise_t": raise_t,
                "action": act, "scenario": "vs RFI",
                "size": _preflop_size(act, pos, stack_bb, bool(tourney), hu),
                "line": f"🧮 SHCP {score} · {pos}{' HU' if hu else ''} call≥{call_t}/3bet≥{raise_t} → {act}{bluff3}"}

    # RFI (açış) — pozisyon eşiği (puana eklenmez); HU'da çok düşük (geniş aç)
    # MASA-BOYUTU (D180): kısa masada ERKEN pozisyonlar daha az kişiyle karşılaşır →
    # GENİŞLE (6-max UTG 5 arkada, 9-max UTG 8 arkada gibi sıkı olmamalı). Geç pozisyon
    # (CO/BTN/SB) behind SABİT → dokunma. Gevşet: ~2 eksik oyuncu/-1, max -3. (Teori-
    # sağlam; GTO'da masa-boyutu verisi yok → temkinli faktör.)
    _early = pos in ("UTG", "UTG+1", "MP", "LJ", "HJ")
    table_adj = -min(3, (9 - n_active) // 2) if (not hu and _early and n_active < 9) else 0
    # PRE-EMPT (D207, bridge prensibi — botta +61pp MTT ROI, in+out-of-sample kanıtlı):
    # turnuvada geç-poz folded-to açış rakibi BLOKE eder (fold-equity) → cash-eşiğinin
    # ALTINDA aç. Az kişi = çok pre-empt (6-max>9-max). Pozisyon-kademe (BTN geniş /
    # SB dar-OOP) + kapatma-bölgesi (final 3-4 tam-gaz) + vulnerability (derin geniş /
    # sığ-baskı çek). Eşiği DÜŞÜRÜR. SADECE turnuva+geç-poz → cash dokunulmaz.
    preempt_adj = 0
    if tourney and not hu and _late_pos:
        pa = 3 + max(0, (9 - n_active) // 2)          # az kişi → daha geniş
        pa += {"BTN": 1, "CO": 0, "SB": -1}.get(pos, 0)  # bridge koltuk
        if n_active <= 3:
            pa += 2                                    # kapatma: tam-gaz
        if stack_bb > 45:
            pa += 1                                    # derin: bol fold-equity
        elif icm_adj > 0:
            pa -= 1                                    # sığ-baskı/bubble: çek
        pa = pa // 2   # D208: pre-empt YARI-genişlik — saf sistemde disiplinli defense'le
        preempt_adj = -pa   # tam-genişlik over-open'dı (sim: BTN RAISE nerede ICM FOLD ×603)
    base_thr = 3 if hu else _RFI.get(pos, 13)
    thr = base_thr + icm_adj + deep_adj + tourney_adj + table_adj + preempt_adj
    rel = "≥" if score >= thr else "<"
    # BB-OPSİYON (D203, F1): RFI dalında pos=BB → bedava-flop opsiyonu var; eşik altı
    # FOLD DEĞİL CHECK (limped/unraised pot'ta BB hiçbir zaman fold etmez, opsiyonunu
    # kullanır). Eşik üstü → RAISE (limper'ları izole / pot kur).
    if pos == "BB" and not hu:
        act = "RAISE (AÇ)" if score >= thr else "CHECK (bedava flop — opsiyon)"
    else:
        act = "RAISE (AÇ)" if score >= thr else "FOLD"
    # TRUE-COUNT göstergesi (D186): eşik bir DENKLEM (base + düzeltmeler). Blackjack
    # true-count gibi açığa çıkar → kullanıcı "neden bu eşik" görür (davranış DEĞİŞMEZ,
    # sadece şeffaflık). Coach paneli/Akademi bunu çubuk olarak çizebilir.
    breakdown = {"base": base_thr, "icm_adj": icm_adj, "deep_adj": deep_adj,
                 "tourney_adj": tourney_adj, "table_adj": table_adj,
                 "preempt_adj": preempt_adj, "effective": thr}
    return {"score": score, "threshold": thr, "action": act, "scenario": "RFI",
            "threshold_breakdown": breakdown,
            "size": _preflop_size(act, pos, stack_bb, bool(tourney), hu),
            "count_line": _threshold_count_line(breakdown),
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
                             tourney=tourney, bot_mode=True)
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
    _pa = (base.get("threshold_breakdown") or {}).get("preempt_adj", 0)
    if not tourney:
        fmt = "🎯 Cash: loose-aggressive — balığı ez"
    elif _pa:                                  # pre-empt aktif: çelişki önle
        fmt = "🏆 Turnuva geç-poz: PRE-EMPT — açış bloke eder, geniş çal"
    else:
        fmt = "🏆 Turnuva: ICM-sıkı, survival"
    out = {
        "phase": "preflop", "scenario": base.get("scenario", scenario),
        "action": action, "tone": _tone_for_action(action), "line": base.get("line", ""),
        "score": score, "threshold": base.get("threshold"),
        "call_t": base.get("call_t"), "raise_t": base.get("raise_t"), "b4": base.get("b4"),
        "threshold_breakdown": base.get("threshold_breakdown"),
        "count_line": base.get("count_line", ""),    # D194: true-count eşik kırılımı
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


def _board_threat(board, label: str, hole=None) -> "tuple[float, list]":
    """Board-tehdit haircut'ı (D198+D200). _hand_strength MUTLAK el-gücü verir
    (random'a karşı) ama board-tehdidini görmez. Bu, made-hand'in board'a karşı
    NE KADAR korunmasız olduğunu RANK-FARKINDALIKLI hesaplar: 3-flush'ta nut-floşun
    yoksa, eşli board'da alt-dolu/zayıf-kicker-trips, DÜZ board'da idiot-end, Ace/
    broadway board'da açan-range vurması. label=_hand_strength el-tipi; hole=hero
    kartları (rank-farkındalık için). nut-floş/üst-dolu vb. gerçekten nut ise muaf."""
    from collections import Counter
    if not board:
        return 0.0, []
    hole = hole or []
    hv = [c.value for c in hole]
    hs = [c.suit for c in hole]
    suit_ct = Counter(c.suit for c in board)
    rank_ct = Counter(c.value for c in board)
    suit_n = max(suit_ct.values())
    bvals = [c.value for c in board]
    ranks = [getattr(c, "rank", "") for c in board]
    h, reasons = 0.0, []

    # 1) FLUSH board (3+ aynı renk) — RANK-FARKINDALIKLI (sub-nut floş NUT değil)
    flush_suit = next((s for s, n in suit_ct.items() if n >= 3), None)
    if flush_suit and label not in ("full house", "quads", "straight flush"):
        hero_flush_ranks = [c.value for c in hole if c.suit == flush_suit]
        if label == "flush":
            if any(v >= 11 for v in hero_flush_ranks):     # A(12)/K(11) floş = (near-)nut → muaf
                pass
            else:
                h += 0.20; reasons.append("sub-nut floş (üst floş mümkün)")
        else:                                              # made-hand, floş yok
            h += 0.34 if suit_n >= 4 else 0.28
            reasons.append("flush board, çubuğun yok")

    # 2) EŞLİ board — RANK-FARKINDALIKLI (alt-dolu / zayıf-kicker trips)
    board_pair = max((r for r, n in rank_ct.items() if n >= 2), default=0)
    if board_pair:
        if label == "trips":
            kick = max((v for v in hv if v != board_pair), default=0)
            if kick < 10:                                  # < Q(10) kicker → üst-trips/dolu mümkün
                h += 0.14; reasons.append("trips zayıf-kicker")
        elif label == "full house":
            if len(hv) == 2 and hv[0] == hv[1] and hv[0] < board_pair:
                h += 0.22; reasons.append("alt-dolu (üst-dolu mümkün)")
        elif label not in ("quads", "set"):
            h += 0.12; reasons.append("eşli board, dolu/trips mümkün")

    # 3) DÜZ board (4-ardışık-board / board düz yapıyor) — D200 yeni
    bu = sorted(set(bvals))
    if 12 in bu:                                           # Ace (bu ölçekte A=12)
        bu = sorted(set(bu + [-1]))                        # tekerlek (A-2-3-4-5, A=düşük)
    four_straight = any(bu[i + 3] - bu[i] <= 4 for i in range(len(bu) - 3))
    board_full_straight = any(bu[i + 4] - bu[i] == 4 for i in range(len(bu) - 4))
    if four_straight and label not in ("flush", "full house", "quads", "straight flush"):
        if board_full_straight and label == "straight":
            h += 0.35; reasons.append("board'da tam düz — board oynuyor olabilirsin (chop)")
        elif label == "straight":
            h += 0.18; reasons.append("düz board, idiot-end riski (üst-düz mümkün)")
        else:
            h += 0.16; reasons.append("düz board, düz hazır olabilir")

    # 4) Ace/broadway board — villain açış-range'i board'u sık vurur
    if label not in ("flush", "full house", "quads", "straight", "set", "trips",
                     "top two pair", "two pair"):
        bro = sum(1 for r in ranks if r in "AKQJT")
        if "A" in ranks:
            h += 0.10; reasons.append("Ace board, açan-range vurur")
        elif bro >= 2:
            h += 0.07; reasons.append("broadway board")
    return min(0.52, h), reasons


def _draw_equity(hole, board) -> "tuple[float, list]":
    """Çekme equity'si — STREET-AWARE + COMBO-AWARE (D201). _hand_strength'in draw'ı
    river'da hayalet-equity verir (board-kart-sayısı kör) + combo (FD+düz) ayırmaz +
    flop(2-kart)/turn(1-kart) realization'ı eşitler. Bu, çekmeyi DOĞRU sayar:
    river→0 (çekme kalmadı), flop rule-of-4, turn rule-of-2, FD+düz ADDITIVE.
    Card değer-ölçeği 0-index (A=12)."""
    n = len(board)
    if n >= 5:
        return 0.0, []                                   # RİVER: çekme yok (hayalet öl)
    if not hole or n < 3:
        return 0.0, []
    from collections import Counter
    hv = [c.value for c in hole]
    hs = [c.suit for c in hole]
    bv = [c.value for c in board]
    sc = Counter(hs + [c.suit for c in board])
    outs, notes = 0, []
    # FLUSH-çekme: hero o renkte ≥1 kart + toplam 4 (5 değil=zaten flush) → 9 out
    fd = next((s for s, c in sc.items() if c == 4 and s in hs), None)
    if fd:
        outs += 9; notes.append("floş-çekme(9)")
    # DÜZ-çekme: açık-uçlu(8) / gutshot(4). Tekerlek için A=−1.
    av = sorted(set(hv + bv))
    if 12 in av:
        av = sorted(set(av + [-1]))
    oesd = any(av[i + 3] - av[i] == 3 for i in range(len(av) - 3))
    gut = (not oesd) and any(av[i + 3] - av[i] == 4 for i in range(len(av) - 3))
    if oesd:
        outs += 8; notes.append("açık-uçlu(8)")
    elif gut:
        outs += 4; notes.append("gutshot(4)")
    # OVERCARD'lar (iki kart da board'un üstünde, başka çekme yoksa) → küçük kredi
    if not fd and not oesd and hv and bv and min(hv) > max(bv):
        outs += 3; notes.append("2 overcard(3)")
    if outs <= 0:
        return 0.0, []
    mult = 4 if n == 3 else 2                             # flop iki-kart / turn tek-kart
    return min(0.72, outs * mult / 100.0), notes


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
        strength, _raw_draws, label = _explain_bb()._hand_strength(hero.hole_cards, board)
        # ÇEKME (D201): _hand_strength draw'ı river-hayalet + combo-kör + street-eşit.
        # _draw_equity DOĞRU sayar (river=0, flop ×4/turn ×2, FD+düz additive).
        draws, draw_notes = _draw_equity(hero.hole_cards, board)
        eq = min(1.0, strength + draws)
        tex = classify_board(board)
        tier = _tier_from(strength, draws)
        blab = _BOARD_TR.get(tex.label, tex.label.upper())
        to_call = hand.to_call(hero_idx)
        pot = max(getattr(hand, "pot", 0.0), 0.01)
        stack = max(getattr(hero, "stack", 0.0), 0.01)
        street = getattr(hand, "street", Street.FLOP)
        # BOARD-TEHDİT (D198): made-hand FACING-A-BET'te board-tehdidiyle (flush/eşli/
        # Ace-broadway) bluff-catcher'a düşer. eq_facing = eq − tehdit (sadece bahse
        # karşı). nut-tipi (flush/dolu vb.) muaf.
        threat, threat_reasons = _board_threat(board, label, hero.hole_cards)
        # Bu board'un GERÇEK nut-tipi (tehdide bağışık): üst-dolu/quads/straight-flush
        # ve near-nut floş (threat~0). Bunun dışındaki made-hand, tehdit yüksekse
        # facing-bet'te bluff-catcher, betting'de pot-kontrol/check (D200 — set on
        # flush board RAISE değil; sub-nut floş NUT değil).
        _real_nut = ((label in ("full house", "quads", "straight flush") and threat < 0.08)
                     or (label == "flush" and threat < 0.05))
        # MULTIWAY (D202): coach HU-varsayımlıydı; çok-yollu pot'ta el-değerleri düşer
        # (her rakip board'u vurabilir), range-cbet fold-equity'si çöker. n_active türet;
        # ≥3 → made-marjinal eq'ye field-haircut (ÇEKMELER MUAF — nut FD değer korur),
        # range-cbet kapat. Pure-threshold üstüne ince katman.
        n_active = getattr(hand, "active_count", 0) or sum(
            1 for pl in hand.players if not getattr(pl, "is_folded", False)
            and not getattr(pl, "is_eliminated", False)) or 2
        _multi = n_active >= 3
        field_hc = min(0.18, 0.07 * (n_active - 2)) if _multi else 0.0
        eq_facing = max(0.0, eq - threat) if to_call > 0 else eq
        if to_call > 0 and _multi and tier != "DRAW" and not _real_nut:
            eq_facing = max(0.0, eq_facing - field_hc)      # çok rakip = çok el seni geçer
            if field_hc:
                threat_reasons = (threat_reasons or []) + [f"{n_active}-yollu (alan haircut)"]
        _bluff_catch = (to_call > 0 and (threat >= 0.18 or (_multi and threat >= 0.10)) and not _real_nut)
        _vuln_bet = (to_call <= 0.01 and threat >= 0.22 and not _real_nut)
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
            if threat >= 0.12:
                _tr = ", ".join(threat_reasons)
                gr = (f"⚖ Board-tehdit ({_tr}): made-hand bluff-catcher → gerçek eq "
                      f"~%{eq_facing*100:.0f} (ham %{eq*100:.0f}), gereken %{be*100:.0f} → "
                      + ("KATLA" if eq_facing < be - 0.02 else
                         ("marjinal: pasif/under-bluffer'a FOLD, agresife CALL"
                          if eq_facing < be + 0.10 else "call uygun")))
            elif eq_facing < be:                       # D202: action ile aynı eq (desync biter)
                _mw = f" ({n_active}-yollu)" if _multi else ""
                gr = f"📉 Pot-odds{_mw}: gereken %{be*100:.0f}, equity %{eq_facing*100:.0f} → FOLD"
            else:
                _mw = f" ({n_active}-yollu)" if _multi else ""
                gr = f"✅ Pot-odds{_mw}: equity %{eq_facing*100:.0f} ≥ gereken %{be*100:.0f} → call uygun"
        # AKSİYON (tier-uyumlu, öğretici)
        if to_call <= 0.01:
            # RANGE-CBET (D188b/A12): kuru flop'ta agresörken golden_rule "her şeyle
            # küçük bas" diyordu ama action HAVA/ZAYIF'ı CHECK ediyordu (çelişki). Kuru
            # board'da TÜM range küçük cbet (blöf dahil — range avantajı + fold-equity).
            # Islak board polarize kalır (sadece value/çekme bas, gerisi check).
            # MULTIWAY: range-cbet (blöf dahil) sadece HU'da — 3+ rakipte fold-equity
            # çöker (C1) → çok-yollu pot'ta sadece value bas.
            _range_cbet = (street == Street.FLOP and tex.label == "dry" and not _multi)
            if _vuln_bet and tier in ("NUT", "GÜÇLÜ", "ORTA"):
                # D200: tehlikeli board'da korunmasız made-hand → BET value DEĞİL,
                # pot-kontrol/check (board konuştu; büyük value-bet kendini fold-ettirir/
                # raise yer). A1: monotone top-pair artık CHECK.
                action = "CHECK (board tehlikeli — pot kontrol/bluff-catch)"
            elif tier in ("NUT", "GÜÇLÜ"):
                action = "BET (value)"
            elif tier == "DRAW":
                action = "BET (semi-blöf)"
            elif _range_cbet and tier in ("ORTA", "ZAYIF", "BLUFF-CATCH", "HAVA"):
                action = "BET (range)"          # kuru board agresör → blöf dahil cbet
            else:
                action = "CHECK"
        else:
            be = to_call / (pot + to_call)
            # FACING-A-BET: board-tehdit-ayarlı eq (eq_facing). Bluff-catch ise
            # eşik civarı = OKUMA-BAĞIMLI (pasife fold / agresife call), kör CALL değil.
            if tier == "NUT" and not _bluff_catch:
                action = "RAISE"
            elif eq_facing >= be + 0.10:
                action = "CALL"
            elif eq_facing >= be - 0.02:
                action = "CALL (marjinal — pasif/under-bluffer'a FOLD, agresife CALL)"
            else:
                action = "FOLD"
            if _bluff_catch:
                tier = "BLUFF-CATCH"           # görünür tier'ı da düzelt (top-pair değil)
        # BOARD-TEHDİT NOTU (D198): birleşik haircut (flush/eşli/Ace-broadway) — eski
        # ayrı "range-aware" (sadece Ace/broadway + GÜÇLÜ hariç) bunu kaçırıyordu.
        range_note = None
        range_adj_eq = None
        if to_call > 0 and threat >= 0.12:
            range_adj_eq = eq_facing
            # gr zaten board-tehdidi gösteriyorsa tekrarlama (dedup) → ek vurgu kısa kalsın
            if "Board-tehdit" not in (gr or ""):
                range_note = ("⚖ Board-tehdit (" + ", ".join(threat_reasons) +
                              f"): made-hand bluff-catcher → gerçek eq ~%{eq_facing*100:.0f} "
                              f"(ham %{eq*100:.0f}). Üst-eline âşık olma; pasife fold, agresife call.")
            else:
                range_note = "💡 Üst-eline âşık olma — board konuştu; pasife fold, agresife call."
        line = f"🎴 {blab} · {tier} → {action}"
        chain = [
            f"🎴 Board {blab} (ıslaklık {wet:.2f})",
            f"📊 El gücün: {tier} (7-kademe)",
            gr or f"💡 {tier} → {action}",
        ]
        if range_note:
            chain.append(range_note)
        # SIZING satırı SADECE bet/raise'te (D4: CHECK/FOLD'da sizing göstermek çelişki).
        # RAISE = önündeki bahsin katı (pot-fraksiyonu DEĞİL — D2: aksi absürt/illegal).
        if "RAISE" in action:
            _rto = round(to_call * 2.7, 1)
            chain.append(f"📏 Sizing: ≈{_rto}bb'ye raise (önündeki bahsin ~2.7×; pot-fraksiyonu değil)")
        elif "BET" in action:
            _spr = stack / pot
            if _spr < 1.3 and tier in ("NUT", "GÜÇLÜ"):
                chain.append("📏 Sizing: düşük SPR + güçlü → jam/commit (küçük bahis yok)")
            else:
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
