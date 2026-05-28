"""River Solver Sandbox — PioSolver tarzı GTO solver ekranı.

Akış:
  1. Hero range'i 13×13 grid'den tıklayarak seç (her tık toggle)
  2. Villain range'i için aynı grid (ayrı tab)
  3. Board input (5 kart, "Qs 7d 2h Jc 5s" formatı)
  4. Pot size + bet size frac slider
  5. "Solve" butonu → CFR çalışır (background thread)
  6. Sonuç tablosu: her el için BET/CHECK/CALL/FOLD frekansları

Solver: app/poker/river_solver.RiverSolver (vanilla CFR, heads-up).
"""
from __future__ import annotations

from typing import List, Set

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QPainter, QFont
from PySide6.QtWidgets import (
    QButtonGroup, QComboBox, QFrame, QGridLayout, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QPushButton, QScrollArea, QSizePolicy, QSlider,
    QSpinBox, QSplitter, QTableWidget, QTableWidgetItem, QTabWidget,
    QVBoxLayout, QWidget,
)

from app.poker.gto_ranges import range_matrix


# ── COLORS ────────────────────────────────────────────────────────────
COLOR_INK   = "#FAFAFA"
COLOR_MUTED = "#94A3B8"
COLOR_BG    = "#0F1419"
COLOR_CARD  = "#111827"
COLOR_LINE  = "#1F2937"
COLOR_HERO  = "#8B5CF6"      # purple — hero selection
COLOR_VILL  = "#F59E0B"      # amber — villain selection
COLOR_BET   = "#DC2626"
COLOR_CHK   = "#2563EB"
COLOR_CALL  = "#10B981"
COLOR_FOLD  = "#64748B"


# ── INTERACTIVE 13×13 RANGE PICKER ────────────────────────────────────

class RangePickerCell(QPushButton):
    """Tek bir 13×13 hücre — toggle ile seçilebilir."""
    def __init__(self, hand: str, color: str, parent=None):
        super().__init__(hand, parent)
        self.hand = hand
        self.color = color
        self.selected = False
        self.setFixedSize(58, 36)
        self.setCheckable(True)
        self.setStyleSheet(self._style())
        self.toggled.connect(self._on_toggle)

    def _style(self) -> str:
        if self.selected:
            return (
                f"QPushButton {{ background: {self.color}; color: white; "
                f"border: 1px solid {COLOR_LINE}; border-radius: 4px; "
                f"font-size: 11px; font-weight: 700; }}"
            )
        return (
            f"QPushButton {{ background: {COLOR_BG}; color: {COLOR_MUTED}; "
            f"border: 1px solid {COLOR_LINE}; border-radius: 4px; "
            f"font-size: 11px; font-weight: 500; }}"
            f"QPushButton:hover {{ background: {COLOR_LINE}; "
            f"color: {COLOR_INK}; }}"
        )

    def _on_toggle(self, checked: bool) -> None:
        self.selected = checked
        self.setStyleSheet(self._style())


