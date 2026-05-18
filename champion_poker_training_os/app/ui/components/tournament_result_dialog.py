"""Tournament Result Dialog — APT-style summary shown when a tournament ends.

Layout matches the user's reference screenshot:
  ┌──────────────────────────────────────────────────────────────────────┐
  │  Online Turbo Low Stakes        [Session Report] [Trophies] [Share] │
  ├──────────────────────────────────────────────────────────────────────┤
  │  Final place  │ Skill Level │ Count Towards    │  WINNERS           │
  │     78        │    Easy     │ Ranking: Yes     │  1. Anderson  $897 │
  ├───────────────┼─────────────┼──────────────────┤  2. Clarissa  $570 │
  │  Buyin  $30   │ Entry $3    │ Your Payout: $0  │  3. Veronica  $398 │
  ├───────────────┼─────────────┼──────────────────┤  4. Chris     $315 │
  │  Players 100  │ Stack 1,000 │ Time/Level: 10   │  ...               │
  │               │             │ All-in luck 🐈   │  78. uygar    $0   │
  └──────────────────────────────────────────────────────────────────────┘
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


# Palette — light cards on dark bg to match the reference
_C_BG          = "#0A0E14"
_C_CARD_WHITE  = "#FAFAFA"
_C_CARD_TEXT   = "#0F1419"
_C_HDR_BLUE    = "#DDE4F6"
_C_HDR_GREEN   = "#D6F0D6"
_C_HDR_PINK    = "#F8DADA"
_C_HDR_YELLOW  = "#FBF0C8"
_C_MUTED       = "#6B7280"
_C_RED         = "#DC2626"
_C_GREEN       = "#10B981"
_C_TEXT        = "#E5E7EB"


def _fake_player_names(n: int, hero_pos: int, hero_name: str = "uygar") -> List[str]:
    """Generate plausible player names so the winners list feels real."""
    first  = ["Anderson", "Clarissa", "Veronica", "Chris", "Johnnie", "Maxwell",
              "Jade", "Marc", "Craig", "Robert", "Felix", "Lena", "Daria",
              "Owen", "Priya", "Sam", "Rachel", "Logan", "Jason", "Kaleb",
              "Elise", "Mateo", "Yara", "Holden", "Karim", "Tessa", "Ronan"]
    last   = ["Maddox", "Hale", "Reese", "Barker", "Waller", "Page", "Walls",
              "Watts", "Tanner", "Holmes", "Reyes", "Spears", "Pratt", "Aguirre",
              "Hovath", "Armstrong", "Terrell", "Weinbrecht", "Cameron", "Voss"]
    rng = random.Random(42)
    names = []
    used = set()
    while len(names) < n:
        name = f"{rng.choice(first)} {rng.choice(last)}"
        if name in used:
            continue
        used.add(name)
        names.append(name)
    if hero_pos - 1 < n:
        names[hero_pos - 1] = hero_name
    return names


def _payout_pyramid(prize_pool: float, places_paid: int) -> List[float]:
    """Pyramid distribution similar to APT/PokerStars MTT structures."""
    pct = [0.22, 0.15, 0.11, 0.08, 0.06, 0.05, 0.04, 0.03, 0.025, 0.02,
           0.018, 0.015, 0.013, 0.012, 0.010]
    out = []
    remaining = prize_pool
    for i in range(places_paid):
        p = pct[min(i, len(pct) - 1)]
        amount = round(prize_pool * p, 0)
        out.append(amount)
        remaining -= amount
    # Normalize so total adds up
    total = sum(out)
    if total > 0:
        scale = prize_pool / total
        out = [round(v * scale, 0) for v in out]
    return out


# ── small helper widgets ──────────────────────────────────────────────────

def _kpi_card(header: str, value: str, header_bg: str = _C_HDR_BLUE) -> QFrame:
    f = QFrame()
    f.setStyleSheet(
        f"QFrame{{background:{_C_CARD_WHITE};border:1px solid #D1D5DB;border-radius:6px;}}"
    )
    f.setMinimumHeight(110)
    v = QVBoxLayout(f)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(0)

    hdr = QLabel(header)
    hdr.setAlignment(Qt.AlignCenter)
    hdr.setStyleSheet(
        f"background:{header_bg};color:{_C_CARD_TEXT};"
        f"font-size:13px;font-weight:600;padding:6px 8px;"
        f"border-top-left-radius:6px;border-top-right-radius:6px;"
        f"border-bottom:1px solid #D1D5DB;"
    )
    v.addWidget(hdr)

    val = QLabel(value)
    val.setAlignment(Qt.AlignCenter)
    val.setStyleSheet(
        f"background:transparent;color:{_C_CARD_TEXT};"
        f"font-size:34px;font-weight:300;padding:6px;"
    )
    v.addWidget(val, 1)
    return f


def _winners_panel(winners: List[tuple], hero_place: int, hero_name: str,
                   hero_payout: float, total_places: int) -> QFrame:
    f = QFrame()
    f.setStyleSheet(
        f"QFrame{{background:{_C_CARD_WHITE};border:1px solid #D1D5DB;border-radius:6px;}}"
    )
    f.setMinimumWidth(280)
    v = QVBoxLayout(f); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(0)

    hdr = QLabel("WINNERS")
    hdr.setAlignment(Qt.AlignCenter)
    hdr.setStyleSheet(
        f"background:#D1D5DB;color:{_C_CARD_TEXT};font-size:14px;font-weight:700;"
        f"padding:8px;border-top-left-radius:6px;"
        f"border-top-right-radius:6px;border-bottom:1px solid #9CA3AF;"
    )
    v.addWidget(hdr)

    # Column header row
    head_row = QHBoxLayout()
    head_row.setContentsMargins(8, 4, 8, 4)
    h_rank = QLabel("#");          h_rank.setStyleSheet(f"color:{_C_CARD_TEXT};font-weight:700;font-size:11px;")
    h_name = QLabel("Player");     h_name.setStyleSheet(f"color:{_C_CARD_TEXT};font-weight:700;font-size:11px;")
    h_pay  = QLabel("Payout");     h_pay.setStyleSheet(f"color:{_C_CARD_TEXT};font-weight:700;font-size:11px;")
    h_rank.setFixedWidth(28)
    h_pay.setAlignment(Qt.AlignRight)
    head_row.addWidget(h_rank)
    head_row.addWidget(h_name, 1)
    head_row.addWidget(h_pay)
    head_w = QWidget(); head_w.setLayout(head_row)
    head_w.setStyleSheet(f"background:#F3F4F6;border-bottom:1px solid #D1D5DB;")
    v.addWidget(head_w)

    # Winners rows
    rows_w = QWidget()
    rows_w.setStyleSheet(f"background:{_C_CARD_WHITE};")
    rl = QVBoxLayout(rows_w); rl.setContentsMargins(0, 0, 0, 0); rl.setSpacing(0)
    for i, (name, amount) in enumerate(winners[:10]):
        row = QHBoxLayout()
        row.setContentsMargins(8, 5, 8, 5)
        n_lbl = QLabel(str(i + 1))
        n_lbl.setStyleSheet(f"color:{_C_CARD_TEXT};font-size:13px;")
        n_lbl.setFixedWidth(28)
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(f"color:{_C_CARD_TEXT};font-size:13px;")
        pay_lbl  = QLabel(f"$ {amount:,.0f}")
        pay_lbl.setStyleSheet(f"color:{_C_CARD_TEXT};font-size:13px;font-weight:600;")
        pay_lbl.setAlignment(Qt.AlignRight)
        row.addWidget(n_lbl)
        row.addWidget(name_lbl, 1)
        row.addWidget(pay_lbl)
        rw = QWidget(); rw.setLayout(row)
        rw.setStyleSheet(f"border-bottom:1px solid #E5E7EB;")
        rl.addWidget(rw)

    # Separator + hero row at the bottom
    if hero_place > 10:
        sep = QLabel("…")
        sep.setAlignment(Qt.AlignCenter)
        sep.setStyleSheet(f"color:{_C_MUTED};font-size:13px;padding:4px;")
        rl.addWidget(sep)
        hero_row = QHBoxLayout()
        hero_row.setContentsMargins(8, 6, 8, 6)
        n = QLabel(str(hero_place)); n.setStyleSheet(f"color:{_C_GREEN};font-size:13px;font-weight:800;")
        n.setFixedWidth(28)
        nm = QLabel(hero_name);     nm.setStyleSheet(f"color:{_C_GREEN};font-size:13px;font-weight:800;")
        py = QLabel(f"$ {hero_payout:,.0f}");
        py.setStyleSheet(f"color:{_C_GREEN};font-size:13px;font-weight:800;")
        py.setAlignment(Qt.AlignRight)
        hero_row.addWidget(n); hero_row.addWidget(nm, 1); hero_row.addWidget(py)
        hrw = QWidget(); hrw.setLayout(hero_row)
        hrw.setStyleSheet(f"background:#F3F4F6;border-top:2px solid #D1D5DB;")
        rl.addWidget(hrw)

    v.addWidget(rows_w, 1)
    return f


# ── main dialog ───────────────────────────────────────────────────────────

class TournamentResultDialog(QDialog):
    """End-of-tournament summary dialog."""
    view_report_requested = Signal()

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        tournament_name: str,
        final_place:     int,
        field_size:      int,
        skill_level:     str,
        skill_style:     str,
        buyin:           float,
        starting_stack:  int,
        time_per_level:  int,
        hero_payout:     float,
        prize_pool:      float,
        all_in_luck:     str = "neutral",      # lucky / neutral / unlucky
        hero_name:       str = "uygar",
        count_towards_ranking: bool = True,
    ):
        super().__init__(parent)
        self.setWindowTitle(f"{tournament_name} — Result")
        self.setMinimumSize(900, 560)
        self.setStyleSheet(
            f"QDialog{{background:{_C_BG};}}"
            f"QPushButton#ActionBtn{{background:{_C_RED};color:white;"
            f"border:none;border-radius:5px;font-size:13px;font-weight:700;padding:8px 18px;}}"
            f"QPushButton#ActionBtn:hover{{background:#B91C1C;}}"
        )

        # Compute winners list
        n_paid = max(2, int(field_size * 0.15))
        payouts = _payout_pyramid(prize_pool, n_paid)
        names = _fake_player_names(field_size, final_place, hero_name)
        winners = list(zip(names[:n_paid], payouts))

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(14)

        # ── Header row ─────────────────────────────────────────────
        header = QHBoxLayout()
        title = QLabel(tournament_name)
        title.setStyleSheet(f"color:{_C_TEXT};font-size:24px;font-weight:700;")
        header.addWidget(title)
        header.addStretch(1)
        for label in ("Session Report", "See All My Trophies", "Share"):
            b = QPushButton(label)
            b.setObjectName("ActionBtn")
            b.setFixedHeight(36)
            if label == "Session Report":
                b.clicked.connect(self.view_report_requested.emit)
            header.addWidget(b)
        root.addLayout(header)

        # ── Body: 3 columns of cards + winners panel ───────────────
        body = QHBoxLayout()
        body.setSpacing(14)

        # Card grid (3 cols × 3 rows)
        cards_w = QWidget()
        grid = QGridLayout(cards_w)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)

        luck_emoji = {"lucky": "🍀", "unlucky": "🐈‍⬛", "neutral": "🎯"}.get(all_in_luck, "🎯")

        cards = [
            ("Final place",          str(final_place),           _C_HDR_BLUE),
            ("Skill Level",          skill_level,                _C_HDR_BLUE),
            ("Count Towards Ranking", "Yes" if count_towards_ranking else "No", _C_HDR_BLUE),
            ("Buyin",                f"$ {buyin:.0f}",           _C_HDR_GREEN),
            ("Entry Fee",            f"$ {buyin * 0.10:.0f}",    _C_HDR_GREEN),
            ("Your Payout",          f"$ {hero_payout:.0f}",     _C_HDR_GREEN),
            ("Starting Players",     f"{field_size}",            _C_HDR_PINK),
            ("Starting Stack",       f"{starting_stack:,}",      _C_HDR_PINK),
            ("Time Per Level",       f"{time_per_level} dk",     _C_HDR_PINK),
        ]
        for i, (h, v, bg) in enumerate(cards):
            grid.addWidget(_kpi_card(h, v, bg), i // 3, i % 3)

        # All-in luck card
        luck_card = _kpi_card(f"All-in luck", luck_emoji, _C_HDR_YELLOW)
        grid.addWidget(luck_card, 3, 1)

        body.addWidget(cards_w, 3)

        # Winners panel on the right
        body.addWidget(_winners_panel(winners, final_place, hero_name,
                                       hero_payout, field_size), 2)

        root.addLayout(body, 1)

        # ── Footer line ────────────────────────────────────────────
        footer = QLabel(
            f"{skill_style} bots / {skill_level} skill   ·   "
            f"prize pool ${prize_pool:,.0f}   ·   "
            f"{n_paid} places paid"
        )
        footer.setStyleSheet(f"color:{_C_MUTED};font-size:12px;padding:6px 4px;")
        footer.setAlignment(Qt.AlignCenter)
        root.addWidget(footer)

        # Bottom row: close
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        close = QPushButton("Close")
        close.setFixedHeight(36)
        close.setStyleSheet(
            f"QPushButton{{background:#1F2937;color:{_C_TEXT};"
            f"border:1px solid #374151;border-radius:6px;padding:0 22px;}}"
            f"QPushButton:hover{{border-color:#22D3EE;color:#22D3EE;}}"
        )
        close.clicked.connect(self.accept)
        bottom.addWidget(close)
        root.addLayout(bottom)
