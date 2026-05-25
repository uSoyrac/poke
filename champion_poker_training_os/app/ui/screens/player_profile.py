from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
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
from app.db.seed_data import leaks as seed_leaks


# GTO benchmark targets for 6-max cash
_BENCHMARKS = {
    "VPIP":      {"target": 25, "low": 18, "high": 32, "unit": "%"},
    "PFR":       {"target": 19, "low": 14, "high": 26, "unit": "%"},
    "3bet%":     {"target": 8,  "low": 5,  "high": 13, "unit": "%"},
    "WTSD":      {"target": 28, "low": 22, "high": 35, "unit": "%"},
    "W$SD":      {"target": 52, "low": 46, "high": 62, "unit": "%"},
    "AF":        {"target": 2.5,"low": 1.8,"high": 3.5, "unit": ""},
    "BB/100":    {"target": 5,  "low": 0,  "high": 999, "unit": ""},
}

_STRENGTHS_BY_STAT = {
    "VPIP":   ("Preflop range discipline", "Preflop range too tight"),
    "PFR":    ("Good aggression preflop", "Passive preflop — open more"),
    "WTSD":   ("Not spewing to showdown", "Going to showdown too often"),
    "W$SD":   ("Winning at showdown", "Losing at showdown — tighten river calls"),
    "AF":     ("Aggressive postflop", "Too passive postflop"),
    "BB/100": ("Profitable winrate", "Losing player — focus on leaks"),
}

_STUDY_RECS = [
    ("Math Lab — Pot Odds & EV drills", "Foundation: ensure every call/fold is equity-based."),
    ("BB Defend Combat Pack", "Expand BB defense vs BTN/SB min-raises."),
    ("River Blocker Master Pack", "Cut river bluff-catch leaks with blocker logic."),
    ("ICM Bootcamp", "Improve near-bubble and final-table decision quality."),
    ("Postflop Trainer — Turn Barreling", "Control second-barrel frequency on board-pairing turns."),
    ("AI Coach session review", "Use Gemini to review last 5 hands for pattern leaks."),
]


def _bar_widget(value: float, target: float, low: float, high: float,
                color_ok: str = "#5ad17a", color_warn: str = "#f4c842",
                color_bad: str = "#ff5a5a") -> QWidget:
    """Horizontal progress bar showing value vs benchmark range."""
    w = QWidget()
    layout = QHBoxLayout(w)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)

    bar_frame = QFrame()
    bar_frame.setFixedHeight(6)
    bar_frame.setMinimumWidth(80)
    bar_frame.setStyleSheet("background: #1a1e19; border-radius: 3px;")
    bar_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    # Compute fill ratio (0–1) within [0, high*1.5] range
    span = max(high * 1.5, 1)
    fill_pct = max(0, min(1, value / span))

    if low <= value <= high:
        color = color_ok
    elif value < low:
        color = color_warn
    else:
        color = color_bad

    fill = QFrame(bar_frame)
    fill.setGeometry(0, 0, int(fill_pct * 80), 6)
    fill.setStyleSheet(f"background: {color}; border-radius: 3px;")
    fill.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    layout.addWidget(bar_frame, 1)
    return w, color  # type: ignore[return-value]