class RangePicker(QWidget):
    """13×13 grid + preset butonlar (Top 10%, 20%, 30% vb.)"""

    range_changed = Signal()

    def __init__(self, color: str, label: str, parent=None):
        super().__init__(parent)
        self.color = color
        self._cells: dict[str, RangePickerCell] = {}

        v = QVBoxLayout(self)
        v.setSpacing(8)
        v.setContentsMargins(8, 8, 8, 8)

        title = QLabel(label)
        title.setStyleSheet(
            f"color: {COLOR_INK}; font-size: 13px; font-weight: 700;"
        )
        v.addWidget(title)

        # Preset butonlar
        presets = QHBoxLayout()
        presets.setSpacing(6)
        for label_p, pct in [("Top 5%", 5), ("10%", 10), ("20%", 20),
                              ("30%", 30), ("Clear", 0)]:
            btn = QPushButton(label_p)
            btn.setFixedHeight(28)
            btn.setStyleSheet(
                f"QPushButton {{ background: {COLOR_BG}; color: {COLOR_INK}; "
                f"border: 1px solid {COLOR_LINE}; border-radius: 4px; "
                f"font-size: 11px; font-weight: 600; padding: 2px 10px; }}"
                f"QPushButton:hover {{ background: {COLOR_LINE}; }}"
            )
            btn.clicked.connect(lambda _, p=pct: self.apply_preset(p))
            presets.addWidget(btn)
        presets.addStretch(1)
        v.addLayout(presets)

        # Grid
        grid_widget = QWidget()
        g = QGridLayout(grid_widget)
        g.setSpacing(1)
        g.setContentsMargins(0, 0, 0, 0)
        for row, hands in enumerate(range_matrix()):
            for col, hand in enumerate(hands):
                cell = RangePickerCell(hand, color)
                cell.toggled.connect(lambda _checked: self.range_changed.emit())
                g.addWidget(cell, row, col)
                self._cells[hand] = cell
        v.addWidget(grid_widget)

        # Range size label
        self.range_label = QLabel("0 hand · 0 combo")
        self.range_label.setStyleSheet(
            f"color: {COLOR_MUTED}; font-size: 11px;"
        )
        v.addWidget(self.range_label)
        self.range_changed.connect(self._refresh_label)

    def apply_preset(self, pct: float) -> None:
        """Top X% range'i otomatik seç."""
        from app.poker.gto_ranges import hands_in_top_pct
        if pct == 0:
            target = set()
        else:
            # bot_brain'deki hands_in_top_pct hand keys döner
            try:
                from app.engine.bot_brain import hands_in_top_pct as h_top
                target = h_top(pct)
            except Exception:
                target = set()
        for hand, cell in self._cells.items():
            should_be_on = hand in target
            if cell.selected != should_be_on:
                cell.blockSignals(True)
                cell.setChecked(should_be_on)
                cell.selected = should_be_on
                cell.setStyleSheet(cell._style())
                cell.blockSignals(False)
        self.range_changed.emit()

    def selected_hands(self) -> List[str]:
        return [h for h, c in self._cells.items() if c.selected]

    def _refresh_label(self) -> None:
        hands = self.selected_hands()
        # Combos: pair=6, suited=4, offsuit=12
        combos = 0
        for h in hands:
            if len(h) == 2:
                combos += 6
            elif h.endswith("s"):
                combos += 4
            else:
                combos += 12
        pct = combos / 1326 * 100
        self.range_label.setText(
            f"{len(hands)} hand · {combos} combo · {pct:.1f}% of range"
        )


# ── SOLVER WORKER ─────────────────────────────────────────────────────

class SolverThread(QThread):
    finished_with_result = Signal(object)
    error = Signal(str)

    def __init__(self, hero_range, villain_range, board, pot, bet_frac, iters):
        super().__init__()
        self.hero_range = hero_range
        self.villain_range = villain_range
        self.board = board
        self.pot = pot
        self.bet_frac = bet_frac
        self.iters = iters

    def run(self) -> None:
        try:
            # Vectorized solver (numpy) — ~27x hızlı. Aynı iter sayısında
            # çok daha hızlı + çok daha converged. iter'i 10x'liyoruz çünkü
            # her iterasyon çok ucuz.
            from app.poker.vector_solver import VectorRiverSolver
            s = VectorRiverSolver(
                self.hero_range, self.villain_range,
                self.board, pot=self.pot, bet_frac=self.bet_frac,
            )
            result = s.solve(iterations=self.iters * 10)
            self.finished_with_result.emit(result)
        except Exception as e:
            # numpy yoksa / hata → per-combo RiverSolver fallback
            try:
                from app.poker.river_solver import RiverSolver
                s = RiverSolver(
                    self.hero_range, self.villain_range,
                    self.board, pot=self.pot, bet_size_frac=self.bet_frac,
                )
                self.finished_with_result.emit(s.solve(iterations=self.iters))
            except Exception as e2:
                self.error.emit(f"{e} / fallback: {e2}")


