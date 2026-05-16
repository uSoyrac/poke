from __future__ import annotations

from app.ai.safety_filters import is_live_strategy_request, refusal_message
from app.poker.alpha_mdf import alpha, mdf
from app.poker.blockers import blocker_note
from app.poker.pot_odds import required_equity
from app.solver.mock_solver import compare_action, solve_spot


def explain_spot(spot: dict, hero_action: str | None = None) -> str:
    """Spot için detaylı Türkçe coach analizi.

    9 bölüm yerine 5 anlamlı blok — gereksiz jargon yok, her cümle bir
    öğretici noktayı vurguluyor. Sonunda bir mnemonic ve drill önerisi.
    """
    if hero_action:
        result = compare_action(spot, hero_action)
    else:
        solver = solve_spot(spot)
        result = {
            "hero_action": "—",
            "best_action": solver.best_action,
            "ev_loss": 0.0,
            "best_frequency": solver.actions[0].frequency if solver.actions else 0.0,
            "solver": {
                "source_confidence": solver.source_confidence,
                "range_advantage": solver.range_advantage,
                "nut_advantage": solver.nut_advantage,
            },
        }

    pot      = float(spot.get("pot_bb", 10.0))
    risk     = max(1.0, pot * 0.66)
    req_eq   = required_equity(risk, pot)
    defense  = mdf(risk, pot)
    source   = result["solver"]["source_confidence"]
    pos      = spot.get("position", "Hero")
    stack    = spot.get("stack_bb", "?")
    pot_t    = spot.get("pot_type", "SRP")
    street   = spot.get("street", "preflop")
    board    = spot.get("board") or "—"
    hero_h   = spot.get("hero_cards", "?")
    hero_a   = result["hero_action"]
    gto_a    = result["best_action"]
    ev_loss  = result["ev_loss"]
    freq     = result.get("best_frequency", 0)

    # Diagnose hata türü
    if ev_loss < 0.05:
        verdict = "✅ Karar doğru — GTO ile uyumlu."
        verdict_color = "✓"
    elif ev_loss < 0.5:
        verdict = "⚠ Marjinal hata — EV kaybı küçük ama tekrarlanırsa leak olur."
        verdict_color = "⚠"
    elif ev_loss < 1.5:
        verdict = "❌ Belirgin hata — bu spot'u drill etmen lazım."
        verdict_color = "✗"
    else:
        verdict = "🔥 Büyük leak — bu hata pahalı, hemen düzelt."
        verdict_color = "‼"

    # Pot odds yorumu
    pot_odds_note = (
        f"%50 pot bahis karşılığında %{req_eq*100:.0f} equity gerekir. "
        f"MDF (savunma frekansı): %{defense*100:.0f}."
    )

    # Range advantage explanation in Türkçe (fallback varsa boş)
    range_note = (result["solver"].get("range_advantage")
                  or _range_advantage_fallback(pos, pot_t, street))
    nut_note   = (result["solver"].get("nut_advantage")
                  or _nut_advantage_fallback(hero_h, board))

    # Blocker analysis
    blockers = blocker_note(hero_h, board if board != "—" else "")
    if not blockers:
        blockers = "Bu eli blocker açısından değerlendir: villain'ın value range'ini blokluyor musun?"

    # Position-specific mnemonic
    mnemonic = _mnemonic_for(pos, pot_t, gto_a)

    return (
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 SPOT: {pos} · {stack}bb · {pot_t} · {street.title()}\n"
        f"   Elin: {hero_h}  |  Board: {board}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{verdict_color} VERDIKT\n"
        f"{verdict}\n"
        f"Sen: {hero_a.upper()}  →  GTO: {gto_a.upper()} (%{freq*100:.0f} frekans)\n"
        f"EV kaybı: {ev_loss:.2f}bb  ·  Solver source: {source}\n\n"

        f"📐 MATEMATIK\n"
        f"{pot_odds_note}\n\n"

        f"🃏 RANGE & BLOCKER\n"
        f"{range_note}\n"
        f"{nut_note}\n"
        f"{blockers}\n\n"

        f"🎓 AKILDA KALSIN\n"
        f"{mnemonic}\n\n"

        f"⚡ EXPLOIT NOTU\n"
        f"Villain over-folds → küçük sizing yüksek frekansla baskı.\n"
        f"Villain calling station → value-heavy plan, bluff'ları kes.\n"
        f"Villain LAG/agresif → trap'le, slow-play düşük frekansta.\n\n"

        f"🔁 SONRAKI ADIM\n"
        f"⚡ 'Drill Bunları' butonuyla benzer 5+ spot çöz. 3 doğru üst üste\n"
        f"yapınca leak otomatik kapanır. Sonra aynı spotu feedback kapalı tekrar dene."
    )


