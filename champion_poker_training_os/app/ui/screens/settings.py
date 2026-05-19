from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core.app_state import AppState
from app.core.compliance import OFFLINE_COMPLIANCE_RULES
from app.core.rta_guard import RtaGuard
from app.solver.csv_importer import get_solver_library


class SettingsScreen(QWidget):
    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.guard = RtaGuard(strict_mode=state.strict_rta_guard)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        scroll.setWidget(body)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        from app.ui.components.poke import PokePageHeader as _PokePageHeader
        page_header = _PokePageHeader(
            num="28 / Settings",
            title="Stay <em>offline</em>.",
            sub="RTA guard · compliance · solver library · reset data.",
        )
        layout.addWidget(page_header)

        # --- RTA Guard card ---
        rta_card = QFrame()
        rta_card.setObjectName("Card")
        rta_layout = QVBoxLayout(rta_card)
        rta_layout.setContentsMargins(14, 12, 14, 12)
        rta_title = QLabel("RTA Guard")
        rta_title.setObjectName("SectionTitle")
        rta_layout.addWidget(rta_title)
        self.strict = QCheckBox("RTA Guard Strict Mode")
        self.strict.setChecked(state.strict_rta_guard)
        self.strict.stateChanged.connect(self.update_strict)
        rta_layout.addWidget(self.strict)
        scan = QPushButton("Scan Poker Clients")
        scan.setObjectName("PrimaryButton")
        scan.clicked.connect(self.scan)
        rta_layout.addWidget(scan)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setObjectName("Green")
        rta_layout.addWidget(self.status)
        rules = QLabel("\n".join(f"• {rule}" for rule in OFFLINE_COMPLIANCE_RULES))
        rules.setObjectName("Muted")
        rules.setWordWrap(True)
        rta_layout.addWidget(rules)
        layout.addWidget(rta_card)

        # --- Solver Library card ---
        solver_card = QFrame()
        solver_card.setObjectName("Card")
        solver_layout = QVBoxLayout(solver_card)
        solver_layout.setContentsMargins(14, 12, 14, 12)
        solver_title = QLabel("Solver Library  (PIO / GTO Wizard CSV)")
        solver_title.setObjectName("SectionTitle")
        solver_layout.addWidget(solver_title)
        self.solver_status = QLabel(self._solver_status_text())
        self.solver_status.setObjectName("Muted")
        self.solver_status.setWordWrap(True)
        solver_layout.addWidget(self.solver_status)

        sl_buttons = QHBoxLayout()
        import_btn = QPushButton("📥  Import solver CSV…")
        import_btn.setStyleSheet(
            "QPushButton { background: #10B981; color: #04110D; font-weight: 800; "
            "padding: 8px 16px; border-radius:0; border: none; }"
            "QPushButton:hover { background: #34D399; }"
        )
        import_btn.setCursor(Qt.PointingHandCursor)
        import_btn.clicked.connect(self._import_solver)
        clear_btn = QPushButton("Clear library")
        clear_btn.clicked.connect(self._clear_library)
        sl_buttons.addWidget(import_btn)
        sl_buttons.addWidget(clear_btn)
        sl_buttons.addStretch(1)
        solver_layout.addLayout(sl_buttons)

        format_help = QLabel(
            "CSV format: spot_id, action, frequency (0-1 or 0-100), ev, sizing (optional), "
            "best (optional 0/1), source (optional). Frequencies normalised per spot. "
            "Imported rows replace mock-solver output for matching spot ids."
        )
        format_help.setWordWrap(True)
        format_help.setObjectName("Muted")
        solver_layout.addWidget(format_help)
        layout.addWidget(solver_card)

        # --- Data Reset card (My Mistakes + Tournament Archive) ---
        reset_card = QFrame()
        reset_card.setObjectName("Card")
        reset_layout = QVBoxLayout(reset_card)
        reset_layout.setContentsMargins(14, 12, 14, 12)
        reset_title = QLabel("🗑  Veri Yönetimi")
        reset_title.setObjectName("SectionTitle")
        reset_layout.addWidget(reset_title)
        reset_info = QLabel(
            "My Mistakes ve Tournament Archive JSON dosyalarındaki tüm geçmişi siler. "
            "Bu işlem GERİ ALINAMAZ — temiz başlangıç istediğinde kullan."
        )
        reset_info.setWordWrap(True)
        reset_info.setObjectName("Muted")
        reset_layout.addWidget(reset_info)

        reset_buttons = QHBoxLayout()
        reset_mistakes_btn = QPushButton("Hataları Temizle")
        reset_mistakes_btn.setStyleSheet(
            "QPushButton { background: #1B2330; color: #FCA5A5; font-weight: 700; "
            "padding: 8px 16px; border-radius:0; border:1px solid #7F1D1D; }"
            "QPushButton:hover { background: #2A1F1F; border-color: #DC2626; }"
        )
        reset_mistakes_btn.clicked.connect(self._reset_mistakes)
        reset_buttons.addWidget(reset_mistakes_btn)

        reset_archive_btn = QPushButton("Turnuva Arşivini Temizle")
        reset_archive_btn.setStyleSheet(
            "QPushButton { background: #1B2330; color: #FCA5A5; font-weight: 700; "
            "padding: 8px 16px; border-radius:0; border:1px solid #7F1D1D; }"
            "QPushButton:hover { background: #2A1F1F; border-color: #DC2626; }"
        )
        reset_archive_btn.clicked.connect(self._reset_archive)
        reset_buttons.addWidget(reset_archive_btn)

        reset_all_btn = QPushButton("⚠  TÜMÜNÜ SIL (Reset)")
        reset_all_btn.setStyleSheet(
            "QPushButton { background: #DC2626; color: #FFF; font-weight: 800; "
            "padding: 8px 18px; border-radius:0; border: none; }"
            "QPushButton:hover { background: #B91C1C; }"
        )
        reset_all_btn.clicked.connect(self._reset_all_data)
        reset_buttons.addWidget(reset_all_btn)
        reset_buttons.addStretch(1)
        reset_layout.addLayout(reset_buttons)
        layout.addWidget(reset_card)

        layout.addStretch(1)
        self.scan()

    # --- handlers --------------------------------------------------------
    def update_strict(self) -> None:
        self.state.strict_rta_guard = self.strict.isChecked()
        self.guard.strict_mode = self.state.strict_rta_guard
        self.scan()

    def scan(self) -> None:
        status = self.guard.scan_processes()
        self.state.strategy_locked = status.locked
        self.status.setObjectName("Red" if status.locked else "Green")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self.status.setText(status.message)

    def _solver_status_text(self) -> str:
        lib = get_solver_library()
        size = lib.size()
        if size == 0:
            return "No solver CSV imported. Trainers fall back to mock solver baseline."
        sources = ", ".join(lib.sources()) or "—"
        return f"{size} solver entries loaded from: {sources}."

    def _import_solver(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Import solver CSV (PIO / GTO Wizard)",
            "", "CSV (*.csv);;All files (*)",
        )
        if not paths:
            return
        lib = get_solver_library()
        total = 0
        for p in paths:
            try:
                total += lib.import_csv_file(p)
            except Exception:
                continue
        self.solver_status.setText(self._solver_status_text())
        QMessageBox.information(
            self, "Solver import complete",
            f"Imported {total} solver row(s) across {len(paths)} file(s)."
            f"\nLibrary size: {lib.size()}.",
        )

    def _reset_mistakes(self) -> None:
        ok = QMessageBox.question(
            self, "My Mistakes Temizle",
            "TÜM My Mistakes geçmişini silmek istediğinden emin misin?\n"
            "Bu işlem GERİ ALINAMAZ.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if ok != QMessageBox.Yes:
            return
        try:
            from app.db.mistakes_queue import clear_mistakes
            clear_mistakes()
            from app.ui.components.toast import Toast
            Toast.show_success(self.window(), "✓ My Mistakes temizlendi")
        except Exception as e:
            QMessageBox.warning(self, "Hata", str(e))

    def _reset_archive(self) -> None:
        ok = QMessageBox.question(
            self, "Tournament Archive Temizle",
            "TÜM kayıtlı turnuvaları silmek istediğinden emin misin?\n"
            "Bu işlem GERİ ALINAMAZ.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if ok != QMessageBox.Yes:
            return
        try:
            from app.db.tournament_archive import clear_archive
            clear_archive()
            from app.ui.components.toast import Toast
            Toast.show_success(self.window(), "✓ Tournament Archive temizlendi")
        except Exception as e:
            QMessageBox.warning(self, "Hata", str(e))

    def _reset_all_data(self) -> None:
        ok = QMessageBox.warning(
            self, "TÜMÜNÜ SIL",
            "Bu, hem My Mistakes hem de Tournament Archive'ı tamamen siler.\n"
            "Tüm progress, leak'ler, turnuva geçmişi KAYBOLACAK.\n\n"
            "Bu işlemi gerçekten yapmak istiyor musun?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if ok != QMessageBox.Yes:
            return
        try:
            from app.db.mistakes_queue import clear_mistakes
            from app.db.tournament_archive import clear_archive
            clear_mistakes()
            clear_archive()
            # AppState in-memory counters
            self.state.completed_drills = 0
            self.state.correct_drills = 0
            self.state.ev_loss_total = 0.0
            self.state.session_notes = []
            from app.ui.components.toast import Toast
            Toast.show_success(self.window(), "✓ Tüm veri temizlendi — temiz başlangıç")
        except Exception as e:
            QMessageBox.warning(self, "Hata", str(e))

    def _clear_library(self) -> None:
        lib = get_solver_library()
        lib.clear()
        self.solver_status.setText(self._solver_status_text())
