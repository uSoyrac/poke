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
    """Master-level Türkçe poker coach chatbot.

    Sorular bir veya birden fazla kategoriye düşer; her kategori için
    profesyonel poker eğitmeni ses tonuyla, neden+nasıl+örnek üçlüsünde
    yanıt veririz. Belirli bir spot seçildiyse hem genel cevap hem
    spot-spesifik analiz birleşir.
    """
    if is_live_strategy_request(prompt):
        return refusal_message()

    lower = prompt.lower().strip()
    if not lower:
        return _coach_help_menu()

    # Spot-spesifik soru — spot seçildiyse ve sorulan şey "neden" benzeri
    spot_context_words = ("neden", "niye", "niçin", "açıkla", "anlat", "why", "explain", "ne yapma", "yapmalı")
    if selected_spot and any(w in lower for w in spot_context_words):
        return explain_spot(selected_spot) + "\n\n" + _coach_meta_reasoning_note()

    # Question type detection — kategori önceliği önemli
    categories = _classify_question(lower)

    pieces: list[str] = []
    for cat in categories[:3]:   # max 3 kategori karışımı (boğmasın)
        block = _category_response(cat, lower, selected_spot, session_stats)
        if block:
            pieces.append(block)

    if not pieces:
        # Hiç kategori eşleşmedi — usta koç stilinde generic rehber
        pieces.append(_generic_master_response(lower, selected_spot))

    # Footer — bir sonraki adım önerisi
    pieces.append(_next_step_suggestion(categories, selected_spot))
    return "\n\n".join(pieces)


# ─── Question classification ──────────────────────────────────────────

_KEYWORDS: dict[str, tuple[str, ...]] = {
    "preflop":   ("preflop", "açış", "open", "rfi", "raise first",
                  "elimde", "hangi el", "açmal", "hangisini oyna"),
    "3bet":      ("3-bet", "3bet", "3 bet", "üç bet", "reraise", "yeniden raise"),
    "4bet":      ("4-bet", "4bet", "4 bet", "dört bet"),
    "squeeze":   ("squeeze", "sqz", "sıkıştır"),
    "blockers":  ("blocker", "blok", "kombinasyon"),
    "equity":    ("equity", "ekvati", "pot odds", "pot oddu", "matemat", "ne kadar"),
    "mdf":       ("mdf", "minimum defense", "defend", "savun"),
    "icm":       ("icm", "bubble", "balon", "final table", "pay jump",
                  "satellite", "$ev", "dolar"),
    "stack":     ("kısa stack", "short stack", "deep stack", "derin stack",
                  "stack depth", "spr", "stack to pot"),
    "position":  ("pozisyon", "position", "btn", "co", "hj", "lj", "utg",
                  "bb", "sb", "in position", "ip", "oop"),
    "bluff":     ("bluff", "bluf", "blöf", "semi bluf"),
    "value":     ("value", "değer", "thin value", "value bet"),
    "cbet":      ("cbet", "c-bet", "c bet", "continuation"),
    "river":     ("river", "5. street", "son kart"),
    "turn":      ("turn", "4. street", "double barrel"),
    "ranges":    ("range", "menzil", "aralık"),
    "thinking":  ("düşünme", "düşünüş", "süreç", "düşün", "thinking",
                  "process", "akıl", "metod"),
    "leak":      ("leak", "zayıf", "hata", "sorun", "düzelt", "fix"),
    "plan":      ("plan", "program", "çalış", "study", "ne yapayım", "ödev"),
    "mindset":   ("tilt", "psikoloji", "konsantras", "stres", "moral", "öfke",
                  "mental", "duygu"),
    "bankroll":  ("bankroll", "para yönet", "bb/100", "winrate", "kasa"),
    "analysis":  ("analiz", "review", "incel", "değerlendir"),
}


def _classify_question(text: str) -> list[str]:
    """Return matching categories, ordered by keyword count."""
    scores: dict[str, int] = {}
    for cat, kws in _KEYWORDS.items():
        for kw in kws:
            if kw in text:
                scores[cat] = scores.get(cat, 0) + 1
    return sorted(scores.keys(), key=lambda k: -scores[k])


# ─── Category-specific responses ──────────────────────────────────────

