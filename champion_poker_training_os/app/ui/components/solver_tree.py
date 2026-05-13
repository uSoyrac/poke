"""SolverTreeView — pre-solved action tree visualizer.

After hero's preflop decision, what does villain do, and what's hero's
follow-up? This widget paints a 3-level tree:

  Hero decision (root)
    └─ Villain response 1 (freq, EV)
    │   └─ Hero next action (freq, EV)
    └─ Villain response 2 (freq, EV)
    ...

Click any node to emit `node_clicked(path)` where path is a list of
(actor, action, frequency) tuples leading to that node.

Data model: build_solver_tree(spot) returns a SolverTreeNode rooted at the
hero's decision. Frequencies derived from preflop_charts; villain response
frequencies are heuristic (BTN-RFI vs IP 3bet → fold 55% / call 35% / 4bet 10%).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget


@dataclass
class SolverTreeNode:
    actor:     str                              # "hero" / "villain"
    action:    str                              # "raise 2.3" / "call" / "fold"
    frequency: float                            = 1.0
    ev:        float                            = 0.0
    children:  list["SolverTreeNode"]           = field(default_factory=list)

    def add_child(self, child: "SolverTreeNode") -> "SolverTreeNode":
        self.children.append(child); return child


# ──────────────────────────────────────────────────────────────────────────
# Tree builder
# ──────────────────────────────────────────────────────────────────────────

# Villain response heuristics by (opener_position, action)
# This is the "next-street model" — coarse but tournament-coach correct.
VILLAIN_RESPONSE = {
    # vs BTN open (BB perspective)
    ("BTN", "raise"): [
        ("fold",  0.55, -0.0),
        ("call",  0.30,  0.2),
        ("3bet",  0.15,  0.4),
    ],
    ("BTN", "3bet"): [
        ("fold",  0.45, -0.5),
        ("call",  0.40,  0.1),
        ("4bet",  0.15,  0.3),
    ],
    ("CO",  "raise"): [
        ("fold",  0.62, -0.0),
        ("call",  0.28,  0.15),
        ("3bet",  0.10,  0.3),
    ],
    ("LJ",  "raise"): [
        ("fold",  0.70, -0.0),
        ("call",  0.22,  0.1),
        ("3bet",  0.08,  0.25),
    ],
    ("UTG", "raise"): [
        ("fold",  0.78, -0.0),
        ("call",  0.17,  0.05),
        ("3bet",  0.05,  0.2),
    ],
    ("HJ",  "raise"): [
        ("fold",  0.66, -0.0),
        ("call",  0.25,  0.15),
        ("3bet",  0.09,  0.3),
    ],
    ("SB",  "raise"): [
        ("fold",  0.50, -0.0),
        ("call",  0.35,  0.2),
        ("3bet",  0.15,  0.4),
    ],
}


# Hero follow-up heuristics (after villain calls)
HERO_FOLLOWUP_AFTER_CALL = [
    ("cbet small 33%", 0.55,  0.4),
    ("cbet medium 50%", 0.25,  0.5),
    ("check",          0.20, -0.05),
]
# Hero follow-up after villain 3-bets
HERO_FOLLOWUP_AFTER_3BET = [
    ("fold",  0.55, -0.5),
    ("call",  0.30,  0.0),
    ("4bet",  0.15,  0.3),
]


def build_solver_tree(spot: dict) -> SolverTreeNode:
    """Construct a 3-level tree rooted at the hero's preflop decision."""
    from app.solver.preflop_charts import chart_for_spot, hand_169_from_cards, strategy_for_hand

    pos    = (spot.get("position") or "BTN").upper()
    cards  = spot.get("hero_cards", "")
    chart  = chart_for_spot(spot)
    hand   = hand_169_from_cards(cards)
    strat  = strategy_for_hand(chart, hand or "") if hand else {}

    # Root — meta node
    root = SolverTreeNode(actor="hero", action=f"{pos} preflop ({hand or '?'})", frequency=1.0)

    # Level 1: hero options sorted by frequency
    actions_sorted = sorted(strat.items(), key=lambda kv: -kv[1])
    for action, freq in actions_sorted:
        if freq < 0.01:
            continue
        # Approximate EV: high freq → positive
        ev = round(freq * 1.2 - 0.4, 2)
        h1 = root.add_child(SolverTreeNode(actor="hero", action=action,
                                            frequency=freq, ev=ev))

        # Level 2: villain response (only meaningful for aggressive hero actions)
        if any(k in action.lower() for k in ("raise", "3bet", "4bet", "bet")):
            responses = VILLAIN_RESPONSE.get((pos, action.lower().split()[0]),
                                              VILLAIN_RESPONSE.get((pos, "raise"), []))
            for resp_action, resp_freq, resp_ev in responses:
                v = h1.add_child(SolverTreeNode(
                    actor="villain", action=resp_action,
                    frequency=resp_freq, ev=resp_ev,
                ))
                # Level 3: hero follow-up
                if resp_action == "call":
                    pool = HERO_FOLLOWUP_AFTER_CALL
                elif resp_action in ("3bet", "4bet"):
                    pool = HERO_FOLLOWUP_AFTER_3BET
                else:  # fold → no follow-up
                    pool = []
                for f_action, f_freq, f_ev in pool:
                    v.add_child(SolverTreeNode(
                        actor="hero", action=f_action,
                        frequency=f_freq, ev=f_ev,
                    ))
    return root


