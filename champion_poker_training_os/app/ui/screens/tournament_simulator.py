from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.ai.coach_engine import explain_spot
from app.core.app_state import AppState

# Color tokens for verdict styling
# Poke-aligned constants (legacy _C_* names preserved for diff sanity)
from app.ui.theme import poke_tokens as _t
_C_BG     = _t.BG
_C_CARD   = _t.SURFACE
_C_PANEL  = _t.SURFACE
_C_BORDER = _t.LINE
_C_MUTED  = _t.MUTED
_C_TEXT   = _t.INK
_C_CYAN   = _t.ACCENT
_C_GREEN  = _t.ACCENT
_C_RED    = _t.DANGER
_C_BLUE   = _t.INFO
_C_AMBER  = _t.WARN
_C_PURPLE = _t.INFO
from app.db.repository import save_decision_review
from app.db.tournament_archive import load_archive
from app.engine.hand_state import positions_for
from app.simulator.mtt_engine import TournamentEngine
from app.training.decision_review import analyze_training_spot_decision
from app.ui.components.live_poker_table import LivePokerTable
from app.ui.components.mtt_setup_dialog import MttConfig, MttSetupDialog
from app.ui.components.poker_table import PokerTableView
from app.ui.components.spot_snapshot import build_spot_snapshot


class StackBar(QWidget):
    """Visualize hero chip stack vs field average."""

    def __init__(self):
        super().__init__()
        self.hero = 0
        self.avg = 0
        self.setMinimumHeight(40)

    def set_values(self, hero: int, avg: int) -> None:
        self.hero = hero
        self.avg = avg
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()
        track_h = 14
        y_track = (h - track_h) // 2
        max_chips = max(self.hero, self.avg, 1) * 1.4

        # Track
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#1F2937"))
        painter.drawRoundedRect(0, y_track, w, track_h, 4, 4)

        # Hero bar
        hero_w = int(w * self.hero / max_chips)
        if self.hero >= self.avg:
            color = QColor("#10B981")
        elif self.hero >= self.avg * 0.6:
            color = QColor("#22D3EE")
        else:
            color = QColor("#F59E0B")
        painter.setBrush(color)
        painter.drawRoundedRect(0, y_track, hero_w, track_h, 4, 4)

        # Average marker
        avg_x = int(w * self.avg / max_chips)
        painter.setPen(QColor("#9CA3AF"))
        painter.drawLine(avg_x, y_track - 3, avg_x, y_track + track_h + 3)

        # Labels
        painter.setPen(QColor("#E5E7EB"))
        painter.drawText(4, y_track - 4, f"Hero {self.hero:,}")
        painter.drawText(max(0, avg_x - 20), y_track + track_h + 14, f"Avg {self.avg:,}")
        painter.end()