def _category_response(cat: str, prompt: str, spot: dict | None,
                        stats: dict | None) -> str:
    """Return a master-coach style block for the given category."""
    handlers = {
        "preflop":   _preflop_response,
        "3bet":      _threebet_response,
        "4bet":      _fourbet_response,
        "squeeze":   _squeeze_response,
        "blockers":  _blockers_response,
        "equity":    _equity_response,
        "mdf":       _mdf_response,
        "icm":       _icm_response,
        "stack":     _stack_depth_response,
        "position":  _position_response,
        "bluff":     _bluff_response,
        "value":     _value_response,
        "cbet":      _cbet_response,
        "river":     _river_response,
        "turn":      _turn_response,
        "ranges":    _range_construction_response,
        "thinking":  _thinking_process_response,
        "leak":      _leak_response,
        "plan":      _plan_response,
        "mindset":   _mindset_response,
        "bankroll":  _bankroll_response,
        "analysis":  lambda p, s, st: (
            session_summary(st, []) if st else
            "Bir session veya el seç, sonra detaylı analiz yapalım. "
            "Tournament Play sonrası 📁 Past'a tıkla, herhangi bir ele çift tık → "
            "🎬 Frame-by-frame replay."
        ),
    }
    h = handlers.get(cat)
    return h(prompt, spot, stats) if h else ""


def _preflop_response(prompt: str, spot: dict | None, stats: dict | None) -> str:
    return (
        "🎯  PREFLOP MANTIĞI\n"
        "Preflop'ta üç anahtar soru sorarsın: (1) Pozisyon avantajım var mı? "
        "(2) Elimle kim dominate ediyor — yukarıda kim var, aşağıda kim? "
        "(3) Bu sıralamada arkamda kimler kaldı — squeeze riski var mı?\n\n"
        "Erken pozisyondan (UTG/LJ) sadece premium + playable suited connectors aç. "
        "Late position (CO/BTN) blind'lara karşı geniş steal range çalış. "
        "SB'den kompleks: open'larsan 3-bet riskine yüksek SPR'de OOP kalırsın — "
        "limp/open karışımı (mixed strategy) GTO yaklaşımı, ama exploitative oyunda "
        "blind'lar tight ise 2.5-3x open daha verimli.\n\n"
        "BB defense'ta pot odds + closing action avantajını kullan. Standard 2.3bb açışa "
        "karşı %16 equity yetiyor — yani neredeyse her playable suited el call."
    )


def _threebet_response(prompt: str, spot: dict | None, stats: dict | None) -> str:
    return (
        "♣  3-BET STRATEJİSİ\n"
        "3-bet iki ayrı işlem yapar: (1) value range'i protect eder, (2) bluff'la "
        "polarize seni denge konumuna sokar. Linear 3-bet (merge) zayıf rakibe karşı "
        "exploitative; polarized 3-bet (premium + blocker bluff) tight rakibe karşı "
        "GTO yaklaşımı.\n\n"
        "Polarized recipe (40bb, IP vs LP open):\n"
        "  • Value: AA-QQ, AKs/o, AQs\n"
        "  • Bluff: A5s-A2s (A blocker), KQs/KJs (top of fold range), 76s-65s "
        "(playable post-call)\n"
        "  • Sizing: BTN vs CO → 3.0-3.3x; BB vs BTN → 3.8-4x (OOP bigger)\n\n"
        "3-bet'lere karşı defend ederken pos+stack matters:\n"
        "  • IP, deep → cold-call genişler (set-mining + suited connectors)\n"
        "  • OOP, kısa → 4-bet/fold polarize"
    )


def _fourbet_response(prompt: str, spot: dict | None, stats: dict | None) -> str:
    return (
        "♠  4-BET MANTIĞI\n"
        "4-bet kararı 3 girdiye bağlıdır: SPR (stack-to-pot ratio), villain'ın 3-bet "
        "frequency'si, ve elindeki blocker'lar.\n\n"
        "40bb'de tipik 4-bet sizing villain'ın 3-bet'ine ~2.2x. Bu boyutta SPR "
        "post-call ~3 — yani flop'ta zaten commit ediyorsun. Bu yüzden 4-bet'ler "
        "polarize olmalı:\n"
        "  • Value: QQ+, AKs/o (KK-AA'ya karşı blocker var)\n"
        "  • Bluff: A5s-A2s (best blocker: villain'ın AA/AK combos azalır)\n\n"
        "Linear 4-bet (JJ, AQs) genelde -EV — 5-bet jam'e karşı çok zayıf, fold'a "
        "force etmek için çok value-heavy. JJ/AQs cold-call > 4-bet."
    )