def _range_advantage_fallback(position: str, pot_type: str, street: str) -> str:
    """Generic range advantage commentary when solver doesn't supply one."""
    pos = (position or "").upper()
    pt  = (pot_type or "SRP").upper()
    st  = (street or "preflop").lower()
    if st == "preflop":
        if pos in ("UTG", "UTG+1", "UTG1", "LJ"):
            return ("Range avantajı: early position dar açış range'i → premium-heavy. "
                    "Late position 3-bet'lere karşı value-heavy savun.")
        if pos in ("BTN", "CO"):
            return ("Range avantajı: late position geniş açış → blind'lara karşı "
                    "küçük edge ama yüksek hand frequency.")
        if pos in ("SB", "BB"):
            return ("Range avantajı: blind'lar OOP, range disadvantage. Pot odds "
                    "+ closing action ile defend; 3-bet polarize.")
    if pt == "3BP":
        return ("3BP'da 3-bettor range avantajına sahip — value-heavy ve linear. "
                "Caller capped range — kendi yapısını koru.")
    if pt == "4BP":
        return "4BP'da her iki range çok daraldı — premium showdown + bluff polarize."
    return "Range advantage texture'a bağlı — kuru boardda OOP raiser, ıslak boardda IP caller avantajlı."


def _nut_advantage_fallback(hero_cards: str, board: str) -> str:
    """Comment on nut advantage based on hero hand and board."""
    if not board or board == "—":
        return "Nut advantage preflop'ta yok — postflop board'a göre değişir."
    # Simple heuristic: check overlap between hero ranks and board
    if hero_cards and len(hero_cards) >= 2:
        hero_ranks = {hero_cards[0].upper(), hero_cards[2].upper() if len(hero_cards) > 2 else ""}
        board_ranks = set()
        for i in range(0, len(board) - 1, 2):
            board_ranks.add(board[i].upper())
        if "A" in hero_ranks and "A" in board_ranks:
            return "Top set/2-pair imkanı — nut advantage hero tarafında."
        if hero_ranks & board_ranks:
            return "Pair olabilir — orta nut tier, value-bet uygun."
    return "Nut advantage düşük — bluff catcher veya semi-bluff modunda oyna."


def _mnemonic_for(position: str, pot_type: str, gto_action: str) -> str:
    """Position+pot_type+action için akılda kalıcı tek-cümle kuralı."""
    pos = (position or "").upper()
    pt  = (pot_type or "SRP").upper()
    a   = (gto_action or "").lower()

    if pt == "3BP" and a == "fold":
        return "3-bet'lere range tighten — marjinal eller premium 4-bet'e veya fold'a gider."
    if pt == "3BP" and a == "4bet":
        return ("4-bet polarize: value (AKs, QQ+) + blocker bluff (A5s-A2s). "
                "Linear 4-bet (KQs, JJ) cold-call yapan rakibe karşı.")
    if pt == "3BP" and a == "call":
        return ("3-bet cold-call: pocket pair set-mining + suited connectors implied odds. "
                "IP'de daha geniş, OOP'da daha sıkı.")
    if pt == "4BP" and a == "jam":
        return "4-bet pot SPR <2 → kalan stack'le jam yap, fold etmek pot odds'a haksızlık."
    if pos in ("UTG", "UTG+1", "UTG1", "LJ") and a == "raise":
        return ("Early position sıkı open: premium + playable suited broadways. "
                "Marjinal eller fold — dominated dominance riski yüksek.")
    if pos in ("BTN", "CO") and a == "raise":
        return ("Late position geniş steal: blind'lar weak/tight ise %50+ open. "
                "Suited connectors + suited gappers playable.")
    if pos in ("BB", "SB") and a == "call" and pt == "SRP":
        return ("Blind defense: pot odds + closing action avantajı. Yakın spotta "
                "suited > offsuit, position vs aggressor önemli.")
    if a == "fold":
        return ("Marjinal spotta fold = chip preservation. Range edge yoksa savaşma; "
                "dominated dominance riski varsa fold > marginal call.")
    if a == "jam":
        return ("Push range = stack/SPR + fold equity matematiği. Short stack "
                "(<15bb): jam range'i genişler, call range'i daralır.")
    if a == "check":
        return ("Check ≠ pasif: range protection ve trap kurma. Strong range vs weak "
                "range'de check daha sık; nut advantage'ın varsa bet sıklığın artar.")
    if a == "bet":
        return ("Bet sizing = range advantage + nut advantage + board texture. "
                "Dry monoton boardda küçük sizing, dynamic wet board'da büyük.")
    return "GTO solver dengeli karışım kullanıyor — frekans önemli, ezberleme."