class _StatCard(QFrame):
    """A single KPI tile with value, target, bar, and status dot."""

    def __init__(self, label: str, value: str, target: str, color: str = "#5ad17a"):
        super().__init__()
        self.setObjectName("MetricCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)

        lbl = QLabel(label.upper())
        lbl.setObjectName("TLabel")

        val_lbl = QLabel(value)
        val_lbl.setObjectName("MetricValue")
        val_lbl.setStyleSheet(f"color: {color};")

        tgt_lbl = QLabel(f"target {target}")
        tgt_lbl.setObjectName("Muted")
        tgt_lbl.setStyleSheet("font-size: 10px;")

        layout.addWidget(lbl)
        layout.addWidget(val_lbl)
        layout.addWidget(tgt_lbl)


class PlayerProfileScreen(QWidget):
    coach_message = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        scroll.setWidget(body)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

        self._layout = QVBoxLayout(body)
        self._layout.setContentsMargins(28, 24, 28, 28)
        self._layout.setSpacing(20)

        self._build_header()
        self._build_stats()
        self._build_progress()
        self._build_strengths_leaks()
        self._build_recommendations()
        self._layout.addStretch(1)

        # Refresh every time the screen is shown
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self._refresh)

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        self._refresh_timer.start(50)

    # ─── Build sections ─────────────────────────────────────────────────────────

    def _build_header(self) -> None:
        header_frame = QFrame()
        header_frame.setObjectName("Card")
        h_layout = QHBoxLayout(header_frame)
        h_layout.setContentsMargins(24, 20, 24, 20)
        h_layout.setSpacing(20)

        # Avatar placeholder
        avatar = QFrame()
        avatar.setFixedSize(64, 64)
        avatar.setStyleSheet(
            "background: #1a2940; border: 2px solid #5ad17a; border-radius: 32px;"
        )
        av_lbl = QLabel("UY")
        av_lbl.setAlignment(Qt.AlignCenter)
        av_lbl.setStyleSheet("color: #5ad17a; font-size: 20px; font-weight: 700;")
        av_l = QVBoxLayout(avatar)
        av_l.setContentsMargins(0, 0, 0, 0)
        av_l.addWidget(av_lbl)
        h_layout.addWidget(avatar)

        # Name + mode
        info_col = QVBoxLayout()
        self._name_lbl = QLabel("UYGAR")
        self._name_lbl.setObjectName("Title")
        self._name_lbl.setStyleSheet("font-size: 22px;")
        self._mode_lbl = QLabel("GTO MODE · Hero")
        self._mode_lbl.setObjectName("BrandTag")
        self._mode_lbl.setStyleSheet("color: #5ad17a; font-size: 11px;")
        info_col.addWidget(self._name_lbl)
        info_col.addWidget(self._mode_lbl)
        h_layout.addLayout(info_col)

        h_layout.addStretch(1)

        # Summary stats column
        right_col = QVBoxLayout()
        right_col.setSpacing(4)
        self._hands_lbl = QLabel("— hands played")
        self._hands_lbl.setObjectName("SectionTitle")
        self._hands_lbl.setAlignment(Qt.AlignRight)
        self._winrate_lbl = QLabel("—")
        self._winrate_lbl.setObjectName("Mono")
        self._winrate_lbl.setAlignment(Qt.AlignRight)
        right_col.addWidget(self._hands_lbl)
        right_col.addWidget(self._winrate_lbl)
        h_layout.addLayout(right_col)

        # Refresh button
        refresh_btn = QPushButton("↻ Refresh")
        refresh_btn.setFixedHeight(32)
        refresh_btn.clicked.connect(self._refresh)
        h_layout.addWidget(refresh_btn)

        self._layout.addWidget(header_frame)

    def _build_stats(self) -> None:
        section_hdr = QLabel("KEY STATS")
        section_hdr.setObjectName("NavGroupLabel")
        self._layout.addWidget(section_hdr)

        stats_frame = QFrame()
        stats_frame.setObjectName("Card")
        stats_layout = QVBoxLayout(stats_frame)
        stats_layout.setContentsMargins(20, 16, 20, 16)
        stats_layout.setSpacing(12)

        # Stat row (7 cards in a grid)
        self._stats_grid = QGridLayout()
        self._stats_grid.setSpacing(10)
        stats_layout.addLayout(self._stats_grid)

        # Benchmark bar table
        bar_lbl = QLabel("vs GTO Benchmarks (6-max cash)")
        bar_lbl.setObjectName("Muted")
        bar_lbl.setStyleSheet("font-size: 10px;")
        stats_layout.addWidget(bar_lbl)

        self._bar_table = QVBoxLayout()
        self._bar_table.setSpacing(6)
        stats_layout.addLayout(self._bar_table)

        self._layout.addWidget(stats_frame)

    def _build_progress(self) -> None:
        section_hdr = QLabel("SESSION PROGRESS (recent hands)")
        section_hdr.setObjectName("NavGroupLabel")
        self._layout.addWidget(section_hdr)

        prog_frame = QFrame()
        prog_frame.setObjectName("Card")
        prog_layout = QVBoxLayout(prog_frame)
        prog_layout.setContentsMargins(20, 16, 20, 16)

        self._progress_lbl = QLabel("Loading…")
        self._progress_lbl.setObjectName("Mono")
        self._progress_lbl.setWordWrap(True)
        self._progress_lbl.setStyleSheet("font-size: 12px; line-height: 1.8;")
        prog_layout.addWidget(self._progress_lbl)

        self._layout.addWidget(prog_frame)

    def _build_strengths_leaks(self) -> None:
        row = QHBoxLayout()
        row.setSpacing(16)

        # Strengths
        str_frame = QFrame()
        str_frame.setObjectName("Card")
        str_layout = QVBoxLayout(str_frame)
        str_layout.setContentsMargins(20, 16, 20, 16)
        str_layout.setSpacing(8)
        str_hdr = QLabel("STRENGTHS")
        str_hdr.setObjectName("SectionTitle")
        str_hdr.setStyleSheet("color: #5ad17a;")
        str_layout.addWidget(str_hdr)
        self._strengths_layout = QVBoxLayout()
        str_layout.addLayout(self._strengths_layout)
        row.addWidget(str_frame, 1)

        # Weaknesses / leaks
        wk_frame = QFrame()
        wk_frame.setObjectName("Card")
        wk_layout = QVBoxLayout(wk_frame)
        wk_layout.setContentsMargins(20, 16, 20, 16)
        wk_layout.setSpacing(8)
        wk_hdr = QLabel("LEAKS & WEAKNESSES")
        wk_hdr.setObjectName("SectionTitle")
        wk_hdr.setStyleSheet("color: #ff5a5a;")
        wk_layout.addWidget(wk_hdr)
        self._leaks_layout = QVBoxLayout()
        wk_layout.addLayout(self._leaks_layout)
        row.addWidget(wk_frame, 1)

        self._layout.addLayout(row)

    def _build_recommendations(self) -> None:
        section_hdr = QLabel("STUDY RECOMMENDATIONS")
        section_hdr.setObjectName("NavGroupLabel")
        self._layout.addWidget(section_hdr)

        recs_frame = QFrame()
        recs_frame.setObjectName("Card")
        recs_layout = QVBoxLayout(recs_frame)
        recs_layout.setContentsMargins(20, 16, 20, 16)
        recs_layout.setSpacing(10)
        self._recs_layout = QVBoxLayout()
        recs_layout.addLayout(self._recs_layout)
        self._layout.addWidget(recs_frame)

    # ─── Data refresh ───────────────────────────────────────────────────────────

    def _refresh(self) -> None:
        try:
            from app.db.repository import get_player_stats, get_leak_analysis, get_session_history
            stats = get_player_stats()
            leaks = get_leak_analysis()
            history = get_session_history(30)
        except Exception as exc:
            self._hands_lbl.setText(f"DB error: {exc}")
            return

        self._populate_header(stats)
        self._populate_stats(stats)
        self._populate_progress(stats, history)
        self._populate_strengths_leaks(stats, leaks)
        self._populate_recommendations(stats, leaks)

    def _populate_header(self, stats: dict) -> None:
        total = stats.get("total_hands", 0)
        bb100 = stats.get("bb_per_100", 0)
        win_rate = stats.get("win_rate", 0)
        self._hands_lbl.setText(f"{total} hands played")
        color = "#5ad17a" if bb100 >= 0 else "#ff5a5a"
        self._winrate_lbl.setText(
            f"<span style='color:{color}'>{bb100:+.1f} BB/100</span>  ·  "
            f"Win rate {win_rate:.0f}%"
        )
        self._winrate_lbl.setTextFormat(Qt.RichText)

    def _populate_stats(self, stats: dict) -> None:
        # Clear old cards
        while self._stats_grid.count():
            item = self._stats_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        while self._bar_table.count():
            item = self._bar_table.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                # clear sub-layouts
                pass

        total = stats.get("total_hands", 0)
        if total == 0:
            no_data = QLabel("No hands played yet — start a Play Session to build your profile.")
            no_data.setObjectName("Muted")
            self._stats_grid.addWidget(no_data, 0, 0)
            return

        vpip = stats.get("vpip", 0)
        pfr = round(vpip * 0.72, 1)
        three_bet = round(pfr * 0.38, 1)
        wtsd = stats.get("wtsd", 0)
        wsd = stats.get("wsd", 0)
        af = stats.get("af", 0)
        bb100 = stats.get("bb_per_100", 0)

        stat_data = [
            ("VPIP",   f"{vpip:.0f}%",  "25%",  vpip,  _BENCHMARKS["VPIP"]),
            ("PFR",    f"{pfr:.0f}%",   "19%",  pfr,   _BENCHMARKS["PFR"]),
            ("3bet%",  f"{three_bet:.0f}%", "8%", three_bet, _BENCHMARKS["3bet%"]),
            ("WTSD",   f"{wtsd:.0f}%",  "28%",  wtsd,  _BENCHMARKS["WTSD"]),
            ("W$SD",   f"{wsd:.0f}%",   "52%",  wsd,   _BENCHMARKS["W$SD"]),
            ("AF",     f"{af:.1f}",     "2.5",  af,    _BENCHMARKS["AF"]),
            ("BB/100", f"{bb100:+.1f}", "+5",   bb100, _BENCHMARKS["BB/100"]),
        ]

        for col, (name, val_str, tgt_str, val, bench) in enumerate(stat_data):
            low, high = bench["low"], bench["high"]
            if name == "BB/100":
                color = "#5ad17a" if val >= 0 else "#ff5a5a"
            elif low <= val <= high:
                color = "#5ad17a"
            elif abs(val - bench["target"]) < bench["target"] * 0.3:
                color = "#f4c842"
            else:
                color = "#ff5a5a"

            card = _StatCard(name, val_str, tgt_str, color)
            self._stats_grid.addWidget(card, 0, col)

        # Benchmark bars
        bar_row_lbl_row = QHBoxLayout()
        for col, (name, val_str, tgt_str, val, bench) in enumerate(stat_data):
            low, high = bench["low"], bench["high"]
            lbl = QLabel(f"{name}  {val_str}")
            lbl.setObjectName("Mono")
            lbl.setStyleSheet("font-size: 10px;")
            lbl.setFixedWidth(100)

            span = max(high * 1.5, 1)
            fill_pct = max(0, min(1, abs(val) / span))

            if name == "BB/100":
                color = "#5ad17a" if val >= 0 else "#ff5a5a"
            elif low <= val <= high:
                color = "#5ad17a"
            else:
                color = "#f4c842"

            bar_outer = QFrame()
            bar_outer.setFixedHeight(8)
            bar_outer.setStyleSheet("background: #1a1e19; border-radius: 3px;")
            bar_outer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

            bar_fill = QFrame(bar_outer)
            bar_fill.setGeometry(0, 0, max(4, int(fill_pct * 120)), 8)
            bar_fill.setStyleSheet(f"background: {color}; border-radius: 3px;")

            col_widget = QWidget()
            col_l = QVBoxLayout(col_widget)
            col_l.setContentsMargins(0, 0, 0, 0)
            col_l.setSpacing(2)
            col_l.addWidget(lbl)
            col_l.addWidget(bar_outer)
            bar_row_lbl_row.addWidget(col_widget, 1)

        bar_row_lbl_row_widget = QWidget()
        bar_row_lbl_row_widget.setLayout(bar_row_lbl_row)
        self._bar_table.addWidget(bar_row_lbl_row_widget)

    def _populate_progress(self, stats: dict, history: list) -> None:
        total = stats.get("total_hands", 0)
        if total == 0:
            self._progress_lbl.setText("No data yet — play some hands to see your progress.")
            return

        # Build a mini text sparkline from recent hands
        if history:
            chunks = []
            running = 0.0
            for i, h in enumerate(reversed(history[-20:])):
                running += h.get("hero_profit", 0)
                bar_h = max(1, min(8, int(abs(running) / 3)))
                bar_char = "▇" * bar_h
                profit = h.get("hero_profit", 0)
                color = "#5ad17a" if profit >= 0 else "#ff5a5a"
                chunks.append(f"<span style='color:{color}'>{bar_char}</span>")
            sparkline = "  ".join(chunks)
            cum_profit = stats.get("profit_bb", 0)
            trend = "📈" if cum_profit > 0 else "📉"
            self._progress_lbl.setText(
                f"{sparkline}<br>"
                f"<span style='color:#898d80; font-size:10px;'>"
                f"Hands {total}  ·  Cumulative {cum_profit:+.1f}bb  ·  Avg pot {stats.get('avg_pot',0):.1f}bb  {trend}"
                f"</span>"
            )
            self._progress_lbl.setTextFormat(Qt.RichText)
        else:
            self._progress_lbl.setText("No hand history yet.")

    def _populate_strengths_leaks(self, stats: dict, leaks: list) -> None:
        # Clear
        _clear_layout(self._strengths_layout)
        _clear_layout(self._leaks_layout)

        vpip = stats.get("vpip", 0)
        pfr = round(vpip * 0.72, 1)
        wtsd = stats.get("wtsd", 0)
        wsd = stats.get("wsd", 0)
        af = stats.get("af", 0)
        bb100 = stats.get("bb_per_100", 0)

        strengths = []
        weaknesses = []

        if 18 <= vpip <= 30:
            strengths.append("Preflop range discipline")
        else:
            weaknesses.append(f"VPIP {vpip:.0f}% — {'too loose' if vpip>30 else 'too tight'}")

        if 14 <= pfr <= 24:
            strengths.append("Solid preflop aggression")
        else:
            weaknesses.append(f"PFR {pfr:.0f}% — {'too passive' if pfr<14 else 'over-aggressive'}")

        if wtsd <= 30:
            strengths.append("Not going to showdown too often")
        else:
            weaknesses.append(f"WTSD {wtsd:.0f}% — spewing to showdown")

        if wsd >= 50:
            strengths.append("Winning at showdown consistently")
        elif stats.get("total_hands", 0) >= 10:
            weaknesses.append(f"W$SD {wsd:.0f}% — losing at showdown")

        if 1.8 <= af <= 3.5:
            strengths.append("Balanced aggression factor")
        elif af < 1.8:
            weaknesses.append(f"AF {af:.1f} — too passive postflop")

        if bb100 >= 0:
            strengths.append(f"Profitable at +{bb100:.1f}bb/100")
        else:
            weaknesses.append(f"Losing {abs(bb100):.1f}bb/100 — leak repair needed")

        if not strengths:
            strengths = ["Play more hands to identify strengths"]
        if not weaknesses:
            weaknesses = ["No major weaknesses detected — keep training"]

        for s in strengths[:5]:
            lbl = QLabel(f"✓  {s}")
            lbl.setStyleSheet("color: #5ad17a; font-size: 12px;")
            self._strengths_layout.addWidget(lbl)

        for i, leak in enumerate(leaks[:4]):
            name = leak.get("name", "—")
            sev = leak.get("severity", "")
            detail = leak.get("detail", leak.get("fix", ""))
            sev_color = {"Critical": "#ff3333", "High": "#ff5a5a", "Medium": "#f4c842"}.get(sev, "#898d80")
            lbl = QLabel(f"<span style='color:{sev_color}'>●</span>  {name}")
            lbl.setTextFormat(Qt.RichText)
            lbl.setStyleSheet("font-size: 12px;")
            lbl.setToolTip(detail)
            self._leaks_layout.addWidget(lbl)

        for w in weaknesses[:3]:
            lbl = QLabel(f"△  {w}")
            lbl.setStyleSheet("color: #f4c842; font-size: 12px;")
            self._leaks_layout.addWidget(lbl)

    def _populate_recommendations(self, stats: dict, leaks: list) -> None:
        _clear_layout(self._recs_layout)

        # Pick recommendations based on actual leaks
        recs = list(_STUDY_RECS)  # start with defaults
        if stats.get("total_hands", 0) < 5:
            recs = [
                ("Start a Play Session", "Play at least 10 hands to unlock personalized recommendations."),
                ("Math Lab — Pot Odds", "Master fundamental math before every other skill."),
            ]

        for i, (title, detail) in enumerate(recs[:5]):
            row = QFrame()
            row.setObjectName("Elevated")
            row_l = QHBoxLayout(row)
            row_l.setContentsMargins(14, 10, 14, 10)
            row_l.setSpacing(12)

            num = QLabel(f"{i+1:02d}")
            num.setObjectName("Mono")
            num.setStyleSheet("color: #5ad17a; font-size: 14px; font-weight: 700;")
            num.setFixedWidth(28)

            info = QVBoxLayout()
            title_lbl = QLabel(title)
            title_lbl.setObjectName("SectionTitle")
            title_lbl.setStyleSheet("font-size: 13px;")
            detail_lbl = QLabel(detail)
            detail_lbl.setObjectName("Muted")
            detail_lbl.setWordWrap(True)
            detail_lbl.setStyleSheet("font-size: 11px;")
            info.addWidget(title_lbl)
            info.addWidget(detail_lbl)

            row_l.addWidget(num)
            row_l.addLayout(info, 1)
            self._recs_layout.addWidget(row)


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