def _squeeze_response(prompt: str, spot: dict | None, stats: dict | None) -> str:
    return (
        "🦅  SQUEEZE STRATEJİSİ\n"
        "Squeeze = open + caller varken yapılan 3-bet. Pot'ta zaten 2 oyuncu olduğu "
        "için bluff equity'si yüksek: hem opener'ı hem caller'ı fold'a zorlamak "
        "için sıkı dead money mevcut.\n\n"
        "Sizing: pot başına ~3-3.5x toplam (yani open 2.5bb + call 2.5bb = 5bb pot'a "
        "karşı 14-17bb). Daha büyük çünkü iki rakibi de fold'a force etmek lazım.\n\n"
        "Squeeze range polarized:\n"
        "  • Value: AA-JJ, AKs, AKo, AQs\n"
        "  • Bluff: A5s-A4s, suited connectors 76s-54s (post-call playable)\n"
        "BB pozisyonundan squeeze en güçlü çünkü closing action + position avantajı "
        "var. CO'dan squeeze daha dar — BTN arkanda kalıyor."
    )


def _blockers_response(prompt: str, spot: dict | None, stats: dict | None) -> str:
    return (
        "🧱  BLOCKER ANALİZİ\n"
        "Blocker = elindeki kartın villain'ın hangi range combos'unu engellediği. "
        "İki şekilde kullanılır:\n\n"
        "1. BLUFF için (call'ı azalt): Villain'ın value combos'unu blokluyorsan, "
        "onun call range'i daralır → bluff başarı şansı artar. Örnek: A♠ blocker "
        "river bluff — villain'ın AA/AK combos'unu azaltır.\n\n"
        "2. CALL için (yakın spotta tie-breaker): Villain'ın bluff'larını "
        "blokluyorsan call'ı zayıflat (villain az bluff yapacak). Villain'ın "
        "value'sunu blokluyorsan call'ı güçlendir.\n\n"
        "Master kural: Bluff için ideal el villain'ın value'sunu BLOKLAR ama "
        "bluff'larını UNBLOK eder. Örnek: K♥ board'unda hero K♣J♣ kötü bluff "
        "(K blocker villain'ın kötü kicker K'larını fold'a zorlar — ama biz "
        "showdown'da kaybediyoruz)."
    )


def _equity_response(prompt: str, spot: dict | None, stats: dict | None) -> str:
    return (
        "📐  POT ODDS & EQUITY\n"
        "Pot odds = ödenecek miktar / (ödenen sonrası toplam pot). Bu sayı sana "
        "minimum gereken equity'yi verir.\n\n"
        "Hızlı formüller:\n"
        "  • Half-pot bet vs sen → %25 equity yeterli\n"
        "  • Pot-sized bet vs sen → %33 equity\n"
        "  • 2x pot overbet → %40 equity\n\n"
        "Ama bu MİNİMUM — implied odds (gelecekteki kazanç potansiyeli) ve reverse "
        "implied odds (dominated olduğunda kaybetme riski) de hesaba kat.\n\n"
        "Math Lab ekranında pot odds + alpha + MDF reflex drill var. Hedef: kararı "
        "5 saniyede ver. Yavaşsan tilt riski artar — automatic olması lazım."
    )


def _mdf_response(prompt: str, spot: dict | None, stats: dict | None) -> str:
    return (
        "🛡  MDF — Minimum Defense Frequency\n"
        "MDF = 1 − (bet / (bet + pot)). Bu, villain'ın bluff'larını -EV yapmak için "
        "savunman gereken minimum frekans.\n\n"
        "Half-pot bet'e MDF %67, pot-bet'e %50, 2x overbet'e %33. Yani villain "
        "pot-bet attığında range'inin %50'sini fold edersen onun bluff'ları "
        "otomatik karlı olur.\n\n"
        "ÖNEMLİ: MDF baseline'dır, command değil. Real-game uyarlama:\n"
        "  • Villain bluff-heavy → MDF'in üstüne çık (call genişlet)\n"
        "  • Villain nit (value only) → MDF'in altına in (fold genişlet)\n"
        "  • Blocker analizi her zaman MDF'i override edebilir"
    )


