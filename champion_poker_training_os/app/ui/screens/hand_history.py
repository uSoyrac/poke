"""Hand History Archive — gün gün arşivli el geçmişi.

200M+ el ölçeklenmesi için tasarlanmış:
- Sol panel: tarihler listesi (CREATE INDEX ile O(log N) tarih sorgusu)
- Orta panel: seçili günün elleri (paginated, 500'er)
- Sağ panel: seçili el detayı + Gemini "Bu eli analiz et" butonu

Tüm sorgular date(created_at) index'i üzerinden çalışır.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QScrollArea, QSizePolicy, QSplitter, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget, QHeaderView,
)

from app.core.app_state import AppState
from app.db.repository import (
    get_dates_with_hands, get_hand_count_for_date, get_hands_for_date,
    get_overall_archive_stats,
)


# ── COLOR PALETTE (theme-uyumlu) ──────────────────────────────────────
COLOR_INK   = "#FAFAFA"
COLOR_MUTED = "#94A3B8"
COLOR_BG    = "#0F1419"
COLOR_CARD  = "#111827"
COLOR_LINE  = "#1F2937"
COLOR_GOOD  = "#10B981"
COLOR_BAD   = "#DC2626"
COLOR_NEUTRAL = "#94A3B8"
COLOR_ACCENT = "#8B5CF6"


class HandHistoryScreen(QWidget):
    """Gün gün arşiv ekranı — calendar-style date picker + paginated hands."""

    coach_message = Signal(str)
    analysis_requested = Signal(str)     # Gemini için prompt

    PAGE_SIZE = 500

    def __init__(self, state: AppState | None = None):
        super().__init__()
        self.state = state
        self._selected_date: Optional[str] = None
        self._selected_hand: Optional[dict] = None
        self._current_page = 0
        self._current_count = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 20)
        root.setSpacing(14)

        # Başlık
        title = QLabel("📅  Hand History Archive")
        title.setStyleSheet(
            f"color: {COLOR_INK}; font-size: 22px; font-weight: 800;"
        )
        root.addWidget(title)
        subtitle = QLabel(
            "Gün gün el arşivi  ·  200M ele kadar ölçeklenir  ·  "
            "Her el için Gemini ile detaylı analiz al."
        )
        subtitle.setStyleSheet(f"color: {COLOR_MUTED}; font-size: 12px;")
        root.addWidget(subtitle)

        # Overall stats banner
        self.stats_banner = QLabel("")
        self.stats_banner.setStyleSheet(
            f"color: {COLOR_INK}; font-size: 12px; padding: 8px 14px; "
            f"background: {COLOR_CARD}; border: 1px solid {COLOR_LINE}; "
            f"border-radius: 8px; font-family: 'JetBrains Mono', monospace;"
        )
        root.addWidget(self.stats_banner)

        # Ana içerik: 3 panel splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(2)

        # Sol: tarih listesi
        splitter.addWidget(self._build_date_panel())
        # Orta: o günün elleri (tablo)
        splitter.addWidget(self._build_hands_panel())
        # Sağ: seçili el detayı
        splitter.addWidget(self._build_detail_panel())

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 2)

        root.addWidget(splitter, 1)

        # İlk yükle: tarihleri çek
        self._refresh_dates()
        self._refresh_overall_stats()

    # ── DATE PANEL ────────────────────────────────────────────────────
    def _build_date_panel(self) -> QWidget:
        panel = QFrame()
        panel.setStyleSheet(
            f"QFrame {{ background: {COLOR_CARD}; border: 1px solid {COLOR_LINE}; "
            f"border-radius: 10px; padding: 12px; }}"
        )
        v = QVBoxLayout(panel)
        v.setSpacing(8)
        v.setContentsMargins(8, 8, 8, 8)

        head = QLabel("TARİHLER")
        head.setStyleSheet(
            f"color: {COLOR_MUTED}; font-size: 11px; font-weight: 700; "
            f"letter-spacing: 1.5px; padding: 4px 8px;"
        )
        v.addWidget(head)

        self.date_list = QListWidget()
        self.date_list.setStyleSheet(
            f"QListWidget {{ background: transparent; border: none; "
            f"color: {COLOR_INK}; font-family: 'JetBrains Mono', monospace; "
            f"font-size: 12px; }} "
            f"QListWidget::item {{ padding: 8px 10px; border-radius: 6px; "
            f"margin: 2px 0; background: {COLOR_BG}; }} "
            f"QListWidget::item:selected {{ background: {COLOR_ACCENT}; "
            f"color: white; }} "
            f"QListWidget::item:hover {{ background: {COLOR_LINE}; }}"
        )
        self.date_list.itemClicked.connect(self._on_date_clicked)
        v.addWidget(self.date_list, 1)

        return panel

    # ── HANDS PANEL ───────────────────────────────────────────────────
    def _build_hands_panel(self) -> QWidget:
        panel = QFrame()
        panel.setStyleSheet(
            f"QFrame {{ background: {COLOR_CARD}; border: 1px solid {COLOR_LINE}; "
            f"border-radius: 10px; padding: 12px; }}"
        )
        v = QVBoxLayout(panel)
        v.setSpacing(8)

        # Header bar
        head_row = QHBoxLayout()
        self.hands_title = QLabel("ELLER  —  Tarih seç")
        self.hands_title.setStyleSheet(
            f"color: {COLOR_MUTED}; font-size: 11px; font-weight: 700; "
            f"letter-spacing: 1.5px;"
        )
        head_row.addWidget(self.hands_title)
        head_row.addStretch(1)

        # Pagination
        self.page_label = QLabel("")
        self.page_label.setStyleSheet(
            f"color: {COLOR_MUTED}; font-size: 11px;"
        )
        self.prev_btn = QPushButton("◀")
        self.next_btn = QPushButton("▶")
        for btn in (self.prev_btn, self.next_btn):
            btn.setFixedWidth(30)
            btn.setStyleSheet(self._small_btn_style())
            btn.setEnabled(False)
        self.prev_btn.clicked.connect(self._page_prev)
        self.next_btn.clicked.connect(self._page_next)
        head_row.addWidget(self.prev_btn)
        head_row.addWidget(self.page_label)
        head_row.addWidget(self.next_btn)
        v.addLayout(head_row)

        # Hands table
        self.hands_table = QTableWidget()
        self.hands_table.setColumnCount(6)
        self.hands_table.setHorizontalHeaderLabels(
            ["#", "Saat", "El", "Board", "Pot", "Net"]
        )
        self.hands_table.verticalHeader().setVisible(False)
        self.hands_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.hands_table.setSelectionMode(QTableWidget.SingleSelection)
        self.hands_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.hands_table.setStyleSheet(
            f"QTableWidget {{ background: transparent; border: none; "
            f"color: {COLOR_INK}; font-family: 'JetBrains Mono', monospace; "
            f"font-size: 11px; gridline-color: {COLOR_LINE}; }} "
            f"QTableWidget::item {{ padding: 6px 4px; border-bottom: 1px solid {COLOR_LINE}; }} "
            f"QTableWidget::item:selected {{ background: {COLOR_ACCENT}; }} "
            f"QHeaderView::section {{ background: {COLOR_BG}; "
            f"color: {COLOR_MUTED}; padding: 6px; border: none; "
            f"border-bottom: 1px solid {COLOR_LINE}; font-weight: 700; "
            f"text-align: left; }}"
        )
        hdr = self.hands_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.Stretch)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.hands_table.itemSelectionChanged.connect(self._on_hand_selected)
        v.addWidget(self.hands_table, 1)

        return panel

    # ── DETAIL PANEL ──────────────────────────────────────────────────
    def _build_detail_panel(self) -> QWidget:
        panel = QFrame()
        panel.setStyleSheet(
            f"QFrame {{ background: {COLOR_CARD}; border: 1px solid {COLOR_LINE}; "
            f"border-radius: 10px; padding: 16px; }}"
        )
        v = QVBoxLayout(panel)
        v.setSpacing(12)

        head = QLabel("EL DETAYI")
        head.setStyleSheet(
            f"color: {COLOR_MUTED}; font-size: 11px; font-weight: 700; "
            f"letter-spacing: 1.5px;"
        )
        v.addWidget(head)

        self.detail_label = QLabel("Bir el seç →")
        self.detail_label.setWordWrap(True)
        self.detail_label.setStyleSheet(
            f"color: {COLOR_INK}; font-size: 12px; "
            f"font-family: 'JetBrains Mono', monospace; "
            f"line-height: 1.7;"
        )
        v.addWidget(self.detail_label)

        # Spacer
        v.addStretch(1)

        # Gemini analiz butonu
        self.gemini_btn = QPushButton("🤖  Gemini ile Analiz Et")
        self.gemini_btn.setFixedHeight(44)
        self.gemini_btn.setStyleSheet(
            f"QPushButton {{ background: {COLOR_ACCENT}; color: white; "
            f"border: none; border-radius: 8px; font-size: 13px; "
            f"font-weight: 700; }} "
            f"QPushButton:hover {{ background: #7c3aed; }} "
            f"QPushButton:disabled {{ background: {COLOR_LINE}; "
            f"color: {COLOR_MUTED}; }}"
        )
        self.gemini_btn.setEnabled(False)
        self.gemini_btn.clicked.connect(self._request_gemini_analysis)
        v.addWidget(self.gemini_btn)

        # Gemini cevabı (analiz dönerse burada gösterilir)
        self.analysis_box = QLabel("")
        self.analysis_box.setWordWrap(True)
        self.analysis_box.setStyleSheet(
            f"color: {COLOR_INK}; font-size: 11px; background: {COLOR_BG}; "
            f"padding: 12px; border-radius: 8px; "
            f"border-left: 3px solid {COLOR_ACCENT};"
        )
        self.analysis_box.hide()
        v.addWidget(self.analysis_box)

        return panel

    def _small_btn_style(self) -> str:
        return (
            f"QPushButton {{ background: {COLOR_BG}; color: {COLOR_INK}; "
            f"border: 1px solid {COLOR_LINE}; border-radius: 4px; "
            f"font-weight: 700; }} "
            f"QPushButton:hover {{ background: {COLOR_LINE}; }} "
            f"QPushButton:disabled {{ color: {COLOR_MUTED}; }}"
        )

    # ── DATA LOADING ──────────────────────────────────────────────────
    def showEvent(self, ev) -> None:
        """Her ekran açıldığında tarihleri yenile (yeni el oynanmış olabilir)."""
        super().showEvent(ev)
        self._refresh_dates()
        self._refresh_overall_stats()

    def _refresh_overall_stats(self) -> None:
        try:
            s = get_overall_archive_stats()
        except Exception as e:
            self.stats_banner.setText(f"DB hatası: {e}")
            return
        if s["total_hands"] == 0:
            self.stats_banner.setText(
                "Arşivde henüz el yok — Play Session veya Tournament "
                "Simulator'da bir el oynayınca otomatik kaydedilir."
            )
            return
        net = s["net_bb"]
        net_str = f"{net:+,.1f}bb"
        net_color = COLOR_GOOD if net >= 0 else COLOR_BAD
        self.stats_banner.setText(
            f"<span style='color:{COLOR_INK};'>"
            f"📊  <b>{s['total_hands']:,}</b> el  ·  "
            f"<b>{s['total_days']}</b> gün  ·  "
            f"Net: <span style='color:{net_color};'><b>{net_str}</b></span>  ·  "
            f"<span style='color:{COLOR_MUTED};'>{s['first_date']} → "
            f"{s['last_date']}</span></span>"
        )

    def _refresh_dates(self) -> None:
        try:
            dates = get_dates_with_hands(limit_days=90)
        except Exception as e:
            self.date_list.clear()
            self.date_list.addItem(f"DB hatası: {e}")
            return
        self.date_list.clear()
        if not dates:
            self.date_list.addItem("Henüz veri yok.")
            return
        for d in dates:
            net = d["net_bb"]
            net_color = COLOR_GOOD if net >= 0 else COLOR_BAD
            net_sym = "+" if net >= 0 else ""
            item_text = (
                f"{d['date']}\n"
                f"  {d['hands']} el · {net_sym}{net:.1f}bb · "
                f"{d['wins']}W"
            )
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, d["date"])
            self.date_list.addItem(item)

    def _on_date_clicked(self, item: QListWidgetItem) -> None:
        date_str = item.data(Qt.UserRole)
        if not date_str:
            return
        self._selected_date = date_str
        self._current_page = 0
        self._current_count = get_hand_count_for_date(date_str)
        self.hands_title.setText(
            f"ELLER  —  {date_str}  ({self._current_count} el)"
        )
        self._load_page()

    def _load_page(self) -> None:
        if not self._selected_date:
            return
        offset = self._current_page * self.PAGE_SIZE
        hands = get_hands_for_date(self._selected_date,
                                    limit=self.PAGE_SIZE, offset=offset)
        # Pagination labels
        first = offset + 1 if hands else 0
        last = offset + len(hands)
        self.page_label.setText(
            f"  {first:,} – {last:,} / {self._current_count:,}  "
        )
        self.prev_btn.setEnabled(self._current_page > 0)
        self.next_btn.setEnabled(last < self._current_count)
        # Populate table
        self.hands_table.setRowCount(len(hands))
        for i, h in enumerate(hands):
            # Saat (created_at → HH:MM:SS)
            ts = (h.get("created_at") or "")[11:19] or "—"
            hero_cards = h.get("hero_cards") or "—"
            board = h.get("community") or "—"
            pot = h.get("pot") or 0
            net = h.get("hero_profit") or 0
            won = h.get("hero_won") or 0

            cells = [
                str(offset + i + 1),
                ts,
                hero_cards,
                board[:24],
                f"{pot:,.0f}",
                f"{net:+,.0f}",
            ]
            for col, txt in enumerate(cells):
                cell = QTableWidgetItem(txt)
                if col == 5:  # Net
                    if net > 0:
                        cell.setForeground(Qt.green)
                    elif net < 0:
                        cell.setForeground(Qt.red)
                self.hands_table.setItem(i, col, cell)
            # Selami: hand verisini ilk hücreye sakla
            self.hands_table.item(i, 0).setData(Qt.UserRole, h)

    def _on_hand_selected(self) -> None:
        sel = self.hands_table.selectedItems()
        if not sel:
            return
        row = sel[0].row()
        item = self.hands_table.item(row, 0)
        if not item:
            return
        hand = item.data(Qt.UserRole)
        if not hand:
            return
        self._selected_hand = hand
        self._show_detail(hand)
        self.gemini_btn.setEnabled(True)
        self.analysis_box.hide()

    def _show_detail(self, hand: dict) -> None:
        hero_cards = hand.get("hero_cards") or "—"
        board = hand.get("community") or "(çekilmedi)"
        pot = hand.get("pot") or 0
        invested = hand.get("hero_invested") or 0
        profit = hand.get("hero_profit") or 0
        won = bool(hand.get("hero_won"))
        winner_hand = hand.get("winner_hand_name") or "—"
        streets = hand.get("streets_seen") or 0
        created = (hand.get("created_at") or "—")[:19]
        outcome_color = COLOR_GOOD if profit > 0 else (COLOR_BAD if profit < 0 else COLOR_MUTED)
        outcome_text = "WON" if won else ("LOST" if invested > 0 else "FOLDED")

        street_map = {1: "preflop", 2: "flop", 3: "turn", 4: "river", 5: "showdown"}
        last_street = street_map.get(streets, "—")

        html = (
            f"<div style='line-height:1.7;'>"
            f"<span style='color:{COLOR_MUTED};'>Zaman:</span>  {created}<br>"
            f"<span style='color:{COLOR_MUTED};'>Hero el:</span>  "
            f"<b>{hero_cards}</b><br>"
            f"<span style='color:{COLOR_MUTED};'>Board:</span>  {board}<br>"
            f"<span style='color:{COLOR_MUTED};'>Son sokak:</span>  "
            f"<b>{last_street}</b><br>"
            f"<span style='color:{COLOR_MUTED};'>Pot:</span>  {pot:,.0f}<br>"
            f"<span style='color:{COLOR_MUTED};'>Hero yatırım:</span>  "
            f"{invested:,.0f}<br>"
            f"<span style='color:{COLOR_MUTED};'>Net:</span>  "
            f"<span style='color:{outcome_color}; font-weight:700;'>"
            f"{profit:+,.0f}  ({outcome_text})</span><br>"
            f"<span style='color:{COLOR_MUTED};'>Kazanan el:</span>  "
            f"{winner_hand}"
            f"</div>"
        )
        self.detail_label.setText(html)

    # ── PAGINATION ────────────────────────────────────────────────────
    def _page_prev(self) -> None:
        if self._current_page > 0:
            self._current_page -= 1
            self._load_page()

    def _page_next(self) -> None:
        if (self._current_page + 1) * self.PAGE_SIZE < self._current_count:
            self._current_page += 1
            self._load_page()

    # ── GEMINI ANALYSIS ───────────────────────────────────────────────
    def _request_gemini_analysis(self) -> None:
        if not self._selected_hand:
            return
        h = self._selected_hand
        prompt = (
            "Bu eli analiz et ve eğitim amaçlı dersler çıkar. "
            "Hero'nun yaptığı doğru ve yanlış kararları belirt, "
            "GTO açısından alternatif aksiyonları açıkla.\n\n"
            f"Tarih: {(h.get('created_at') or '')[:19]}\n"
            f"Hero kartlar: {h.get('hero_cards') or '—'}\n"
            f"Board: {h.get('community') or '(preflop bitti)'}\n"
            f"Pot: {h.get('pot') or 0}\n"
            f"Hero yatırım: {h.get('hero_invested') or 0}\n"
            f"Hero net: {h.get('hero_profit') or 0}\n"
            f"Hero kazandı mı: {'Evet' if h.get('hero_won') else 'Hayır'}\n"
            f"Streets görüldü: {h.get('streets_seen') or 0}/5\n"
            f"Kazanan el: {h.get('winner_hand_name') or '—'}\n\n"
            "Cevabı Türkçe, 3-5 cümlede ver."
        )
        self.analysis_box.setText("⏳  Gemini analiz ediyor...")
        self.analysis_box.show()
        self.gemini_btn.setEnabled(False)
        self.analysis_requested.emit(prompt)

    def show_analysis_result(self, text: str) -> None:
        """main.py'nin Gemini cevabını bu metoda yönlendirmesi için public API."""
        self.analysis_box.setText(text)
        self.analysis_box.show()
        self.gemini_btn.setEnabled(True)
