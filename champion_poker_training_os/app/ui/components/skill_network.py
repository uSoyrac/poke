"""SkillNetworkWidget — Poke-styled skill-tree network graph.

Replaces the legacy linear list of category rows with a node-link
visualisation:

    • Each skill category = a circular node.
    • Node radius scales with the player's level (1..10).
    • Node fill intensity scales with mastery% (0..100) — lime accent.
    • Outline ring is the line-2 token (sharp brutalist edge).
    • Hairline edges connect related categories (preflop → 3bet → blind
      defense; flop → turn → river; icm → pko → tournament; etc.).
    • Hover highlights the node + emits ``hovered`` (id, name).
    • Click emits ``clicked`` (id) — caller wires that to a navigate call.

Designed for the Dashboard sidebar at ~360×340 px. Resizes gracefully.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor, QFont, QFontMetricsF, QPainter, QPen, QPolygonF,
)
from PySide6.QtWidgets import QSizePolicy, QWidget

from app.ui.theme import poke_tokens as t


@dataclass
class _NodeLayout:
    """Normalised position (0..1) for one skill node on the canvas."""
    id: str
    x: float
    y: float


# Curated layout — clusters mirror the natural poker skill tree:
#   left-top     preflop / 3bet / blind defense
#   centre-top   flop → turn → river (the street spine)
#   left-bottom  math / mental
#   right-top    icm → pko → tournament
#   right-bottom exploit
_NODE_LAYOUT: list[_NodeLayout] = [
    _NodeLayout("preflop",       0.18, 0.18),
    _NodeLayout("blind_defense", 0.07, 0.40),
    _NodeLayout("three_bet",     0.32, 0.30),
    _NodeLayout("flop",          0.50, 0.18),
    _NodeLayout("turn",          0.50, 0.46),
    _NodeLayout("river",         0.50, 0.74),
    _NodeLayout("icm",           0.78, 0.22),
    _NodeLayout("pko",           0.90, 0.46),
    _NodeLayout("tournament",    0.78, 0.70),
    _NodeLayout("math",          0.12, 0.78),
    _NodeLayout("mental",        0.30, 0.90),
    _NodeLayout("exploit",       0.92, 0.85),
]

# Edges represent reasonable "this skill enables that one" relationships.
_EDGES: list[tuple[str, str]] = [
    ("preflop",   "three_bet"),
    ("preflop",   "blind_defense"),
    ("blind_defense", "three_bet"),
    ("preflop",   "flop"),
    ("flop",      "turn"),
    ("turn",      "river"),
    ("flop",      "exploit"),
    ("river",     "exploit"),
    ("math",      "preflop"),
    ("math",      "river"),
    ("math",      "icm"),
    ("mental",    "tournament"),
    ("icm",       "tournament"),
    ("icm",       "pko"),
    ("pko",       "tournament"),
]


class SkillNetworkWidget(QWidget):
    """Painted skill-tree network. Wire ``clicked`` to a navigate slot."""

    clicked = Signal(str)            # emits the skill node id
    hovered = Signal(str, str)       # (id, name) — name is "" when hovering empty

    def __init__(self, nodes: dict | None = None, parent=None):
        super().__init__(parent)
        # `nodes` is the SkillTree.get_summary()["categories"] list-of-dicts
        # converted to a {id: dict} mapping. Keeping the raw dict so we
        # don't depend on the SkillTree class type at runtime.
        self._nodes: dict[str, dict] = {}
        if nodes:
            self.set_nodes(nodes)
        self.setMinimumSize(360, 320)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)
        self._hovered_id: Optional[str] = None

    def set_nodes(self, nodes) -> None:
        """Accept a list of category dicts (as from `get_summary()`) or a
        dict-of-dicts. Each entry needs `id`, `name`, `level`, `mastery`."""
        if isinstance(nodes, list):
            self._nodes = {n["id"]: n for n in nodes}
        else:
            self._nodes = dict(nodes)
        self.update()

    # ── geometry helpers ─────────────────────────────────────────────
    def _node_pos(self, layout: _NodeLayout) -> QPointF:
        w = self.width()
        h = self.height()
        margin = 24
        return QPointF(
            margin + layout.x * (w - 2 * margin),
            margin + layout.y * (h - 2 * margin),
        )

    def _node_radius(self, level: int) -> float:
        # level 1 → 12 px, level 10 → 22 px
        return 12.0 + max(0, min(10, level)) * 1.0

    def _node_for_pos(self, pos: QPointF) -> Optional[str]:
        for layout in _NODE_LAYOUT:
            node = self._nodes.get(layout.id)
            if node is None:
                continue
            centre = self._node_pos(layout)
            r = self._node_radius(int(node.get("level", 1)))
            if (pos - centre).manhattanLength() <= r + 4:
                if abs(pos.x() - centre.x()) <= r + 4 and abs(
                        pos.y() - centre.y()) <= r + 4:
                    return layout.id
        return None

    # ── painting ─────────────────────────────────────────────────────
    def paintEvent(self, event) -> None:  # type: ignore[override]
        try:
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)

            # Background — Poke surface
            p.fillRect(self.rect(), QColor(t.SURFACE))
            # Hairline border so the widget reads as a card surface
            p.setPen(QPen(QColor(t.LINE), 1))
            p.setBrush(Qt.NoBrush)
            p.drawRect(self.rect().adjusted(0, 0, -1, -1))

            if not self._nodes:
                self._paint_empty(p)
                p.end()
                return

            # 1) Edges first — behind the nodes
            edge_pen = QPen(QColor(t.LINE_2), 1)
            edge_pen.setCosmetic(True)
            p.setPen(edge_pen)
            id_to_layout = {n.id: n for n in _NODE_LAYOUT}
            for a, b in _EDGES:
                la = id_to_layout.get(a)
                lb = id_to_layout.get(b)
                if not (la and lb):
                    continue
                if a not in self._nodes or b not in self._nodes:
                    continue
                pa = self._node_pos(la)
                pb = self._node_pos(lb)
                p.drawLine(pa, pb)

            # 2) Nodes
            ink_pen   = QPen(QColor(t.LINE_2), 1)
            accent    = QColor(t.ACCENT)
            ink_color = QColor(t.INK)
            muted_col = QColor(t.MUTED)
            for layout in _NODE_LAYOUT:
                node = self._nodes.get(layout.id)
                if node is None:
                    continue
                centre = self._node_pos(layout)
                level = int(node.get("level", 1))
                mastery = float(node.get("mastery", 0))
                r = self._node_radius(level)

                # Fill — lime, alpha-scaled by mastery
                fill = QColor(accent)
                fill.setAlphaF(0.15 + 0.65 * (mastery / 100.0))
                p.setBrush(fill)

                # Outline — accent when hovered or mastery ≥ 80, line_2 otherwise
                if self._hovered_id == layout.id:
                    p.setPen(QPen(QColor(t.ACCENT), 2))
                elif mastery >= 80:
                    p.setPen(QPen(QColor(t.ACCENT), 1))
                else:
                    p.setPen(ink_pen)
                p.drawEllipse(centre, r, r)

                # Level number inside the node (Space Grotesk, bold)
                f = QFont("Space Grotesk")
                f.setBold(True)
                f.setPixelSize(int(r * 0.9))
                p.setFont(f)
                p.setPen(ink_color)
                p.drawText(
                    QRectF(centre.x() - r, centre.y() - r, 2 * r, 2 * r),
                    Qt.AlignCenter,
                    str(level),
                )

                # Name label below the node
                lf = QFont("JetBrains Mono")
                lf.setPixelSize(10)
                p.setFont(lf)
                p.setPen(muted_col)
                metrics = QFontMetricsP = QFontMetricsF(lf)
                name = (node.get("name") or layout.id).upper()
                lbl_w = metrics.horizontalAdvance(name)
                p.drawText(
                    QRectF(centre.x() - lbl_w / 2, centre.y() + r + 4,
                            lbl_w, 14),
                    Qt.AlignCenter,
                    name,
                )

            # 3) Hover tooltip — show node detail in a small floating chip
            if self._hovered_id:
                node = self._nodes.get(self._hovered_id)
                if node:
                    self._paint_tooltip(p, node)
            p.end()
        except Exception:
            # paintEvent must never raise — Qt swallows the exception and
            # crashes the process on macOS (per AGENTS.md landmines list).
            try:
                p.end()
            except Exception:
                pass

    def _paint_empty(self, p: QPainter) -> None:
        p.setPen(QColor(t.MUTED))
        f = QFont("JetBrains Mono")
        f.setPixelSize(11)
        p.setFont(f)
        p.drawText(self.rect(), Qt.AlignCenter,
                    "▸  NO SKILL DATA YET — PLAY HANDS / SOLVE DRILLS")

    def _paint_tooltip(self, p: QPainter, node: dict) -> None:
        lf = QFont("JetBrains Mono")
        lf.setPixelSize(10)
        p.setFont(lf)
        line1 = f"▸  {(node.get('name') or '').upper()}"
        line2 = (
            f"LV {int(node.get('level', 1)):02d}  ·  "
            f"{int(node.get('mastery', 0))}% MASTERY  ·  "
            f"{int(node.get('xp', 0))} / "
            f"{int(node.get('xp_next', 0))} XP"
        )
        m = QFontMetricsF(lf)
        w = max(m.horizontalAdvance(line1), m.horizontalAdvance(line2)) + 16
        h = 36
        rect = QRectF(8, self.height() - h - 8, w, h)
        p.setBrush(QColor(t.BG_2))
        p.setPen(QPen(QColor(t.LINE_2), 1))
        p.drawRect(rect)
        p.setPen(QColor(t.INK))
        p.drawText(
            QRectF(rect.x() + 8, rect.y() + 4, rect.width() - 16, 14),
            Qt.AlignLeft | Qt.AlignVCenter,
            line1,
        )
        p.setPen(QColor(t.MUTED))
        p.drawText(
            QRectF(rect.x() + 8, rect.y() + 18, rect.width() - 16, 14),
            Qt.AlignLeft | Qt.AlignVCenter,
            line2,
        )

    # ── interaction ──────────────────────────────────────────────────
    def mouseMoveEvent(self, event) -> None:
        nid = self._node_for_pos(QPointF(event.pos()))
        if nid != self._hovered_id:
            self._hovered_id = nid
            node = self._nodes.get(nid) if nid else None
            name = (node or {}).get("name", "") if node else ""
            self.hovered.emit(nid or "", name)
            self.setCursor(Qt.PointingHandCursor if nid else Qt.ArrowCursor)
            self.update()

    def mousePressEvent(self, event) -> None:
        nid = self._node_for_pos(QPointF(event.pos()))
        if nid:
            self.clicked.emit(nid)

    def leaveEvent(self, event) -> None:
        if self._hovered_id is not None:
            self._hovered_id = None
            self.update()
