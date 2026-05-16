"""HandReviewDialog — basit bir 'tek el review' diyalogu.

Tournament archive'dan bir el seçildiğinde açılır. Şunları gösterir:
  • Hero + board kartları (CardView)
  • Stack in/out + delta + position + blinds
  • Pot final değeri
  • Hero kazandı/kaybetti rozeti
  • 'Bu spotu drill et' butonu — Spot Trainer'a yönlenir

`hand_record` parametresi `TournamentRecord.hand_history` listesindeki bir
dict (HandRecord asdict()) olarak gelir.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.components.card_view import CardView


_C_BG     = "#0A0E14"
_C_PANEL  = "#0F141C"
_C_BORDER = "#1E2733"
_C_TEXT   = "#E5E7EB"
_C_MUTED  = "#9CA3AF"
_C_CYAN   = "#22D3EE"
_C_GREEN  = "#10B981"
_C_RED    = "#EF4444"


def _section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color:{_C_MUTED};font-size:10px;font-weight:700;letter-spacing:1.2px;"
        f"background:transparent;padding-bottom:4px;"
    )
    return lbl


def _stat_pill(caption: str, value: str, accent: str = _C_TEXT) -> QFrame:
    f = QFrame()
    f.setStyleSheet(
        f"QFrame{{background:{_C_PANEL};border:1px solid {_C_BORDER};border-radius:6px;}}"
    )
    f.setMinimumWidth(110)
    v = QVBoxLayout(f)
    v.setContentsMargins(12, 6, 12, 6)
    v.setSpacing(0)
    cap = QLabel(caption)
    cap.setStyleSheet(f"color:{_C_MUTED};font-size:10px;font-weight:700;"
                      f"letter-spacing:1px;background:transparent;")
    val = QLabel(value)
    val.setStyleSheet(f"color:{accent};font-size:15px;font-weight:800;background:transparent;")
    v.addWidget(cap)
    v.addWidget(val)
    return f


def _card_row(card_str: str) -> QHBoxLayout:
    """Parse a string like 'AsKh' or 'Td9c2s' into a row of CardView widgets."""
    row = QHBoxLayout()
    row.setSpacing(6)
    if not card_str:
        ph = QLabel("—")
        ph.setStyleSheet(f"color:{_C_MUTED};font-size:13px;padding:8px;")
        row.addWidget(ph)
        return row
    tokens: list[str] = []
    i = 0
    while i < len(card_str) - 1:
        if card_str[i].isspace():
            i += 1; continue
        tokens.append(card_str[i:i+2])
        i += 2
    for tok in tokens:
        row.addWidget(CardView(tok))
    row.addStretch(1)
    return row


class HandReviewDialog(QDialog):
    """Single-hand summary view shown from the tournament archive."""
    drill_requested = Signal(dict)

    def _open_frame_replay(self) -> None:
        """Open the frame-by-frame replay dialog for this hand."""
        from app.ui.components.hand_frame_replay import HandFrameReplayDialog
        dlg = HandFrameReplayDialog(self, self._hand)
        dlg.exec()

    def __init__(self, parent: Optional[QWidget], hand_record: dict,
                 tournament_name: str = ""):
        super().__init__(parent)
        self.setWindowTitle(f"El #{hand_record.get('hand_no', '?')} — Review")
        self.setMinimumSize(760, 540)
        self.setStyleSheet(f"QDialog{{background:{_C_BG};}}")
        self._hand = hand_record

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(14)

        # ── Header ─────────────────────────────────────────────────
        delta = (hand_record.get("hero_stack_out", 0)
                 - hand_record.get("hero_stack_in", 0))
        sign = "+" if delta >= 0 else ""
        head = QHBoxLayout()
        title = QLabel(
            f"🃏  El #{hand_record.get('hand_no', '?')}"
            + (f"   ·   {tournament_name}" if tournament_name else "")
        )
        title.setStyleSheet(f"color:{_C_TEXT};font-size:18px;font-weight:800;")
        head.addWidget(title)
        head.addStretch(1)
        won = hand_record.get("hero_won", False)
        if won:
            badge = QLabel(f"🏆  KAZANDI  ·  {sign}{delta:,.0f}")
            badge.setStyleSheet(
                f"background:#0E2A1E;color:#6EE7B7;font-size:13px;font-weight:800;"
                f"padding:8px 14px;border-radius:6px;border:1px solid #10B981;"
            )
        else:
            badge = QLabel(f"❌  KAYBETTİ  ·  {sign}{delta:,.0f}")
            badge.setStyleSheet(
                f"background:#2A0E0E;color:#FCA5A5;font-size:13px;font-weight:800;"
                f"padding:8px 14px;border-radius:6px;border:1px solid #7F1D1D;"
            )
        head.addWidget(badge)
        root.addLayout(head)

        # ── Stat row ───────────────────────────────────────────────
        stats = QHBoxLayout()
        stats.setSpacing(10)
        stats.addWidget(_stat_pill("LEVEL",
                                    f"L{hand_record.get('level', 1)}", _C_TEXT))
        stats.addWidget(_stat_pill("BLINDS",
                                    str(hand_record.get('blinds', '—')), _C_TEXT))
        stats.addWidget(_stat_pill("POS",
                                    hand_record.get('hero_pos', '?'), _C_CYAN))
        stats.addWidget(_stat_pill("POT",
                                    f"{hand_record.get('pot_final', 0):,.0f}", "#F59E0B"))
        stats.addWidget(_stat_pill("STACK IN",
                                    f"{hand_record.get('hero_stack_in', 0):,.0f}", _C_TEXT))
        stats.addWidget(_stat_pill("STACK OUT",
                                    f"{hand_record.get('hero_stack_out', 0):,.0f}",
                                    _C_GREEN if delta >= 0 else _C_RED))
        stats.addStretch(1)
        root.addLayout(stats)

        # ── Hero cards ─────────────────────────────────────────────
        hero_block = QFrame()
        hero_block.setStyleSheet(
            f"QFrame{{background:{_C_PANEL};border:1px solid {_C_BORDER};border-radius:8px;}}"
        )
        hero_layout = QVBoxLayout(hero_block)
        hero_layout.setContentsMargins(16, 12, 16, 12)
        hero_layout.addWidget(_section_label("ELİN"))
        hero_layout.addLayout(_card_row(hand_record.get("hero_cards", "")))
        root.addWidget(hero_block)

        # ── Board ──────────────────────────────────────────────────
        board_block = QFrame()
        board_block.setStyleSheet(
            f"QFrame{{background:{_C_PANEL};border:1px solid {_C_BORDER};border-radius:8px;}}"
        )
        board_layout = QVBoxLayout(board_block)
        board_layout.setContentsMargins(16, 12, 16, 12)
        board_layout.addWidget(_section_label("BOARD"))
        board_layout.addLayout(_card_row(hand_record.get("board", "")))
        root.addWidget(board_block)

        # ── Action log (action-by-action replay) ───────────────────
        actions = hand_record.get("actions") or []
        if actions:
            action_block = QFrame()
            action_block.setStyleSheet(
                f"QFrame{{background:{_C_PANEL};border:1px solid {_C_BORDER};border-radius:8px;}}"
            )
            al = QVBoxLayout(action_block)
            al.setContentsMargins(16, 12, 16, 12)
            al.setSpacing(2)
            al.addWidget(_section_label("AKSİYON GEÇMİŞİ"))
            current_street = None
            for a in actions:
                street = a.get("street", "?")
                if street != current_street:
                    current_street = street
                    sl = QLabel(f"  ▸ {street.title()}")
                    sl.setStyleSheet(
                        f"color:{_C_CYAN};font-size:11px;font-weight:800;"
                        f"padding-top:4px;background:transparent;"
                    )
                    al.addWidget(sl)
                verb = a.get("action", "?").upper()
                amount = a.get("amount", 0)
                pos = a.get("pos", "?")
                name = a.get("name", "?")
                if len(name) > 14:
                    name = name[:13] + "…"
                amt_str = f" {amount:.0f}" if amount else ""
                line = QLabel(
                    f"      {pos:>4} · {name:<14}  →  {verb}{amt_str}"
                )
                line.setStyleSheet(
                    f"color:{_C_TEXT};font-size:11px;background:transparent;"
                    f"font-family:'SF Mono', Monaco, monospace;"
                )
                al.addWidget(line)
            root.addWidget(action_block)

        # ── Showdown / coach blurb (if any) ────────────────────────
        showdown = hand_record.get("showdown", "")
        if showdown:
            sd = QLabel(f"🎴 Showdown: {showdown}")
            sd.setStyleSheet(f"color:{_C_MUTED};font-size:12px;padding:4px 0;")
            root.addWidget(sd)

        root.addStretch(1)

        # ── Footer buttons ─────────────────────────────────────────
        footer = QHBoxLayout()
        # Replay button — frame-by-frame animation
        if actions:
            replay = QPushButton("🎬  Frame-by-frame Replay")
            replay.setFixedHeight(38)
            replay.setStyleSheet(
                f"QPushButton{{background:#0E2A1E;color:#6EE7B7;"
                f"border:1px solid #10B981;border-radius:7px;padding:0 18px;"
                f"font-size:12px;font-weight:700;}}"
                f"QPushButton:hover{{background:#0F3320;color:#34D399;}}"
            )
            replay.clicked.connect(self._open_frame_replay)
            footer.addWidget(replay)

        drill = QPushButton("🎯  Bu Spotu Drill Et")
        drill.setFixedHeight(38)
        drill.setStyleSheet(
            f"QPushButton{{background:{_C_CYAN};color:#061018;border:none;"
            f"border-radius:7px;padding:0 22px;font-size:13px;font-weight:800;}}"
            f"QPushButton:hover{{background:#0EA9C2;}}"
        )
        drill.clicked.connect(lambda: (self.drill_requested.emit(self._hand), self.accept()))
        footer.addWidget(drill)
        footer.addStretch(1)
        close = QPushButton("Kapat")
        close.setFixedHeight(38)
        close.setStyleSheet(
            f"QPushButton{{background:{_C_PANEL};color:{_C_TEXT};"
            f"border:1px solid {_C_BORDER};border-radius:7px;padding:0 22px;}}"
            f"QPushButton:hover{{border-color:{_C_CYAN};color:{_C_CYAN};}}"
        )
        close.clicked.connect(self.accept)
        footer.addWidget(close)
        root.addLayout(footer)
