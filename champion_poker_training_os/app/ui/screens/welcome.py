"""WelcomeScreen — first-run / launch landing.

Master-coach style onboarding:
  • 3-step workflow callouts (Learn → Practice → Play)
  • Today's recommended training (from DrillGeneratorAgent + recent leaks)
  • Skill score + streak progress
  • Quick links to every training surface with one-line explanations

Built to be the user's "home base" — they should always know what to do next.
"""
from __future__ import annotations

from typing import Optional

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

from app.agents import AgentOrchestrator, DrillGeneratorAgent, LeakDetectionAgent
from app.core.app_state import AppState

_C_BG     = "#0A0E14"
_C_CARD   = "#0F141C"
_C_PANEL  = "#131A24"
_C_BORDER = "#1E2733"
_C_TEXT   = "#E5E7EB"
_C_MUTED  = "#6B7280"
_C_CYAN   = "#22D3EE"
_C_GREEN  = "#10B981"
_C_AMBER  = "#F59E0B"


class _ActionCard(QFrame):
    """Large clickable card with icon, title, description, and CTA button."""
    clicked = Signal(str)  # emits the nav target

    def __init__(self, icon: str, title: str, description: str,
                 cta_label: str, nav_target: str, primary: bool = False):
        super().__init__()
        self._target = nav_target
        self.setFrameShape(QFrame.NoFrame)
        self.setMinimumHeight(180)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        border = _C_GREEN if primary else _C_BORDER
        self.setStyleSheet(
            f"QFrame{{background:{_C_PANEL};border:2px solid {border};border-radius:12px;}}"
            f"QFrame:hover{{border-color:{_C_CYAN};}}"
        )
        v = QVBoxLayout(self)
        v.setContentsMargins(20, 18, 20, 18)
        v.setSpacing(10)

        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet("font-size:36px;")
        v.addWidget(icon_lbl)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"color:{_C_TEXT};font-size:18px;font-weight:800;")
        v.addWidget(title_lbl)

        desc_lbl = QLabel(description)
        desc_lbl.setStyleSheet(f"color:{_C_MUTED};font-size:12px;")
        desc_lbl.setWordWrap(True)
        v.addWidget(desc_lbl)

        v.addStretch(1)

        cta = QPushButton(cta_label)
        cta.setFixedHeight(40)
        if primary:
            cta.setStyleSheet(
                f"QPushButton{{background:{_C_GREEN};color:#000;border:none;"
                "border-radius:8px;font-weight:800;font-size:13px;padding:6px 16px;}}"
                "QPushButton:hover{background:#0EA371;}"
            )
        else:
            cta.setStyleSheet(
                f"QPushButton{{background:{_C_PANEL};color:{_C_TEXT};"
                f"border:1px solid {_C_BORDER};border-radius:8px;"
                "font-weight:700;font-size:13px;padding:6px 16px;}}"
                f"QPushButton:hover{{border-color:{_C_CYAN};color:{_C_CYAN};}}"
            )
        cta.clicked.connect(lambda: self.clicked.emit(self._target))
        v.addWidget(cta)


class _MiniMetric(QFrame):
    """Compact stat card for top KPI row."""
    def __init__(self, label: str, value: str, accent: str = _C_CYAN):
        super().__init__()
        self.setFrameShape(QFrame.NoFrame)
        self.setMinimumHeight(100)
        self.setStyleSheet(
            f"QFrame{{background:{_C_PANEL};border:1px solid {_C_BORDER};border-radius:10px;}}"
        )
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 14, 16, 14)
        v.setSpacing(6)
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color:{_C_MUTED};font-size:11px;font-weight:600;letter-spacing:1px;text-transform:uppercase;")
        val = QLabel(value)
        val.setStyleSheet(f"color:{accent};font-size:26px;font-weight:800;")
        v.addWidget(lbl)
        v.addWidget(val)


