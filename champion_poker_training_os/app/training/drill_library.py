"""Shared drill library — app-wide singleton backed by the seed drills.

Other screens (LeakFinder, SpotTrainer, StudyPlanner…) share one instance
so drills generated anywhere are immediately visible everywhere.
"""
from __future__ import annotations

import random
from typing import Callable

from PySide6.QtCore import QObject, Signal

from app.db.seed_data import generate_spot_drills


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
