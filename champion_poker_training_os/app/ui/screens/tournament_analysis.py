"""Tournament Analysis Screen.

Left panel  — scrollable history list + "Genel Analiz" button.
Right panel — selected tournament: hero card, KPIs, AI coach analysis.

AI analysis is triggered on demand (never automatic):
  - Per-tournament: Gemini gets full stats + position breakdown hint.
  - Genel: Gemini gets aggregated stats over ALL past tournaments.
"""
from __future__ import annotations

import math
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSizePolicy, QTextEdit, QVBoxLayout, QWidget,
)

from app.core.app_state import AppState
from app.db.repository import get_tournament_history


# ── helpers ──────────────────────────────────────────────────────────

def _mono(text: str, color: str = "#d6d8cf", size: int = 11) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"font-family:'JetBrains Mono',Menlo,monospace; font-size:{size}px; color:{color};"
    )
    return lbl


def _head(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("TLabel")
    return lbl


def _sep() -> QFrame:
    f = QFrame(); f.setFrameShape(QFrame.HLine)
    f.setStyleSheet("background:#23271f; border:none; max-height:1px;")
    return f


def _grade(finish: int, field: int) -> tuple[str, str]:
    pct = (1 - finish / max(field, 1)) * 100
    if finish == 1: return "S",  "#5ad17a"
    if pct >= 85:   return "A+", "#5ad17a"
    if pct >= 70:   return "A",  "#5ad17a"
    if pct >= 55:   return "B+", "#a8d17a"
    if pct >= 40:   return "B",  "#d6c668"
    if pct >= 20:   return "C",  "#d6a668"
    return "D", "#e87474"


def _roi_color(roi: float) -> str:
    return "#5ad17a" if roi >= 0 else "#e87474"


# ── small card widget ─────────────────────────────────────────────────

class _TournCard(QFrame):
    clicked = Signal(dict)

    def __init__(self, record: dict, is_selected: bool = False):
        super().__init__()
        self._record = record
        self._itm = (record.get("prize_won", 0.0) > 0)
        self._build()                 # layout + widget'lar BİR KEZ kurulur
        self._refresh(is_selected)    # yalnızca seçim kenarlığını günceller

    def _refresh(self, selected: bool) -> None:
        """Seçim durumunu günceller — SADECE kenarlık/arka plan. Layout'u
        yeniden KURMAZ (eskiden her seçimde ikinci QVBoxLayout ekliyordu →
        'already has a layout' uyarısı)."""
        border = "#5ad1ce" if selected else ("#2a2e26" if not self._itm else "#2a4a30")
        self.setStyleSheet(
            f"QFrame {{ background: {'#0d1a0f' if self._itm else '#131613'}; "
            f"border: 1px solid {border}; }} "
            f"QFrame:hover {{ border-color: #5a5e54; }}"
        )
        self.setCursor(Qt.PointingHandCursor)

    def _build(self) -> None:
        record  = self._record
        finish  = record.get("finish_position") or record.get("field_size", 0)
        field   = record.get("field_size", 0)
        buyin   = record.get("buyin", 0.0)
        prize   = record.get("prize_won", 0.0)
        profit  = record.get("profit", prize - buyin)
        roi     = (profit / buyin * 100) if buyin > 0 else 0.0
        name    = (record.get("name") or "—")[:24]
        grade, gc = _grade(finish, field)

        v = QVBoxLayout(self)
        v.setContentsMargins(12, 9, 12, 9)
        v.setSpacing(3)

        top = QHBoxLayout()
        g_lbl = QLabel(grade)
        g_lbl.setFixedSize(26, 26)
        g_lbl.setAlignment(Qt.AlignCenter)
        g_lbl.setStyleSheet(
            f"font-family:'Space Grotesk',Inter,sans-serif; font-size:13px; "
            f"font-weight:900; color:{gc}; border:1px solid {gc};"
        )
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet("font-size:12px; font-weight:700; color:#f4f5ee;")
        roi_lbl = QLabel(f"{roi:+.0f}%")
        roi_lbl.setStyleSheet(
            f"font-family:'JetBrains Mono',Menlo,monospace; font-size:11px; "
            f"font-weight:700; color:{_roi_color(roi)};"
        )
        top.addWidget(g_lbl)
        top.addWidget(name_lbl, 1)
        top.addWidget(roi_lbl)
        v.addLayout(top)

        ordinals = {1: "1st", 2: "2nd", 3: "3rd"}
        fin_str = ordinals.get(finish, f"{finish}th")
        sub = _mono(
            f"{fin_str}/{field}  ·  ${prize:,.0f}  ·  {record.get('hands_played',0)} el",
            color="#898d80", size=10,
        )
        v.addWidget(sub)

    def mousePressEvent(self, _):
        self.clicked.emit(self._record)


# ── main screen ───────────────────────────────────────────────────────

class TournamentAnalysisScreen(QWidget):
    coach_message    = Signal(str)
    analysis_requested = Signal(str)   # prompt → main.py → Gemini

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self._selected: Optional[dict] = None
        self._cards: list[_TournCard] = []

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── LEFT PANEL ────────────────────────────────────────────────
        left = QFrame()
        left.setFixedWidth(300)
        left.setStyleSheet("background:#0c0f0b; border-right:1px solid #1e221d;")
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(0)

        # header
        lh = QFrame()
        lh.setStyleSheet("background:#0c0f0b; border-bottom:1px solid #1e221d;")
        lhv = QVBoxLayout(lh)
        lhv.setContentsMargins(16, 14, 16, 14)
        lhv.setSpacing(6)
        title = QLabel("TURNUVA ANALİZLERİ")
        title.setObjectName("TLabel")
        title.setStyleSheet("font-size:13px; letter-spacing:1.5px;")
        lhv.addWidget(title)

        gen_btn = QPushButton("⊞  GENEL ANALİZ AL")
        gen_btn.setObjectName("PrimaryButton")
        gen_btn.setMinimumHeight(34)
        gen_btn.setStyleSheet(
            "QPushButton { padding: 6px 14px; font-size: 11px; letter-spacing: 1.2px; }"
        )
        gen_btn.clicked.connect(self._request_general_analysis)
        lhv.addWidget(gen_btn)
        lv.addWidget(lh)

        # scrollable list
        self._list_scroll = QScrollArea()
        self._list_scroll.setWidgetResizable(True)
        self._list_scroll.setFrameShape(QFrame.NoFrame)
        self._list_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._list_body = QWidget()
        self._list_layout = QVBoxLayout(self._list_body)
        self._list_layout.setContentsMargins(10, 10, 10, 10)
        self._list_layout.setSpacing(6)
        self._list_layout.addStretch(1)
        self._list_scroll.setWidget(self._list_body)
        lv.addWidget(self._list_scroll, 1)

        root.addWidget(left)

        # ── RIGHT PANEL ───────────────────────────────────────────────
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.NoFrame)
        self._right_body = QWidget()
        self._right_layout = QVBoxLayout(self._right_body)
        self._right_layout.setContentsMargins(28, 24, 28, 40)
        self._right_layout.setSpacing(16)
        right_scroll.setWidget(self._right_body)
        root.addWidget(right_scroll, 1)

        self._show_empty_state()
        self._load_history()

    # ── history list ──────────────────────────────────────────────────

    def _load_history(self) -> None:
        """(Re)load tournament history from DB and rebuild left panel list."""
        # Clear existing cards
        for c in self._cards:
            c.setParent(None)
        self._cards.clear()
        # Remove all items except stretch
        while self._list_layout.count() > 1:
            it = self._list_layout.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

        history = get_tournament_history(limit=50)
        if not history:
            no_data = _mono("Henüz turnuva yok.\nTournament Simulator'da oyna!", "#5a5e54", 11)
            no_data.setWordWrap(True)
            no_data.setAlignment(Qt.AlignCenter)
            self._list_layout.insertWidget(0, no_data)
            return

        for rec in history:
            card = _TournCard(rec, is_selected=False)
            card.clicked.connect(self._on_card_clicked)
            self._list_layout.insertWidget(self._list_layout.count() - 1, card)
            self._cards.append(card)

        # Auto-select newest
        if self._cards:
            self._on_card_clicked(history[0])

    def refresh(self) -> None:
        """Call when returning to this screen so new results appear."""
        self._load_history()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._load_history()

    # ── selection ─────────────────────────────────────────────────────

    def _on_card_clicked(self, record: dict) -> None:
        self._selected = record
        # Update card borders
        for card in self._cards:
            is_sel = card._record.get("id") == record.get("id")
            card._refresh(is_sel)
        self._show_tournament_detail(record)

    # ── RIGHT PANEL: empty state ──────────────────────────────────────

    def _show_empty_state(self) -> None:
        self._clear_right()
        lbl = _mono(
            "← Soldan bir turnuva seç\nveya GENEL ANALİZ al.",
            color="#5a5e54", size=13,
        )
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setWordWrap(True)
        self._right_layout.addStretch(1)
        self._right_layout.addWidget(lbl)
        self._right_layout.addStretch(1)

    def _clear_right(self) -> None:
        while self._right_layout.count():
            it = self._right_layout.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

    # ── RIGHT PANEL: tournament detail ────────────────────────────────

    def _show_tournament_detail(self, rec: dict) -> None:
        self._clear_right()
        l = self._right_layout

        finish  = rec.get("finish_position") or rec.get("field_size", 0)
        field   = rec.get("field_size", 0)
        buyin   = rec.get("buyin", 0.0)
        prize   = rec.get("prize_won", 0.0)
        profit  = rec.get("profit", prize - buyin)
        roi     = (profit / buyin * 100) if buyin > 0 else 0.0
        vpip    = rec.get("vpip", 0.0)
        pfr     = rec.get("pfr", 0.0)
        bb100   = rec.get("bb_per_100", 0.0)
        hands   = rec.get("hands_played", 0)
        name    = rec.get("name", "—")
        struct  = rec.get("structure", "regular").upper()
        itm     = prize > 0
        won     = finish == 1
        grade, gc = _grade(finish, field)
        ordinals = {1: "1st", 2: "2nd", 3: "3rd"}
        fin_str = ordinals.get(finish, f"{finish}th")
        pct_rank = (1 - finish / max(field, 1)) * 100

        # Page num
        page_lbl = _mono(f"TURNUVA  ·  {rec.get('played_at','')[:16]}", "#5a5e54", 10)
        l.addWidget(page_lbl)

        # ── Hero card ────────────────────────────────────────────────
        hero_card = QFrame()
        border_c = "#5ad17a" if won else ("#5ad1ce" if itm else "#2a2e26")
        bg_c     = "#0d2b14" if won else ("#0d1a26" if itm else "#131613")
        hero_card.setStyleSheet(
            f"background:{bg_c}; border:2px solid {border_c};"
        )
        hc_h = QHBoxLayout(hero_card)
        hc_h.setContentsMargins(22, 18, 22, 18)
        hc_h.setSpacing(24)

        # Finish block
        fb = QVBoxLayout(); fb.setSpacing(3)
        fl = _mono("FİNİŞ", "#5a5e54", 9); fl.setObjectName("TLabel")
        fv = QLabel(f"{fin_str} / {field:,}")
        fv.setStyleSheet(
            f"font-family:'Space Grotesk',Inter,sans-serif; font-size:36px; "
            f"font-weight:800; color:{gc};"
        )
        fr = _mono(
            f"{'🏆 ŞAMPİYON' if won else ('✓ ITM' if itm else f'top {100 - pct_rank:.0f}%')}",
            color=gc, size=11,
        )
        fb.addWidget(fl); fb.addWidget(fv); fb.addWidget(fr)
        hc_h.addLayout(fb, 2)

        dv = QFrame(); dv.setFrameShape(QFrame.VLine)
        dv.setStyleSheet("color:#2a2e26; background:#2a2e26; max-width:1px;")
        hc_h.addWidget(dv)

        # Prize block
        pb = QVBoxLayout(); pb.setSpacing(3)
        pl = _mono("ÖDÜL", "#5a5e54", 9); pl.setObjectName("TLabel")
        pv = QLabel(f"${prize:,.2f}")
        pv.setStyleSheet(
            f"font-family:'Space Grotesk',Inter,sans-serif; font-size:32px; "
            f"font-weight:800; color:{'#5ad17a' if prize>0 else '#f4f5ee'};"
        )
        pr = _mono(
            f"ROI {roi:+.1f}%  ·  net {profit:+.2f}$",
            color=_roi_color(roi), size=11,
        )
        pb.addWidget(pl); pb.addWidget(pv); pb.addWidget(pr)
        hc_h.addLayout(pb, 2)

        dv2 = QFrame(); dv2.setFrameShape(QFrame.VLine)
        dv2.setStyleSheet("color:#2a2e26; background:#2a2e26; max-width:1px;")
        hc_h.addWidget(dv2)

        # Grade block
        gb = QVBoxLayout(); gb.setSpacing(6)
        g_box = QLabel(grade)
        g_box.setFixedSize(56, 56)
        g_box.setAlignment(Qt.AlignCenter)
        g_box.setStyleSheet(
            f"font-family:'Space Grotesk',Inter,sans-serif; font-size:28px; "
            f"font-weight:900; color:{gc}; border:2px solid {gc};"
        )
        g_meta = _mono(
            f"{name}\n{struct}  ·  ${buyin:.0f} buy-in\n{hands} el",
            "#898d80", 10,
        )
        g_meta.setWordWrap(True)
        gb.addWidget(g_box); gb.addWidget(g_meta)
        hc_h.addLayout(gb, 2)

        l.addWidget(hero_card)

        # ── KPI strip ────────────────────────────────────────────────
        kpi_row = QHBoxLayout(); kpi_row.setSpacing(8)
        kpis = [
            ("VPIP",   f"{vpip:.1f}%",  20 <= vpip <= 30),
            ("PFR",    f"{pfr:.1f}%",   pfr >= 15),
            ("BB/100", f"{bb100:+.1f}", bb100 > 0),
            ("ELLER",  str(hands),      True),
        ]
        for lbl_t, val_t, good in kpis:
            kf = QFrame(); kf.setObjectName("Card")
            kv = QVBoxLayout(kf)
            kv.setContentsMargins(14, 10, 14, 10); kv.setSpacing(2)
            kl = _mono(lbl_t, "#5a5e54", 9); kl.setObjectName("TLabel")
            vl = QLabel(val_t)
            c = "#5ad17a" if good else "#e87474"
            vl.setStyleSheet(
                f"font-family:'Space Grotesk',Inter,sans-serif; font-size:20px; "
                f"font-weight:700; color:{c};"
            )
            kv.addWidget(kl); kv.addWidget(vl)
            kpi_row.addWidget(kf, 1)
        l.addLayout(kpi_row)

        # ── Quick eval bullets ────────────────────────────────────────
        eval_card = QFrame(); eval_card.setObjectName("Card")
        ev_l = QVBoxLayout(eval_card)
        ev_l.setContentsMargins(18, 14, 18, 14); ev_l.setSpacing(5)
        ev_l.addWidget(_head("HIZLI DEĞERLENDİRME"))

        bullets = self._make_bullets(finish, field, vpip, pfr, bb100, prize, buyin)
        for icon, color, text in bullets:
            row = QHBoxLayout(); row.setSpacing(8)
            il = _mono(icon, color, 11); il.setFixedWidth(14)
            tl = _mono(text, "#d6d8cf", 12); tl.setWordWrap(True)
            row.addWidget(il); row.addWidget(tl, 1)
            ev_l.addLayout(row)
        l.addWidget(eval_card)

        # ── AI Coach analysis panel ───────────────────────────────────
        ai_card = QFrame(); ai_card.setObjectName("Card")
        ai_l = QVBoxLayout(ai_card)
        ai_l.setContentsMargins(18, 14, 18, 14); ai_l.setSpacing(10)

        ai_header = QHBoxLayout()
        ai_header.addWidget(_head("AI COACH  ·  KAPSAMLI ANALİZ"))
        ai_header.addStretch(1)
        analyse_btn = QPushButton("⊞  ANALİZ AL")
        analyse_btn.setObjectName("PrimaryButton")
        analyse_btn.setMinimumHeight(30)
        analyse_btn.setStyleSheet("padding:5px 16px; font-size:11px; letter-spacing:1.2px;")
        analyse_btn.clicked.connect(lambda: self._request_tournament_analysis(rec))
        ai_header.addWidget(analyse_btn)
        ai_l.addLayout(ai_header)

        hint = _mono(
            "↑  Butona bas → AI coach bu turnuvayı kapsamlı analiz eder:\n"
            "preflop/postflop kararlar, stack basıncı, leak pattern, sonraki adımlar.",
            "#5a5e54", 10,
        )
        hint.setWordWrap(True)
        ai_l.addWidget(hint)

        self._analysis_box = QTextEdit()
        self._analysis_box.setReadOnly(True)
        self._analysis_box.setPlaceholderText("Analiz bekleniyor…")
        self._analysis_box.setMinimumHeight(180)
        self._analysis_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._analysis_box.setStyleSheet(
            "QTextEdit { background:#090e08; color:#d6d8cf; "
            "font-family:'JetBrains Mono',Menlo,monospace; font-size:12px; "
            "border:1px solid #1e221d; padding:10px; }"
        )
        ai_l.addWidget(self._analysis_box)
        l.addWidget(ai_card)
        l.addStretch(1)

    # ── RIGHT PANEL: genel analiz view ───────────────────────────────

    def _show_general_view(self) -> None:
        self._clear_right()
        l = self._right_layout
        history = get_tournament_history(limit=50)

        if not history:
            l.addWidget(_mono("Henüz turnuva yok.", "#5a5e54", 13))
            l.addStretch(1)
            return

        n      = len(history)
        itm_n  = sum(1 for h in history if h.get("prize_won", 0) > 0)
        wins_n = sum(1 for h in history if h.get("finish_position") == 1)
        t_profit = sum(h.get("profit", 0) for h in history)
        t_invest = sum(h.get("buyin", 0) for h in history)
        g_roi    = (t_profit / t_invest * 100) if t_invest > 0 else 0.0
        avg_vpip = sum(h.get("vpip", 0) for h in history) / n
        avg_pfr  = sum(h.get("pfr", 0) for h in history) / n
        avg_bb   = sum(h.get("bb_per_100", 0) for h in history) / n
        avg_fin  = sum((h.get("finish_position") or h.get("field_size", 1)) / max(h.get("field_size", 1), 1) for h in history) / n

        page_lbl = _mono(f"GENEL ANALİZ  ·  {n} turnuva", "#5a5e54", 10)
        l.addWidget(page_lbl)

        # Summary card
        sc = QFrame(); sc.setObjectName("Card")
        sv = QVBoxLayout(sc); sv.setContentsMargins(20, 16, 20, 16); sv.setSpacing(8)
        sv.addWidget(_head("ÖZET PERFORMANS"))

        summary_items = [
            ("Toplam Turnuva",   str(n),              True),
            ("ITM",              f"{itm_n} ({100*itm_n/n:.0f}%)", itm_n/n >= 0.15),
            ("Galibiyet",        str(wins_n),          wins_n > 0),
            ("Net P&L",          f"{t_profit:+.2f}$",  t_profit >= 0),
            ("Genel ROI",        f"{g_roi:+.1f}%",     g_roi >= 0),
            ("Ort. VPIP",        f"{avg_vpip:.1f}%",   20 <= avg_vpip <= 30),
            ("Ort. PFR",         f"{avg_pfr:.1f}%",    avg_pfr >= 15),
            ("Ort. BB/100",      f"{avg_bb:+.1f}",     avg_bb >= 0),
            ("Ort. Finish %ile", f"top {100-avg_fin*100:.0f}%", avg_fin <= 0.5),
        ]
        grid_rows = [summary_items[i:i+3] for i in range(0, len(summary_items), 3)]
        from PySide6.QtWidgets import QGridLayout
        grid = QGridLayout(); grid.setSpacing(8)
        for r, row_items in enumerate(grid_rows):
            for c, (lbl_t, val_t, good) in enumerate(row_items):
                kf = QFrame(); kf.setObjectName("Card")
                kv = QVBoxLayout(kf); kv.setContentsMargins(12, 8, 12, 8); kv.setSpacing(2)
                kl = _mono(lbl_t, "#5a5e54", 9); kl.setObjectName("TLabel")
                vc = "#5ad17a" if good else "#e87474"
                vl = QLabel(val_t)
                vl.setStyleSheet(
                    f"font-family:'Space Grotesk',Inter,sans-serif; "
                    f"font-size:17px; font-weight:700; color:{vc};"
                )
                kv.addWidget(kl); kv.addWidget(vl)
                grid.addWidget(kf, r, c)
        sv.addLayout(grid)
        l.addWidget(sc)

        # Trend card (last 5 vs earlier)
        if n >= 6:
            recent = history[:5]
            older  = history[5:]
            r_roi  = (sum(h.get("profit",0) for h in recent) /
                      max(sum(h.get("buyin",0) for h in recent), 1)) * 100
            o_roi  = (sum(h.get("profit",0) for h in older) /
                      max(sum(h.get("buyin",0) for h in older), 1)) * 100
            trend  = r_roi - o_roi
            tc = QFrame(); tc.setObjectName("Card")
            tv = QVBoxLayout(tc); tv.setContentsMargins(18, 14, 18, 14); tv.setSpacing(6)
            tv.addWidget(_head("TREND  ·  son 5 vs önceki"))
            tc_lbl = _mono(
                f"Son 5 turnuva ROI: {r_roi:+.1f}%   "
                f"Önceki {len(older)} turnuva ROI: {o_roi:+.1f}%   "
                f"Trend: {'+' if trend >= 0 else ''}{trend:.1f}%",
                color="#5ad17a" if trend >= 0 else "#e87474", size=12,
            )
            tc_lbl.setWordWrap(True)
            tv.addWidget(tc_lbl)
            l.addWidget(tc)

        # AI analysis panel
        ai_card = QFrame(); ai_card.setObjectName("Card")
        ai_l = QVBoxLayout(ai_card)
        ai_l.setContentsMargins(18, 14, 18, 14); ai_l.setSpacing(10)

        ai_hdr = QHBoxLayout()
        ai_hdr.addWidget(_head("AI COACH  ·  TÜM TURNUVA GEÇMİŞİ ANALİZİ"))
        ai_hdr.addStretch(1)
        gen_btn2 = QPushButton("⊞  KAPSAMLI ANALİZ AL")
        gen_btn2.setObjectName("PrimaryButton")
        gen_btn2.setMinimumHeight(30)
        gen_btn2.setStyleSheet("padding:5px 16px; font-size:11px; letter-spacing:1.2px;")
        gen_btn2.clicked.connect(self._request_general_analysis)
        ai_hdr.addWidget(gen_btn2)
        ai_l.addLayout(ai_hdr)

        hint2 = _mono(
            "Tüm turnuvalarının istatistikleri Gemini'ye gönderilir.\n"
            "Oynadıkça analiz derinleşir ve pattern tespiti gelişir.",
            "#5a5e54", 10,
        )
        hint2.setWordWrap(True)
        ai_l.addWidget(hint2)

        self._analysis_box = QTextEdit()
        self._analysis_box.setReadOnly(True)
        self._analysis_box.setPlaceholderText("Analiz bekleniyor…")
        self._analysis_box.setMinimumHeight(200)
        self._analysis_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._analysis_box.setStyleSheet(
            "QTextEdit { background:#090e08; color:#d6d8cf; "
            "font-family:'JetBrains Mono',Menlo,monospace; font-size:12px; "
            "border:1px solid #1e221d; padding:10px; }"
        )
        ai_l.addWidget(self._analysis_box)
        l.addWidget(ai_card)
        l.addStretch(1)

    # ── bullet helper ─────────────────────────────────────────────────

    def _make_bullets(self, finish, field, vpip, pfr, bb100, prize, buyin):
        bullets = []
        itm = prize > 0
        ordinals = {1:"1st",2:"2nd",3:"3rd"}
        fin_str = ordinals.get(finish, f"{finish}th")
        paid_approx = max(1, round(field * 0.15))
        if finish == 1:
            bullets.append(("✓", "#5ad17a", "Turnuva galibiyeti — olağanüstü sonuç."))
        elif itm:
            bullets.append(("✓", "#5ad17a", f"{fin_str} — para ödülüne girdi, pozitif sonuç."))
        else:
            bullets.append(("✗", "#e87474",
                f"{fin_str} — ödülün {finish - paid_approx} yer uzağında elendi."))
        if 20 <= vpip <= 30:
            bullets.append(("✓", "#5ad17a", f"VPIP {vpip:.1f}% — sağlıklı aralıkta."))
        elif vpip > 30:
            bullets.append(("⚠", "#d6c668", f"VPIP {vpip:.1f}% — geniş, early pozisyonları sık."))
        else:
            bullets.append(("⚠", "#d6c668", f"VPIP {vpip:.1f}% — dar, steal/defend spotlar kaçıyor."))
        if pfr > 0:
            gap = vpip - pfr
            if gap <= 8:
                bullets.append(("✓", "#5ad17a", f"PFR {pfr:.1f}% — agresif ve sağlıklı (gap {gap:.1f}%)."))
            else:
                bullets.append(("✗", "#e87474", f"PFR {pfr:.1f}% — pasif (gap {gap:.1f}%). Limp azalt."))
        if bb100 > 5:
            bullets.append(("✓", "#5ad17a", f"Chip EV {bb100:+.1f} bb/100 — kazançlı ritim."))
        elif bb100 > -10:
            bullets.append(("→", "#898d80", f"Chip EV {bb100:+.1f} bb/100 — breakeven yakını."))
        else:
            bullets.append(("✗", "#e87474", f"Chip EV {bb100:+.1f} bb/100 — ciddi chip kayıpları."))
        return bullets

    # ── AI coach prompts ──────────────────────────────────────────────

    def _request_tournament_analysis(self, rec: dict) -> None:
        finish  = rec.get("finish_position") or rec.get("field_size", 0)
        field   = rec.get("field_size", 0)
        buyin   = rec.get("buyin", 0.0)
        prize   = rec.get("prize_won", 0.0)
        profit  = rec.get("profit", prize - buyin)
        roi     = (profit / buyin * 100) if buyin > 0 else 0.0
        vpip    = rec.get("vpip", 0.0)
        pfr     = rec.get("pfr", 0.0)
        bb100   = rec.get("bb_per_100", 0.0)
        hands   = rec.get("hands_played", 0)
        name    = rec.get("name", "—")
        struct  = rec.get("structure", "regular")
        ordinals = {1:"1st",2:"2nd",3:"3rd"}
        fin_str = ordinals.get(finish, f"{finish}th")
        pct_rank = (1 - finish / max(field, 1)) * 100
        gap = vpip - pfr

        prompt = (
            f"TURNUVA KOÇLUK ANALİZİ — kapsamlı, el-bazlı perspektif:\n\n"
            f"Event: {name}\n"
            f"Field: {field:,} oyuncu  ·  ${buyin:.0f} buy-in  ·  {struct.upper()}\n"
            f"Sonuç: {fin_str} / {field:,}  (top {pct_rank:.0f}% finish)\n"
            f"Ödül: ${prize:.2f}  ·  ROI: {roi:+.1f}%  ·  Net: {profit:+.2f}$\n"
            f"Oynanan el: {hands}\n\n"
            f"İstatistikler:\n"
            f"  VPIP:    {vpip:.1f}%  (hedef 20-28%)\n"
            f"  PFR:     {pfr:.1f}%  (VPIP-PFR gap: {gap:.1f}%)\n"
            f"  BB/100:  {bb100:+.1f}bb\n\n"
            "Bu turnuvayı sanki her eli izlemişsin gibi KAPSAMLI analiz et:\n\n"
            "1. FİNİŞ ANALİZİ: Bu field boyutu + yapısında bu finish ne anlama gelir? "
            "   Variance mi, skill mi?\n"
            "2. PREFLOP: VPIP/PFR/gap istatistiklerine göre preflop profil ne gösteriyor? "
            "   Hangi pozisyonlarda ne tür hatalar muhtemel?\n"
            "3. POSTFLOP: BB/100 sonucuna göre postflop sıkıntılar nerede? "
            "   Stack basıncı, cbet disiplini, değer elde etme.\n"
            "4. MTT SPESIFIK: Bu field boyutunda bubble, ICM, stack-to-blind baskısı "
            "   nasıl yönetilmeli?\n"
            "5. ÖNÜMÜZDEKI 3 HAFTA: Somut, öncelikli 3 çalışma maddesi ver.\n\n"
            "Türkçe, maddeler halinde, net ve somut ol. Platitude yok, gerçek coaching."
        )

        if hasattr(self, "_analysis_box"):
            self._analysis_box.setPlainText("⏳  Analiz hazırlanıyor…")
        self.analysis_requested.emit(prompt)

    def _request_general_analysis(self) -> None:
        history = get_tournament_history(limit=50)
        if not history:
            self.coach_message.emit("Henüz analiz edilecek turnuva yok. Oyna ve geri gel!")
            return

        # Switch right panel to general view first
        self._show_general_view()

        n        = len(history)
        itm_n    = sum(1 for h in history if h.get("prize_won", 0) > 0)
        t_profit = sum(h.get("profit", 0) for h in history)
        t_invest = sum(h.get("buyin", 0) for h in history)
        g_roi    = (t_profit / t_invest * 100) if t_invest > 0 else 0.0
        avg_vpip = sum(h.get("vpip", 0) for h in history) / n
        avg_pfr  = sum(h.get("pfr", 0) for h in history) / n
        avg_bb   = sum(h.get("bb_per_100", 0) for h in history) / n
        avg_gap  = avg_vpip - avg_pfr

        # Last 5 trend
        r5   = history[:min(5, n)]
        r5_roi = (sum(h.get("profit",0) for h in r5) /
                  max(sum(h.get("buyin",0) for h in r5), 1)) * 100

        # Breakdown table for prompt
        tourney_lines = []
        for i, h in enumerate(history[:15], 1):
            fin   = h.get("finish_position") or h.get("field_size", 0)
            field = h.get("field_size", 0)
            pct   = (1 - fin / max(field, 1)) * 100
            tourney_lines.append(
                f"  {i:>2}. {h.get('name','')[:20]:<22} "
                f"{fin}/{field} (top {pct:.0f}%)  "
                f"${h.get('prize_won',0):>6.0f}  "
                f"ROI {(h.get('profit',0)/max(h.get('buyin',1),1)*100):>+5.0f}%  "
                f"VPIP {h.get('vpip',0):.0f}%"
            )

        prompt = (
            f"GENEL TURNUVA GEÇMİŞİ ANALİZİ — {n} turnuva:\n\n"
            f"Özet:\n"
            f"  Toplam: {n} turnuva  ·  ITM: {itm_n} ({100*itm_n/max(n,1):.0f}%)\n"
            f"  Net P&L: {t_profit:+.2f}$  ·  Yatırılan: {t_invest:.0f}$\n"
            f"  Genel ROI: {g_roi:+.1f}%\n"
            f"  Son 5 turnuva ROI: {r5_roi:+.1f}%\n"
            f"  Ort. VPIP: {avg_vpip:.1f}%  ·  PFR: {avg_pfr:.1f}%  "
            f"  Gap: {avg_gap:.1f}%  ·  BB/100: {avg_bb:+.1f}\n\n"
            f"Son {min(15,n)} turnuva listesi:\n"
            + "\n".join(tourney_lines) + "\n\n"
            "Bu geçmiş verisi üzerinden KAPSAMLI KOÇLUK ANALİZİ yap:\n\n"
            "1. ROI PATTERN: Bu genel ROI bu seviyede ne anlama geliyor? "
            "   Kalıcı bir edge var mı, variance mı?\n"
            "2. İSTATİSTİK PROFİLİ: Ort. VPIP/PFR/gap tüm turnuvalarda ne gösteriyor? "
            "   Tutarlı bir leak var mı?\n"
            "3. TREND: Son 5 vs önceki turnuvalar — gelişiyor mu, kötüleşiyor mu? Neden?\n"
            "4. EN KRİTİK TEK LEAK: Tüm verilere bakınca en büyük EV kaybettiren davranış nedir?\n"
            "5. 30 GÜNLÜK PLAN: Bu spesifik oyuncuya özel, somut 30 günlük çalışma planı.\n\n"
            f"Türkçe, net ve somut. Oynadıkça bu analiz gelişir — şu an {n} turnuva verisi var."
        )

        if hasattr(self, "_analysis_box"):
            self._analysis_box.setPlainText("⏳  Kapsamlı analiz hazırlanıyor…")
        self.analysis_requested.emit(prompt)

    # ── called by main.py with Gemini result ─────────────────────────

    def show_analysis_result(self, text: str) -> None:
        if hasattr(self, "_analysis_box"):
            self._analysis_box.setPlainText(text)
        self.coach_message.emit(text)