def _icm_response(prompt: str, spot: dict | None, stats: dict | None) -> str:
    return (
        "💰  ICM — Independent Chip Model\n"
        "ICM'de chip'in $ değeri DEĞİL, prize pool'daki payın değerli. Yani "
        "kazanılan chip'in marginal $ değeri kaybedilen chip'in $ değerinden DÜŞÜK. "
        "Sonuç: risk premium ekleyerek chipEV kararlarını sıkılaştırırsın.\n\n"
        "Üç ICM zone:\n"
        "  • EARLY/MIDDLE → chipEV ≈ $EV, normal oyun\n"
        "  • BUBBLE → risk premium %5-15, kısa stack üzerinde maksimum baskı\n"
        "  • FINAL TABLE → her pay jump için ayrı kalkülasyon, tight call-off\n\n"
        "Medium stack olarak: chipEV call'ları %20-30 sıkılaştır, covering "
        "stack olarak: baskı kur (open daha geniş, 3-bet daha sık).\n\n"
        "ICM Trainer'da bubble/FT/satellite drill'leri var — risk premium "
        "intuition geliştirir."
    )


def _stack_depth_response(prompt: str, spot: dict | None, stats: dict | None) -> str:
    return (
        "📏  STACK DEPTH STRATEJİSİ\n"
        "Stack depth her şeyi değiştirir — aynı el, farklı stack'te farklı oynanır.\n\n"
        "  • 100bb+ (deep): implied odds, suited connectors, set-mining devrede. "
        "Set under set, flush over flush gibi reverse implied risk yüksek\n"
        "  • 40bb: standard SPR — 3-bet pot'larda SPR ~5, c-bet/jam discipline\n"
        "  • 25bb: 3-bet pot'larda flop SPR ~2 — premium 3-bet, çok dar 4-bet "
        "(jam) range\n"
        "  • 15bb: shove/fold dynamics — open-shove range açılır, call vs jam "
        "ranges kritik\n"
        "  • 10bb veya altı: pure shove/fold, position-stack mathematics\n\n"
        "SPR = stack / pot. SPR < 3 → commit; SPR > 5 → manevra alanı var."
    )


def _position_response(prompt: str, spot: dict | None, stats: dict | None) -> str:
    return (
        "📍  POZİSYON STRATEJİSİ\n"
        "Pozisyon poker'in #1 değişkeni. IP (in position) avantajı:\n"
        "  • Daha fazla bilgi (villain önce act eder)\n"
        "  • Pot kontrol esnekliği (check arkası serbest)\n"
        "  • Bluff başarı artar (villain check'i zayıflık göstergesi)\n\n"
        "Pozisyon başına yaklaşım:\n"
        "  • UTG/LJ: sıkı, premium-heavy. %12-18 open range\n"
        "  • HJ: standart RFI — playable suited broadways eklenir. %18-22\n"
        "  • CO: open genişler — bottom suited connectors, suited Ax. %22-28\n"
        "  • BTN: en geniş — close action + position avantajı. %35-45\n"
        "  • SB: en zor pozisyon — OOP kalırsın. Open daha sıkı YA da limp mix\n"
        "  • BB: defend pot odds + closing action ile. RFI sadece SB vs BB"
    )


def _bluff_response(prompt: str, spot: dict | None, stats: dict | None) -> str:
    return (
        "♠♥  BLUFF FELSEFESİ\n"
        "Karlı bluff için 3 koşul: (1) Villain'ın fold edebileceği range var, "
        "(2) Sizing inandırıcı, (3) Senin range'in bu spot'ta yeterli value combos "
        "içeriyor.\n\n"
        "Bluff frequency = bet size'a göre ayarlanır:\n"
        "  • Half-pot bet → optimal 1 bluff : 2 value (yani 33% bluff)\n"
        "  • Pot bet → 1:2 yine (33% bluff) — bet size value-bluff oranını sabit tutmaz\n"
        "  • 2x overbet → 1:3 (25% bluff) — bigger size = daha az bluff\n\n"
        "Bluff candidate seçimi: backdoor equity + blocker. Open bluffs (no equity, "
        "no blocker) sadece river'da, çok seçici. River bluff'larda villain'ın value "
        "blocker'ı şart."
    )