# ─── Hand Review (Post-game Analysis) ───────────────────────────────


def analyze_played_hand(result: dict) -> str:
    """Analyze a completed hand and provide street-by-street coaching."""
    hero_cards = result.get("hero_cards", "??")
    community = result.get("community", "")
    profit = result.get("hero_profit", 0)
    won = result.get("hero_won", False)
    invested = result.get("hero_invested", 0)
    pot = result.get("pot", 0)
    winner_hand = result.get("winner_hand_name", "")

    parts = [f"📋 El Analizi: Hero {hero_cards} | Board: {community}"]
    parts.append(f"💰 Sonuç: {'Kazandın' if won else 'Kaybettin'} ({profit:+.1f}bb)")
    parts.append(f"📊 Pot: {pot:.1f}bb | Yatırımın: {invested:.1f}bb | Kazanan el: {winner_hand}")
    parts.append("")

    # Preflop analysis
    parts.append("🃏 Preflop:")
    if hero_cards and len(hero_cards) >= 3:
        _analyze_preflop_hand(hero_cards, parts)

    # Board interaction
    if community and community != "—":
        parts.append("")
        parts.append("🎯 Board Etkileşimi:")
        _analyze_board_interaction(hero_cards, community, parts)

    # Result-based coaching
    parts.append("")
    if not won and invested > pot * 0.3:
        parts.append("⚠️ Gelişim önerisi:")
        parts.append("  • Yüksek yatırımla kaybedilen pot — pot control ve hand reading geliştir")
        parts.append("  • Blocker analizi: elinin villain'ın bluff'larını mı value'sunu mu bloklayıp bakmadığını kontrol et")
    elif won and invested < pot * 0.15:
        parts.append("💡 Not:")
        parts.append("  • Az yatırımla kazandın — thin value fırsatı kaçırılmış olabilir")
        parts.append("  • Rakip capped olduğunda küçük bet ile value almayı dene")
    elif won:
        parts.append("✅ İyi oynanan el. Kazanç sağladın.")

    return "\n".join(parts)


def _analyze_preflop_hand(hero_cards: str, parts: list) -> None:
    """Analyze preflop hand quality."""
    # Extract ranks
    clean = hero_cards.replace(" ", "").replace("♥", "h").replace("♦", "d").replace("♠", "s").replace("♣", "c")
    if len(clean) < 4:
        parts.append("  • El bilgisi yetersiz")
        return

    r1, r2 = clean[0], clean[2]
    s1, s2 = clean[1], clean[3]
    suited = s1 == s2
    pair = r1 == r2

    rank_order = "23456789TJQKA"
    v1 = rank_order.index(r1) if r1 in rank_order else 0
    v2 = rank_order.index(r2) if r2 in rank_order else 0

    if pair:
        if v1 >= 10:  # TT+
            parts.append(f"  • Premium pair ({r1}{r1}) — 3bet/4bet değerli")
        elif v1 >= 6:  # 88-99
            parts.append(f"  • Medium pair ({r1}{r1}) — set mining, pozisyona bağlı open/call")
        else:
            parts.append(f"  • Small pair ({r1}{r1}) — set mine, cautious postflop")
    elif max(v1, v2) >= 11:  # Broadway
        if suited:
            parts.append(f"  • Suited broadway ({r1}{r2}s) — güçlü, 3bet veya cold call uygun")
        else:
            parts.append(f"  • Offsuit broadway ({r1}{r2}o) — pozisyona göre oyna")
    elif suited and abs(v1 - v2) <= 2:
        parts.append(f"  • Suited connector ({r1}{r2}s) — multiway ve IP oynamaya çalış")
    else:
        parts.append(f"  • Marginal el ({r1}{r2}) — pozisyon ve table dynamics önemli")


