"""Knowledge Base — 3 sekmeli bilgi tabanı.

Sekmeler:
  • 📖 Sözlük       — 98 Türkçe poker terimi (poker_glossary.py)
  • 🃏 Pro Oyuncular — 14 efsane oyuncu profili (pro_profiles.py)
  • 💡 Konseptler   — Eski concept kartları (rag.search_concepts)

Her sekmede üst arama kutusu + kategori filter + scrollable detay paneli.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.ai.rag import search_concepts
from app.core.app_state import AppState
from app.data.poker_glossary import GLOSSARY, category_index, format_entry, search_glossary
from app.data.pro_profiles import PROS, format_pro, search_pros
from app.training.concept_routing import APPLICATION_NAV, route_for


_C_BG     = "#0A0E14"
_C_PANEL  = "#0F141C"
_C_BORDER = "#1E2733"
_C_TEXT   = "#E5E7EB"
_C_MUTED  = "#9CA3AF"
_C_CYAN   = "#22D3EE"

_CATEGORY_LABELS = {
    "position":  "📍 Pozisyon",
    "preflop":   "♣ Preflop",
    "postflop":  "🎯 Postflop",
    "math":      "📐 Matematik",
    "icm":       "💰 ICM",
    "players":   "👥 Oyuncu Tipleri",
    "stats":     "📊 İstatistik",
    "general":   "📖 Genel",
}


def _tab_btn(label: str, active: bool = False) -> QPushButton:
    b = QPushButton(label)
    b.setCheckable(True)
    b.setChecked(active)
    b.setFixedHeight(36)
    b.setCursor(Qt.PointingHandCursor)
    b.setStyleSheet(
        f"QPushButton{{background:transparent;color:{_C_MUTED};"
        f"border:none;border-bottom:2px solid transparent;"
        f"padding:0 22px;font-size:13px;font-weight:700;}}"
        f"QPushButton:hover{{color:{_C_TEXT};}}"
        f"QPushButton:checked{{color:{_C_CYAN};border-bottom-color:{_C_CYAN};}}"
    )
    return b


class KnowledgeBaseScreen(QWidget):
    coach_message = Signal(str)
    navigate_requested = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.setStyleSheet(f"background:{_C_BG};")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ────────────────────────────────────────────────
        header = QFrame()
        header.setStyleSheet(
            f"QFrame{{background:{_C_PANEL};border-bottom:1px solid {_C_BORDER};}}"
        )
        hl = QVBoxLayout(header)
        hl.setContentsMargins(24, 14, 24, 8)
        hl.setSpacing(8)
        title = QLabel("🧠  Knowledge Base")
        title.setStyleSheet(f"color:{_C_TEXT};font-size:20px;font-weight:800;")
        hl.addWidget(title)

        # Tabs
        tab_row = QHBoxLayout()
        tab_row.setSpacing(0)
        self._tab_buttons = []
        for i, label in enumerate(("📖  Sözlük (98)",
                                    "🃏  Pro Oyuncular (14)",
                                    "💡  Konseptler")):
            b = _tab_btn(label, i == 0)
            b.clicked.connect(lambda _=False, idx=i: self._switch(idx))
            self._tab_buttons.append(b)
            tab_row.addWidget(b)
        tab_row.addStretch(1)
        hl.addLayout(tab_row)
        root.addWidget(header)

        # ── Stacked content ──────────────────────────────────────
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_glossary_tab())
        self._stack.addWidget(self._build_pros_tab())
        self._stack.addWidget(self._build_concepts_tab())
        root.addWidget(self._stack, 1)

    def _switch(self, idx: int) -> None:
        for i, b in enumerate(self._tab_buttons):
            b.setChecked(i == idx)
        self._stack.setCurrentIndex(idx)

    # ── Glossary tab ────────────────────────────────────────────

    def _build_glossary_tab(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(20, 16, 20, 16)
        v.setSpacing(10)

        # Search
        self._gloss_search = QLineEdit()
        self._gloss_search.setPlaceholderText(
            "Ara: MDF, 3-bet, ICM, pot odds, polarized, blocker..."
        )
        self._gloss_search.setStyleSheet(
            f"QLineEdit{{background:{_C_PANEL};color:{_C_TEXT};"
            f"border:1px solid {_C_BORDER};border-radius:6px;padding:8px 12px;font-size:13px;}}"
        )
        self._gloss_search.textChanged.connect(self._gloss_refresh)
        v.addWidget(self._gloss_search)

        # Split: list left, detail right
        split = QSplitter(Qt.Horizontal)
        # Left: terim listesi
        self._gloss_list = QListWidget()
        self._gloss_list.setStyleSheet(self._list_style())
        self._gloss_list.itemClicked.connect(self._gloss_show)
        # Right: detail panel
        self._gloss_detail = QTextEdit()
        self._gloss_detail.setReadOnly(True)
        self._gloss_detail.setStyleSheet(
            f"QTextEdit{{background:{_C_PANEL};color:{_C_TEXT};"
            f"border:1px solid {_C_BORDER};border-radius:6px;padding:16px;"
            f"font-size:13px;}}"
        )
        split.addWidget(self._gloss_list)
        split.addWidget(self._gloss_detail)
        split.setSizes([280, 700])
        v.addWidget(split, 1)

        self._gloss_refresh()
        return page

    def _gloss_refresh(self) -> None:
        q = self._gloss_search.text().strip()
        self._gloss_list.clear()
        # Tüm girişler veya arama sonucu
        if q:
            entries = search_glossary(q, max_results=50)
        else:
            entries = sorted(GLOSSARY, key=lambda e: (e["category"], e["term"].lower()))
        current_cat = None
        for e in entries:
            cat = e["category"]
            if cat != current_cat:
                current_cat = cat
                # Category header (non-selectable)
                hdr = QListWidgetItem(_CATEGORY_LABELS.get(cat, cat.upper()))
                hdr.setFlags(Qt.ItemIsEnabled)   # not selectable
                hdr.setForeground(Qt.gray)
                self._gloss_list.addItem(hdr)
            it = QListWidgetItem(f"   {e['term']}")
            it.setData(Qt.UserRole, e)
            self._gloss_list.addItem(it)
        # Auto-select first selectable
        for i in range(self._gloss_list.count()):
            it = self._gloss_list.item(i)
            if it.data(Qt.UserRole):
                self._gloss_list.setCurrentRow(i)
                self._gloss_show(it)
                break

    def _gloss_show(self, item) -> None:
        e = item.data(Qt.UserRole)
        if not e:
            return
        self._gloss_detail.setPlainText(format_entry(e))

    # ── Pro players tab ─────────────────────────────────────────

    def _build_pros_tab(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(20, 16, 20, 16)
        v.setSpacing(10)

        self._pro_search = QLineEdit()
        self._pro_search.setPlaceholderText(
            "Ara: ivey, doyle, hellmuth, negreanu, dwan, jungleman..."
        )
        self._pro_search.setStyleSheet(
            f"QLineEdit{{background:{_C_PANEL};color:{_C_TEXT};"
            f"border:1px solid {_C_BORDER};border-radius:6px;padding:8px 12px;font-size:13px;}}"
        )
        self._pro_search.textChanged.connect(self._pros_refresh)
        v.addWidget(self._pro_search)

        split = QSplitter(Qt.Horizontal)
        self._pro_list = QListWidget()
        self._pro_list.setStyleSheet(self._list_style())
        self._pro_list.itemClicked.connect(self._pro_show)
        self._pro_detail = QTextEdit()
        self._pro_detail.setReadOnly(True)
        self._pro_detail.setStyleSheet(
            f"QTextEdit{{background:{_C_PANEL};color:{_C_TEXT};"
            f"border:1px solid {_C_BORDER};border-radius:6px;padding:16px;"
            f"font-size:13px;}}"
        )
        split.addWidget(self._pro_list)
        split.addWidget(self._pro_detail)
        split.setSizes([260, 720])
        v.addWidget(split, 1)

        self._pros_refresh()
        return page

    def _pros_refresh(self) -> None:
        q = self._pro_search.text().strip()
        self._pro_list.clear()
        items = search_pros(q) if q else PROS
        for p in items:
            it = QListWidgetItem(f"   {p['name']}\n      {p['style_tag']}")
            it.setData(Qt.UserRole, p)
            self._pro_list.addItem(it)
        if self._pro_list.count() > 0:
            self._pro_list.setCurrentRow(0)
            self._pro_show(self._pro_list.item(0))

    def _pro_show(self, item) -> None:
        p = item.data(Qt.UserRole)
        if not p:
            return
        self._pro_detail.setPlainText(format_pro(p))

    # ── Concepts tab (legacy) ───────────────────────────────────

    def _build_concepts_tab(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(20, 16, 20, 16)
        v.setSpacing(10)

        self._concept_search = QLineEdit()
        self._concept_search.setPlaceholderText("Search concepts: MDF, Bayes, ICM, blockers...")
        self._concept_search.setStyleSheet(
            f"QLineEdit{{background:{_C_PANEL};color:{_C_TEXT};"
            f"border:1px solid {_C_BORDER};border-radius:6px;padding:8px 12px;font-size:13px;}}"
        )
        self._concept_search.returnPressed.connect(self._concepts_render)
        v.addWidget(self._concept_search)

        # Concept cards (existing ConceptCard reused)
        self._concept_scroll = QScrollArea()
        self._concept_scroll.setWidgetResizable(True)
        self._concept_scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        self._concept_body = QWidget()
        self._concept_layout = QVBoxLayout(self._concept_body)
        self._concept_layout.setSpacing(10)
        self._concept_scroll.setWidget(self._concept_body)
        v.addWidget(self._concept_scroll, 1)

        self._concepts_render()
        return page

    def _concepts_render(self) -> None:
        # Clear existing
        while self._concept_layout.count():
            item = self._concept_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        # Render
        for card_data in search_concepts(self._concept_search.text() or "poker"):
            card = _ConceptCard(card_data)
            card.practice_clicked.connect(self._on_practice)
            card.coach_clicked.connect(self._on_coach)
            self._concept_layout.addWidget(card)
        self._concept_layout.addStretch(1)

    # ── Concept handlers (legacy) ───────────────────────────────

    def _on_practice(self, card: dict) -> None:
        app = card.get("application") or "Spot Practice Trainer"
        nav_target, filters = route_for(app)
        if filters is not None:
            self.state.drill_filters = {
                **filters,
                "concept": card.get("concept", ""),
                "concept_source": card.get("source", ""),
            }
        else:
            self.state.drill_filters = {
                "concept": card.get("concept", ""),
                "concept_source": card.get("source", ""),
            }
        self.coach_message.emit(
            f"Practice mode: '{card.get('concept', '?')}' — {nav_target}'a yönlendiriliyorsun. "
            f"({card.get('source', '')})"
        )
        self.navigate_requested.emit(nav_target)

    def _on_coach(self, card: dict) -> None:
        self.coach_message.emit(
            f"Concept '{card.get('concept', '?')}' from {card.get('source', '?')}.\n\n"
            f"{card.get('summary', '')}\n\n"
            f"Application: {card.get('application', '—')}\n"
            f"Drill idea: {card.get('drill_idea', '—')}"
        )

    # ── style helpers ───────────────────────────────────────────

    @staticmethod
    def _list_style() -> str:
        return (
            f"QListWidget{{background:{_C_PANEL};color:{_C_TEXT};"
            f"border:1px solid {_C_BORDER};border-radius:6px;font-size:12px;"
            f"padding:6px;}}"
            f"QListWidget::item{{padding:6px 8px;border-radius:4px;}}"
            f"QListWidget::item:selected{{background:#0D2030;color:{_C_CYAN};}}"
            f"QListWidget::item:hover{{background:#13202E;}}"
        )


class _ConceptCard(QFrame):
    """Legacy concept card kept for the third tab."""
    practice_clicked = Signal(dict)
    coach_clicked = Signal(dict)

    def __init__(self, card: dict):
        super().__init__()
        self.card = card
        self.setObjectName("Card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel(card["concept"])
        title.setObjectName("SectionTitle")
        header.addWidget(title)
        header.addStretch(1)
        source_pill = QLabel(card["source"])
        source_pill.setStyleSheet(
            "background:#1B2A3D;color:#22D3EE;font-weight:700;"
            "padding:3px 10px;border-radius:11px;"
        )
        header.addWidget(source_pill)
        layout.addLayout(header)

        summary = QLabel(card["summary"])
        summary.setWordWrap(True)
        summary.setObjectName("Muted")
        layout.addWidget(summary)

        meta = QLabel(
            f"📚 Linked module: <b>{card.get('application', '—')}</b>  ·  "
            f"💡 {card.get('drill_idea', '—')}"
        )
        meta.setTextFormat(Qt.RichText)
        meta.setStyleSheet("color:#9CA3AF;")
        meta.setWordWrap(True)
        layout.addWidget(meta)

        if card.get("misuse_risk"):
            risk = QLabel(f"⚠ {card['misuse_risk']}")
            risk.setStyleSheet("color:#F59E0B;font-size:11px;")
            risk.setWordWrap(True)
            layout.addWidget(risk)

        actions = QHBoxLayout()
        practice_btn = QPushButton("▶ Practice this concept")
        practice_btn.setObjectName("PrimaryButton")
        practice_btn.setStyleSheet(
            "QPushButton{background:#10B981;color:#04110D;font-weight:800;"
            "padding:7px 14px;border-radius:7px;border:none;}"
            "QPushButton:hover{background:#34D399;}"
        )
        practice_btn.setCursor(Qt.PointingHandCursor)
        practice_btn.clicked.connect(lambda: self.practice_clicked.emit(self.card))
        coach_btn = QPushButton("🤖 Ask AI Coach")
        coach_btn.setCursor(Qt.PointingHandCursor)
        coach_btn.clicked.connect(lambda: self.coach_clicked.emit(self.card))
        actions.addWidget(practice_btn)
        actions.addWidget(coach_btn)
        actions.addStretch(1)
        layout.addLayout(actions)


# Backward compat — old name
ConceptCard = _ConceptCard