# ──────────────────────────────────────────────────────────────────────────
# Widget
# ──────────────────────────────────────────────────────────────────────────

ACTOR_COLOURS = {
    "hero":    (QColor("#0F2A1E"), QColor("#10B981"), "#6EE7B7"),
    "villain": (QColor("#1B2D4A"), QColor("#3B82F6"), "#93C5FD"),
}


class SolverTreeView(QWidget):
    """Horizontal tree visualisation of pre-solved action sequences."""

    node_clicked = Signal(object)  # emits the SolverTreeNode

    def __init__(self, parent=None):
        super().__init__(parent)
        self._root: Optional[SolverTreeNode] = None
        self._node_rects: list[tuple] = []  # (rect, node)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(640, 420)

    def set_tree(self, root: SolverTreeNode) -> None:
        self._root = root
        self.update()

    def set_from_spot(self, spot: dict) -> None:
        self.set_tree(build_solver_tree(spot))

    def clear(self) -> None:
        self._root = None
        self._node_rects = []
        self.update()

    # ── interaction ────────────────────────────────────────────────────
    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            return
        x, y = event.position().x(), event.position().y()
        for rect, node in self._node_rects:
            rx, ry, rw, rh = rect
            if rx <= x <= rx + rw and ry <= y <= ry + rh:
                self.node_clicked.emit(node)
                return

    # ── paint ──────────────────────────────────────────────────────────
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self._node_rects = []
        if not self._root:
            painter.setPen(QColor("#6B7280"))
            painter.drawText(self.rect(), Qt.AlignCenter,
                              "Solver tree boş.  Spot seç → tree mode'a geç.")
            painter.end(); return

        # Layout: 4 columns (root, hero L1, villain L2, hero L3)
        col_w = self.width() / 4
        margin_x = 12
        margin_y = 16

        # Walk tree and compute layout positions
        # Level 0: root at column 0, vertically centered
        # Level 1: hero options spread vertically in column 1
        # Level 2: villain responses spread within their parent's slice
        # Level 3: hero follow-ups within their parent's slice
        self._paint_node_recursive(
            painter, node=self._root, level=0,
            x_start=margin_x, x_width=col_w - 2 * margin_x,
            y_start=margin_y, y_height=self.height() - 2 * margin_y,
            col_w=col_w, parent_anchor=None,
        )
        painter.end()

    def _paint_node_recursive(self, painter, node: SolverTreeNode, level: int,
                               x_start: float, x_width: float,
                               y_start: float, y_height: float,
                               col_w: float, parent_anchor: Optional[tuple]) -> None:
        # This node's box
        box_w = min(x_width, col_w - 30)
        box_h = min(64, y_height)
        x = x_start
        y = y_start + (y_height - box_h) / 2

        # Colours
        bg, border, fg = ACTOR_COLOURS.get(node.actor, ACTOR_COLOURS["hero"])
        painter.setBrush(bg)
        painter.setPen(QPen(border, 2))
        painter.drawRoundedRect(int(x), int(y), int(box_w), int(box_h), 8, 8)

        # Text
        font_title = QFont(); font_title.setBold(True); font_title.setPointSize(11)
        painter.setFont(font_title)
        painter.setPen(QColor(fg))
        painter.drawText(int(x + 8), int(y + 4), int(box_w - 16), 22,
                          Qt.AlignVCenter | Qt.AlignLeft, node.action.upper())

        font_meta = QFont(); font_meta.setPointSize(9)
        painter.setFont(font_meta)
        painter.setPen(QColor("#9CA3AF"))
        meta = f"{node.frequency*100:.0f}%  ·  EV {node.ev:+.2f}"
        painter.drawText(int(x + 8), int(y + 28), int(box_w - 16), 18,
                          Qt.AlignVCenter | Qt.AlignLeft, meta)

        # Actor badge
        actor_label = node.actor.upper()
        painter.setPen(QColor(border.name()))
        painter.drawText(int(x + 8), int(y + box_h - 18), int(box_w - 16), 14,
                          Qt.AlignLeft, f"· {actor_label}")

        # Record for hit testing
        self._node_rects.append(((x, y, box_w, box_h), node))

        # Draw connection from parent to this node
        if parent_anchor is not None:
            px, py = parent_anchor
            painter.setPen(QPen(QColor("#3A4659"), 1.5))
            painter.drawLine(int(px), int(py), int(x), int(y + box_h / 2))

        my_anchor = (x + box_w, y + box_h / 2)

        # Children
        if not node.children:
            return
        child_x_start = x + col_w
        child_x_width = col_w - 30
        # Vertical slice for children — divide y_height evenly
        n = len(node.children)
        slice_h = y_height / n
        for i, child in enumerate(node.children):
            child_y_start = y_start + i * slice_h
            self._paint_node_recursive(
                painter, child, level + 1,
                x_start=child_x_start, x_width=child_x_width,
                y_start=child_y_start, y_height=slice_h,
                col_w=col_w, parent_anchor=my_anchor,
            )
