from __future__ import annotations

from app.ai.safety_filters import is_live_strategy_request, refusal_message
from app.poker.alpha_mdf import alpha, mdf
from app.poker.blockers import blocker_note
from app.poker.pot_odds import required_equity
from app.solver.mock_solver import compare_action, solve_spot


def explain_spot(spot: dict, hero_action: str | None = None) -> str:
    if hero_action:
        result = compare_action(spot, hero_action)
    else:
        solver = solve_spot(spot)
        result = {
            "hero_action": "not selected",
            "best_action": solver.best_action,
            "ev_loss": 0.0,
            "best_frequency": solver.actions[0].frequency if solver.actions else 0.0,
            "solver": {
                "source_confidence": solver.source_confidence,
                "range_advantage": solver.range_advantage,
                "nut_advantage": solver.nut_advantage,
            },
        }

    pot = float(spot.get("pot_bb", 10.0))
    risk = max(1.0, pot * 0.66)
    req_eq = required_equity(risk, pot)
    a = alpha(risk, pot)
    defense = mdf(risk, pot)
    source = result["solver"]["source_confidence"]
    return (
        "1. Spot özeti: "
        f"{spot.get('position', 'Hero')} {spot.get('stack_bb', '?')}bb, "
        f"{spot.get('pot_type', 'SRP')} {spot.get('street', 'flop')} node, board {spot.get('board') or 'preflop'}.\n\n"
        f"2. Hero aksiyonu: {result['hero_action']}.\n"
        f"3. Solver baseline: {result['best_action']} ({result.get('best_frequency', 0):.0%} ana frekans). "
        f"Kaynak güveni: {source}.\n"
        f"4. Matematik: pot odds ~{req_eq:.0%}, alpha {a:.0%}, MDF {defense:.0%}, "
        f"EV loss {result['ev_loss']:.2f}bb. {blocker_note(spot.get('hero_cards', ''), spot.get('board', ''))}\n"
        f"5. Strateji: {result['solver']['range_advantage']}; {result['solver']['nut_advantage']}. "
        "Board texture ve pozisyon avantajı sizing seçimini belirliyor.\n"
        "6. Hata tipi: action/frequency sapması ve gerektiğinde sizing sapması.\n"
        "7. Exploit alternatif: rakip overfold ise küçük yüksek frekans baskı; station ise value ağırlıklı plan.\n"
        "8. Tekrar drill: benzer 5 spot çöz, sonra aynı eli feedback kapalı tekrar dene.\n"
        "9. Akılda kalacak ders: solver çıktısını ezberleme, range avantajı + risk/reward + blocker üçlüsünü birlikte oku."
    )


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


# ─── Playbook highlights (offline) ──────────────────────────────────


def _playbook_highlights(lower: str) -> str:
    """Strateji sorularına Playbook'tan özet ver (Strategy Playbook ekranıyla
    aynı kaynak). MTT mi cash mi sorulduğunu kelimeden anla."""
    from app.poker.playbook import CASH_PLAYBOOK, MTT_PLAYBOOK

    is_mtt = any(k in lower for k in ("turnuva", "mtt", "icm", "bubble", "final table"))
    book = MTT_PLAYBOOK if is_mtt else CASH_PLAYBOOK
    head = "♣ MTT" if is_mtt else "♠ CASH GAME"
    parts = [f"{head} — uzun-vade strateji çerçeveleri (Strategy Playbook'tan):", ""]
    for sec in book:
        parts.append(f"▸ {sec['title']}")
        parts.append(f"   {sec['frame']}")
        rule, why = sec["rules"][0]
        parts.append(f"   • {rule}")
    parts.append("")
    parts.append("Detay + 'neden'ler + pratik bağlantıları için: Strategy Playbook ekranı.")
    return "\n".join(parts)


# ─── Bankroll / üstel büyüme koçu (offline) ─────────────────────────


def _bankroll_coach(stats: dict | None) -> str:
    """Gerçek winrate'ten bankroll + iflas riski + Kelly çerçevesi tavsiyesi.

    Üstel büyümenin iki şartını somutlar: (1) edge var mı, (2) iflas etmeden
    hayatta kalmak. Std bilinmiyor → cash 6-max tipik (90 bb/100) varsayılır."""
    from app.poker.growth_lab import bankroll_for_ror

    wr = float((stats or {}).get("bb_per_100", 0) or 0)
    std = 90.0   # cash 6-max tipik; MTT için ~150 (varsayım, not düşülür)
    parts = ["📊 Bankroll & Üstel Büyüme"]

    if not stats or not stats.get("total_hands"):
        return ("Bankroll analizi için önce birkaç yüz el oyna (winrate'in "
                "oturması lazım). Sonra Growth & Edge Lab'da kendi winrate + "
                "varyansınla iflas riskini (RoR) ve güvenli roll'u görürsün. "
                "İlke: üstel büyüme = pozitif edge × iflas etmeden hayatta kalmak.")

    if wr <= 0:
        parts.append(
            f"🔴 Winrate'in {wr:+.1f} bb/100 — şu örneklemde EDGE YOK. Bu en "
            "kritik nokta: edge negatifken bankroll ne olursa olsun compounding "
            "seni AŞAĞI götürür. Önce yeneceğin masa/format bul (game selection) "
            "ve sızıntıları kapat (Leak Finder). Bankroll iflası önleyemez — "
            "önce edge.")
    else:
        safe_bb = bankroll_for_ror(wr, std, 0.05)
        safe_bi = safe_bb / 100.0
        parts.append(
            f"🟢 Winrate {wr:+.1f} bb/100 (pozitif edge). ~{std:.0f} bb/100 cash "
            f"varyansı varsayımıyla, %5 iflas riski için ≈ {safe_bi:.0f} buy-in "
            "bankroll gerekir.")
        parts.append(
            "• Bunun üstündeki roll = güvenli bölge → stake yükseltmeyi düşün.")
        parts.append(
            "• Altındaysan stake düşür ya da roll büyüt: edge gerçek olsa bile "
            "bir downswing seni silebilir (ergodicity — tek yörüngede iflas = oyun biter).")
    parts.append(
        "• Sizing kuralı: Kelly/fraction. Full Kelly büyümeyi maksimize eder ama "
        "varyansı yüksek; pratikte HALF-KELLY (büyümenin ~%75'i, varyansın yarısı).")
    parts.append("Detaylı hesap: Growth & Edge Lab (winrate/varyans/roll → RoR).")
    return "\n".join(parts)


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

    if any(k in lower for k in ("bankroll", "kasa", "roll", "iflas", "ruin",
                                "kelly", "varyans", "variance", "stake",
                                "üstel", "compound", "büyüme", "edge")):
        return _bankroll_coach(session_stats)

    if any(k in lower for k in ("strateji", "strategy", "playbook", "uzun vade",
                                "uzun dönem", "cash game", "nakit", "turnuva", "mtt")):
        return _playbook_highlights(lower)

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
        "  • 'Strateji' → uzun-vade cash/MTT playbook özeti\n"
        "  • 'Bankroll' → iflas riski + Kelly + güvenli roll\n"
        "  • 'Analiz' → session veya el review\n"
        "  • 'Plan' → günlük çalışma programı\n"
        "  • 'ICM' → turnuva stratejisi\n"
        "  • 'River' → bluff-catch ve blocker analizi\n"
        "  • 'Leak' → zayıf yön tespiti\n"
        "  • Bir spot seç → GTO baseline + matematik + exploit önerisi"
    )
