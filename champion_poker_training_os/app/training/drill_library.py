"""Shared drill library — app-wide singleton backed by the seed drills.

Other screens (LeakFinder, SpotTrainer, StudyPlanner…) share one instance
so drills generated anywhere are immediately visible everywhere.
"""
from __future__ import annotations

import random
from typing import Callable

from PySide6.QtCore import QObject, Signal

from app.db.seed_data import generate_spot_drills


# D240: leak'e ÖZEL preflop drill reçeteleri — gerçek leak'in olduğu spot-tipi + eller.
# best_action SABİT DEĞİL → soyrac_advice'tan hesaplanır (yoksa junk'a 'call' diye yanlış
# öğretip leak'i pekiştiriyordu). name → (scenario, defender_pos, opener, [hands]).
_LEAK_DRILL_SPEC = {
    "Çöp/spekülatif over-defend": ("vs RFI", ["BB", "CO", "BTN"], "UTG",
                                   ["K2s", "Q4s", "J6s", "K3o", "Q7o", "J2s", "T6o"]),
    "Çok geniş açış (eşik-altı)": ("RFI", ["UTG", "UTG+1", "MP"], None,
                                   ["K5o", "Q7o", "J6s", "95s", "T6s", "Q4o", "K3o"]),
    "3-bet pot over-call": ("vs 3-bet", ["MP", "CO", "BTN"], "CO",
                            ["33", "44", "55", "66", "A8s", "KJo"]),
    "Aşırı 3-bet (non-premium)": ("vs RFI", ["MP", "CO", "BTN"], "UTG",
                                  ["33", "44", "ATo", "KQo", "A9s", "QJo"]),
    "Raise-yerine-flat ters çevirme": ("vs RFI", ["CO", "BTN", "SB"], "MP",
                                       ["33", "44", "A5s", "T9s", "98s", "76s"]),
}
_ACT_TO_OPT = {"FOLD": "fold", "CALL": "call", "JAM": "jam"}


def _correct_preflop_option(hk, pos, scenario, vs_pos, stack_bb):
    """soyrac_advice → drill option (fold/call/raise/jam). Doğru cevap motordan, sabit değil."""
    try:
        from app.poker.soyrac_advisor import soyrac_advice
        act = soyrac_advice(hk, pos, scenario=scenario, vs_position=vs_pos,
                            stack_bb=stack_bb, tourney=True).get("action", "FOLD")
    except Exception:
        return "fold"
    for key, opt in _ACT_TO_OPT.items():
        if key in act:
            return opt
    if any(k in act for k in ("RAISE", "3-BET", "4-BET", "BET", "AÇ")):
        return "raise"
    return "fold"