def _analyze_board_interaction(hero_cards: str, community: str, parts: list) -> None:
    """Analyze how hero cards interact with the board."""
    clean_hero = hero_cards.replace(" ", "").replace("♥", "").replace("♦", "").replace("♠", "").replace("♣", "")
    clean_board = community.replace(" ", "").replace("♥", "").replace("♦", "").replace("♠", "").replace("♣", "")

    hero_ranks = set(clean_hero[::2]) if len(clean_hero) >= 2 else set()
    board_ranks = set(clean_board[::2]) if clean_board else set()

    connected = hero_ranks & board_ranks
    if connected:
        parts.append(f"  • Board'la bağlantı: {', '.join(connected)} ile pair/set potansiyeli")
    else:
        parts.append("  • Board'la direkt bağlantı yok — bluff veya draw oynama pozisyonunda olabilirsin")


# ─── Session Summary ────────────────────────────────────────────────


def session_summary(stats: dict, hands: list) -> str:
    """Generate end-of-session coaching summary."""
    total = stats.get("hands", 0)
    profit = stats.get("profit_bb", stats.get("profit", 0))
    vpip = stats.get("vpip", 0)
    win_rate = stats.get("win_rate", 0)

    parts = ["📊 Session Özeti"]
    parts.append(f"  Eller: {total} | Profit: {profit:+.1f}bb | VPIP: {vpip:.0f}% | Win rate: {win_rate:.0f}%")
    parts.append("")

    # Performance grade
    if profit > 15:
        parts.append("🏆 Harika session! Disiplini koru.")
    elif profit > 0:
        parts.append("✅ Pozitif session. Küçük iyileştirmelerle daha da iyi olabilir.")
    elif profit > -10:
        parts.append("⚠️ Hafif kayıp. Normal varyans olabilir, leak check yap.")
    else:
        parts.append("🔴 Ciddi kayıp. Leak analizi ve hand review yapman önemli.")

    # VPIP assessment
    parts.append("")
    if vpip > 35:
        parts.append("📌 VPIP çok yüksek — preflop range'ini sıkılaştır, özellikle EP ve MP'den.")
    elif vpip < 15:
        parts.append("📌 VPIP çok düşük — karlı steal ve defend fırsatlarını kaçırıyorsun.")
    else:
        parts.append("📌 VPIP normal aralıkta — preflop disiplini iyi görünüyor.")

    # Win/loss analysis from hand results
    if hands:
        big_wins = [h for h in hands if h.get("hero_profit", 0) > 15]
        big_losses = [h for h in hands if h.get("hero_profit", 0) < -15]
        if big_wins:
            parts.append(f"  💰 Büyük kazançlar: {len(big_wins)} el (toplam +{sum(h['hero_profit'] for h in big_wins):.1f}bb)")
        if big_losses:
            parts.append(f"  💸 Büyük kayıplar: {len(big_losses)} el (toplam {sum(h['hero_profit'] for h in big_losses):.1f}bb)")

    parts.append("")
    parts.append("📋 Sonraki adımlar:")
    parts.append("  1. En pahalı 3 eli hand review ile incele")
    parts.append("  2. Preflop range accuracy'ni range trainer'da kontrol et")
    parts.append("  3. Leak finder'da otomatik analiz çalıştır")

    return "\n".join(parts)


