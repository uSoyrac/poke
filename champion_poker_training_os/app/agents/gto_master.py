"""GTOMasterAgent — pro-coach-level spot analysis.

Where CoachAgent gives a quick correct/wrong + math, GTOMasterAgent walks
through the spot the way a tournament coach (think Galfond / Saulsberry)
would: range advantage, nut advantage, blocker effects, board texture,
position dynamics, recommended sizing + frequency, common leak warnings,
and a personalized drill prescription.

Returns a structured dict so the UI can render each section as its own
card / accordion, AND a flat markdown string for chat-style display.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.agents.base import Agent, AgentResult
from app.poker.alpha_mdf import alpha, mdf
from app.poker.blockers import blocker_note
from app.poker.pot_odds import required_equity
from app.solver.mock_solver import compare_action, solve_spot
from app.solver.preflop_charts import (
    chart_for_spot,
    hand_169_from_cards,
    strategy_for_hand,
)


# ── range-advantage heuristics ────────────────────────────────────────────

def _range_advantage_note(spot: dict) -> str:
    pos    = (spot.get("position") or "").upper()
    pot_t  = (spot.get("pot_type") or "").upper()
    street = (spot.get("street") or "preflop").lower()
    name   = (spot.get("name", "") + " " + spot.get("action_history", "")).upper()

    if pot_t == "SRP" and pos == "BB":
        return (
            "BB SRP defansında range çok geniş, suited connectors ve marginal aces "
            "ağırlıkta. IP villain'in nut advantage'ı (overpair'ler, kingler) daha "
            "yüksek → cbet için karşılık verirken sadece güçlü made hand + güçlü "
            "draws ile devam et."
        )
    if pot_t == "3BP" and pos in ("BTN", "CO"):
        return (
            "3BP IP olarak range avantajı sende: opener daha geniş yapı, sen daha sık "
            "TT+/AQs+ tutuyorsun. Flop'ta value heavy sizing yap, geniş cbet bağlama."
        )
    if pot_t == "SRP" and pos in ("UTG", "LJ"):
        return (
            "Erken pozisyon SRP'de range avantajı senin (tight opener), nut advantage "
            "da senin (overpair density). Dry boardlarda %33 yüksek frekans cbet uygun."
        )
    if "BUBBLE" in name or "ICM" in name:
        return (
            "Bubble dinamiği: chipEV'in üstüne risk premium ekle. Short stack jam "
            "range'i çok daralır, büyük stack'ler short'lara baskı için range'i açar; "
            "orta stack ICM-shy oynar."
        )
    if street in ("turn", "river") and "PAIRED" in spot.get("board_texture", "").upper():
        return (
            "Paired board: range advantage konseptini board texture ezer. Boatlar ve "
            "trip'ler dağıldığında polarize sizing kullan, geniş cbet yapma."
        )
    return (
        "Range advantage çift yönlü değerlendirilir: hero'nun range'i bu pozisyonda "
        "hangi handlere yakın? Villain'in range'i ne kadar geniş açıldı? Bu iki "
        "soruyu cevapla, sizing kararı buradan akıyor."
    )


def _nut_advantage_note(spot: dict) -> str:
    board = spot.get("board", "")
    street = (spot.get("street") or "preflop").lower()
    pos = (spot.get("position") or "").upper()
    pot_t = (spot.get("pot_type") or "").upper()

    if not board or street == "preflop":
        return "Preflop'ta nut advantage = pocket pair + büyük broadway yoğunluğu."
    texture = spot.get("board_texture", "").lower()
    if "monotone" in texture:
        return "Monotone board → flush nut advantage hangi range'de daha çok suited combo varsa orada."
    if "paired" in texture:
        return "Paired board → trip advantage opener'ın range'inde daha yüksek; defender daha az."
    if "connected" in texture or "straight" in texture:
        return "Connected board → straight ve 2-pair combo'ları her iki range'de de var, polarize sizing iyi."
    if pos == "BTN" and pot_t == "SRP":
        return "BTN SRP cbet'i: A-high dry boardlarda nut advantage senin (Ax combos), kingler dağıldığında dikkat."
    return "Nut advantage = top-equity combo sayısı. Bunlarla over-betting yapmak EV'i maksimize eder."


def _blocker_analysis(spot: dict) -> str:
    return blocker_note(spot.get("hero_cards", ""), spot.get("board", ""))


def _board_texture_note(spot: dict) -> str:
    street = (spot.get("street") or "preflop").lower()
    if street == "preflop":
        return "—  (preflop spot, board texture daha sonra önemli)"
    tex = spot.get("board_texture", "").lower()
    if "dry" in tex or "a-high" in tex:
        return "Kuru board → small cbet (33%) yüksek frekans, value-bluff dengesi koru."
    if "wet" in tex or "connected" in tex or "monotone" in tex:
        return "Wet/connected board → check daha sık, bet ettiğinde polarize sizing."
    if "paired" in tex:
        return "Paired board → cbet frekansını DÜŞÜR, range advantage burda az iş yapar."
    if "two-tone" in tex:
        return "Two-tone board → flush draw considerations; range cbet OK ama overbet sınırlı."
    return f"Board texture: {tex or 'genel/dinamik'} — sizing seçimi texture'a göre."


def _position_dynamics_note(spot: dict) -> str:
    pos = (spot.get("position") or "").upper()
    pot_t = (spot.get("pot_type") or "").upper()
    if pos == "BTN":
        return "BTN: postflop pozisyon avantajı maksimum, range en geniş, bluff frequency yüksek."
    if pos == "CO":
        return "CO: BTN'e karşı dezavantaj ama herkese karşı IP. Steal range geniş, 3-bet defansı genişle."
    if pos == "BB":
        return "BB: closing action var, pot odds büyük, ama postflop OOP — defansta selective ol."
    if pos == "SB":
        return "SB: en kötü pozisyon, raise-or-fold ağırlıklı, complete (limp) çoğu durumda kötü."
    if pos in ("UTG", "LJ"):
        return "Erken pozisyon: tight range, premium odaklı, multi-way pot riskini yönet."
    return f"{pos}: position-relative range mantığını uygula."


def _recommended_action(spot: dict) -> tuple[str, float, dict]:
    """Return (best_action, frequency, full_action_strategy)."""
    result = solve_spot(spot)
    strat = {a.action: a.frequency for a in result.actions}
    if not strat:
        return ("fold", 1.0, {"fold": 1.0})
    best, freq = max(strat.items(), key=lambda kv: kv[1])
    return (best, freq, strat)


def _common_leak_warning(spot: dict) -> str:
    pos = (spot.get("position") or "").upper()
    pot_t = (spot.get("pot_type") or "").upper()
    street = (spot.get("street") or "preflop").lower()

    if pos == "BB" and pot_t == "SRP" and street == "preflop":
        return (
            "Yaygın hata: BB defansında pot odds'a aldanarak weak hands ile call. "
            "Pot 2.5bb için 1bb call → 28% equity gerek; bunu sağlamayan suited "
            "junk'ı fold et."
        )
    if pos == "SB" and street == "preflop":
        return (
            "Yaygın hata: SB'den çok geniş complete (limp). SB'de raise-or-fold "
            "yaklaşımı uzun vadede daha kazançlı (limp'i sadece dengeleyici olarak kullan)."
        )
    if pot_t == "3BP" and street == "flop":
        return (
            "Yaygın hata: 3BP flop'ta küçük cbet yerine pot bet kullanmak. SPR düşük, "
            "33-50% sizing yeterli baskıyı sağlar."
        )
    if street == "river":
        return (
            "Yaygın river hatası: marginal value handler ile thin value bet (raised). "
            "Bet'ini gerçekten daha kötü el ödemeli; aksi halde check-call daha iyi."
        )
    return "Hatasız oyunun temeli: sizing + frequency disiplini. Boyutu duruma uydur."


def _drill_prescription(spot: dict) -> str:
    pos = (spot.get("position") or "?")
    pot_t = (spot.get("pot_type") or "SRP")
    street = (spot.get("street") or "preflop")
    return (
        f"Bu hatayı kapatmak için → {pos} {pot_t} {street} drill paketi aç. "
        "5-10 benzer spot çöz, sonra aynı eli feedback kapalı tekrar dene."
    )


# ── master analysis assembly ──────────────────────────────────────────────

@dataclass
class MasterAnalysis:
    spot_id:        str
    headline:       str
    range_adv:      str
    nut_adv:        str
    blocker:        str
    texture:        str
    position:       str
    recommended:    str
    leak_warning:   str
    drill:          str
    math:           dict[str, Any] = field(default_factory=dict)
    strategy:       dict[str, float] = field(default_factory=dict)

    def to_markdown(self) -> str:
        return (
            f"## {self.headline}\n\n"
            f"**1) Recommended:** {self.recommended}\n\n"
            f"**2) Range advantage:** {self.range_adv}\n\n"
            f"**3) Nut advantage:** {self.nut_adv}\n\n"
            f"**4) Blockers:** {self.blocker}\n\n"
            f"**5) Board texture:** {self.texture}\n\n"
            f"**6) Position dynamics:** {self.position}\n\n"
            f"**7) Common leak:** {self.leak_warning}\n\n"
            f"**8) Drill prescription:** {self.drill}\n\n"
            f"**Math:** req-equity {self.math.get('required_equity', 0)*100:.0f}% · "
            f"MDF {self.math.get('mdf', 0)*100:.0f}% · "
            f"α {self.math.get('alpha', 0)*100:.0f}%"
        )


class GTOMasterAgent(Agent):
    """Tournament-coach-grade analysis of a spot.

    Use:
        master = GTOMasterAgent()
        report = master.run(spot=spot, hero_action="fold")
        print(report.data["analysis"].to_markdown())
    """
    name = "GTOMasterAgent"

    def run(self, *, spot: dict, hero_action: str | None = None, **kwargs) -> AgentResult:
        if not spot:
            return AgentResult(agent=self.name, success=False, summary="No spot.")

        best, best_freq, strategy = _recommended_action(spot)
        pot   = float(spot.get("pot_bb", 10.0))
        risk  = max(1.0, pot * 0.66)
        math  = {
            "pot_bb":          pot,
            "required_equity": round(required_equity(risk, pot), 3),
            "alpha":           round(alpha(risk, pot), 3),
            "mdf":              round(mdf(risk, pot), 3),
        }

        # Hand-specific strategy if we have hero cards
        hand_169 = hand_169_from_cards(spot.get("hero_cards", ""))
        hand_strat = {}
        if hand_169 and (spot.get("street") or "preflop").lower() == "preflop":
            chart = chart_for_spot(spot)
            if chart:
                hand_strat = strategy_for_hand(chart, hand_169)

        # Hero comparison
        verdict_line = f"GTO best: **{best}** ({best_freq*100:.0f}%)"
        if hero_action:
            cmp_ = compare_action(spot, hero_action)
            if cmp_["is_correct"]:
                verdict_line += f"  ·  Senin **{hero_action}** seçimin ✅ doğru."
            else:
                verdict_line += (
                    f"  ·  Senin **{hero_action}** seçimin ❌ — EV kayıp "
                    f"{cmp_['ev_loss']:.2f}bb."
                )

        headline = (
            f"{spot.get('name', spot.get('id', '?'))}  ·  "
            f"{spot.get('position', '?')} {spot.get('stack_bb', '?')}bb  ·  "
            f"{spot.get('street', '?').title()}"
        )

        analysis = MasterAnalysis(
            spot_id      = spot.get("id", "?"),
            headline     = headline,
            range_adv    = _range_advantage_note(spot),
            nut_adv      = _nut_advantage_note(spot),
            blocker      = _blocker_analysis(spot),
            texture      = _board_texture_note(spot),
            position     = _position_dynamics_note(spot),
            recommended  = verdict_line,
            leak_warning = _common_leak_warning(spot),
            drill        = _drill_prescription(spot),
            math         = math,
            strategy     = dict(hand_strat or {k: v for k, v in strategy.items() if v > 0.01}),
        )

        return AgentResult(
            agent   = self.name,
            success = True,
            summary = headline + "  →  " + verdict_line,
            data    = {
                "analysis":  analysis,
                "markdown":  analysis.to_markdown(),
                "math":      math,
                "strategy":  analysis.strategy,
            },
            actions = list(analysis.strategy.keys()),
        )
