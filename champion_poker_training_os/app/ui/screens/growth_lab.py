"""Growth & Edge Lab — pozitif edge'i üstel büyümeye çevirmenin matematiği.

İki sekme:
  • POKER BANKROLL: winrate + varyans + roll → iflas riski (RoR) + güvenli
    bankroll önerisi. Kendi profilinden (My Profile) otomatik doldurabilir.
  • EDGE / KELLY (genel): herhangi +EV bahis/işlem (kripto bot dahil) → optimal
    Kelly kesri, half-Kelly, overbet uyarısı, N işlemde sermaye çarpanı.

Felsefe: üstel büyüme = (edge var mı?) × (iflas etmeden hayatta kalmak).
Bu ekran ikisini de sayısal gösterir.
"""
from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)

from app.core.app_state import AppState
from app.poker.growth_lab import (
    TYPICAL_STD, analyze_bankroll, analyze_edge,
)

_ACCENT = "#5ad17a"
_INFO = "#5ad1ce"
_WARN = "#d6c668"
_DANGER = "#e87474"


def _card(title: str) -> tuple:
    f = QFrame()
    f.setObjectName("Card")
    lay = QVBoxLayout(f)
    lay.setContentsMargins(18, 14, 18, 16)
    lay.setSpacing(10)
    t = QLabel(title)
    t.setObjectName("SectionTitle")
    lay.addWidget(t)
    return f, lay


def _stat(label: str, value: str, color: str, sub: str = "") -> QFrame:
    f = QFrame()
    f.setObjectName("MetricCard")
    lay = QVBoxLayout(f)
    lay.setContentsMargins(12, 10, 12, 10)
    lay.setSpacing(3)
    l = QLabel(label.upper())
    l.setStyleSheet("color:#898d80; font-size:10px; font-weight:700;")
    v = QLabel(value)
    v.setStyleSheet(f"color:{color}; font-size:22px; font-weight:800;")
    lay.addWidget(l)
    lay.addWidget(v)
    if sub:
        s = QLabel(sub)
        s.setWordWrap(True)
        s.setStyleSheet("color:#b9bcae; font-size:11px;")
        lay.addWidget(s)
    return f