def _value_response(prompt: str, spot: dict | None, stats: dict | None) -> str:
    return (
        "💎  VALUE BET STRATEJİSİ\n"
        "Value bet kuralı: weaker hands call edebiliyor mu? Eğer evet, bet. "
        "Yarım sıralı eller (top pair good kicker) value-bet için ideal — daha "
        "zayıf top pair'leri ve middle pair'leri call'a çağırır.\n\n"
        "Thin value bet (en zor karar): showdown value var, ama biraz daha kazanmak "
        "istiyorsun. İki risk: (1) check-raise'e gelirsen büyük kayıp, (2) sadece "
        "daha iyi eller call ediyorsa -EV.\n\n"
        "Sizing: value-heavy range küçük sizing (33%-50% pot), value-bluff "
        "polarized range büyük sizing (75%-pot+). Sizing'i range yapısına göre "
        "seç, eline göre değil — yoksa balanced olmazsın."
    )


def _cbet_response(prompt: str, spot: dict | None, stats: dict | None) -> str:
    return (
        "🎯  C-BET STRATEJİSİ\n"
        "C-bet (continuation bet) preflop raiser'ın flop'ta yaptığı bet. Üç parametre:\n"
        "  • RANGE ADVANTAGE: senin range'in board'a daha iyi mi düşüyor? "
        "Örnek: BTN vs BB SRP'de A-high board → BTN range advantage var\n"
        "  • NUT ADVANTAGE: nutty combos (set, 2pair+) hangi range'de daha çok?\n"
        "  • BOARD TEXTURE: dry/wet, paired, monotone\n\n"
        "Kuru high-card board (A72r, K83r): %75-90 c-bet, küçük sizing (33% pot)\n"
        "Islak coordinated board (T98ss, 765tt): %40-55 c-bet, büyük sizing (66-75%)\n"
        "Paired board (KK7, 998): %30-40 c-bet, polarize ranges\n\n"
        "Donk bet (caller'ın leadi) = lokomotif sinyali. Villain genelde middling "
        "made hand'ler veya bluff'larla yapar — board texture'a göre raise vs call."
    )


def _river_response(prompt: str, spot: dict | None, stats: dict | None) -> str:
    return (
        "🏁  RIVER KARAR FELSEFESİ\n"
        "River'da hand strength sabit — sadece villain'ın range'i ve bet sizing'i "
        "okuyacaksın. 4 adım:\n\n"
        "1. RANGE: Villain bu noktaya hangi combos ile gelmiş olabilir? "
        "Preflop + flop + turn aksiyonlarını filtrele\n"
        "2. SIZING: Villain'ın sizing'i hangi range'le tutarlı? "
        "Block bet → marginal showdown / draw busted; pot bet → polarize (nuts/bluff)\n"
        "3. BLOCKER: Senin elin villain'ın value'sunu bloklar mı, bluff'larını mı? "
        "Value blocker → call; bluff blocker → fold eğilimi\n"
        "4. MDF baseline: Villain'ın yarım pot bet'ine MDF %67. Bunu start point yap, "
        "blocker analiziyle ±%20 uyarla.\n\n"
        "RIVER BLUFF: Mutlaka backdoor equity DAHA İYİ → showdown value. River'da "
        "bluff combos seç: kaybetmek üzere olan eller (busted draws), value "
        "blocker'lı (Ax suited)."
    )


def _turn_response(prompt: str, spot: dict | None, stats: dict | None) -> str:
    return (
        "🌀  TURN KARAR PUNCTUATION\n"
        "Turn poker'in en önemli decision noktası — pot zaten büyümüş, river kararı "
        "kritik olacak. Üç tür turn kart:\n\n"
        "  • SCARE CARD (overcard / flush card): caller'ın range'i daralır, "
        "double barrel +EV. Örnek: BTN raised, BB called, flop K72r, turn A → BTN'in "
        "range avantajı arttı, big bet zorlu\n"
        "  • BRICK (low offsuit): kimsenin range'ini değiştirmez. Sizing'i "
        "polarize et — büyük bet bluff'lar için, küçük bet thin value için\n"
        "  • BOARD-PAIRING TURN: capped range'in dezavantajı. Top pair üst pozisyonun, "
        "set/trips ise daha sık caller'da → c-bet frequency düşürülür\n\n"
        "Double barrel %50 frequency baseline. Tek card scare'larda %70+, "
        "brick'lerde %40, paired turn'lerde %30."
    )


