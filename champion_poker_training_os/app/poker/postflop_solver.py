"""Canlı postflop spot → TexasSolver EXACT çözümü (on-demand, Phase D9).

Canlı reveal'deki CONCEPT postflop önerisini, kullanıcı isterse GERÇEK
solver frekanslarıyla kesinleştirir. Otomatik DEĞİL — TexasSolver bir flop'u
~10s+ çözer; bu yüzden talep üzerine (buton) çağrılır.

AGPL NOTU: TexasSolver binary repo'da DEĞİL; sadece arms-length subprocess
(`texassolver_adapter`). Binary yoksa fonksiyon None döner (graceful).

Saf-ish: range kurgusu + adapter çağrısı; Qt bağımsız.
"""
from __future__ import annotations

from typing import Optional

# Pot-tipine göre (OOP range, IP range) — TexasSolver PioSOLVER-stili string.
# SRP (tek raise), 3BP (3-bet'li pot, daha sıkı), 4BP (4-bet'li, çok sıkı).
_SRP_OOP = ("22+,A2s+,K5s+,Q7s+,J8s+,T8s+,97s+,86s+,75s+,64s+,53s+,"
            "A8o+,KTo+,QTo+,JTo")
_SRP_IP = ("22+,A2s+,K2s+,Q5s+,J7s+,T7s+,96s+,85s+,74s+,64s+,53s+,"
           "A5o+,K9o+,Q9o+,J9o+,T9o")
# 3-bet'li pot: 3-bettor (OOP varsayım) polarize+value, caller (IP) sıkı çağırış.
_3BP_OOP = ("88+,A4s-A2s,A9s+,KTs+,QTs+,JTs,AJo+,KQo")
_3BP_IP = ("99+,ATs+,KTs+,QJs,JTs,T9s,AQo+,KQo")
# 4-bet'li pot: her iki taraf çok sıkı.
_4BP_OOP = ("QQ+,AKs,AKo,A5s")
_4BP_IP = ("QQ+,AKs,AKo")

_POT_TYPE_RANGES = {
    "SRP": (_SRP_OOP, _SRP_IP),
    "3BP": (_3BP_OOP, _3BP_IP),
    "4BP": (_4BP_OOP, _4BP_IP),
    "limped": (_SRP_OOP, _SRP_IP),
}


def solver_available() -> bool:
    try:
        from app.poker.texassolver_adapter import TexasSolverEngine
        return TexasSolverEngine().available
    except Exception:
        return False


def _norm_board(board: str) -> str:
    """'Ah 7c 2d' veya 'Ah7c2d' → TexasSolver 'Ah7c2d' (boşluksuz)."""
    return (board or "").replace(" ", "").strip()


def solve_spot_exact(
    board: str,
    pot_bb: float,
    eff_stack_bb: float,
    hero_in_position: bool,
    hero_combo: str,
    bet_sizes: Optional[list] = None,
    iterations: int = 60,
    pot_type: str = "SRP",
) -> Optional[dict]:
    """Bir postflop spotunu TexasSolver ile çöz, hero elinin EXACT frekansları.

    ``pot_type`` (SRP/3BP/4BP/limped): pota uygun OOP/IP range'leri seçilir —
    3-bet/4-bet potlarda iki taraf da daha sıkı. Döndürür: {action: freq%}
    veya None (binary yok / board geçersiz / çözüm başarısız). EXACT — verilen
    range'ler koşuluyla solver-kesin.
    """
    bd = _norm_board(board)
    if len(bd) < 6:                  # en az 3 kart (flop)
        return None
    try:
        from app.poker.texassolver_adapter import TexasSolverEngine
    except Exception:
        return None
    eng = TexasSolverEngine()
    if not eng.available:
        return None

    range_oop, range_ip = _POT_TYPE_RANGES.get(
        (pot_type or "SRP").upper() if pot_type else "SRP",
        (_SRP_OOP, _SRP_IP))
    res = eng.solve(
        board=bd,
        pot=round(float(pot_bb), 1),
        effective_stack=round(float(eff_stack_bb), 1),
        range_oop=range_oop,
        range_ip=range_ip,
        bet_sizes=bet_sizes or [33, 75],
        iterations=max(10, int(iterations)),
        accuracy=0.5,
    )
    if not res.ok:
        return None
    strat = res.ip_strategy if hero_in_position else res.oop_strategy
    if not strat:
        return None
    # Hero combo'yu strateji tablosunda ara (suit sıralaması değişebilir)
    combo = (hero_combo or "").replace(" ", "")
    freqs = strat.get(combo)
    if freqs is None and len(combo) == 4:
        freqs = strat.get(combo[2:] + combo[:2])   # kart sırasını çevir
    if not freqs:
        return None
    return {a: round(100.0 * f, 1) for a, f in freqs.items()}