class GrowthLabScreen(QWidget):
    """Kelly + risk-of-ruin + compounding hesaplayıcı."""

    coach_message = Signal(str)
    navigate_requested = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self._mode = "bankroll"

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
        self._layout.setSpacing(16)

        title = QLabel("Growth & Edge Lab")
        title.setObjectName("Title")
        title.setStyleSheet("font-size:22px; font-weight:800; color:#f4f5ee;")
        self._layout.addWidget(title)

        sub = QLabel(
            "Üstel büyüme = (doğrulanmış pozitif edge) × (iflas etmeden hayatta "
            "kalmak). Bir kazanç edge değildir — edge örneklemde, sizing'de ve "
            "hayatta kalmada saklı. Poker bunu öğrenmenin en hızlı simülatörü."
        )
        sub.setObjectName("Muted")
        sub.setWordWrap(True)
        self._layout.addWidget(sub)

        toggle = QHBoxLayout()
        toggle.setSpacing(8)
        self._bk_btn = QPushButton("♠  Poker Bankroll")
        self._edge_btn = QPushButton("📈  Edge / Kelly (genel)")
        for b in (self._bk_btn, self._edge_btn):
            b.setCursor(Qt.PointingHandCursor)
            b.setCheckable(True)
        self._bk_btn.clicked.connect(lambda: self._set_mode("bankroll"))
        self._edge_btn.clicked.connect(lambda: self._set_mode("edge"))
        toggle.addWidget(self._bk_btn)
        toggle.addWidget(self._edge_btn)
        toggle.addStretch(1)
        self._layout.addLayout(toggle)

        # Girdi + sonuç kapları
        self._inputs_host = QVBoxLayout()
        self._layout.addLayout(self._inputs_host)
        self._results_host = QVBoxLayout()
        self._layout.addLayout(self._results_host)
        self._layout.addStretch(1)

        self._build_bankroll_inputs()
        self._build_edge_inputs()
        self._set_mode("bankroll")

    # ── mod ──
    def _set_mode(self, mode: str) -> None:
        self._mode = mode
        self._bk_btn.setChecked(mode == "bankroll")
        self._edge_btn.setChecked(mode == "edge")
        for b, on in ((self._bk_btn, mode == "bankroll"),
                      (self._edge_btn, mode == "edge")):
            if on:
                b.setStyleSheet(
                    f"QPushButton {{ background:{_ACCENT}; color:#0d0f0c; "
                    f"border:none; border-radius:5px; padding:9px 18px; "
                    f"font-size:13px; font-weight:700; }}")
            else:
                b.setStyleSheet(
                    "QPushButton { background:#131613; color:#898d80; "
                    "border:1px solid #33382c; border-radius:5px; "
                    "padding:9px 18px; font-size:13px; }")
        self._bankroll_box.setVisible(mode == "bankroll")
        self._edge_box.setVisible(mode == "edge")
        self._recompute()

    # ── Poker bankroll girdileri ──
    def _build_bankroll_inputs(self) -> None:
        box, lay = _card("Girdiler — Poker Bankroll")
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(8)

        self._fmt = QComboBox()
        self._fmt.addItems(list(TYPICAL_STD.keys()))
        self._fmt.currentTextChanged.connect(self._on_format)

        self._winrate = QDoubleSpinBox()
        self._winrate.setRange(-50, 50); self._winrate.setValue(5.0)
        self._winrate.setSingleStep(0.5); self._winrate.setSuffix(" bb/100")
        self._std = QDoubleSpinBox()
        self._std.setRange(10, 400); self._std.setValue(90.0)
        self._std.setSingleStep(5); self._std.setSuffix(" bb/100")
        self._buyin = QDoubleSpinBox()
        self._buyin.setRange(1, 100000); self._buyin.setValue(100.0)
        self._buyin.setSuffix(" bb")
        self._roll = QDoubleSpinBox()
        self._roll.setRange(1, 1_000_000); self._roll.setValue(2000.0)
        self._roll.setSingleStep(100); self._roll.setSuffix(" bb")

        for w in (self._winrate, self._std, self._buyin, self._roll):
            w.valueChanged.connect(self._recompute)

        grid.addWidget(QLabel("Format"), 0, 0); grid.addWidget(self._fmt, 0, 1)
        grid.addWidget(QLabel("Winrate"), 0, 2); grid.addWidget(self._winrate, 0, 3)
        grid.addWidget(QLabel("Std sapma"), 1, 0); grid.addWidget(self._std, 1, 1)
        grid.addWidget(QLabel("Buy-in"), 1, 2); grid.addWidget(self._buyin, 1, 3)
        grid.addWidget(QLabel("Bankroll"), 2, 0); grid.addWidget(self._roll, 2, 1)
        lay.addLayout(grid)

        fill = QPushButton("⟶  Profilimden winrate/std doldur")
        fill.setObjectName("NavButton")
        fill.clicked.connect(self._fill_from_profile)
        lay.addWidget(fill)

        self._bankroll_box = box
        self._inputs_host.addWidget(box)

    def _on_format(self, name: str) -> None:
        if name in TYPICAL_STD:
            self._std.setValue(TYPICAL_STD[name])

    def _fill_from_profile(self) -> None:
        try:
            from app.db.repository import get_player_stats
            s = get_player_stats()
            wr = s.get("bb_per_100", 0)
            self._winrate.setValue(float(wr))
            self.coach_message.emit(
                f"Profilinden dolduruldu: winrate {wr:+.1f} bb/100. "
                "Std'yi kendi varyansına göre ayarla (örneklemin büyüdükçe netleşir)."
            )
        except Exception:
            self.coach_message.emit("Profil verisi okunamadı — manuel gir.")

    # ── Edge/Kelly girdileri ──
    def _build_edge_inputs(self) -> None:
        box, lay = _card("Girdiler — Edge / Kelly (bot, işlem, herhangi +EV bahis)")
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(8)

        self._winp = QDoubleSpinBox()
        self._winp.setRange(1, 99); self._winp.setValue(55.0); self._winp.setSuffix(" %")
        self._payoff = QDoubleSpinBox()
        self._payoff.setRange(0.01, 100); self._payoff.setValue(1.0)
        self._payoff.setSingleStep(0.1); self._payoff.setPrefix("×")
        self._lossf = QDoubleSpinBox()
        self._lossf.setRange(0.01, 1.0); self._lossf.setValue(1.0)
        self._lossf.setSingleStep(0.05); self._lossf.setPrefix("×")
        self._frac = QDoubleSpinBox()
        self._frac.setRange(0, 100); self._frac.setValue(0.0); self._frac.setSuffix(" %")
        self._frac.setSpecialValueText("Half-Kelly (oto)")
        self._ntrials = QSpinBox()
        self._ntrials.setRange(1, 100000); self._ntrials.setValue(100)

        for w in (self._winp, self._payoff, self._lossf, self._frac):
            w.valueChanged.connect(self._recompute)
        self._ntrials.valueChanged.connect(self._recompute)

        grid.addWidget(QLabel("Kazanma olasılığı"), 0, 0); grid.addWidget(self._winp, 0, 1)
        grid.addWidget(QLabel("Kazanç (yatırılanın katı)"), 0, 2); grid.addWidget(self._payoff, 0, 3)
        grid.addWidget(QLabel("Kayıp (yatırılanın katı)"), 1, 0); grid.addWidget(self._lossf, 1, 1)
        grid.addWidget(QLabel("Bahis kesri (0=oto)"), 1, 2); grid.addWidget(self._frac, 1, 3)
        grid.addWidget(QLabel("İşlem sayısı (proj.)"), 2, 0); grid.addWidget(self._ntrials, 2, 1)
        lay.addLayout(grid)

        hint = QLabel(
            "İpucu: kripto botun için 'kazanma olasılığı' = kazançlı işlem oranı; "
            "kazanç/kayıp = işlem başına ort. % getiri/zarar (fee/slippage dahil!). "
            "Edge yoksa Kelly 0 çıkar — büyüme yoktur."
        )
        hint.setObjectName("Muted"); hint.setWordWrap(True)
        lay.addWidget(hint)

        self._edge_box = box
        self._inputs_host.addWidget(box)

    # ── Hesapla + sonuç çiz ──
    def _recompute(self) -> None:
        while self._results_host.count():
            it = self._results_host.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        if self._mode == "bankroll":
            self._render_bankroll()
        else:
            self._render_edge()

    def _render_bankroll(self) -> None:
        rep = analyze_bankroll(
            self._winrate.value(), self._std.value(),
            self._roll.value(), self._buyin.value())
        box, lay = _card("Sonuç — Bankroll Sağlığı")
        row = QHBoxLayout(); row.setSpacing(12)

        ror_color = _ACCENT if rep.ror < 0.05 else (_WARN if rep.ror < 0.20 else _DANGER)
        row.addWidget(_stat("İflas riski (RoR)", f"%{rep.ror*100:.1f}", ror_color,
                            "Bu winrate+varyans+roll ile tüm bankroll'u kaybetme olasılığı."))
        row.addWidget(_stat("Roll (buy-in)", f"{rep.buyins:.0f}", _INFO,
                            f"Bankroll {rep.bankroll_bb:.0f}bb / {rep.buyin_bb:.0f}bb buy-in."))
        if rep.safe_buyins == float("inf"):
            row.addWidget(_stat("Güvenli roll", "∞", _DANGER,
                                "Winrate ≤ 0 → hiçbir bankroll iflası önlemez. Önce EDGE."))
        else:
            row.addWidget(_stat("Güvenli roll (%5 RoR)", f"{rep.safe_buyins:.0f} BI", _ACCENT,
                                f"≈ {rep.safe_bankroll_bb:.0f}bb. Bunun üstü güvenli bölge."))
        lay.addLayout(row)

        if rep.winrate_per100 <= 0:
            verdict = ("🔴 Winrate ≤ 0: EDGE YOK. Compounding seni aşağı götürür. "
                       "Önce yeneceğin masa/format bul (game selection) — bankroll "
                       "tek başına iflası önleyemez.")
            vc = _DANGER
        elif rep.healthy:
            verdict = ("🟢 Sağlıklı bölge: edge pozitif ve roll iflas riskini "
                       "düşük tutuyor. Edge × hacim × disiplin → üstel büyüme bu "
                       "koşulda çalışır. Stake yükseltmeyi düşünebilirsin.")
            vc = _ACCENT
        else:
            verdict = (f"🟡 Roll ince: iflas riski %{rep.ror*100:.0f}. Edge gerçek "
                       f"olsa bile bir downswing seni silebilir. {rep.safe_buyins:.0f} "
                       "buy-in'e çıkana dek stake düşür ya da roll büyüt.")
            vc = _WARN
        v = QLabel(verdict); v.setWordWrap(True)
        v.setStyleSheet(f"color:{vc}; font-size:13px; padding-top:6px;")
        lay.addWidget(v)

        link = QLabel("İlke: bkz. Playbook → Bankroll & Masa Seçimi / MTT Bankroll & Varyans.")
        link.setObjectName("Muted"); link.setWordWrap(True)
        lay.addWidget(link)
        self._results_host.addWidget(box)

    def _render_edge(self) -> None:
        chosen = None if self._frac.value() <= 0 else self._frac.value() / 100.0
        rep = analyze_edge(
            self._winp.value() / 100.0, self._payoff.value(),
            self._lossf.value(), chosen, self._ntrials.value())
        box, lay = _card("Sonuç — Edge / Kelly")
        row = QHBoxLayout(); row.setSpacing(12)

        ev_color = _ACCENT if rep.ev > 0 else _DANGER
        row.addWidget(_stat("Edge (EV/birim)", f"{rep.ev:+.3f}", ev_color,
                            "İşlem başına aritmetik beklenen değer. ≤0 ise büyüme yok."))
        row.addWidget(_stat("Full Kelly", f"%{rep.kelly*100:.1f}", _INFO,
                            "Log-büyümeyi maksimize eden bahis kesri."))
        row.addWidget(_stat("Half-Kelly (öneri)", f"%{rep.half_kelly*100:.1f}", _ACCENT,
                            "Pratik standart: büyümenin ~%75'i, varyansın yarısı."))
        lay.addLayout(row)

        row2 = QHBoxLayout(); row2.setSpacing(12)
        gc = _ACCENT if rep.growth_chosen > 0 else _DANGER
        row2.addWidget(_stat(f"Kullanılan kesir", f"%{rep.chosen_frac*100:.1f}", _INFO,
                            "overbet" if rep.overbet else "Kelly içinde"))
        mult_txt = (f"{rep.multiple_chosen:.2f}×" if rep.multiple_chosen < 1e6 else "≫")
        row2.addWidget(_stat(f"{rep.n_trials} işlemde", mult_txt, gc,
                            "Beklenen sermaye çarpanı (geometrik)."))
        dbl = ("∞" if rep.trials_double == float("inf") else f"{rep.trials_double:.0f}")
        row2.addWidget(_stat("2'ye katlama", dbl, _INFO, "Gereken işlem sayısı."))
        lay.addLayout(row2)

        if not rep.has_edge:
            verdict = ("🔴 EDGE YOK (Kelly 0). Bu parametrelerde compounding sermayeni "
                       "eritir. Botun burada takılıyorsa: fee/slippage edge'i yiyor ya da "
                       "edge backtest'te var, canlıda yok. Önce edge'i doğrula.")
            vc = _DANGER
        elif rep.overbet:
            verdict = (f"🟡 OVERBET: kullandığın %{rep.chosen_frac*100:.0f}, full Kelly "
                       f"%{rep.kelly*100:.0f}'in üstünde. Edge gerçek olsa bile aşırı "
                       "sizing büyümeyi düşürür, ruin riskini patlatır. Half-Kelly'e in.")
            vc = _WARN
        else:
            verdict = ("🟢 Edge var ve sizing makul. Üstel büyümenin iki şartı da "
                       "sağlanıyor: pozitif edge + hayatta kalır boyut. Hacim arttıkça "
                       "şans ortalanır, edge ortaya çıkar.")
            vc = _ACCENT
        v = QLabel(verdict); v.setWordWrap(True)
        v.setStyleSheet(f"color:{vc}; font-size:13px; padding-top:6px;")
        lay.addWidget(v)
        self._results_host.addWidget(box)
