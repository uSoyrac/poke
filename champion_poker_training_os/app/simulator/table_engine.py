from __future__ import annotations


def table_seats(table_size: int = 6) -> list[dict]:
    labels = ["Hero", "BTN Bot", "SB Bot", "BB Bot", "UTG Bot", "CO Bot", "HJ Bot", "LJ Bot", "Reg Bot"]
    return [
        {"name": labels[idx], "stack": 100 - idx * 4, "position": idx}
        for idx in range(table_size)
    ]

