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

# Scenario → (OOP range, IP range) — tek-raise'li pot için makul varsayılanlar.
# TexasSolver PioSOLVER-stili range string'i kabul eder (virgüllü, ağırlıklı).
_SRP_OOP = ("22+,A2s+,K5s+,Q7s+,J8s+,T8s+,97s+,86s+,75s+,64s+,53s+,"
            "A8o+,KTo+,QTo+,JTo")
_SRP_IP = ("22+,A2s+,K2s+,Q5s+,J7s+,T7s+,96s+,85s+,74s+,64s+,53s+,"
           "A5o+,K9o+,Q9o+,J9o+,T9o")


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
) -> Optional[dict]:
    """Bir postflop spotunu TexasSolver ile çöz, hero elinin EXACT frekansları.

    Döndürür: {action: freq%} (örn {"CHECK": 35.0, "BET 5": 65.0}) veya None
    (binary yok / board geçersiz / çözüm başarısız). EXACT — verilen range'ler
    koşuluyla solver-kesin (provenance: EXACT-HU-SRP).
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

    res = eng.solve(
        board=bd,
        pot=round(float(pot_bb), 1),
        effective_stack=round(float(eff_stack_bb), 1),
        range_oop=_SRP_OOP,
        range_ip=_SRP_IP,
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
