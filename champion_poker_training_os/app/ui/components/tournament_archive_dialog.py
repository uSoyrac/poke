"""TournamentArchiveDialog — Poke-styled card-per-tournament archive.

Replaces the legacy QListWidget pop-up with editorial Poke cards:

    ┌─ 04 / 2026-05-19 14:32 ──────────────────── ITM #38 / 100 ─┐
    │ Online Turbo Low Stakes  ·  $50 buy-in                    │
    │ ROI +260%   ·   accuracy 71%   ·   EV-loss 18.4bb          │
    │                                                            │
    │ ▸ TOP LEAKS                                                │
    │   BTN / SRP / fold     -12.4bb  · 4 mistakes               │
    │   BB  / 3BP / call     -4.8bb   · 2 mistakes               │
    │                                                            │
    │  ──────────────────────────────────────────────────────    │
    │  [Replay hands]  [Drill these leaks]                       │
    └────────────────────────────────────────────────────────────┘
"""
from __future__ import annotations

from collections import Counter
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget,
)

from app.db.tournament_archive import TournamentRecord, load_archive
from app.ui.components.poke import (
    PokeBtn, PokeCard, PokePageHeader, PokeTag,
)
from app.ui.theme import poke_tokens as t


def _grotesk(text: str, color: str, size: int = 12, weight: int = 500,
              wrap: bool = False) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {color}; background: transparent; "
        f"font-family: 'Space Grotesk'; font-weight: {weight}; "
        f"font-size: {size}px;"
    )
    if wrap:
        lbl.setWordWrap(True)
    return lbl


def _mono(text: str, color: str, size: int = 10, weight: int = 500) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {color}; background: transparent; "
        f"font-family: 'JetBrains Mono'; font-weight: {weight}; "
        f"font-size: {size}px;"
    )
    return lbl


def _summarise_leaks(record: TournamentRecord) -> list[tuple[str, float, int]]:
    """Group notable_mistakes by leak signature → list of (sig, ev, count)."""
    bucket: dict[str, dict] = {}
    for m in record.notable_mistakes or []:
        sig = (
            f"{(m.get('position') or '?').upper()} / "
            f"{(m.get('pot_type') or 'SRP').upper()} / "
            f"{(m.get('hero_action') or '?').lower()}"
        )
        b = bucket.setdefault(sig, {"ev": 0.0, "count": 0})
        b["ev"] += abs(float(m.get("ev_loss") or 0))
        b["count"] += 1
    out = [(sig, round(d["ev"], 1), int(d["count"])) for sig, d in bucket.items()]
    out.sort(key=lambda x: x[1], reverse=True)
    return out[:3]


class _TournamentCard(PokeCard):
    """One Poke card per archived tournament."""

    replay_requested = Signal(object)        # emits TournamentRecord
    drill_requested  = Signal(object)        # emits TournamentRecord

    def __init__(self, idx: int, record: TournamentRecord, parent=None):
        # Header: section number + tournament name + ITM/Bust tag
        finish_tag = PokeTag(
            f"ITM #{record.finish_position} / {record.field_size}"
            if record.cashed
            else f"BUST #{record.finish_position}",
            tone="g" if record.cashed else "r",
            dot=True,
        )
        super().__init__(
            title=record.tournament_name,
            num=f"{idx:02d} / {record.ended_at[:10]}",
            sub=f"${record.buyin:.0f} BUY-IN  ·  {record.field_size} PLAYERS",
            action=finish_tag,
            parent=parent,
        )
        self.body_layout().setSpacing(10)
        self._record = record

        # Stat row — ROI / accuracy / EV-loss / hands
        stat_row = QHBoxLayout()
        stat_row.setSpacing(18)
        for label, value, tone in [
            (
                "ROI",
                f"{record.roi_pct:+.0f}%",
                "g" if record.roi_pct >= 0 else "r",
            ),
            ("ACCURACY", f"{record.accuracy:.0f}%", "neutral"),
            ("EV LOSS",  f"{record.total_ev_loss:.1f}bb", "y"),
            ("HANDS",    str(record.hands_played), "neutral"),
        ]:
            col = QVBoxLayout()
            col.setSpacing(2)
            col.addWidget(_mono(label, t.MUTED, size=9))
            color = {
                "g": t.ACCENT, "r": t.DANGER_2, "y": t.WARN,
                "neutral": t.INK,
            }.get(tone, t.INK)
            v = QLabel(value)
            v.setStyleSheet(
                f"color: {color}; background: transparent; "
                f"font-family: 'Space Grotesk'; font-weight: 700; "
                f"font-size: 18px;"
            )
            col.addWidget(v)
            stat_row.addLayout(col)
        stat_row.addStretch(1)
        self.add_layout_to_body(stat_row)

        # Top-leaks block
        leaks = _summarise_leaks(record)
        if leaks:
            eyebrow = _mono("▸  TOP LEAKS", t.MUTED, size=10)
            self.add_to_body(eyebrow)
            for sig, ev, cnt in leaks:
                row = QFrame()
                row.setAttribute(Qt.WA_StyledBackground, True)
                row.setObjectName("ArchiveLeakRow")
                row.setStyleSheet(
                    f"#ArchiveLeakRow {{ background: transparent; "
                    f"border-top: 1px solid {t.LINE}; }}"
                )
                rl = QHBoxLayout(row)
                rl.setContentsMargins(0, 6, 0, 6)
                rl.setSpacing(12)
                sig_lbl = _mono(sig, t.ACCENT, size=11, weight=600)
                sig_lbl.setFixedWidth(180)
                rl.addWidget(sig_lbl)
                rl.addWidget(_mono(f"{cnt} mistakes", t.MUTED, size=10), 1)
                ev_lbl = QLabel(f"-{ev:.1f}bb")
                ev_lbl.setStyleSheet(
                    f"color: {t.DANGER_2}; background: transparent; "
                    f"font-family: 'JetBrains Mono'; font-weight: 700; "
                    f"font-size: 13px;"
                )
                rl.addWidget(ev_lbl)
                self.add_to_body(row)
        else:
            self.add_to_body(_grotesk(
                "Bu turnuvada notable mistake yok — temiz oyun.",
                t.MUTED, size=12, wrap=True,
            ))

        # Action row
        actions = QHBoxLayout()
        actions.setSpacing(8)
        replay = PokeBtn("View hands", variant="default", size="sm",
                          kbd="V")
        replay.clicked.connect(
            lambda: self.replay_requested.emit(self._record))
        actions.addWidget(replay)
        if leaks:
            drill = PokeBtn("Drill these leaks", variant="primary",
                              size="sm", kbd="D")
            drill.clicked.connect(
                lambda: self.drill_requested.emit(self._record))
            actions.addWidget(drill)
        actions.addStretch(1)
        self.add_layout_to_body(actions)