class TournamentSimulatorScreen(QWidget):
    coach_message = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.engine = TournamentEngine()
        self.action_layout = QHBoxLayout()

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

        # Title row
        title_row = QHBoxLayout()
        title = QLabel("🎰  Tournament Simulator  (MTT karar pratiği)")
        title.setObjectName("Title")
        title_row.addWidget(title)
        title_row.addStretch(1)
        self.setup_btn = QPushButton("⚙  Yapılandır")
        self.setup_btn.clicked.connect(self._open_setup)
        title_row.addWidget(self.setup_btn)
        self.reset_btn = QPushButton("↺  Sıfırla")
        self.reset_btn.clicked.connect(self._reset)
        title_row.addWidget(self.reset_btn)
        layout.addLayout(title_row)

        # Setup row — shown summary of current config (use MttSetupDialog to edit)
        setup = QFrame()
        setup.setObjectName("Card")
        setup_layout = QHBoxLayout(setup)
        setup_layout.setContentsMargins(14, 10, 14, 10)
        self._setup_summary = QLabel("Field: 800  ·  Buy-in: $100  ·  Speed: regular  ·  9-handed")
        self._setup_summary.setObjectName("Muted")
        setup_layout.addWidget(self._setup_summary)
        setup_layout.addStretch(1)
        # Keep a table-size pseudo-spin used by _refresh_live_table compatibility
        self.table_size_spin = QSpinBox()
        self.table_size_spin.setRange(2, 11)
        self.table_size_spin.setValue(9)
        self.table_size_spin.setVisible(False)
        layout.addWidget(setup)

        # MTT context (blind / stack / players)
        ctx = QFrame()
        ctx.setObjectName("Card")
        ctx_layout = QGridLayout(ctx)
        ctx_layout.setContentsMargins(14, 12, 14, 12)
        ctx_layout.setHorizontalSpacing(20)
        self.label_blinds = self._ctx_metric(ctx_layout, 0, 0, "Blinds", "L1 100/200")
        self.label_stack = self._ctx_metric(ctx_layout, 0, 1, "Hero Stack", "30,000")
        self.label_stack_bb = self._ctx_metric(ctx_layout, 0, 2, "Stack (bb)", "150")
        self.label_m = self._ctx_metric(ctx_layout, 0, 3, "M-Oran", "100")
        self.label_avg = self._ctx_metric(ctx_layout, 0, 4, "Avg Stack", "30,000")
        self.label_left = self._ctx_metric(ctx_layout, 0, 5, "Kalan Oyuncu", "800")
        self.label_paid = self._ctx_metric(ctx_layout, 0, 6, "Ödüllü", "120")
        self.label_pool = self._ctx_metric(ctx_layout, 0, 7, "Ödül Havuzu", "$74,400")
        self.stack_bar = StackBar()
        ctx_layout.addWidget(self.stack_bar, 1, 0, 1, 8)
        layout.addWidget(ctx)

        # Main row: live oval table + decision panel + payout ladder
        body_row = QHBoxLayout()
        body_row.setSpacing(14)

        # Real oval poker table — shows up to 11 seats with positions, stacks, dealer, action chips
        self.live_table = LivePokerTable()
        self.live_table.setMinimumHeight(380)
        body_row.addWidget(self.live_table, 3)
        # Legacy PokerTableView kept hidden — LivePokerTable replaces it
        self.table = PokerTableView()
        self.table.setVisible(False)

        # Decision panel
        decision = QFrame()
        decision.setObjectName("DataPanel")
        d_layout = QVBoxLayout(decision)
        d_layout.setContentsMargins(14, 14, 14, 14)
        self.spot_title = QLabel()
        self.spot_title.setObjectName("SectionTitle")
        self.spot_title.setWordWrap(True)
        self.spot_info = QLabel()
        self.spot_info.setWordWrap(True)
        self.spot_info.setObjectName("Muted")
        self.report = QLabel()
        self.report.setWordWrap(True)
        self.report.setObjectName("Cyan")
        d_layout.addWidget(self.spot_title)
        d_layout.addWidget(self.spot_info)
        d_layout.addWidget(self.report)
        d_layout.addLayout(self.action_layout)
        d_layout.addStretch(1)
        body_row.addWidget(decision, 2)

        # Payout ladder
        ladder = QFrame()
        ladder.setObjectName("Card")
        ladder_layout = QVBoxLayout(ladder)
        ladder_layout.setContentsMargins(14, 14, 14, 14)
        ladder_title = QLabel("🏆  Ödül Merdiveni")
        ladder_title.setObjectName("SectionTitle")
        ladder_layout.addWidget(ladder_title)
        self.ladder_grid = QGridLayout()
        self.ladder_grid.setHorizontalSpacing(16)
        ladder_layout.addLayout(self.ladder_grid)
        ladder_layout.addStretch(1)
        self.label_finish = QLabel("Tahmini bitiş: —")
        self.label_finish.setObjectName("Amber")
        ladder_layout.addWidget(self.label_finish)
        body_row.addWidget(ladder, 2)

        layout.addLayout(body_row)

        # Performance stats
        perf = QFrame()
        perf.setObjectName("Card")
        perf_layout = QHBoxLayout(perf)
        perf_layout.setContentsMargins(14, 10, 14, 10)
        self.label_acc = QLabel("Doğruluk: 0%")
        self.label_acc.setObjectName("Green")
        self.label_punts = QLabel("ICM Punt: 0")
        self.label_punts.setObjectName("Red")
        self.label_roi = QLabel("ROI Tahmini: 0.0")
        self.label_roi.setObjectName("Cyan")
        self.label_decisions = QLabel("Kararlar: 0")
        for w in (self.label_acc, self.label_punts, self.label_roi, self.label_decisions):
            perf_layout.addWidget(w)
        perf_layout.addStretch(1)
        layout.addWidget(perf)

        layout.addStretch(1)
        self._refresh_context()
        self.load_spot()

    # --- helpers ---------------------------------------------------------
    def _ctx_metric(self, grid: QGridLayout, row: int, col: int, label: str, value: str) -> QLabel:
        wrap = QVBoxLayout()
        wrap.setSpacing(2)
        name = QLabel(label)
        name.setObjectName("Muted")
        val = QLabel(value)
        val.setObjectName("MetricValue")
        wrap.addWidget(name)
        wrap.addWidget(val)
        container = QWidget()
        container.setLayout(wrap)
        grid.addWidget(container, row, col)
        return val

    def _open_setup(self) -> None:
        """Open the shared MTT setup dialog and FULLY restart the simulator."""
        preset = MttConfig(
            tournament_name   = "Online Turbo Low Stakes",
            field_size        = self.engine.field_size,
            buyin             = self.engine.buyin,
            starting_stack    = self.engine.starting_stack,
            minutes_per_level = 10,
            skill_style       = "Human-Like",
            skill_level       = "Medium",
            table_size        = self.table_size_spin.value(),
        )
        dlg = MttSetupDialog(self, preset)
        if dlg.exec() != dlg.Accepted:
            return
        cfg = dlg.config
        # Tam yeniden başlatma — eski engine state'ini bırak
        from app.simulator.mtt_engine import TournamentEngine
        self.engine = TournamentEngine(
            field_size     = cfg.field_size,
            starting_stack = cfg.starting_stack,
            speed          = cfg.speed_class,
            pko            = True,
            buyin          = float(cfg.buyin),
        )
        self.table_size_spin.setValue(cfg.table_size)
        self._setup_summary.setText(
            f"{cfg.tournament_name}  ·  {cfg.field_size} oyuncu  ·  "
            f"${cfg.buyin:.0f} buy-in  ·  {cfg.starting_stack:,} chip  ·  "
            f"{cfg.skill_style}/{cfg.skill_level}  ·  {cfg.table_size}-handed"
        )
        self._refresh_context()
        self.load_spot()  # New spot loads — index reset
        # Clear stale report
        self.report.setText(
            f"✅ Turnuva başlatıldı: {cfg.field_size} oyuncu  ·  "
            f"{cfg.skill_style}/{cfg.skill_level}\n"
            "İlk karar bekleniyor — ekrana göre FOLD/CALL/RAISE/JAM seç."
        )
        self.report.setStyleSheet(f"color:{_C_GREEN};")
        try:
            from app.ui.components.toast import Toast
            Toast.show_success(
                self.window(),
                f"✅ Turnuva başlatıldı: {cfg.field_size} oyuncu, "
                f"{cfg.skill_style}/{cfg.skill_level}"
            )
        except Exception:
            pass

    def _reset(self) -> None:
        # MTT engine doesn't have a reset() method — recreate it
        from app.simulator.mtt_engine import TournamentEngine
        self.engine = TournamentEngine(
            field_size=self.engine.field_size,
            starting_stack=self.engine.starting_stack,
            speed=self.engine.speed,
            pko=self.engine.pko,
            buyin=self.engine.buyin,
        )
        self._refresh_context()
        self.load_spot()
        self.report.setText("↺  Turnuva sıfırlandı. Yeniden başla.")
        try:
            from app.ui.components.toast import Toast
            Toast.show_info(self.window(), "↺ Turnuva sıfırlandı")
        except Exception:
            pass

    def _refresh_context(self) -> None:
        e = self.engine
        self.label_blinds.setText(e.blinds_label)
        self.label_stack.setText(f"{e.chip_stack:,}")
        self.label_stack_bb.setText(f"{e.stack_in_bb}bb")
        self.label_m.setText(str(e.m_ratio))
        self.label_avg.setText(f"{e.avg_stack:,}")
        self.label_left.setText(f"{e.players_left:,} / {e.field_size:,}")
        self.label_paid.setText(str(e.paid_places))
        self.label_pool.setText(f"${e.prize_pool:,.0f}")
        self.stack_bar.set_values(e.chip_stack, e.avg_stack)
        self.label_finish.setText(
            f"Tahmini bitiş: #{e.finish_position or '—'} / {e.field_size}"
        )
        self.label_acc.setText(f"Doğruluk: {e.accuracy()}%")
        self.label_punts.setText(f"ICM Punt: {e.icm_punts}")
        self.label_roi.setText(f"ROI Tahmini: {e.roi_projection:+.2f}")
        self.label_decisions.setText(f"Kararlar: {e.decisions_made}")
        # Refresh payout ladder
        for i in reversed(range(self.ladder_grid.count())):
            item = self.ladder_grid.itemAt(i)
            if item and item.widget():
                item.widget().deleteLater()
        for r, (place, amount) in enumerate(e.payout_ladder()):
            place_lbl = QLabel(f"{place}.")
            place_lbl.setFixedWidth(28)
            amount_lbl = QLabel(f"${amount:,.0f}")
            amount_lbl.setObjectName("Cyan" if place > 3 else "Green")
            self.ladder_grid.addWidget(place_lbl, r, 0)
            self.ladder_grid.addWidget(amount_lbl, r, 1)
            if e.finish_position == place:
                marker = QLabel("◀ tahmini bitiş")
                marker.setObjectName("Amber")
                self.ladder_grid.addWidget(marker, r, 2)

    def _refresh_live_table(self) -> None:
        """Re-render the oval table for the current spot + table size."""
        spot = self.engine.current_spot
        n = self.table_size_spin.value() if hasattr(self, "table_size_spin") else 9
        snap = build_spot_snapshot(
            spot=spot,
            num_players=n,
            hero_chip_stack=self.engine.chip_stack,
            avg_stack=self.engine.avg_stack,
            blind_size_chips=self.engine._current_blinds()[1],
        )
        self.live_table.update_state(snap)

    def load_spot(self) -> None:
        spot = self.engine.current_spot
        self.state.selected_spot = spot
        self.table.set_hand(spot["hero_cards"], spot["board"], spot["pot_bb"])
        self._refresh_live_table()
        self.spot_title.setText(f"{spot['id']} | {spot['title']}")
        self.spot_info.setText(
            f"Aşama: {spot.get('stage', '—')}  ·  Risk premium {spot['risk_premium']:.1%}  ·  "
            f"Bubble faktörü {spot['bubble_factor']}  ·  Bounty EV {spot['bounty_ev']:+.2f}"
        )
        if not self.report.text():
            self.report.setText(
                "İlk kararı ver: chipEV mi, $EV mi öncelikli? "
                "Bubble baskısını yorumla ve risk premium'a göre karar al."
            )
        _clear_layout(self.action_layout)
        # Use the shared GTO action button so this screen looks identical
        # to Spot Trainer, GTO Trainer, Tournament Play, etc.
        from app.ui.components.action_buttons import GtoActionButton, action_display
        pot_bb = float(spot.get("pot_bb", 10.0))
        stack_bb = float(spot.get("stack_bb", 40.0))
        for action in spot["options"]:
            label = action_display(action, pot_bb, stack_bb)
            button = GtoActionButton(label, action)
            button.clicked.connect(lambda checked=False, a=action: self.decide(a))
            self.action_layout.addWidget(button)

    def decide(self, action: str) -> None:
        spot = self.engine.current_spot
        result = self.engine.decide(action)
        review = analyze_training_spot_decision(
            spot,
            action,
            20000 + self.engine.decisions_made,
            dollar_ev_loss=result["dollar_ev_loss"],
            context="tournament",
        )
        try:
            save_decision_review(review)
        except Exception:
            pass

        # ── Persist wrong decisions to global My Mistakes queue ──
        if not result.get("is_correct", review.get("ev_loss", 0) < 0.1):
            try:
                from datetime import datetime
                from app.db.mistakes_queue import (
                    MistakeEntry as MqEntry, add_mistake, new_id as new_mistake_id,
                )
                add_mistake(MqEntry(
                    id           = new_mistake_id(),
                    logged_at    = datetime.now().isoformat(timespec="seconds"),
                    context      = "tournament_simulator",
                    spot_id      = spot.get("id", ""),
                    position     = (spot.get("position") or "").upper(),
                    stack_bb     = float(spot.get("stack_bb", 40)),
                    pot_type     = (spot.get("pot_type") or "ICM").upper(),
                    hero_cards   = spot.get("hero_cards", ""),
                    hero_action  = action.lower(),
                    gto_action   = str(result["best_action"]).lower(),
                    ev_loss      = round(float(result["dollar_ev_loss"]), 2),
                    why          = f"Tournament Sim — risk premium {spot.get('risk_premium', 0):.1%}",
                ))
                # Toast
                try:
                    from app.ui.components.toast import Toast
                    label = "🚨 ICM PUNT" if result["dollar_ev_loss"] > 0.7 else "❌ MTT hata"
                    Toast.show_warning(
                        self.window(),
                        f"{label}  ·  $EV kayıp: {result['dollar_ev_loss']:.2f}"
                    )
                except Exception:
                    pass
            except Exception:
                pass

        # Build a Türkçe verdict line with learning context
        ev_loss = result["dollar_ev_loss"]
        if ev_loss < 0.1:
            verdict = f"✅  Doğru karar"
            verdict_color = _C_GREEN
        elif ev_loss < 0.5:
            verdict = f"⚠  Marjinal — küçük EV kaybı"
            verdict_color = _C_AMBER
        elif ev_loss < 1.5:
            verdict = f"❌  Hata — drill et"
            verdict_color = _C_RED
        else:
            verdict = f"🔥  ICM PUNT — büyük leak"
            verdict_color = _C_RED
        self.report.setText(
            f"{verdict}\n"
            f"Sen: {action.upper()}  →  chipEV: {str(result['best_action']).upper()}  ·  "
            f"$EV kayıp: ${ev_loss:.2f}  ·  Stack: {result['chip_stack']:,} chip\n"
            f"Risk premium {result['risk_premium']:.1%}  ·  source: {review['source_confidence']}"
        )
        self.report.setStyleSheet(f"color:{verdict_color};")
        self.coach_message.emit(
            explain_spot(spot, action)
            + "\n\n━━━━━━━━━━━━━━━━━━━━━━\n"
            + "TURNUVA KARAR DEĞERLENDİRMESİ\n"
            + "━━━━━━━━━━━━━━━━━━━━━━\n"
            + f"Hero {review['hero_action']} vs baseline {review['solver_action']}\n"
            + f"$EV kayıp: ${review['ev_loss']:.2f}  ·  {review['exploit_note']}\n"
            + f"Drill hedefi: {review['drill_target']}"
        )
        self._refresh_context()
        self.load_spot()


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget:
            widget.deleteLater()