def identify_patterns(hands: list) -> str:
    """Detect recurring patterns in played hands."""
    if len(hands) < 5:
        return "Pattern tespiti için en az 5 el gerekli."

    total = len(hands)
    wins = sum(1 for h in hands if h.get("hero_won", False))
    showdowns = sum(1 for h in hands if h.get("streets_seen", 0) >= 4)
    folds = sum(1 for h in hands if h.get("streets_seen", 0) <= 1 and not h.get("hero_won", False))

    parts = [f"🔍 Pattern Analizi ({total} el):"]

    fold_pct = 100 * folds / total if total else 0
    if fold_pct > 70:
        parts.append(f"  ⚠️ Çok fazla fold ({fold_pct:.0f}%) — blind steal ve defend frekansını artır")
    elif fold_pct < 30:
        parts.append(f"  ⚠️ Az fold ({fold_pct:.0f}%) — marginal ellerle daha fazla fold et")

    sd_pct = 100 * showdowns / total if total else 0
    if sd_pct > 40:
        parts.append(f"  ⚠️ Çok fazla showdown ({sd_pct:.0f}%) — river calling range'ini sıkılaştır")

    win_pct = 100 * wins / total if total else 0
    if win_pct > 60:
        parts.append(f"  ✅ Yüksek win rate ({win_pct:.0f}%) — bu pace'i korumaya çalış")
    elif win_pct < 25:
        parts.append(f"  🔴 Düşük win rate ({win_pct:.0f}%) — preflop selection ve postflop discipline geliştir")

    return "\n".join(parts) if len(parts) > 1 else "Belirgin bir pattern tespit edilmedi. Oynamaya devam et."


# ─── Coach Chat (Enhanced) ──────────────────────────────────────────


def coach_chat(prompt: str, selected_spot: dict | None = None, session_stats: dict | None = None) -> str:
    if is_live_strategy_request(prompt):
        return refusal_message()

    if selected_spot:
        return explain_spot(selected_spot)

    lower = prompt.lower()

    if "analiz" in lower or "review" in lower or "incel" in lower:
        if session_stats:
            return session_summary(session_stats, [])
        return "Bir el veya session seç, sonra detaylı analiz yapalım."

    if "pattern" in lower or "kalıp" in lower or "tekrar" in lower:
        return "Pattern analizi için Play Session'da en az 5 el oyna, sonra buraya gel."

    if any(k in lower for k in ("plan", "program", "çalış", "study")):
        return (
            "Bugünkü plan:\n"
            "  1. 10dk math reflex (pot odds + alpha hız)\n"
            "  2. 20dk preflop range trainer (RFI + 3bet)\n"
            "  3. 30dk Play Session (6-max, Balanced Reg botlar)\n"
            "  4. 20dk postflop trainer (flop cbet discipline)\n"
            "  5. 10dk hand review (en pahalı 3 el)\n"
            "Ana hedef: EV loss/100 karar < 20bb."
        )

    if "icm" in lower:
        return (
            "ICM'de önce stack dağılımını ve pay jump maliyetini oku. "
            "Medium stack olarak chipEV call'ları sıkılaştır; covering stack olarak baskı kur. "
            "ICM Trainer'da bubble, final table ve satellite drills var."
        )

    if any(k in lower for k in ("river", "bluff", "blocker")):
        return (
            "River kararları: MDF baseline'ı hesapla, sonra blocker analizi yap.\n"
            "  • Villain'ın bluff'larını blokluyorsan → fold eğilimli ol\n"
            "  • Villain'ın value'sunu blokluyorsan → call eğilimli ol\n"
            "  • Unblocker avantajı → bluff için ideal\n"
            "River Trainer'da detaylı pratik yapabilirsin."
        )

    if any(k in lower for k in ("leak", "zayıf", "hata", "sorun")):
        return (
            "Leak tespiti: Leak Finder'da otomatik analiz çalıştır.\n"
            "En yaygın leak'ler:\n"
            "  1. BB underdefend vs steal\n"
            "  2. River overbluff\n"
            "  3. ICM call-off too loose\n"
            "  4. Turn overbarrel on paired boards\n"
            "Her leak için Combat Trainer'da repair pack var."
        )

    if any(k in lower for k in ("güçlü", "iyi", "strong")):
        return (
            "Güçlü yönlerini görmek için:\n"
            "  1. Play Session'da 20+ el oyna\n"
            "  2. Reports'ta accuracy breakdown'a bak\n"
            "  3. Profil sayfanda otomatik güçlü yön tespiti görünecek"
        )

    return (
        "Offline koç modundayım. Şunları sorabilisin:\n"
        "  • 'Analiz' → session veya el review\n"
        "  • 'Plan' → günlük çalışma programı\n"
        "  • 'ICM' → turnuva stratejisi\n"
        "  • 'River' → bluff-catch ve blocker analizi\n"
        "  • 'Leak' → zayıf yön tespiti\n"
        "  • Bir spot seç → GTO baseline + matematik + exploit önerisi"
    )