class DrillLibrary(QObject):
    """Singleton drill store.  Call ``DrillLibrary.instance()``."""

    drill_added = Signal(dict)   # fires once per newly added drill

    _instance: "DrillLibrary | None" = None

    @classmethod
    def instance(cls) -> "DrillLibrary":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        super().__init__()
        self._drills: list[dict] = []
        self._scores: dict[str, int] = {}   # drill_id → best score 0-100

        # Seed the library with built-in drills
        for d in generate_spot_drills(80):
            d = dict(d)
            d["source"] = "seeded"
            self._drills.append(d)

    # ── write ──────────────────────────────────────────────────────────

    def add_drill(self, drill: dict) -> None:
        """Add one drill dict and notify listeners."""
        self._drills.append(drill)
        self.drill_added.emit(drill)

    def generate_repair_pack(self, leaks: list[dict],
                             max_total: int = 18) -> list[dict]:
        """Gerçek leak listesinden ağırlıklı 'tamir paketi' üret.

        Spaced-repetition mantığı: daha ağır leak → daha çok tekrar (drill).
        Critical=6, High=4, Medium=2 drill (max_total ile sınırlı). Info/Low
        atlanır. `get_leak_analysis()` çıktısını doğrudan kabul eder.
        """
        weight = {"Critical": 6, "High": 4, "Medium": 2}
        # En ağırdan başla (EV kaybı / severity)
        ordered = sorted(
            (l for l in (leaks or []) if l.get("severity") in weight),
            key=lambda l: (weight.get(l.get("severity"), 0),
                           float(l.get("ev_lost", 0) or 0)),
            reverse=True,
        )
        pack: list[dict] = []
        for leak in ordered:
            if len(pack) >= max_total:
                break
            n = weight.get(leak.get("severity"), 2)
            n = min(n, max_total - len(pack))
            pack.extend(self.generate_from_leak(leak, count=n))
        return pack

    def generate_from_leak(self, leak: dict, count: int = 5) -> list[dict]:
        """Create ``count`` focused drill entries from a *leak* dict.

        The drills are added to the library immediately (drill_added fires
        for each one) and the list is returned for convenience.
        """
        count = max(1, int(count))
        # D240: leak'e ÖZEL preflop drill (gerçek-veri leak'leri) — doğru cevap motordan.
        _nm = leak.get("name", "")
        for _key, _sp in _LEAK_DRILL_SPEC.items():
            if _key in _nm:
                return self._gen_leak_preflop_drills(leak, _sp, count)
        category = leak.get("category", "Preflop")
        street_map = {
            "Preflop": "preflop", "Flop": "flop", "Turn": "turn",
            "River": "river", "ICM": "preflop", "MTT": "preflop",
            "Postflop": "flop",
        }
        street = street_map.get(category, "preflop")
        positions = ["UTG", "LJ", "HJ", "CO", "BTN", "SB", "BB"]
        options_map = {
            "preflop": ("fold", "call", "raise", "jam"),
            "flop":    ("check", "bet small", "bet medium", "bet large"),
            "turn":    ("check", "bet", "raise", "fold"),
            "river":   ("check", "bet", "fold", "jam"),
        }
        options = options_map.get(street, ("fold", "call", "raise"))
        boards = ["Ah7c2d", "KsQh8s", "9s8s4d", "QcQd3h", "Jc7c2c"]
        hands  = ["AsKh", "QdQs", "JhTh", "8s8c", "Ac5c"]
        stacks = [15, 25, 40, 60, 100]

        fix_short = leak.get("fix", "")[:60]
        leak_tag = leak["name"][:12].replace(" ", "")

        new_drills: list[dict] = []
        for i in range(count):
            # Kütüphane boyutunu da kat → tekrar üretimde ID çakışmasın
            drill_id = f"LEAK-{leak_tag}-{len(self._drills)+1}"
            pos = positions[i % len(positions)]
            stack = stacks[i % len(stacks)]
            d: dict = {
                "id":               drill_id,
                "title":            f"{leak['name']} — spot {i+1}",
                "format":           "cash" if category not in ("ICM", "MTT") else "MTT",
                "table":            "6-max",
                "street":           street,
                "position":         pos,
                "stack_bb":         stack,
                "pot_bb":           round(3.5 + i * 2.5, 1),
                "hero_cards":       hands[i % len(hands)],
                "board":            "" if street == "preflop" else boards[i % len(boards)],
                "board_texture":    category,
                "pot_type":         "SRP",
                "action_history":   f"Hero in {pos}. Focus: {fix_short}",
                "options":          options,
                "best_action":      options[1],
                "base_ev":          round(0.75 + i * 0.10, 2),
                "range_advantage":  "Neutral ranges",
                "nut_advantage":    "Shared nut density",
                "icm":              "bubble" if category == "ICM" else "off",
                "source_confidence":"Rule-based heuristic",
                # library metadata
                "source":           "leak",
                "leak_name":        leak["name"],
                "leak_category":    category,
                "severity":         leak.get("severity", "Medium"),
            }
            self._drills.append(d)
            self.drill_added.emit(d)
            new_drills.append(d)

        return new_drills

    @staticmethod
    def _hk_to_cards(hk: str) -> str:
        """Hand-key → görünür kart (K2s→Ks 2s, 33→3h 3d, ATo→Ah Td)."""
        r1, r2 = hk[0], hk[1]
        if r1 == r2:
            return f"{r1}h {r2}d"
        suited = hk.endswith("s")
        return f"{r1}h {r2}h" if suited else f"{r1}h {r2}d"

    def _gen_leak_preflop_drills(self, leak: dict, spec: tuple, count: int) -> list[dict]:
        """D240: leak'e ÖZEL preflop drill — leak'in olduğu eller + DOĞRU cevap (soyrac_advice)."""
        scenario, positions, opener, hands = spec
        stacks = [40, 60, 100, 50, 80]
        options = ("fold", "call", "raise", "jam")
        fix_short = leak.get("fix", "")[:70]
        leak_tag = leak["name"][:12].replace(" ", "")
        new_drills: list[dict] = []
        for i in range(count):
            hk = hands[i % len(hands)]
            pos = positions[i % len(positions)]
            stack = stacks[i % len(stacks)]
            best = _correct_preflop_option(hk, pos, scenario, opener, stack)
            hist = f"{scenario}" + (f" — {opener} açtı, " if opener else " — ") + \
                   f"sen {pos} ({stack}bb). Odak: {fix_short}"
            d = {
                "id": f"LEAK-{leak_tag}-{len(self._drills)+1}",
                "title": f"{leak['name']} — spot {i+1} ({hk})",
                "format": "MTT" if leak.get("category") in ("ICM", "MTT") else "cash",
                "table": "6-max", "street": "preflop", "position": pos,
                "stack_bb": stack, "pot_bb": round(2.5 + i * 1.5, 1),
                "hero_cards": self._hk_to_cards(hk), "board": "",
                "board_texture": "Preflop", "pot_type": "SRP",
                "action_history": hist, "options": options,
                "best_action": best,                      # ← MOTORDAN, sabit değil
                "base_ev": round(0.8 + i * 0.1, 2),
                "range_advantage": "—", "nut_advantage": "—", "icm": "off",
                "source_confidence": "Soyrac engine (GTO-aligned)",
                "source": "leak", "leak_name": leak["name"],
                "leak_category": leak.get("category", "Preflop"),
                "severity": leak.get("severity", "Medium"),
            }
            self._drills.append(d)
            self.drill_added.emit(d)
            new_drills.append(d)
        return new_drills

    # ── read ───────────────────────────────────────────────────────────

    def get_drills(self, category: str = "All") -> list[dict]:
        """Return all drills, optionally filtered by street / category."""
        if category == "All":
            return list(self._drills)
        street_map = {
            "Preflop": "preflop", "Flop": "flop",
            "Turn": "turn",        "River": "river",
        }
        if category in street_map:
            target_street = street_map[category]
            return [d for d in self._drills if d.get("street") == target_street]
        # Leak categories (ICM, MTT, Postflop …)
        return [d for d in self._drills if d.get("leak_category") == category]

    def record_score(self, drill_id: str, score: int) -> None:
        existing = self._scores.get(drill_id)
        if existing is None or score > existing:
            self._scores[drill_id] = score

    def get_score(self, drill_id: str) -> int | None:
        return self._scores.get(drill_id)

    def __len__(self) -> int:
        return len(self._drills)