class TournamentArchiveDialog(QDialog):
    """Modal archive viewer. Connect `hand_history_requested` and
    `drill_pack_requested` to wire Replay / Drill actions back to the
    Tournament Play screen."""

    hand_history_requested = Signal(object)  # emits TournamentRecord
    drill_pack_requested   = Signal(object)  # emits TournamentRecord

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Tournament archive")
        self.setModal(True)
        self.setMinimumSize(820, 640)
        self.setStyleSheet(
            f"QDialog {{ background: {t.BG}; }}"
            f"QLabel {{ color: {t.INK}; background: transparent; }}"
        )

        records = load_archive()

        # Aggregate summary stats across all tournaments
        cashed = sum(1 for r in records if r.cashed)
        total_buy = sum(r.buyin for r in records)
        total_payout = sum(r.payout for r in records)
        net = total_payout - total_buy

        root = QVBoxLayout(self)
        root.setContentsMargins(t.PAGE_PAD, t.PAGE_PAD, t.PAGE_PAD, 24)
        root.setSpacing(16)

        # Page header — single sentence summary of the user's archive
        sub_bits = []
        if records:
            sub_bits.append(f"{len(records)} tournaments")
            sub_bits.append(f"{cashed} ITM")
            sub_bits.append(f"net ${net:+.0f}")
        else:
            sub_bits.append("no completed tournaments yet")
        root.addWidget(PokePageHeader(
            num="11 / Archive",
            title="Review your <em>runs</em>.",
            sub=" · ".join(sub_bits),
        ))

        # Empty state
        if not records:
            empty = _grotesk(
                "Henüz bir turnuva tamamlanmamış. Tournament Play Mode'a "
                "git, ▶ New Tournament ile başla. Bust ya da ITM olunca "
                "burada görünecek.",
                t.MUTED, size=14, wrap=True,
            )
            root.addWidget(empty, 1)
        else:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            inner = QWidget()
            iv = QVBoxLayout(inner)
            iv.setContentsMargins(0, 0, 0, 0)
            iv.setSpacing(12)
            for idx, r in enumerate(records, start=1):
                card = _TournamentCard(idx, r)
                card.replay_requested.connect(self.hand_history_requested)
                card.drill_requested.connect(self.drill_pack_requested)
                iv.addWidget(card)
            iv.addStretch(1)
            scroll.setWidget(inner)
            root.addWidget(scroll, 1)

        # Footer — close
        footer = QHBoxLayout()
        footer.setSpacing(10)
        footer.addStretch(1)
        close = PokeBtn("Close", variant="ghost", size="md", kbd="Esc")
        close.clicked.connect(self.accept)
        footer.addWidget(close)
        root.addLayout(footer)
