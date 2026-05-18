"""Welcome / Home — Poke brutalist editorial.

Rewritten to use the Poke design system primitives (PokePageHeader,
PokeCard, PokeStat, PokeBtn, PokeTag). All content + behaviour
preserved; only the visual language changes.

The legacy `_BigCard` / `_StatCard` / `_QuickLink` classes are kept as
public symbols so external tooling (ui_simulator) can still findChildren
on them — they just delegate to the new Poke widgets under the hood.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.core.app_state import AppState
from app.ui.components.poke import (
    PokeBtn, PokeCard, PokePageHeader, PokeStat, PokeTag,
)
from app.ui.theme import poke_tokens as t


# ─── Back-compat classes (used by ui_simulator.findChildren) ─────────


class _BigCard(QFrame):
    """Big 'click-to-start' card. Public for ui_simulator compatibility.

    Renders with Poke brutalist styling: dark surface, 1px hairline
    border, 0 radius, accent-coloured left rule, mono uppercase eyebrow
    + display title + body + CTA button at the bottom.
    """
    clicked = Signal(str)

    def __init__(self, icon: str, title: str, subtitle: str,
                 cta: str, target: str, accent: str = None):
        super().__init__()
        self._target = target
        self.setObjectName("BigCard")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setMinimumSize(280, 320)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        accent_col = accent or t.ACCENT
        self.setStyleSheet(
            f"#BigCard {{ background: {t.SURFACE}; "
            f"border: 1px solid {t.LINE_2}; "
            f"border-left: 3px solid {accent_col}; }}"
            f"#BigCard:hover {{ background: {t.SURFACE_2}; }}"
        )

        v = QVBoxLayout(self)
        v.setContentsMargins(24, 22, 24, 22)
        v.setSpacing(0)

        # Eyebrow — small mono label above icon
        eyebrow = QLabel("▸  START HERE".upper())
        eyebrow.setStyleSheet(
            f"color: {t.MUTED}; background: transparent; "
            f"font-family: 'JetBrains Mono'; font-size: 10px; "
            f"font-weight: 500;"
        )
        v.addWidget(eyebrow)
        v.addSpacing(10)

        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet(
            f"font-size: 36px; background: transparent; "
            f"color: {accent_col};"
        )
        v.addWidget(icon_lbl)
        v.addSpacing(14)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"color: {t.INK}; background: transparent; "
            f"font-family: 'Space Grotesk'; font-weight: 700; "
            f"font-size: 24px;"
        )
        v.addWidget(title_lbl)
        v.addSpacing(8)

        sub_lbl = QLabel(subtitle)
        sub_lbl.setWordWrap(True)
        sub_lbl.setMinimumHeight(64)
        sub_lbl.setStyleSheet(
            f"color: {t.INK_2}; background: transparent; "
            f"font-family: 'Space Grotesk'; font-size: 13px;"
        )
        v.addWidget(sub_lbl)
        v.addStretch(1)

        # CTA — use a PokeBtn under primary variant for the canonical look
        btn = PokeBtn(cta, variant="primary", size="md", block=True)
        btn.clicked.connect(lambda: self.clicked.emit(self._target))
        v.addWidget(btn)

    def mousePressEvent(self, event) -> None:
        # Click anywhere on the card → navigate (mouse alternative)
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._target)
        super().mousePressEvent(event)


class _StatCard(QFrame):
    """Small KPI cell — kept for back-compat. Internally just a PokeStat
    wrapped in a QFrame with the same public attrs."""

    def __init__(self, label: str, value: str, accent: str = None):
        super().__init__()
        self.setObjectName("StatCard")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedHeight(88)
        self.setMinimumWidth(140)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        # Render via PokeStat but compact (no delta/sub).
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        stat = PokeStat(label, value)
        v.addWidget(stat)


class _QuickLink(QPushButton):
    """Sidebar-quick-nav tile. Brutalist: hairline border, left-rule
    flips to accent on hover."""

    def __init__(self, icon: str, label: str, target: str):
        super().__init__(f"  {icon}   {label}")
        self.setObjectName("QuickLink")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._target = target
        self.setMinimumHeight(46)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet(
            f"#QuickLink {{"
            f"  background: {t.BG_2}; color: {t.INK_2};"
            f"  border: 1px solid {t.LINE}; border-left: 2px solid {t.LINE_2};"
            f"  font-family: 'Space Grotesk'; font-size: 13px; "
            f"  font-weight: 500; padding: 0 14px; text-align: left;"
            f"}}"
            f"#QuickLink:hover {{"
            f"  background: {t.SURFACE}; color: {t.ACCENT};"
            f"  border-color: {t.LINE_2}; border-left-color: {t.ACCENT};"
            f"}}"
        )


# ─── Main Welcome screen ─────────────────────────────────────────────


class WelcomeScreen(QWidget):
    """Brutalist editorial entry surface — Poke design system.

    Layout:
      ┌─────────────────────────────────────────────────────────┐
      │ 00 / WELCOME                                            │
      │ Sharpen your <em>edge</em>.                  [Drill ▶] │
      │ A GTO-backed offline trainer.                            │
      ╞═════════════════════════════════════════════════════════╡
      │ ▸ START HERE                                            │
      │ [GTO Trainer]  [Spot Practice]  [Play Table]            │
      │                                                          │
      │ ▸ DAILY CONCEPT                                         │
      │ [Glossary card]                                          │
      │                                                          │
      │ ▸ PROGRESS                                              │
      │ [Drills] [Acc] [Open Leaks] [Drilled] [Tour]            │
      │                                                          │
      │ ▸ RECENT TOURNAMENTS                                    │
      │ [tour row × 5]                                           │
      │                                                          │
      │ ▸ QUICK LINKS                                           │
      │ [3 × 4 grid of nav tiles]                                │
      └─────────────────────────────────────────────────────────┘
    """
    navigate_requested = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self._state = state
        self.setObjectName("WelcomeRoot")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(f"#WelcomeRoot {{ background: {t.BG}; }}")

        # ── Scroll wrapper ───────────────────────────────────────────
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(
            f"QScrollArea {{ background: {t.BG}; border: 0; }}"
            f"QScrollBar:vertical {{ width: 8px; background: transparent; }}"
            f"QScrollBar::handle:vertical {{ background: {t.LINE_2}; }}"
        )
        content = QWidget()
        content.setStyleSheet(f"QWidget {{ background: {t.BG}; }}")
        scroll.setWidget(content)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll, 1)

        root = QVBoxLayout(content)
        root.setContentsMargins(t.PAGE_PAD, t.PAGE_PAD, t.PAGE_PAD, 48)
        root.setSpacing(28)

        # ── Page header ──────────────────────────────────────────────
        header_action = PokeBtn("Drill now", variant="primary", size="md", kbd="↵")
        header_action.clicked.connect(
            lambda: self.navigate_requested.emit("Spot Practice Trainer")
        )
        header = PokePageHeader(
            num="00 / Welcome",
            title="Sharpen your <em>edge</em>.",
            sub=("A GTO-backed offline poker trainer. Drill solver-verified "
                 "spots, get coached on your own hands, watch your leaks close."),
            actions=header_action,
        )
        root.addWidget(header)

        # ── ▸ START HERE — 3 big cards ───────────────────────────────
        root.addWidget(self._kicker("▸  START HERE"))
        cards_row = QHBoxLayout()
        cards_row.setSpacing(14)

        learn = _BigCard(
            "◆", "GTO Trainer",
            "A 13×13 range matrix and a 325-spot library. See the GTO "
            "frequency for every hand by position and pot type.",
            "OPEN GTO TRAINER", "Range Studio", t.ACCENT,
        )
        learn.clicked.connect(self.navigate_requested)
        cards_row.addWidget(learn)

        practice = _BigCard(
            "▲", "Spot Practice",
            "See a hand, make a call: FOLD / CALL / RAISE / JAM. Instant "
            "feedback with the per-option GTO frequency bar.",
            "OPEN SPOTS", "Spot Practice Trainer", t.INFO,
        )
        practice.clicked.connect(self.navigate_requested)
        cards_row.addWidget(practice)

        play = _BigCard(
            "●", "Play a Table",
            "Real hands against bots. Button rotation, blinds, side-pots, "
            "showdowns — the full poker loop in BB-native sizing.",
            "TAKE A SEAT", "Play Session", t.WARN,
        )
        play.clicked.connect(self.navigate_requested)
        cards_row.addWidget(play)

        root.addLayout(cards_row)

        # ── ▸ DAILY CONCEPT (glossary term of the day) ───────────────
        try:
            from datetime import date
            from app.data.poker_glossary import GLOSSARY
            seed_idx = date.today().toordinal() % len(GLOSSARY)
            term = GLOSSARY[seed_idx]
            root.addWidget(self._kicker("▸  DAILY CONCEPT"))
            card = PokeCard(
                title=term["term"].upper(),
                num="◇",
                sub="GLOSSARY",
                action=PokeBtn("Open glossary", variant="ghost", size="sm",
                                on_click=lambda: self.navigate_requested.emit("Knowledge Base")),
            )
            body = QLabel(term.get("short", "")[:240])
            body.setWordWrap(True)
            body.setStyleSheet(
                f"color: {t.INK_2}; background: transparent; "
                f"font-family: 'Space Grotesk'; font-size: 14px;"
            )
            card.add_to_body(body)
            root.addWidget(card)
        except Exception:
            pass

        # ── ▸ PROGRESS (5 stats) ─────────────────────────────────────
        root.addWidget(self._kicker("▸  PROGRESS"))

        # Pull live data
        drills_v = str(state.completed_drills) if state.completed_drills else "0"
        acc_v    = f"{state.accuracy:.0f}" if state.accuracy else "—"
        try:
            from app.db.mistakes_queue import load_mistakes
            mistakes = load_mistakes()
            open_leaks    = sum(1 for m in mistakes if not m.drilled)
            drilled_leaks = sum(1 for m in mistakes if m.drilled)
            leaks_v   = str(open_leaks)
            drilled_v = str(drilled_leaks)
        except Exception:
            leaks_v = "—"; drilled_v = "—"
        try:
            from app.db.tournament_archive import load_archive
            archive = load_archive()
            tours_v = str(len(archive)) if archive else "0"
        except Exception:
            tours_v = "—"

        stat_row = QHBoxLayout()
        stat_row.setSpacing(10)
        # Use _StatCard (which wraps PokeStat) so ui_simulator.findChildren
        # still works — audit expects ≥ 3 _StatCard instances on Welcome.
        for label, val in [
            ("Drills",        drills_v),
            ("Accuracy",      acc_v),
            ("Open leaks",    leaks_v),
            ("Drilled leaks", drilled_v),
            ("Tournaments",   tours_v),
        ]:
            stat_row.addWidget(_StatCard(label, val))
        root.addLayout(stat_row)

        # ── ▸ RECENT TOURNAMENTS ─────────────────────────────────────
        try:
            from app.db.tournament_archive import load_archive
            recent = load_archive()[:5]
        except Exception:
            recent = []
        if recent:
            root.addWidget(self._kicker("▸  RECENT TOURNAMENTS"))
            for r in recent:
                row = self._tournament_row(r)
                root.addWidget(row)

        # ── ▸ QUICK LINKS ────────────────────────────────────────────
        root.addWidget(self._kicker("▸  QUICK LINKS"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        links = [
            ("♔", "Tournament Play", "Tournament Play Mode"),
            ("⚔", "Heads-Up",        "Heads-Up Trainer"),
            ("⚡", "Fast Play",       "Fast Play Simulator"),
            ("☷", "Study Library",   "GTO Study Library"),
            ("✧", "Drills",          "Drills"),
            ("⚗", "Hand Analyzer",   "Hand History Analyzer"),
            ("⊕", "Leak Finder",     "Leak Finder"),
            ("◈", "ICM / PKO",       "ICM / PKO Trainer"),
            ("≋", "Postflop",        "Postflop Trainer"),
            ("⌖", "River",           "River Decision Trainer"),
            ("⊙", "AI Coach",        "AI Poker Coach"),
            ("▭", "Reports",         "Reports"),
        ]
        cols = 4
        for idx, (icon, label, target) in enumerate(links):
            btn = _QuickLink(icon, label, target)
            btn.clicked.connect(
                lambda _=False, tgt=target: self.navigate_requested.emit(tgt))
            grid.addWidget(btn, idx // cols, idx % cols)
        root.addLayout(grid)

        root.addStretch(1)

    # ── helpers ──────────────────────────────────────────────────────

    def _kicker(self, text: str) -> QLabel:
        """Small uppercase JetBrains-Mono section kicker."""
        lbl = QLabel(text.upper())
        lbl.setStyleSheet(
            f"color: {t.ACCENT}; background: transparent; "
            f"font-family: 'JetBrains Mono'; font-size: 11px; "
            f"font-weight: 600; padding-top: 6px;"
        )
        return lbl

    def _tournament_row(self, r) -> QFrame:
        """One pill-row per recent tournament."""
        f = QFrame()
        f.setAttribute(Qt.WA_StyledBackground, True)
        side = t.ACCENT if r.cashed else t.DANGER_2
        f.setStyleSheet(
            f"QFrame {{ background: {t.SURFACE}; "
            f"border: 1px solid {t.LINE}; border-left: 3px solid {side}; }}"
        )
        f.setMinimumHeight(44)
        h = QHBoxLayout(f)
        h.setContentsMargins(14, 8, 14, 8)
        h.setSpacing(14)

        # Status tag
        status_tag = PokeTag("ITM" if r.cashed else "BUST",
                              tone="g" if r.cashed else "r", dot=True)
        h.addWidget(status_tag)

        # Name + finish
        name_lbl = QLabel(r.tournament_name)
        name_lbl.setStyleSheet(
            f"color: {t.INK}; background: transparent; "
            f"font-family: 'Space Grotesk'; font-size: 13px; font-weight: 600;"
        )
        h.addWidget(name_lbl)

        finish_lbl = QLabel(f"#{r.finish_position} / {r.field_size}")
        finish_lbl.setStyleSheet(
            f"color: {t.MUTED}; background: transparent; "
            f"font-family: 'JetBrains Mono'; font-size: 11px;"
        )
        h.addWidget(finish_lbl)

        h.addStretch(1)

        # ROI + accuracy
        roi_lbl = QLabel(f"ROI {r.roi_pct:+.1f}%")
        roi_col = t.ACCENT if r.roi_pct >= 0 else t.DANGER_2
        roi_lbl.setStyleSheet(
            f"color: {roi_col}; background: transparent; "
            f"font-family: 'JetBrains Mono'; font-size: 12px; font-weight: 600;"
        )
        h.addWidget(roi_lbl)

        acc_lbl = QLabel(f"acc {r.accuracy}%")
        acc_lbl.setStyleSheet(
            f"color: {t.MUTED}; background: transparent; "
            f"font-family: 'JetBrains Mono'; font-size: 11px;"
        )
        h.addWidget(acc_lbl)

        # Clickable → tournament play mode
        f.mousePressEvent = (
            lambda _e: self.navigate_requested.emit("Tournament Play Mode")
        )
        f.setCursor(Qt.PointingHandCursor)
        return f