def _range_construction_response(prompt: str, spot: dict | None, stats: dict | None) -> str:
    return (
        "🎨  RANGE CONSTRUCTION\n"
        "Bir solid range 3 katmanda kurulur:\n\n"
        "1. CORE VALUE: Otomatik aksiyon alacağın eller. Premium pocket pairs "
        "(QQ+), big aces (AKs/o, AQs). Bu eller her zaman frequency 100% raise/call.\n\n"
        "2. PLAYABLE BODIES: Pozisyona göre eklenenler. Suited broadways (KQs, "
        "QJs, JTs), middle pocket pairs (88-JJ), suited connectors (T9s-65s). "
        "Bunlar mixed frequency — pozisyona göre %50-100.\n\n"
        "3. BLUFF/RANDOM SEÇİM: Range'i balanced yapmak için bazı 'kötü' "
        "ellerle 'iyi' eller aynı line'da olmalı. A5s ile QJs aynı 3-bet bluff "
        "range'de — biri blocker, diğeri post-call playable.\n\n"
        "Test: range'in 169 hücre toplamı oynanan eller. Eğer %70 görülürse "
        "loose, %15 görülürse nit. Profesyonel range'ler %20-30 between."
    )


def _thinking_process_response(prompt: str, spot: dict | None, stats: dict | None) -> str:
    return (
        "🧠  USTA POKER OYUNCUSU GİBİ DÜŞÜNME\n"
        "Bir karar verirken her zaman bu sırayla:\n\n"
        "1. ELİM — kategoriye sok (premium/playable/marjinal/junk).\n"
        "2. POZİSYON — bilgi avantajım var mı? Closing action benim mi?\n"
        "3. STACK — SPR ne? Commit mi yapacağım, manevra mı?\n"
        "4. VILLAIN RANGE — preflop + flop history hangi combos eler?\n"
        "5. BOARD TEXTURE — range avantajı bende mi, villain'da mı? Nut combos kimde?\n"
        "6. BLOCKER — elim villain'ın value'sunu blokluyor mu, bluff'larını mı?\n"
        "7. POT ODDS — matematik karara izin veriyor mu?\n"
        "8. EXPLOITATIVE NOTU — villain bu spot'ta bilinen bir leak gösteriyor mu?\n\n"
        "Master oyuncular 'auto-pilot' değil — her karara bu 8 adımdan en az 3'ü "
        "girer. 'Bu el kötü' deyip fold'lamak yerine 'BB pozisyonunda close action "
        "olduğum için pot odds yetiyor' der.\n\n"
        "Mental egzersiz: bir karar verdikten sonra 5 saniye dur, 'NEDEN bunu "
        "yaptım' diye iç sesinle açıkla. Eğer 'eli kötüydü' diyorsan range "
        "analizi yapmamışsın demek."
    )


def _leak_response(prompt: str, spot: dict | None, stats: dict | None) -> str:
    try:
        from app.db.mistakes_queue import load_mistakes, grouped_by_leak
        mistakes = [m for m in load_mistakes() if not m.drilled]
        if mistakes:
            grouped = grouped_by_leak(mistakes)
            top = sorted(grouped.items(),
                         key=lambda kv: -sum(m.ev_loss for m in kv[1]) / max(1, len(kv[1])))[:3]
            top_text = "\n".join(
                f"  • {sig} — {len(items)} örnek, ortalama EV kaybı "
                f"{sum(m.ev_loss for m in items)/len(items):.2f}bb"
                for sig, items in top
            )
            personal = f"\n\nSEN İÇİN EN ACİL 3 LEAK (My Mistakes'ten):\n{top_text}"
        else:
            personal = "\n\nŞu an kayıtlı açık leak yok — devam edersen otomatik tespit ediyoruz."
    except Exception:
        personal = ""

    return (
        "🩺  LEAK TESPİTİ VE DÜZELTME\n"
        "Leak = sistematik -EV pattern. Bir spotu rastgele yanlış oynamak leak "
        "değil — aynı tip spotu DEFALARCA yanlış oynamak leak.\n\n"
        "En yaygın 5 leak (tüm seviyelerde):\n"
        "  1. BB underdefend vs steal (preflop) — ~5bb/100\n"
        "  2. River overbluff (value combos azken) — ~8bb/100\n"
        "  3. ICM call-off too loose (bubble) — ~10bb/100 turnuvada\n"
        "  4. Paired board double-barrel — ~3bb/100\n"
        "  5. Thin value missed (capped river vs value) — ~2bb/100\n\n"
        "Düzeltme protokolü:\n"
        "  1. My Mistakes'te leak signature'ı bul (örn 'BB / SRP / fold')\n"
        "  2. Drill Bunları → Spot Trainer filtreli açılır\n"
        "  3. 3 doğru üst üste yap → leak otomatik kapanır\n"
        "  4. 100 el sonra tekrar gözden geçir, regression varsa repeat"
        + personal
    )


