"""MTT setup dialog — config for tournament play.

User-facing config:
  • Tournament type (Online Turbo / Live / Hyper / etc.)
  • Field size (number of players)
  • Buy-in
  • Starting stack
  • Minutes per level (speed)
  • Big-blind ante on/off
  • Bot skill: Human-Like (Easy / Medium / Hard) vs GTO-Style
  • Player mix: % loose vs tight, % aggro vs passive

Returns a `MttConfig` dict on accept that downstream code consumes.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field, asdict
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


from app.simulator.skill_pools import HUMAN_LIKE_POOL as _HUMAN_LIKE_POOL, GTO_POOL as _GTO_POOL


@dataclass
class MttConfig:
    tournament_name:   str  = "Online Turbo Low Stakes"
    field_size:        int  = 100
    buyin:             float = 50.0
    starting_stack:    int  = 2000
    minutes_per_level: int  = 10
    bb_ante:           bool = True
    skill_style:       str  = "Human-Like"   # or "GTO-Style"
    skill_level:       str  = "Medium"        # Easy / Medium / Hard
    table_size:        int  = 9                # seats at the active table
    seed:              Optional[int] = None

    # ── Derived properties — these are what the engine actually reads ──

    @property
    def speed_class(self) -> str:
        """Map (tournament_name + minutes_per_level) to engine speed key."""
        name = self.tournament_name.lower()
        # Explicit overrides by name
        if "hyper" in name:                   return "hyper"
        if "live" in name:                    return "regular"
        if "wsop" in name:                    return "regular"
        # Else use minutes_per_level
        if self.minutes_per_level <= 4:       return "hyper"
        if self.minutes_per_level <= 8:       return "turbo"
        return "regular"

    @property
    def ante_factor(self) -> float:
        """How much ante per orbit (as fraction of BB). 0 if disabled."""
        return 1.0 if self.bb_ante else 0.0

    @property
    def prize_pool(self) -> float:
        return self.buyin * self.field_size * 0.93   # 7% rake

    def make_bot_mix(self, n_seats: int) -> list[str]:
        """Generate a realistic per-seat archetype list for one table.

        Mixing is randomised but driven by the chosen style+level.
        """
        rng = random.Random(self.seed) if self.seed is not None else random.Random()
        pool = _GTO_POOL if self.skill_style == "GTO-Style" else _HUMAN_LIKE_POOL
        archetypes = pool.get(self.skill_level, pool["Medium"])
        # Don't bias to the same archetype — sample with replacement and shuffle
        chosen = [rng.choice(archetypes) for _ in range(n_seats)]
        rng.shuffle(chosen)
        return chosen


# ── Dialog ────────────────────────────────────────────────────────────────

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


def _label(text: str, muted: bool = False, min_w: int = 140) -> QLabel:
    lbl = QLabel(text)
    color = _C_MUTED if muted else _C_TEXT
    weight = "500" if muted else "700"
    lbl.setStyleSheet(f"color:{color};font-size:13px;font-weight:{weight};background:transparent;")
    lbl.setMinimumWidth(min_w)
    return lbl


def _section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color:{_C_RED};font-size:13px;font-weight:800;"
        f"background:transparent;padding:4px 0;"
    )
    return lbl


class MttSetupDialog(QDialog):
    """Modal config dialog. After accept() use `.config` to read result."""

    def __init__(self, parent: Optional[QWidget] = None, preset: Optional[MttConfig] = None):
        super().__init__(parent)
        self.setWindowTitle("MULTI-TABLE TOURNAMENT CONFIGURATION")
        self.setModal(True)
        self.setMinimumWidth(780)
        self.setMinimumHeight(480)
        self.config = preset or MttConfig()
        self.setStyleSheet(
            f"QDialog {{ background:#0A0E14; }}"
            f"QSpinBox, QComboBox {{"
            f"  background:{_C_PANEL}; color:{_C_TEXT};"
            f"  border:1px solid {_C_BORDER}; border-radius:0;"
            f"  padding:5px 8px; font-size:13px; min-height:24px;"
            f"}}"
            f"QSpinBox:focus, QComboBox:focus {{ border-color:{_C_CYAN}; }}"
            f"QCheckBox {{ color:{_C_TEXT}; font-size:13px; spacing:8px; }}"
            f"QCheckBox::indicator {{ width:16px; height:16px; }}"
            f"QCheckBox::indicator:unchecked {{"
            f"  background:{_C_PANEL}; border:1.5px solid {_C_BORDER}; border-radius:0;"
            f"}}"
            f"QCheckBox::indicator:checked {{"
            f"  background:{_C_CYAN}; border:1.5px solid {_C_CYAN}; border-radius:0;"
            f"}}"
        )

        # ── Title bar ──────────────────────────────────────────────────
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(14)

        title = QLabel("♠  MULTI-TABLE TOURNAMENT CONFIGURATION")
        title.setStyleSheet(
            f"color:{_C_RED};font-size:18px;font-weight:800;"
            f"padding:4px 0 8px 0;background:transparent;"
        )
        title.setAlignment(Qt.AlignCenter)
        root.addWidget(title)

        # ── Basic Options panel ────────────────────────────────────────
        basic = QFrame()
        basic.setStyleSheet(
            f"QFrame {{ background:{_C_PANEL}; border:1px solid {_C_BORDER}; border-radius:0; }}"
        )
        bl = QVBoxLayout(basic)
        bl.setContentsMargins(16, 12, 16, 14)
        bl.setSpacing(10)
        bl.addWidget(_section_label("Basic Options"))

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(10)
        # Give each input column a sane minimum so values/labels don't clip
        grid.setColumnMinimumWidth(0, 150)   # left labels
        grid.setColumnMinimumWidth(1, 180)   # left inputs
        grid.setColumnMinimumWidth(2, 24)    # gap
        grid.setColumnMinimumWidth(3, 110)   # right labels
        grid.setColumnMinimumWidth(4, 150)   # right inputs

        # Row 0 — Type
        grid.addWidget(_label("Type:"), 0, 0)
        self.type_combo = QComboBox()
        self.type_combo.addItems([
            "Online Turbo Low Stakes",
            "Online Turbo Mid Stakes",
            "Online Hyper Turbo",
            "Live Regional MTT",
            "Live WSOP-Style",
            "Sit & Go",
            "PKO Bounty",
            "Daily Freezeout",
        ])
        self.type_combo.setCurrentText(self.config.tournament_name)
        self.type_combo.setToolTip(
            "Turnuva tipi:\n"
            "  • 'Hyper' adı → çok hızlı blind artışı\n"
            "  • 'Live' / 'WSOP' adı → yavaş, derin yapı (regular)\n"
            "  • Diğerleri → Minutes/Level değerine göre belirlenir\n"
            "Sonuç ekranındaki ve archive'daki turnuva ismi de bu olur."
        )
        grid.addWidget(self.type_combo, 0, 1, 1, 2)

        # Row 0 — Skill style buttons
        grid.addWidget(_label("Skill:"), 0, 3)
        skill_row = QHBoxLayout()
        skill_row.setSpacing(0)
        self.btn_human = QPushButton("Human-Like")
        self.btn_gto = QPushButton("GTO-Style")
        self.btn_human.setToolTip(
            "Human-Like: Bot'lar gerçek oyuncu davranışı sergiler (Fish, "
            "Calling Station, Aggro Fish, Maniac, TAG, vb. arketipleri "
            "karıştırılarak masaya yerleştirilir)."
        )
        self.btn_gto.setToolTip(
            "GTO-Style: Bot'lar dengeli oynar (Balanced Reg, Shark, TAG). "
            "Daha tutarlı raise/3bet frekansları, daha az exploitable."
        )
        for b in (self.btn_human, self.btn_gto):
            b.setCheckable(True)
            b.setFixedHeight(28)
        self.btn_human.setChecked(self.config.skill_style == "Human-Like")
        self.btn_gto.setChecked(self.config.skill_style == "GTO-Style")
        self._update_skill_btns()
        self.btn_human.clicked.connect(lambda: self._set_skill_style("Human-Like"))
        self.btn_gto.clicked.connect(lambda: self._set_skill_style("GTO-Style"))
        skill_row.addWidget(self.btn_human)
        skill_row.addWidget(self.btn_gto)
        skill_w = QWidget(); skill_w.setLayout(skill_row)
        grid.addWidget(skill_w, 0, 4, 1, 2)

        # Row 1 — Field size, skill level
        grid.addWidget(_label("Number of Players:"), 1, 0)
        self.players_spin = QSpinBox()
        self.players_spin.setRange(2, 5000)
        self.players_spin.setSingleStep(10)
        self.players_spin.setValue(self.config.field_size)
        self.players_spin.setToolTip(
            "Toplam turnuva oyuncu sayısı. Sen masada ~9 kişiyle oynarsın; "
            "diğer (N−1) oyuncu arka planda istatistiksel olarak simüle "
            "edilir (FieldSimulator). Daha çok oyuncu → daha uzun turnuva, "
            "daha geç ITM."
        )
        grid.addWidget(self.players_spin, 1, 1)

        grid.addWidget(_label("Skill Level:"), 1, 3)
        self.level_combo = QComboBox()
        self.level_combo.addItems(["Easy", "Medium", "Hard"])
        self.level_combo.setCurrentText(self.config.skill_level)
        self.level_combo.setToolTip(
            "Bot havuzunun seviyesi:\n"
            "  • Easy → Fish + Calling Station + Maniac (gevşek/zayıf)\n"
            "  • Medium → TAG + Reg + bazı fish (dengeli)\n"
            "  • Hard → Shark + Balanced Reg + LAG (sıkı/agresif)"
        )
        grid.addWidget(self.level_combo, 1, 4)

        # Row 2 — Minutes per level, buy-in
        grid.addWidget(_label("Minutes per Level:"), 2, 0)
        self.mins_spin = QSpinBox()
        self.mins_spin.setRange(1, 120)
        self.mins_spin.setValue(self.config.minutes_per_level)
        self.mins_spin.setToolTip(
            "Her blind seviyesi için süre (dakika):\n"
            "  • ≤4 dk → Hyper turbo blind yapısı\n"
            "  • 5–8 dk → Turbo blind yapısı\n"
            "  • ≥9 dk → Regular (yavaş) blind yapısı\n"
            "Tournament Play modunda 10 el sonrası bir sonraki seviyeye geçilir."
        )
        grid.addWidget(self.mins_spin, 2, 1)

        grid.addWidget(_label("Buy-in ($):"), 2, 3)
        self.buyin_spin = QSpinBox()
        self.buyin_spin.setRange(1, 100000)
        self.buyin_spin.setValue(int(self.config.buyin))
        self.buyin_spin.setToolTip(
            "Buy-in ($). Prize pool = buy-in × oyuncu sayısı × 0.93 "
            "(7% rake). Bitiş sıralamana göre ROI buradan hesaplanır ve "
            "Past Tournaments arşivine kaydedilir."
        )
        grid.addWidget(self.buyin_spin, 2, 4)

        # Row 3 — Starting stack, table size
        grid.addWidget(_label("Starting Stack:"), 3, 0)
        self.stack_spin = QSpinBox()
        self.stack_spin.setRange(100, 1000000)
        self.stack_spin.setSingleStep(500)
        self.stack_spin.setValue(self.config.starting_stack)
        self.stack_spin.setToolTip(
            "Başlangıç chip stack'i. Blind yapısı buna göre otomatik "
            "ölçeklenir → L1 BB ≈ starting_stack / 100 (yani 100bb deep "
            "başlarsın). 2000 chip → L1 = 10/20, 20000 chip → L1 = 100/200."
        )
        grid.addWidget(self.stack_spin, 3, 1)

        grid.addWidget(_label("Table Seats:"), 3, 3)
        self.seats_spin = QSpinBox()
        self.seats_spin.setRange(2, 11)
        self.seats_spin.setValue(self.config.table_size)
        self.seats_spin.setSuffix(" seats")
        self.seats_spin.setToolTip(
            "Hero'nun oturduğu masadaki toplam koltuk sayısı (hero dahil). "
            "9 = full ring, 6 = 6-max, 2 = heads-up. Toplam oyuncu sayısı "
            "ayrı (yukarıdaki 'Number of Players')."
        )
        grid.addWidget(self.seats_spin, 3, 4)

        # Row 4 — BB ante checkbox
        self.bb_ante = QCheckBox("Use Big Blind Ante")
        self.bb_ante.setChecked(self.config.bb_ante)
        self.bb_ante.setToolTip(
            "Modern online turnuvalarda BB her el ekstra ante öder (orbit "
            "başına extra cost). Açıkken bot'lar ve hero blind/ante baskısı "
            "altında daha çok el oynamak zorunda kalır. Kapatınca sadece "
            "SB/BB cost'u, daha relaxed yapı."
        )
        grid.addWidget(self.bb_ante, 4, 0, 1, 2)

        bl.addLayout(grid)
        root.addWidget(basic)

        # ── Preview line ───────────────────────────────────────────────
        self.preview = QLabel()
        self.preview.setStyleSheet(
            f"color:{_C_MUTED};font-size:12px;background:transparent;padding:2px 4px;"
        )
        self.preview.setWordWrap(True)
        root.addWidget(self.preview)
        for w in (self.type_combo, self.level_combo):
            w.currentTextChanged.connect(self._refresh_preview)
        for w in (self.players_spin, self.buyin_spin, self.stack_spin,
                  self.mins_spin, self.seats_spin):
            w.valueChanged.connect(self._refresh_preview)
        self.bb_ante.stateChanged.connect(self._refresh_preview)
        self._refresh_preview()

        # ── Submit row ─────────────────────────────────────────────────
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setFixedHeight(36)
        cancel.setStyleSheet(
            f"QPushButton{{background:{_C_PANEL};color:{_C_TEXT};"
            f"border:1px solid {_C_BORDER};border-radius:0;font-size:13px;padding:0 18px;}}"
        )
        cancel.clicked.connect(self.reject)
        bottom.addWidget(cancel)

        submit = QPushButton("▶  Start Tournament")
        submit.setFixedHeight(40)
        submit.setStyleSheet(
            f"QPushButton{{background:{_C_GREEN};color:#061018;"
            f"border:none;border-radius:0;font-size:14px;font-weight:800;padding:0 22px;}}"
            f"QPushButton:hover{{background:#0EA371;}}"
        )
        submit.clicked.connect(self._accept)
        bottom.addWidget(submit)
        root.addLayout(bottom)

    def _set_skill_style(self, style: str) -> None:
        self.config.skill_style = style
        self.btn_human.setChecked(style == "Human-Like")
        self.btn_gto.setChecked(style == "GTO-Style")
        self._update_skill_btns()
        self._refresh_preview()

    def _update_skill_btns(self) -> None:
        for b, active_color in ((self.btn_human, _C_RED), (self.btn_gto, _C_CYAN)):
            if b.isChecked():
                b.setStyleSheet(
                    f"QPushButton{{background:{active_color};color:#061018;"
                    f"border:none;font-weight:800;font-size:12px;padding:0 14px;border-radius:0;}}"
                )
            else:
                b.setStyleSheet(
                    f"QPushButton{{background:{_C_PANEL};color:{_C_MUTED};"
                    f"border:1px solid {_C_BORDER};font-size:12px;padding:0 14px;border-radius:0;}}"
                )

    def _refresh_preview(self) -> None:
        n     = self.players_spin.value()
        stack = self.stack_spin.value()
        bb    = max(20, stack // 100)
        buyin = self.buyin_spin.value()
        pool  = int(n * buyin * 0.93)
        ante  = "BB-ante ON" if self.bb_ante.isChecked() else "no ante"
        # Build a transient MttConfig to read derived speed_class
        tmp = MttConfig(
            tournament_name   = self.type_combo.currentText(),
            minutes_per_level = self.mins_spin.value(),
        )
        speed = tmp.speed_class.upper()
        self.preview.setText(
            f"► {n} oyuncu  ·  ${buyin} buy-in  ·  başlangıç {stack:,} chip "
            f"(~{stack // bb}bb)  ·  level {self.mins_spin.value()}dk → {speed}  ·  {ante}\n"
            f"   Prize pool ≈ ${pool:,}  ·  Bots: "
            f"{self.config.skill_style} / {self.level_combo.currentText()}  ·  "
            f"{self.seats_spin.value()}-handed table"
        )

    def _accept(self) -> None:
        self.config = MttConfig(
            tournament_name   = self.type_combo.currentText(),
            field_size        = self.players_spin.value(),
            buyin             = float(self.buyin_spin.value()),
            starting_stack    = self.stack_spin.value(),
            minutes_per_level = self.mins_spin.value(),
            bb_ante           = self.bb_ante.isChecked(),
            skill_style       = "GTO-Style" if self.btn_gto.isChecked() else "Human-Like",
            skill_level       = self.level_combo.currentText(),
            table_size        = self.seats_spin.value(),
        )
        self.accept()


def open_mtt_setup(parent: QWidget, preset: Optional[MttConfig] = None) -> Optional[MttConfig]:
    """Convenience: open dialog modally and return MttConfig or None on cancel."""
    dlg = MttSetupDialog(parent, preset)
    if dlg.exec() == QDialog.Accepted:
        return dlg.config
    return None