class WelcomeScreen(QWidget):
    """Onboarding home screen — guides user to next action."""

    coach_message = Signal(str)
    navigate_requested = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.orchestrator = AgentOrchestrator()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        scroll.setWidget(body)
        root_l = QVBoxLayout(self)
        root_l.setContentsMargins(0, 0, 0, 0)
        root_l.addWidget(scroll)

        layout = QVBoxLayout(body)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        # ── Hero header ────────────────────────────────────────────────
        hero = QFrame()
        hero.setStyleSheet(
            f"QFrame{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"stop:0 #0F2A1E, stop:1 #0A1A2E);"
            f"border:1px solid {_C_BORDER};border-radius:14px;}}"
        )
        hv = QVBoxLayout(hero)
        hv.setContentsMargins(28, 24, 28, 24)
        hv.setSpacing(6)
        title = QLabel("🎯  Champion Poker Training OS")
        title.setStyleSheet(f"color:{_C_TEXT};font-size:26px;font-weight:800;")
        subtitle = QLabel("Master-level GTO training, drill packs, and post-session reviews — all offline.")
        subtitle.setStyleSheet(f"color:{_C_MUTED};font-size:13px;")
        hv.addWidget(title)
        hv.addWidget(subtitle)
        layout.addWidget(hero)

        # ── KPI row ────────────────────────────────────────────────────
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(12)
        kpi_row.addWidget(_MiniMetric("Drills completed", f"{state.completed_drills}", _C_CYAN))
        accuracy = f"{state.accuracy:.0f}%" if state.completed_drills > 0 else "—"
        kpi_row.addWidget(_MiniMetric("Accuracy", accuracy, _C_GREEN if state.accuracy >= 70 else _C_AMBER))
        kpi_row.addWidget(_MiniMetric("EV loss session", f"{state.ev_loss_total:.1f}bb", _C_AMBER))
        kpi_row.addWidget(_MiniMetric("Catalog size", "325", _C_CYAN))
        layout.addLayout(kpi_row)

        # ── 3-step workflow callouts ───────────────────────────────────
        steps_title = QLabel("Start training in 3 steps")
        steps_title.setStyleSheet(f"color:{_C_TEXT};font-size:18px;font-weight:700;")
        layout.addWidget(steps_title)

        steps_row = QHBoxLayout()
        steps_row.setSpacing(14)

        learn_card = _ActionCard(
            "📚", "1) Learn GTO Charts",
            "Browse pre-solved ranges for every position × stack × situation. "
            "13×13 matrix with EV / equity heatmaps.",
            "Open GTO Trainer  →", "GTO Trainer (Range View)",
            primary=False,
        )
        learn_card.clicked.connect(self.navigate_requested.emit)
        steps_row.addWidget(learn_card, 1)

        practice_card = _ActionCard(
            "🎯", "2) Practice Spots",
            "Drill 325 hand-crafted GTO spots with adaptive difficulty. "
            "Mistake queue, sizing options, real-time feedback.",
            "Start Drilling  →", "Spot Practice Trainer",
            primary=True,
        )
        practice_card.clicked.connect(self.navigate_requested.emit)
        steps_row.addWidget(practice_card, 1)

        play_card = _ActionCard(
            "🏆", "3) Play vs Bots",
            "Real Texas Hold'em — 2 to 11 players, full game engine, "
            "every decision reviewed against GTO.",
            "Start Tournament  →", "Tournament Play Mode",
            primary=False,
        )
        play_card.clicked.connect(self.navigate_requested.emit)
        steps_row.addWidget(play_card, 1)
        layout.addLayout(steps_row)

        # ── Personalized recommendation ────────────────────────────────
        reco_title = QLabel("💡  Recommended for you")
        reco_title.setStyleSheet(f"color:{_C_TEXT};font-size:18px;font-weight:700;")
        layout.addWidget(reco_title)

        reco = self._build_recommendation_panel()
        layout.addWidget(reco)

        # ── Full surface map ───────────────────────────────────────────
        surface_title = QLabel("All training surfaces")
        surface_title.setStyleSheet(f"color:{_C_TEXT};font-size:18px;font-weight:700;")
        layout.addWidget(surface_title)

        grid_w = QWidget()
        grid = QGridLayout(grid_w)
        grid.setSpacing(10)
        surfaces = [
            ("📊", "GTO Study Library",   "Browse spots by category + filter",      "GTO Study Library"),
            ("🃏", "Hand History Analyzer", "Import PokerStars/CoinPoker hands",     "Hand History Analyzer"),
            ("⚡",  "Fast Play Simulator", "Rapid-fire hands with shot clock",       "Fast Play Simulator"),
            ("🥊", "Heads-Up Trainer",     "1v1 with HU-specific ranges",           "Heads-Up Trainer"),
            ("💰", "ICM / PKO Trainer",    "Final table / bubble pressure spots",   "ICM / PKO Trainer"),
            ("📈", "Range Trainer",        "13×13 quiz with mistake-only mode",     "Preflop Range Trainer"),
            ("🔍", "Leak Finder",          "Auto-detect systemic mistakes",         "Leak Finder"),
            ("🤖", "AI Poker Coach",       "Master-level structured analysis",      "AI Poker Coach"),
            ("📚", "Knowledge Base",       "Concepts + theory deep-dives",          "Knowledge Base"),
            ("📅", "Study Planner",        "Multi-day training plans",              "Study Planner"),
            ("📋", "Reports",              "Weekly progress + position breakdown",  "Reports"),
            ("⚙️", "Settings",             "RTA guard + solver CSV import",         "Settings / Compliance Guard"),
        ]
        for i, (icon, name, desc, target) in enumerate(surfaces):
            chip = QPushButton(f"{icon}  {name}\n{desc}")
            chip.setMinimumHeight(64)
            chip.setStyleSheet(
                f"QPushButton{{background:{_C_PANEL};color:{_C_TEXT};"
                f"border:1px solid {_C_BORDER};border-radius:8px;"
                "text-align:left;padding:8px 14px;font-size:12px;font-weight:600;}}"
                f"QPushButton:hover{{border-color:{_C_CYAN};color:{_C_CYAN};}}"
            )
            chip.clicked.connect(lambda _c=False, t=target: self.navigate_requested.emit(t))
            grid.addWidget(chip, i // 3, i % 3)
        layout.addWidget(grid_w)
        layout.addStretch(1)

    # ── personalized recommendation card ──────────────────────────────────
    def _build_recommendation_panel(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame{{background:{_C_PANEL};border:1px solid {_C_BORDER};border-radius:12px;}}"
        )
        v = QVBoxLayout(frame)
        v.setContentsMargins(20, 18, 20, 18)
        v.setSpacing(10)

        # Get a leak summary via the agent (uses session_notes / completed drills)
        # If nothing tracked yet, suggest the BB defense pack as canonical start
        text = self._get_recommendation_text()
        body = QLabel(text)
        body.setStyleSheet(f"color:{_C_TEXT};font-size:13px;line-height:1.5;")
        body.setWordWrap(True)
        v.addWidget(body)

        btn_row = QHBoxLayout()
        b1 = QPushButton("Start recommended drill pack")
        b1.setFixedHeight(38)
        b1.setStyleSheet(
            f"QPushButton{{background:{_C_GREEN};color:#000;border:none;"
            "border-radius:8px;font-weight:700;padding:6px 18px;}}"
            "QPushButton:hover{background:#0EA371;}"
        )
        b1.clicked.connect(lambda: self.navigate_requested.emit("Spot Practice Trainer"))
        btn_row.addWidget(b1)

        b2 = QPushButton("View leaks")
        b2.setFixedHeight(38)
        b2.setStyleSheet(
            f"QPushButton{{background:{_C_PANEL};color:{_C_TEXT};"
            f"border:1px solid {_C_BORDER};border-radius:8px;"
            "font-weight:700;padding:6px 18px;}}"
            f"QPushButton:hover{{border-color:{_C_CYAN};color:{_C_CYAN};}}"
        )
        b2.clicked.connect(lambda: self.navigate_requested.emit("Leak Finder"))
        btn_row.addWidget(b2)

        b3 = QPushButton("Ask Master Coach")
        b3.setFixedHeight(38)
        b3.setStyleSheet(b2.styleSheet())
        b3.clicked.connect(lambda: self.navigate_requested.emit("AI Poker Coach"))
        btn_row.addWidget(b3)
        btn_row.addStretch(1)
        v.addLayout(btn_row)
        return frame

    def _get_recommendation_text(self) -> str:
        completed = self.state.completed_drills
        if completed == 0:
            return (
                "Yeni başlıyorsun. İlk önerim: <b>BB Defense vs BTN RFI 40bb</b> drill paketi. "
                "BB defansı kazançlı oyunun temelidir; bunu sağlam öğrendikten sonra diğer "
                "pozisyonlar daha hızlı oturur. Ardından <b>BTN Open-Raising 40bb</b> ile "
                "geniş aggression range'i çalış. Birlikte ~25 spot etmen yeter."
            )
        if completed < 30:
            return (
                f"{completed} spot çözdün. Şimdi <b>postflop cbet</b> mantığına ilerlemek "
                "için <b>Flop Strategy</b> kategorisindeki 20 spot iyi bir basamak. Range "
                "avantajı + nut advantage + texture üçlüsünü hissetmeye başlayacaksın."
            )
        if self.state.ev_loss_total > 5.0:
            return (
                f"Bu session'da {self.state.ev_loss_total:.1f}bb EV kaybettin. Leak Finder'a "
                "git, hangi spot tipinde takıldığını gör. Sonra hedefli bir drill paketiyle "
                "o spot tipini 10-15 kez tekrarla."
            )
        return (
            "Performansın iyi gidiyor. İlerleme için: <b>ICM / PKO Trainer</b>'a geç ve "
            "bubble + final table dinamiklerini çalış. Bu spotlar 1bb chipEV'den çok daha "
            "kıymetli kararlar içerir — turnuva ROI'ni en çok bunlar belirler."
        )