def _plan_response(prompt: str, spot: dict | None, stats: dict | None) -> str:
    return (
        "📅  GÜNLÜK ÇALIŞMA PLANI (90 dakika)\n"
        "  ▸ 10 dk Math Lab — pot odds + MDF + alpha reflex (target: <5sn karar)\n"
        "  ▸ 15 dk Range Studio Trainer — preflop chart drill (RFI + 3-bet defend)\n"
        "  ▸ 25 dk Spot Practice — kategori karışık, focus: en yüksek EV-loss leak\n"
        "  ▸ 20 dk Tournament Play — gerçek oyun, hybrid auto-flow ile, hata yaptıkça\n"
        "         My Mistakes'e otomatik yazılır\n"
        "  ▸ 15 dk Hand Review — son turnuvanın 3 pahalı eli, frame-by-frame replay\n"
        "  ▸ 5 dk Skills Report — haftalık trend kontrolü\n\n"
        "Haftalık hedef: EV loss/100 karar < 20bb, açık leak < 5\n\n"
        "Pro tip: aynı leak tipini ardışık 3 gün çalıştır, sonra 1 hafta dinlendir "
        "(spaced repetition). Tek seferde her şeyi düzeltmeye çalışırsan unutursun."
    )


def _mindset_response(prompt: str, spot: dict | None, stats: dict | None) -> str:
    return (
        "🧘  POKER PSİKOLOJİSİ\n"
        "Tilt = duygusal durumun karar kalitesini bozması. İki tür:\n"
        "  • REVENGE tilt: kaybettiğin spot'u 'kazanmak için' loose oynamak\n"
        "  • DESPAIR tilt: kötü stretch sonrası nit oynamak, missed value\n\n"
        "Anti-tilt protokol:\n"
        "  1. Her büyük loss sonrası 30sn dur, derin nefes 3 kere\n"
        "  2. 'Variance' kelimesini içsel olarak söyle — sonuç ≠ karar kalitesi\n"
        "  3. 100bb+ kaybedersen oturumu kapat, ertesi gün döndür\n\n"
        "Pre-session ritüel:\n"
        "  • 5 dk meditation veya yürüyüş\n"
        "  • 'Bugün hedef X karar kalitesi' (ROI değil, EV decision quality)\n"
        "  • Dikkat dağıtıcı app'leri kapat\n\n"
        "Master mindset: 'Her karar bağımsız. Geçmiş eli unutuyorum. Şu anki spot'a "
        "fresh bakıyorum.' Bu fraktal odaklanma uzun vadede +EV yapar."
    )


def _bankroll_response(prompt: str, spot: dict | None, stats: dict | None) -> str:
    return (
        "💵  BANKROLL YÖNETİMİ\n"
        "Standard bankroll rules:\n"
        "  • Cash NL → 30-50 buy-in (örn $100NL için $3000-5000)\n"
        "  • MTT — variance yüksek → 100-200 buy-in\n"
        "  • SnG (single table) → 40-60 buy-in\n"
        "  • Hyper turbo → 200+ buy-in (variance extreme)\n\n"
        "Move-up rules:\n"
        "  1. Hedef stake için 30 buy-in topla\n"
        "  2. 25 buy-in'e düşersen geri in (drop-down)\n"
        "  3. Hedef level'da 5,000+ el oyna, sample size makul olsun\n\n"
        "Winrate measurement: 10,000 el minimum sample (cash), 100 turnuva minimum "
        "(MTT). Daha az veride 'good run' ile 'good player'ı karıştırırsın.\n\n"
        "Profesyonel kural: bankroll'unun %5'inden fazlasını TEK oturumda riske "
        "etme. Multi-tabling +EV ama tilt riski + dikkat dağılması."
    )


