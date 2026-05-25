"""Knowledge Base — kavram kartları + oyuncu profil kütüphanesi."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QTabWidget, QVBoxLayout, QWidget,
)

from app.ai.rag import search_concepts
from app.core.app_state import AppState
from app.engine.bot_brain import BOT_ARCHETYPES

_ACCENT = "#5ad17a"
_DANGER = "#e87474"
_WARN   = "#d6c668"
_MUTED  = "#898d80"
_INK    = "#f4f5ee"
_INK2   = "#d6d8cf"
_BG2    = "#131613"
_LINE2  = "#33382c"
_INFO   = "#5ad1ce"

# Renk etiketleri oyuncu tiplerine göre
_PROFILE_COLORS = {
    "TAG":            (_ACCENT, "Tight-Aggressive"),
    "Balanced Reg":   (_ACCENT, "Reg"),
    "Reg":            (_ACCENT, "Reg"),
    "Shark":          (_INFO,   "Threat"),
    "Solver Bot":     (_INFO,   "GTO"),
    "GTO Expert":     (_INFO,   "GTO"),
    "LAG":            (_WARN,   "Loose-Aggressive"),
    "Aggro Fish":     (_WARN,   "Spew"),
    "Maniac":         (_DANGER, "Wild"),
    "Karma (Mixed)":  (_WARN,   "Random"),
    "Fish":           (_MUTED,  "Passive"),
    "Calling Station":(_MUTED,  "Station"),
    "Nit":            (_MUTED,  "Tight"),
    "Rock":           (_MUTED,  "Ultra-Nit"),
    "Tight Passive":  (_MUTED,  "Passive"),
    "Bubble Nit":     (_MUTED,  "ICM-Tight"),
}

# Detaylı profil bilgileri — her archetype için
_PROFILE_DETAILS: dict[str, dict] = {
    "TAG": {
        "thinking":   "Her kararı equity bazlı. Pot odds hesaplar, marginal sporlarda sıkı kalır.",
        "tendencies": "Folds to 3-bets unless strong. C-bets regularly with value/semi-bluff range.",
        "exploit":    "3-bet bluffs az — fold equity düşük. Postflop float etkili (IP). Steal blinds agresif.",
        "tells":      "Bet = güçlü range. Check-raise = çok güçlü. Fold to big river bet.",
        "danger":     "Orta seviye — exploitable but consistent.",
    },
    "LAG": {
        "thinking":   "Fold equity + pot equity her elde. Zayıf elleri de barrel eder. Position odaklı.",
        "tendencies": "3-bets light, barrels frequently, will bluff river with missed draws.",
        "exploit":    "Trap kur — check güçlü elleri. Float ve check-raise bluff çalışmaz. Value bet thin.",
        "tells":      "Sizing büyük ama her zaman güçlü değil. 3-bet'e fold ihtimali düşük.",
        "danger":     "Tehlikeli IP — OOP'ta daha pasif.",
    },
    "Nit": {
        "thinking":   "Sadece nut-heavy ellerde hareket. Risk minimizasyonu öncelikli.",
        "tendencies": "Folds to aggression. Rarely 3-bets. When they bet, they HAVE it.",
        "exploit":    "Steal blinds constantly. Fold to their 3-bets / big bets. Float their missed cbets.",
        "tells":      "Check = weak (usually). Bet = value always. Never bluffs river.",
        "danger":     "Düşük — sadece karşı durunca kaybedirsin.",
    },
    "Calling Station": {
        "thinking":   "Showdown değeri arar. Pot odds nadiren hesaplar. Fold etmekten çekinir.",
        "tendencies": "Calls everything — pre/post. Rarely raises without nuts.",
        "exploit":    "Value bet thin (top pair+). ASLA bluff. Büyük sizing'le value al.",
        "tells":      "Bet = value. Check = weakness. Big raise = very strong.",
        "danger":     "EV+ vs — sadece değer betlerin kaybolursa zarar.",
    },
    "Maniac": {
        "thinking":   "Aggression = leverage. Azar azar equity hesabı. Çok bluff.",
        "tendencies": "Overbets, 3-bets wide, bluffs everywhere, hard to put on range.",
        "exploit":    "Trap: check güçlü elleri, induce bluffs. Tighten preflop. Call down lighter.",
        "tells":      "Her bet aggressive değil — but fold to their river shove only with weak hand.",
        "danger":     "Yüksek varyans — bankroll için risk. Ama EV+ dostunla.",
    },
    "Shark": {
        "thinking":   "GTO-ish yaklaşım. Leakleri exploit eder. Solver output bilgisi var.",
        "tendencies": "Balanced 3-bet range, mixed strategies, exploits poorly defended spots.",
        "exploit":    "Zor — mixed strategy kulllanır. Solver çalışması gerektirir. Timing tell ara.",
        "tells":      "Timing consistent. Bet sizing tells az. Pay attention to sizing changes.",
        "danger":     "Çok tehlikeli — edge küçük. Masa değiştir.",
    },
    "Fish": {
        "thinking":   "El gücüne odaklanır — pot odds, equity yok. Limping çok.",
        "tendencies": "Plays too many hands, calls pre wide, gives up postflop when hit nothing.",
        "exploit":    "Value bet every pair+. Iso raise the fish. Steal their blind often.",
        "tells":      "Limp = weak range. Check = usually weak. Big raise = strong.",
        "danger":     "Düşük — EV+ karşı.",
    },
    "Rock": {
        "thinking":   "Kayıp yoksa kazanç var. Extreme risk aversion.",
        "tendencies": "12% VPIP or less. Never bluffs. Only plays nuts.",
        "exploit":    "Steal every single pot. Fold to any aggression unless nuts.",
        "tells":      "Bet/raise = absolute nuts. 100% of the time.",
        "danger":     "Sıfır — sadece bet kazan.",
    },
    "GTO Expert": {
        "thinking":   "Solver balanced. Mixed frequencies. Rarely exploitable.",
        "tendencies": "Mixes value and bluffs at correct ratios. Polarized rivers.",
        "exploit":    "Zor — sadece timing tells. Minimal exploitation possible.",
        "tells":      "Consistent timing and sizing — az bilgi.",
        "danger":     "Çok yüksek — masa değiştir.",
    },
    "Aggro Fish": {
        "thinking":   "Aggression = good. No logic behind sizing. High variance.",
        "tendencies": "Fires frequently without equity. Big sizings randomly.",
        "exploit":    "Call down lighter. Trap check-raise. Don't bluff.",
        "tells":      "Random sizings. Check = rare (keeps betting). Fold to massive raise.",
        "danger":     "Varyans yüksek — call down correctly = profit.",
    },
    "Tight Passive": {
        "thinking":   "Risk yok. Limp-call. Showdown odaklı.",
        "tendencies": "Checks and calls. Rarely bets without strong hand.",
        "exploit":    "Take every free card. Bet for value. Pressure them to fold marginal.",
        "tells":      "Bet = strong. Check = weak, bet them off.",
        "danger":     "Düşük — never attacks.",
    },
    "Bubble Nit": {
        "thinking":   "ICM pressure max. Sadece nut hands play.",
        "tendencies": "Over-folds on bubble. Only commits with top 3%.",
        "exploit":    "Shove any 2 into bubble nit. Steal constantly.",
        "tells":      "Any hesitation = fold coming. Instant raise = nuts.",
        "danger":     "Sadece tuzak kur karşılaşırsan.",
    },
}


def _stat_bar(label: str, value: float, max_val: float, color: str) -> QFrame:
    """Mini istatistik çubuğu."""
    f = QFrame()
    f.setStyleSheet(f"background:#0a0c0a; border:none;")
    h = QHBoxLayout(f)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(6)
    lbl = QLabel(label)
    lbl.setFixedWidth(80)
    lbl.setStyleSheet(f"font-family:'JetBrains Mono',monospace; font-size:9px; color:{_MUTED};")
    val_lbl = QLabel(f"{value:.0f}%")
    val_lbl.setFixedWidth(38)
    val_lbl.setStyleSheet(f"font-family:'JetBrains Mono',monospace; font-size:10px; font-weight:700; color:{color};")
    # Bar arka plan
    bar_bg = QFrame()
    bar_bg.setFixedHeight(6)
    bar_bg.setStyleSheet(f"background:#1a1e18; border:none;")
    bar_inner = QFrame(bar_bg)
    bar_inner.setFixedHeight(6)
    bar_w = max(4, int(120 * min(value / max_val, 1.0)))
    bar_inner.setFixedWidth(bar_w)
    bar_inner.setStyleSheet(f"background:{color}; border:none;")
    h.addWidget(lbl)
    h.addWidget(val_lbl)
    h.addWidget(bar_bg, 1)
    return f


def _build_profile_card(name: str, prof) -> QFrame:
    color, tag = _PROFILE_COLORS.get(name, (_MUTED, "Unknown"))
    details = _PROFILE_DETAILS.get(name, {})

    card = QFrame()
    card.setObjectName("GTOCard")
    card.setStyleSheet(
        f"QFrame#GTOCard {{ background:{_BG2}; border:1px solid {_LINE2}; "
        f"border-left:3px solid {color}; }}"
    )
    v = QVBoxLayout(card)
    v.setContentsMargins(16, 14, 16, 14)
    v.setSpacing(10)

    # Başlık satırı
    h_row = QHBoxLayout()
    name_lbl = QLabel(name)
    name_lbl.setStyleSheet(
        f"font-family:'JetBrains Mono',monospace; font-size:15px; "
        f"font-weight:700; color:{color};"
    )
    tag_lbl = QLabel(tag)
    tag_lbl.setStyleSheet(
        f"font-family:'JetBrains Mono',monospace; font-size:9px; "
        f"font-weight:700; letter-spacing:1.5px; color:{_BG2}; "
        f"background:{color}; padding:2px 7px;"
    )
    notes_lbl = QLabel(getattr(prof, "notes", ""))
    notes_lbl.setStyleSheet(
        f"font-family:'JetBrains Mono',monospace; font-size:10px; "
        f"color:{_MUTED}; font-style:italic;"
    )
    h_row.addWidget(name_lbl)
    h_row.addWidget(tag_lbl)
    h_row.addStretch(1)
    v.addLayout(h_row)
    v.addWidget(notes_lbl)

    # İstatistik çubukları
    stats_grid = QHBoxLayout()
    stats_grid.setSpacing(16)
    left_stats = QVBoxLayout()
    left_stats.setSpacing(3)
    right_stats = QVBoxLayout()
    right_stats.setSpacing(3)

    vpip = getattr(prof, "vpip", 0)
    pfr  = getattr(prof, "pfr", 0)
    three_bet = getattr(prof, "three_bet", 0)
    fold_cbet = getattr(prof, "fold_to_cbet", 0)
    aggr = getattr(prof, "aggression", 0) * 20   # 0-5 → 0-100%
    river_bluff = getattr(prof, "river_bluff", 0) * 100
    call_down   = getattr(prof, "call_down", 0) * 100

    left_stats.addWidget(_stat_bar("VPIP",       vpip,       60,  color))
    left_stats.addWidget(_stat_bar("PFR",        pfr,        60,  _INFO))
    left_stats.addWidget(_stat_bar("3-BET",      three_bet,  20,  _WARN))
    right_stats.addWidget(_stat_bar("F-CBET",    fold_cbet,  90,  _MUTED))
    right_stats.addWidget(_stat_bar("AGGRESSION",aggr,       100, color))
    right_stats.addWidget(_stat_bar("RV BLUFF",  river_bluff,60,  _DANGER))

    stats_grid.addLayout(left_stats, 1)
    stats_grid.addLayout(right_stats, 1)
    v.addLayout(stats_grid)

    # Davranış detayları
    if details:
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{_LINE2}; border:none;")
        v.addWidget(sep)

        det_grid = QHBoxLayout()
        det_grid.setSpacing(16)

        for col_items in [
            [("🧠 Düşünce", details.get("thinking", "")),
             ("📊 Eğilimler", details.get("tendencies", ""))],
            [("⚔ Exploit Et", details.get("exploit", "")),
             ("⚠ Tehlike", details.get("danger", ""))],
        ]:
            col = QVBoxLayout()
            col.setSpacing(6)
            for icon_label, text in col_items:
                if not text:
                    continue
                ll = QLabel(icon_label)
                ll.setStyleSheet(
                    f"font-family:'JetBrains Mono',monospace; font-size:9px; "
                    f"letter-spacing:1.5px; color:{_INFO}; font-weight:700;"
                )
                tl = QLabel(text)
                tl.setStyleSheet(
                    f"font-family:'JetBrains Mono',monospace; font-size:10px; "
                    f"color:{_INK2};"
                )
                tl.setWordWrap(True)
                col.addWidget(ll)
                col.addWidget(tl)
            det_grid.addLayout(col, 1)

        v.addLayout(det_grid)

    return card


class KnowledgeBaseScreen(QWidget):
    def __init__(self, state: AppState):
        super().__init__()
        self.state = state

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Başlık
        header = QFrame()
        header.setStyleSheet("background:#131613; border-bottom:1px solid #23271f;")
        h_l = QHBoxLayout(header)
        h_l.setContentsMargins(22, 14, 22, 14)
        t = QLabel("KNOWLEDGE BASE")
        t.setObjectName("SectionTitle")
        h_l.addWidget(t)
        root.addWidget(header)

        # Sekmeler
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane { border:none; background:#0a0c0a; }
            QTabBar::tab { background:#131613; color:#898d80;
                           font-family:'JetBrains Mono',monospace; font-size:11px;
                           letter-spacing:1.5px; padding:10px 20px;
                           border:1px solid #23271f; border-bottom:none; }
            QTabBar::tab:selected { color:#5ad17a; border-bottom:2px solid #5ad17a;
                                    background:#0a0c0a; }
        """)

        # ── Sekme 1: GTO Kavramlar ────────────────────────────────
        concepts_tab = QWidget()
        c_l = QVBoxLayout(concepts_tab)
        c_l.setContentsMargins(18, 14, 18, 14)
        c_l.setSpacing(10)
        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Kavram ara: MDF, ICM, blockers, cbet...")
        self.search.setMinimumHeight(36)
        btn = QPushButton("Ara")
        btn.setObjectName("PrimaryButton")
        btn.setMinimumHeight(36)
        btn.clicked.connect(self._render_concepts)
        self.search.returnPressed.connect(self._render_concepts)
        search_row.addWidget(self.search, 1)
        search_row.addWidget(btn)
        c_l.addLayout(search_row)
        self.cards_layout = QVBoxLayout()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        body.setLayout(self.cards_layout)
        scroll.setWidget(body)
        c_l.addWidget(scroll, 1)
        tabs.addTab(concepts_tab, "GTO KAVRAMLAR")

        # ── Sekme 2: Oyuncu Profil Kütüphanesi ───────────────────
        profiles_tab = QWidget()
        p_l = QVBoxLayout(profiles_tab)
        p_l.setContentsMargins(0, 0, 0, 0)
        p_scroll = QScrollArea()
        p_scroll.setWidgetResizable(True)
        p_scroll.setFrameShape(QFrame.NoFrame)
        p_body = QWidget()
        p_body.setStyleSheet("background:#0a0c0a;")
        pb_l = QVBoxLayout(p_body)
        pb_l.setContentsMargins(18, 16, 18, 20)
        pb_l.setSpacing(14)

        intro = QLabel(
            "Tüm rakip profilleri — istatistikler, düşünce yapısı, exploit stratejisi ve tehlike seviyesi."
        )
        intro.setStyleSheet(
            f"font-family:'JetBrains Mono',monospace; font-size:11px; "
            f"color:{_MUTED}; padding-bottom:6px;"
        )
        intro.setWordWrap(True)
        pb_l.addWidget(intro)

        # Profilleri önceliğe göre sırala
        order = [
            "GTO Expert", "Shark", "TAG", "Balanced Reg", "Reg", "Solver Bot",
            "LAG", "Aggro Fish", "Maniac", "Karma (Mixed)",
            "Fish", "Calling Station", "Tight Passive", "Nit", "Rock", "Bubble Nit",
        ]
        for name in order:
            prof = BOT_ARCHETYPES.get(name)
            if prof:
                pb_l.addWidget(_build_profile_card(name, prof))

        pb_l.addStretch(1)
        p_scroll.setWidget(p_body)
        p_l.addWidget(p_scroll)
        tabs.addTab(profiles_tab, "RAKİP PROFİLLERİ")

        root.addWidget(tabs, 1)
        self._render_concepts()

    def _render_concepts(self) -> None:
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for card in search_concepts(self.search.text() or "poker"):
            label = QLabel(
                f"<b>{card['concept']}</b> · {card['source']}<br>"
                f"{card['summary']}<br>"
                f"<span style='color:#898d80'>Uygulama: {card['application']}</span>"
            )
            label.setTextFormat(Qt.RichText)
            label.setWordWrap(True)
            label.setObjectName("Card")
            label.setStyleSheet(
                "padding:14px; font-family:'JetBrains Mono',monospace; font-size:11px;"
            )
            self.cards_layout.addWidget(label)
        self.cards_layout.addStretch(1)
