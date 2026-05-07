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


def coach_chat(prompt: str, selected_spot: dict | None = None) -> str:
    if is_live_strategy_request(prompt):
        return refusal_message()
    if selected_spot:
        return explain_spot(selected_spot)
    lower = prompt.lower()
    if "plan" in lower or "program" in lower:
        return (
            "Bugün: 10 dk math reflex, 20 dk preflop, 30 dk postflop, "
            "20 dk fast play, 20 dk hand review. Ana hedef: EV loss/100 karar < 20bb."
        )
    if "icm" in lower:
        return (
            "ICM'de önce stack dağılımını ve pay jump maliyetini oku. "
            "Medium stack olarak chipEV call'ları sıkılaştır; covering stack olarak baskı kur."
        )
    return (
        "Offline koç modundayım. Bir spot, leak veya matematik konusu seçersen "
        "GTO baseline, matematik, exploit ve drill önerisini Türkçe özetlerim."
    )