def _generic_master_response(prompt: str, spot: dict | None) -> str:
    """Eşleşmeyen sorular için usta-koç tonunda generic yön."""
    return (
        "🎓  KOÇ DÜŞÜNCE NOTU\n"
        f"Sorunu (\"{prompt[:80]}\") şu üç açıdan değerlendiriyorum:\n\n"
        "1. Bu durumun POZISYON, STACK, BOARD TEXTURE üçlüsünden hangisine en "
        "çok dayandığını net olarak söyle — context olmadan strateji evrensel "
        "değil.\n"
        "2. Bir SPOT seç (Spot Trainer'da) ve buraya gel — sana o spot için "
        "matematik + range + blocker + exploit analizi yapayım.\n"
        "3. Eğer GENEL strateji sorusuysa anahtar kelime kullan: 'preflop', "
        "'3bet', 'river bluff', 'ICM', 'blocker', 'düşünme süreci'.\n\n"
        "İyi soru sormak iyi cevap almanın yarısı — usta koçlar sana 'ne istiyorsun' "
        "diye sormaz, 'bu durum hangi kategoride?' diye sorar."
    )


def _coach_meta_reasoning_note() -> str:
    """When a spot is loaded — appended note about reasoning process."""
    return (
        "🔍  BU KARARIN ARDINDAKİ MANTIK\n"
        "GTO frekansı bir 'doğru cevap' DEĞİL — denge noktası. Sen sıkça karşıya "
        "geldiğin rakip tipine göre exploit'le, ama exploitation'ın temeli denge.\n"
        "'Eğer hep raise edersem ne olur' diye düşün → balanced range bu sapmanın "
        "korunağı."
    )


def _next_step_suggestion(categories: list[str], spot: dict | None) -> str:
    """Footer: bir sonraki adım önerisi (UX yönü)."""
    if "leak" in categories:
        return "👉 SONRAKİ: ⚡ My Mistakes ekranına git, en üstteki leak'i drill et."
    if "icm" in categories:
        return "👉 SONRAKİ: 💰 ICM/PKO Trainer ekranını aç, bubble drill yap."
    if "river" in categories or "blockers" in categories:
        return "👉 SONRAKİ: 🏁 River Decision Trainer'da blocker spotları çöz."
    if "preflop" in categories or "3bet" in categories or "4bet" in categories:
        return "👉 SONRAKİ: 🎯 Range Studio'da preflop chart drill yap."
    if "plan" in categories or "thinking" in categories:
        return "👉 SONRAKİ: 🏆 Tournament Play'de gerçek el oynayarak teoriyi pratiğe dök."
    if spot:
        return "👉 SONRAKİ: '🤖 Coach Açıkla' butonuna bas, GTO baseline ile karşılaştır."
    return "👉 SONRAKİ: Bir trainer ekranına gir, bir spot çöz, sonra 'Coach Açıkla' ile derin analiz al."


def _coach_help_menu() -> str:
    return (
        "🎓  COACH'A SORABİLECEKLERİN\n\n"
        "TEORİ:\n"
        "  • 'preflop', 'açış range', 'pozisyon stratejisi'\n"
        "  • '3-bet', '4-bet', 'squeeze'\n"
        "  • 'blocker', 'equity', 'pot odds', 'MDF'\n"
        "  • 'cbet', 'turn', 'river bluff'\n"
        "  • 'range construction', 'düşünme süreci'\n\n"
        "PRATİK:\n"
        "  • 'leak' / 'hata' → kişisel leak analizi\n"
        "  • 'plan' → günlük çalışma programı\n"
        "  • 'analiz' → session review\n\n"
        "TURNUVA:\n"
        "  • 'ICM', 'bubble', 'final table'\n"
        "  • 'kısa stack', 'short shove'\n\n"
        "META:\n"
        "  • 'mindset', 'tilt', 'psikoloji'\n"
        "  • 'bankroll'\n\n"
        "Veya bir trainer ekranından spot seç → spot-spesifik master review."
    )