class TexasSolverThread(QThread):
    """TexasSolver console binary'sini arka planda süren thread."""
    finished_with_result = Signal(object)
    error = Signal(str)

    def __init__(self, hero_range, villain_range, board, pot, bet_pct, iters):
        super().__init__()
        self.hero_range = hero_range
        self.villain_range = villain_range
        self.board = board
        self.pot = pot
        self.bet_pct = bet_pct
        self.iters = iters

    def run(self) -> None:
        try:
            from app.poker.texassolver_adapter import TexasSolverEngine
            eng = TexasSolverEngine()
            # Board: "7s 4d 2c Kh 9s" → "7s,4d,2c,Kh,9s"
            board_ts = ",".join(self.board.replace(",", " ").split())
            r = eng.solve(
                board=board_ts,
                pot=self.pot,
                effective_stack=self.pot * 3,   # makul varsayım
                range_oop=",".join(self.hero_range),
                range_ip=",".join(self.villain_range),
                bet_sizes=[int(self.bet_pct)],
                iterations=max(50, self.iters),
                threads=4,
            )
            self.finished_with_result.emit(r)
        except Exception as e:
            self.error.emit(str(e))


# ── MAIN SCREEN ───────────────────────────────────────────────────────

class SolverSandboxScreen(QWidget):
    """River solver — PioSolver tarzı pro tool."""

    coach_message = Signal(str)

    def __init__(self, state=None):
        super().__init__()
        self.state = state
        self._worker: SolverThread | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 20)
        root.setSpacing(12)

        # Header
        title = QLabel("⚙️  River Solver Sandbox")
        title.setStyleSheet(
            f"color: {COLOR_INK}; font-size: 22px; font-weight: 800;"
        )
        root.addWidget(title)
        subtitle = QLabel(
            "Range vs Range CFR — heads-up river spotları için gerçek GTO çıktısı.  "
            "PioSolver/GTO+ gibi pro tool'lara benzer mantık."
        )
        subtitle.setStyleSheet(f"color: {COLOR_MUTED}; font-size: 12px;")
        root.addWidget(subtitle)

        # Top control bar
        root.addLayout(self._build_controls())

        # Main content: tabbed range pickers (left) + results (right)
        splitter = QSplitter(Qt.Horizontal)

        # LEFT: range tabs
        left_wrap = QWidget()
        lv = QVBoxLayout(left_wrap)
        lv.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(
            f"QTabWidget::pane {{ background: {COLOR_CARD}; "
            f"border: 1px solid {COLOR_LINE}; border-radius: 8px; }} "
            f"QTabBar::tab {{ background: transparent; color: {COLOR_MUTED}; "
            f"padding: 8px 18px; font-weight: 700; }} "
            f"QTabBar::tab:selected {{ color: {COLOR_INK}; "
            f"border-bottom: 2px solid {COLOR_HERO}; }} "
        )
        self.hero_picker = RangePicker(COLOR_HERO, "Hero range")
        self.vill_picker = RangePicker(COLOR_VILL, "Villain range")
        self.tabs.addTab(self.hero_picker, "🟪 Hero")
        self.tabs.addTab(self.vill_picker, "🟧 Villain")
        lv.addWidget(self.tabs)

        splitter.addWidget(left_wrap)

        # RIGHT: results
        splitter.addWidget(self._build_results_panel())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        root.addWidget(splitter, 1)

    # ── CONTROL BAR ───────────────────────────────────────────────────
    def _build_controls(self) -> QHBoxLayout:
        h = QHBoxLayout()
        h.setSpacing(14)

        h.addWidget(self._chip_label("Board"))
        self.board_input = QLineEdit("7s 4d 2c Kh 9s")
        self.board_input.setFixedWidth(220)
        self.board_input.setStyleSheet(
            f"QLineEdit {{ background: {COLOR_BG}; color: {COLOR_INK}; "
            f"border: 1px solid {COLOR_LINE}; border-radius: 6px; "
            f"padding: 6px 10px; font-family: 'JetBrains Mono', monospace; "
            f"font-size: 12px; }}"
        )
        h.addWidget(self.board_input)

        h.addWidget(self._chip_label("Pot"))
        self.pot_input = QSpinBox()
        self.pot_input.setRange(10, 10000)
        self.pot_input.setValue(100)
        self.pot_input.setStyleSheet(
            f"QSpinBox {{ background: {COLOR_BG}; color: {COLOR_INK}; "
            f"border: 1px solid {COLOR_LINE}; border-radius: 6px; "
            f"padding: 4px 8px; }}"
        )
        h.addWidget(self.pot_input)

        h.addWidget(self._chip_label("Bet %"))
        self.bet_pct = QComboBox()
        self.bet_pct.addItems(["33", "50", "66", "75", "100", "150"])
        self.bet_pct.setCurrentText("75")
        h.addWidget(self.bet_pct)

        h.addWidget(self._chip_label("Iter"))
        self.iter_box = QComboBox()
        self.iter_box.addItems(["100 (quick)", "300 (default)", "1000 (precise)"])
        self.iter_box.setCurrentIndex(1)
        h.addWidget(self.iter_box)

        # Engine seçici — built-in vs TexasSolver (kuruluysa)
        h.addWidget(self._chip_label("Engine"))
        self.engine_box = QComboBox()
        try:
            from app.poker.texassolver_adapter import texassolver_status
            ts = texassolver_status()
        except Exception:
            ts = {"available": False, "binary": ""}
        self._ts_available = ts.get("available", False)
        if self._ts_available:
            self.engine_box.addItems(["Built-in CFR 🟠", "TexasSolver ✅"])
            self.engine_box.setCurrentText("TexasSolver ✅")
            self.engine_box.setToolTip(f"TexasSolver bulundu: {ts.get('binary')}")
        else:
            self.engine_box.addItems(["Built-in CFR 🟠"])
            self.engine_box.setToolTip(
                "TexasSolver bulunamadı (built-in CFR kullanılıyor). "
                "EXACT solver için: github.com/bupticybee/TexasSolver indir, "
                "console_solver binary'sini TEXASSOLVER_PATH ile tanıt."
            )
        h.addWidget(self.engine_box)

        h.addStretch(1)

        self.solve_btn = QPushButton("▶  SOLVE")
        self.solve_btn.setFixedHeight(40)
        self.solve_btn.setStyleSheet(
            f"QPushButton {{ background: {COLOR_HERO}; color: white; "
            f"border: none; border-radius: 8px; padding: 6px 24px; "
            f"font-size: 14px; font-weight: 800; letter-spacing: 1.5px; }} "
            f"QPushButton:hover {{ background: #7c3aed; }} "
            f"QPushButton:disabled {{ background: {COLOR_LINE}; "
            f"color: {COLOR_MUTED}; }}"
        )
        self.solve_btn.clicked.connect(self._run_solver)
        h.addWidget(self.solve_btn)

        return h

    def _chip_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {COLOR_MUTED}; font-size: 11px; font-weight: 700; "
            f"text-transform: uppercase; letter-spacing: 1px;"
        )
        return lbl

    # ── RESULTS PANEL ─────────────────────────────────────────────────
    def _build_results_panel(self) -> QWidget:
        panel = QFrame()
        panel.setStyleSheet(
            f"QFrame {{ background: {COLOR_CARD}; border: 1px solid {COLOR_LINE}; "
            f"border-radius: 8px; padding: 12px; }}"
        )
        v = QVBoxLayout(panel)
        v.setSpacing(10)

        head = QLabel("📊  SOLVER OUTPUT")
        head.setStyleSheet(
            f"color: {COLOR_MUTED}; font-size: 11px; font-weight: 700; "
            f"letter-spacing: 1.5px;"
        )
        v.addWidget(head)

        self.status_label = QLabel(
            "Hero ve villain range'i seç, board gir, SOLVE'a bas."
        )
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet(
            f"color: {COLOR_MUTED}; font-size: 12px;"
        )
        v.addWidget(self.status_label)

        # Hero strategies table
        hero_label = QLabel("HERO — acts first")
        hero_label.setStyleSheet(
            f"color: {COLOR_HERO}; font-size: 11px; font-weight: 700; "
            f"letter-spacing: 1.5px; margin-top: 8px;"
        )
        v.addWidget(hero_label)

        self.hero_table = self._make_strategy_table(
            ["Hand", "BET", "CHECK"]
        )
        v.addWidget(self.hero_table, 1)

        # Villain table
        vill_label = QLabel("VILLAIN — vs hero bet")
        vill_label.setStyleSheet(
            f"color: {COLOR_VILL}; font-size: 11px; font-weight: 700; "
            f"letter-spacing: 1.5px; margin-top: 8px;"
        )
        v.addWidget(vill_label)

        self.vill_table = self._make_strategy_table(
            ["Hand", "CALL", "FOLD"]
        )
        v.addWidget(self.vill_table, 1)

        return panel

    def _make_strategy_table(self, columns: List[str]) -> QTableWidget:
        t = QTableWidget()
        t.setColumnCount(len(columns))
        t.setHorizontalHeaderLabels(columns)
        t.verticalHeader().setVisible(False)
        t.setEditTriggers(QTableWidget.NoEditTriggers)
        t.setSelectionBehavior(QTableWidget.SelectRows)
        t.setStyleSheet(
            f"QTableWidget {{ background: transparent; border: none; "
            f"color: {COLOR_INK}; font-family: 'JetBrains Mono', monospace; "
            f"font-size: 11px; gridline-color: {COLOR_LINE}; }} "
            f"QTableWidget::item {{ padding: 4px 6px; "
            f"border-bottom: 1px solid {COLOR_LINE}; }} "
            f"QHeaderView::section {{ background: {COLOR_BG}; "
            f"color: {COLOR_MUTED}; padding: 6px; border: none; "
            f"border-bottom: 1px solid {COLOR_LINE}; font-weight: 700; }}"
        )
        hdr = t.horizontalHeader()
        for i in range(len(columns)):
            hdr.setSectionResizeMode(
                i, QHeaderView.Stretch if i == 0 else QHeaderView.ResizeToContents
            )
        return t

    # ── SOLVE ─────────────────────────────────────────────────────────
    def _run_solver(self) -> None:
        hero_range = self.hero_picker.selected_hands()
        vill_range = self.vill_picker.selected_hands()

        if not hero_range or not vill_range:
            self.status_label.setText(
                "❌  Hem hero hem villain range'i seçmelisin (en az 1 hand)."
            )
            self.status_label.setStyleSheet(
                f"color: {COLOR_BET}; font-size: 12px;"
            )
            return

        board = self.board_input.text().strip()
        if not board:
            self.status_label.setText("❌  Board boş.")
            return

        pot = float(self.pot_input.value())
        bet_frac = float(self.bet_pct.currentText()) / 100
        iters_str = self.iter_box.currentText().split()[0]
        iters = int(iters_str)

        use_ts = (self.engine_box.currentText().startswith("TexasSolver")
                  and getattr(self, "_ts_available", False))

        self.solve_btn.setEnabled(False)

        if use_ts:
            self.status_label.setText(
                "⏳  TexasSolver (EXACT) çalışıyor... full postflop çözüm, "
                "biraz sürebilir."
            )
            self.status_label.setStyleSheet("color: #F59E0B; font-size: 12px;")
            self._worker = TexasSolverThread(
                hero_range, vill_range, board, pot,
                int(self.bet_pct.currentText()), iters,
            )
            self._worker.finished_with_result.connect(self._on_ts_solved)
            self._worker.error.connect(self._on_error)
            self._worker.start()
            return

        self.status_label.setText(
            f"⏳  Built-in CFR (🟠 study-grade) çalışıyor... ({len(hero_range)} "
            f"hero × {len(vill_range)} villain × {iters} iter)"
        )
        self.status_label.setStyleSheet(f"color: #F59E0B; font-size: 12px;")
        self._worker = SolverThread(
            hero_range, vill_range, board, pot, bet_frac, iters
        )
        self._worker.finished_with_result.connect(self._on_solved)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_ts_solved(self, result) -> None:
        """TexasSolver sonucu — OOP strategy tablosu (RAISE/CALL/CHECK/FOLD)."""
        self.solve_btn.setEnabled(True)
        if not getattr(result, "ok", False):
            self._on_error(getattr(result, "error", "TexasSolver hatası"))
            return
        self.status_label.setText(
            f"✅  TexasSolver EXACT  ·  {result.elapsed_ms}ms  ·  "
            f"{len(result.oop_strategy)} hand (OOP). Solver-grade GTO."
        )
        self.status_label.setStyleSheet(
            f"color: {COLOR_CALL}; font-size: 12px; font-weight: 600;"
        )
        # OOP stratejiyi hero tablosuna doldur (action'lar dinamik)
        strats = result.oop_strategy
        self.hero_table.setRowCount(len(strats))
        # actions birleşik küme
        all_actions = []
        for hand, acts in strats.items():
            for a in acts:
                if a not in all_actions:
                    all_actions.append(a)
        self.hero_table.setColumnCount(1 + len(all_actions))
        self.hero_table.setHorizontalHeaderLabels(["Hand"] + all_actions)
        for row, (hand, acts) in enumerate(strats.items()):
            self.hero_table.setItem(row, 0, QTableWidgetItem(hand))
            for ci, a in enumerate(all_actions):
                self.hero_table.setItem(row, ci + 1,
                                        QTableWidgetItem(f"{acts.get(a, 0):.0f}%"))

    def _on_solved(self, result) -> None:
        self.solve_btn.setEnabled(True)
        self.status_label.setText(
            f"✓  Solved in {result.elapsed_ms}ms  ·  "
            f"{result.iterations} iter  ·  "
            f"{len(result.hero_strategies)} hero combos × "
            f"{len(result.villain_strategies)} villain combos"
        )
        self.status_label.setStyleSheet(
            f"color: {COLOR_CALL}; font-size: 12px; font-weight: 600;"
        )
        # Populate hero table — group by hand key to avoid 1000 rows
        self._populate_strategy_table(
            self.hero_table, result.hero_strategies,
            ["bet_freq", "check_freq"]
        )
        self._populate_strategy_table(
            self.vill_table, result.villain_strategies,
            ["v_call_freq", "v_fold_freq"]
        )

    def _populate_strategy_table(self, table, strategies, fields) -> None:
        # Group concrete combos by canonical hand key
        # e.g. AcAd, AcAh, ... → "AA"
        grouped: dict[str, list] = {}
        for s in strategies:
            h = s.hand_label
            # AcAd → AA, AcKd → AKo (different suits), AcKc → AKs (same suit)
            r1, s1, r2, s2 = h[0], h[1], h[2], h[3]
            if r1 == r2:
                key = r1 + r2
            else:
                # Sort by rank for canonical form
                from app.engine.hand_state import RANK_VALUES
                if RANK_VALUES[r1] < RANK_VALUES[r2]:
                    r1, r2 = r2, r1
                key = r1 + r2 + ("s" if s1 == s2 else "o")
            grouped.setdefault(key, []).append(s)

        table.setRowCount(len(grouped))
        for row, (key, ss) in enumerate(grouped.items()):
            avg = {f: sum(getattr(s, f, 0) for s in ss) / len(ss) for f in fields}
            cells = [key] + [f"{avg[f]:.0f}%" for f in fields]
            for col, txt in enumerate(cells):
                item = QTableWidgetItem(txt)
                if col == 0:
                    item.setForeground(QColor(COLOR_INK))
                else:
                    # Highest-freq action → bold + bright
                    field_name = fields[col - 1]
                    pct = avg[field_name]
                    if pct >= 60:
                        item.setForeground(QColor(COLOR_BET if "bet" in field_name
                                                    or "call" in field_name
                                                    else COLOR_FOLD))
                    elif pct >= 30:
                        item.setForeground(QColor("#F59E0B"))
                    else:
                        item.setForeground(QColor(COLOR_MUTED))
                table.setItem(row, col, item)

    def _on_error(self, msg: str) -> None:
        self.solve_btn.setEnabled(True)
        self.status_label.setText(f"❌  Hata: {msg[:200]}")
        self.status_label.setStyleSheet(
            f"color: {COLOR_BET}; font-size: 12px;"
        )
