from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout

from app.core.app_state import AppState
from app.core.rta_guard import RtaGuardStatus


class _Cell(QFrame):
    def __init__(self, title: str, value: str, accent: str = ""):
        super().__init__()
        self.setObjectName("TopCell")
        self.setStyleSheet("border-left: 1px solid #23271f;")
        l = QVBoxLayout(self)
        l.setContentsMargins(16, 6, 16, 6)
        l.setSpacing(2)
        self.title_lbl = QLabel(title)
        self.title_lbl.setObjectName("TLabel")
        self.value_lbl = QLabel(value)
        self.value_lbl.setObjectName(accent or "Mono")
        self.value_lbl.setStyleSheet("font-family: 'JetBrains Mono', Menlo, monospace; font-size: 12px;")
        l.addWidget(self.title_lbl)
        l.addWidget(self.value_lbl)

    def set_value(self, value: str, accent: str = "") -> None:
        self.value_lbl.setText(value)
        if accent:
            self.value_lbl.setObjectName(accent)
            self.value_lbl.style().unpolish(self.value_lbl)
            self.value_lbl.style().polish(self.value_lbl)


class _ExperienceToggle(QFrame):
    """Tıklanır hücre: Real Experience Mode aç/kapa.

    REAL (yeşil) = oyun sırasında GTO gizli, el sonu notlandırılmış reveal.
    TRAIN (muted) = eğitim modu, range bağlamı görünür.
    """

    toggled = Signal(bool)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.setObjectName("TopCell")
        self.setStyleSheet("border-left: 1px solid #23271f;")
        self.setCursor(Qt.PointingHandCursor)
        l = QVBoxLayout(self)
        l.setContentsMargins(16, 6, 16, 6)
        l.setSpacing(2)
        self.title_lbl = QLabel("DENEYİM MODU")
        self.title_lbl.setObjectName("TLabel")
        self.value_lbl = QLabel()
        self.value_lbl.setStyleSheet(
            "font-family: 'JetBrains Mono', Menlo, monospace; font-size: 12px;")
        l.addWidget(self.title_lbl)
        l.addWidget(self.value_lbl)
        self._render()

    def _render(self) -> None:
        on = bool(getattr(self.state, "real_experience", False))
        if on:
            self.value_lbl.setText("● REAL")
            self.value_lbl.setStyleSheet(
                "font-family:'JetBrains Mono',Menlo,monospace; font-size:12px; "
                "color:#5ad17a; font-weight:700;")
            self.setToolTip("Real Experience: oyun sırasında GTO ipucu YOK. "
                            "El sonu notlandırılmış reveal. Tıkla → eğitim moduna geç.")
        else:
            self.value_lbl.setText("○ TRAIN")
            self.value_lbl.setStyleSheet(
                "font-family:'JetBrains Mono',Menlo,monospace; font-size:12px; "
                "color:#898d80; font-weight:700;")
            self.setToolTip("Eğitim modu: GTO range bağlamı görünür. "
                            "Tıkla → gerçek deneyim moduna geç (ipuçları gizlenir).")

    def mousePressEvent(self, ev) -> None:   # noqa: N802 (Qt override)
        self.state.real_experience = not getattr(self.state, "real_experience", False)
        self._render()
        self.toggled.emit(self.state.real_experience)
        super().mousePressEvent(ev)


class ComplianceStatusBadge(QLabel):
    def __init__(self):
        super().__init__("STRICT")
        self.setObjectName("Green")
        self.setStyleSheet(
            "font-family: 'JetBrains Mono', Menlo, monospace; font-size: 11px;"
        )

    def set_status(self, status: RtaGuardStatus) -> None:
        self.setText(status.label.upper() if hasattr(status, "label") else "STRICT")
        self.setObjectName("Red" if status.locked else "Green")
        self.style().unpolish(self)
        self.style().polish(self)


class TopStatusBar(QFrame):
    experience_toggled = Signal(bool)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.setObjectName("TopBar")
        self.setFixedHeight(56)

        # Left: section/mode crumb
        self.section_num = QLabel("00 / DASHBOARD")
        self.section_num.setStyleSheet(
            "font-family: 'JetBrains Mono', Menlo, monospace; font-size: 10px; "
            " color: #5a5e54;"
        )
        self.mode_label = QLabel("Dashboard")
        self.mode_label.setObjectName("SectionTitle")
        self.mode_label.setStyleSheet("font-size: 16px; font-weight: 600;")

        crumbs = QVBoxLayout()
        crumbs.setContentsMargins(0, 0, 0, 0)
        crumbs.setSpacing(0)
        crumbs.addWidget(self.section_num)
        crumbs.addWidget(self.mode_label)

        crumbs_w = QFrame()
        crumbs_w.setLayout(crumbs)

        # Right: stat cells
        self.cell_status = _Cell("STATUS", "ACTIVE", "Green")
        self.cell_session = _Cell("SESSION", "0 hands", "Mono")
        self.experience = _ExperienceToggle(state)
        self.experience.toggled.connect(self.experience_toggled.emit)
        self.cell_rta = _Cell("RTA GUARD", "STRICT", "Green")
        self.compliance = ComplianceStatusBadge()

        right = QHBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        right.addWidget(self.cell_status)
        right.addWidget(self.cell_session)
        right.addWidget(self.experience)
        right.addWidget(self.cell_rta)

        right_w = QFrame()
        right_w.setLayout(right)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(22, 6, 0, 6)
        layout.setSpacing(14)
        layout.addWidget(crumbs_w)
        layout.addStretch(1)
        layout.addWidget(right_w)

    def set_mode(self, mode: str) -> None:
        self.mode_label.setText(mode)
        # Pick a section number from the mode name (best effort)
        index_map = {
            "Dashboard": "00",
            "Play Session": "02",
            "Tournament Simulator": "03",
            "GTO Study Library": "04",
            "Spot Practice Trainer": "05",
            "Hand History Analyzer": "06",
            "Fast Play Simulator": "07",
            "AI Poker Coach": "08",
            "Leak Finder": "09",
        }
        prefix = index_map.get(mode, "—")
        self.section_num.setText(f"{prefix} / {mode.upper()}")

    def set_session(self, label: str) -> None:
        self.cell_session.set_value(label)
