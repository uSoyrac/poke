from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QTextEdit,
    QVBoxLayout, QWidget,
)

from app.agents import GTOMasterAgent
from app.ai.coach_engine import coach_chat, explain_spot
from app.core.app_state import AppState
from app.data.pro_profiles import PROS, format_pro, lookup_pro
from app.ui.components.poke import (
    PokeBtn, PokeCard, PokePageHeader, PokeTag,
)
from app.ui.theme import poke_tokens as t


class AiCoachScreen(QWidget):
    """AI Poker Coach — Poke editorial layout.

    Three roles in one panel:
      • Chat — Turkish Q&A backed by the glossary + pro profiles
      • Spot Explain — 7-section GTO breakdown of the selected spot
      • Master Review — tournament-coach analysis (range / blockers / texture)

    The screen is composed of two Poke cards:
      A1  CONVERSATION    — chat transcript + input area
      A2  QUICK ACCESS    — pro selector + sözlük term chips + actions
    """

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.master = GTOMasterAgent()

        # ── root dark background — kill the legacy bleed-through ──
        self.setObjectName("AiCoachScreenRoot")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            f"#AiCoachScreenRoot {{ background: {t.BG}; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(t.PAGE_PAD, t.PAGE_PAD, t.PAGE_PAD, 24)
        layout.setSpacing(16)

        # ── Page header ──────────────────────────────────────────────
        header = PokePageHeader(
            num="21 / AI Coach",
            title="Ask the <em>coach</em>.",
            sub=("Türkçe Q&A · 98 terim sözlüğü · 14 pro profili · "
                 "tournament-grade master review."),
        )
        layout.addWidget(header)

        # ── Two-column body ───────────────────────────────────────────
        body = QHBoxLayout()
        body.setSpacing(16)
        layout.addLayout(body, 1)

        # ── LEFT: Conversation card (large) ──────────────────────────
        conv_card = PokeCard(
            "Conversation",
            num="A1",
            sub="LIVE COACH",
        )
        conv_card.body_layout().setSpacing(10)

        self.history = QTextEdit()
        self.history.setReadOnly(True)
        self.history.setPlainText(
            "Hazır. Soru yaz, pro seç veya sözlük terimi tıkla.\n"
            "Trainer'dan spot seçtikten sonra 'Master Review' → "
            "pro-koç analizi alırsın."
        )
        self.history.setStyleSheet(
            f"QTextEdit {{"
            f"  background: {t.BG_2}; color: {t.INK_2};"
            f"  border: 1px solid {t.LINE};"
            f"  font-family: 'Space Grotesk'; font-size: 13px;"
            f"  padding: 14px;"
            f"}}"
            f"QScrollBar:vertical {{ width: 6px; background: transparent; }}"
            f"QScrollBar::handle:vertical {{ background: {t.LINE_2}; }}"
        )
        conv_card.add_to_body(self.history)

        # Input + action row
        self.input = QTextEdit()
        self.input.setMaximumHeight(88)
        self.input.setPlaceholderText(
            "Soru yaz: 'preflop UTG ile ne yapayım?', 'ivey ne yapardı?', "
            "'MDF nedir?', 'leak'lerim ne?', 'plan ver'..."
        )
        self.input.setStyleSheet(
            f"QTextEdit {{"
            f"  background: {t.BG_2}; color: {t.INK};"
            f"  border: 1px solid {t.LINE_2};"
            f"  font-family: 'Space Grotesk'; font-size: 13px;"
            f"  padding: 10px;"
            f"}}"
            f"QTextEdit:focus {{ border-color: {t.ACCENT}; }}"
        )
        conv_card.add_to_body(self.input)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        ask = PokeBtn("Coach'a sor", variant="primary", size="md", kbd="↵")
        ask.clicked.connect(self.ask)
        action_row.addWidget(ask)

        explain = PokeBtn("Seçili spotu açıkla", variant="default", size="md")
        explain.clicked.connect(self.explain_selected)
        action_row.addWidget(explain)

        master_btn = PokeBtn("Master review", variant="default",
                              size="md", kbd="M")
        master_btn.clicked.connect(self.master_review)
        action_row.addWidget(master_btn)

        action_row.addStretch(1)

        clear_btn = PokeBtn("Temizle", variant="ghost", size="md")
        clear_btn.clicked.connect(self._clear_history)
        action_row.addWidget(clear_btn)

        conv_card.add_layout_to_body(action_row)

        body.addWidget(conv_card, 5)

        # ── RIGHT: Quick access card ─────────────────────────────────
        quick_card = PokeCard(
            "Quick access",
            num="A2",
            sub=f"{len(PROS)} PROS · 6 CORE TERMS",
        )
        quick_card.body_layout().setSpacing(12)

        # Eyebrow: PRO PROFILES
        eyebrow1 = QLabel("▸  PRO PROFILES")
        eyebrow1.setStyleSheet(
            f"color: {t.MUTED}; background: transparent; "
            f"font-family: 'JetBrains Mono'; font-weight: 500; font-size: 10px;"
        )
        quick_card.add_to_body(eyebrow1)

        self.pro_combo = QComboBox()
        self.pro_combo.addItem("— Pro oyuncu seç —")
        for p in PROS:
            self.pro_combo.addItem(p["name"])
        self.pro_combo.setStyleSheet(
            f"QComboBox {{"
            f"  background: {t.BG_2}; color: {t.INK};"
            f"  border: 1px solid {t.LINE_2};"
            f"  padding: 8px 12px;"
            f"  font-family: 'Space Grotesk'; font-size: 13px;"
            f"}}"
            f"QComboBox:focus {{ border-color: {t.ACCENT}; }}"
            f"QComboBox::drop-down {{ border: none; width: 22px; }}"
        )
        self.pro_combo.currentIndexChanged.connect(self._on_pro_picked)
        quick_card.add_to_body(self.pro_combo)

        # Eyebrow: CORE TERMS
        eyebrow2 = QLabel("▸  CORE TERMS")
        eyebrow2.setStyleSheet(
            f"color: {t.MUTED}; background: transparent; "
            f"font-family: 'JetBrains Mono'; font-weight: 500; font-size: 10px;"
            f"padding-top: 8px;"
        )
        quick_card.add_to_body(eyebrow2)

        # 2x3 grid of term chips
        term_grid = QFrame()
        term_grid.setStyleSheet("QFrame { background: transparent; }")
        tgl = QVBoxLayout(term_grid)
        tgl.setContentsMargins(0, 0, 0, 0)
        tgl.setSpacing(6)
        terms = ["GTO", "MDF", "ICM", "Pot Odds", "Blocker", "Range"]
        for i in range(0, len(terms), 3):
            row = QHBoxLayout()
            row.setSpacing(6)
            for term in terms[i:i + 3]:
                b = PokeBtn(term, variant="ghost", size="sm")
                b.clicked.connect(lambda _=False, t_=term: self._quick_term(t_))
                row.addWidget(b)
            row.addStretch(1)
            tgl.addLayout(row)
        quick_card.add_to_body(term_grid)

        # Eyebrow: STATUS
        eyebrow3 = QLabel("▸  STATUS")
        eyebrow3.setStyleSheet(
            f"color: {t.MUTED}; background: transparent; "
            f"font-family: 'JetBrains Mono'; font-weight: 500; font-size: 10px;"
            f"padding-top: 8px;"
        )
        quick_card.add_to_body(eyebrow3)

        status_row = QHBoxLayout()
        status_row.setSpacing(6)
        status_row.addWidget(PokeTag("OFFLINE", tone="g", dot=True))
        status_row.addWidget(PokeTag("MOCK MODEL", tone="b"))
        status_row.addStretch(1)
        quick_card.add_layout_to_body(status_row)

        # Spot context indicator — updated in showEvent
        self.spot_ctx_label = QLabel("Henüz spot seçilmedi.")
        self.spot_ctx_label.setWordWrap(True)
        self.spot_ctx_label.setStyleSheet(
            f"color: {t.INK_2}; background: transparent; "
            f"font-family: 'Space Grotesk'; font-size: 12px; "
            f"padding-top: 4px;"
        )
        quick_card.add_to_body(self.spot_ctx_label)

        quick_card.body_layout().addStretch(1)

        body.addWidget(quick_card, 2)

    # ── Quick-access handlers ────────────────────────────────────────
    def _on_pro_picked(self, idx: int) -> None:
        if idx == 0:
            return
        pro_name = self.pro_combo.currentText()
        pro = lookup_pro(pro_name)
        if pro:
            self.history.append(f"\n\n{format_pro(pro)}\n")
        self.pro_combo.setCurrentIndex(0)

    def _quick_term(self, term: str) -> None:
        answer = coach_chat(term)
        self.history.append(f"\n\nSoru: {term}\n{answer}")

    def _clear_history(self) -> None:
        self.history.clear()

    def showEvent(self, event) -> None:
        """Auto-trigger a deep-dive if Spot Trainer set context."""
        super().showEvent(event)
        # Refresh spot context label
        sp = self.state.selected_spot
        if sp:
            name = sp.get("name") or sp.get("id") or "spot"
            self.spot_ctx_label.setText(f"Aktif spot: {name}")
        else:
            self.spot_ctx_label.setText("Henüz spot seçilmedi.")

        ctx = getattr(self.state, "coach_deepdive_context", None) or {}
        if not ctx:
            return
        spot = ctx.get("spot") or self.state.selected_spot
        if not spot:
            return
        hero_action = ctx.get("hero_action", "?")
        gto_action  = ctx.get("gto_action", "?")
        ev_loss     = ctx.get("ev_loss", 0.0)
        correct     = ctx.get("is_correct", False)
        verdict     = "DOĞRU KARAR" if correct else f"YANLIŞ KARAR (−{ev_loss:.2f}bb)"
        intro = (
            "\n────────────────────────────────────\n"
            "DEEP-DIVE COACH\n"
            "────────────────────────────────────\n"
            f"Spot: {spot.get('name', spot.get('id', '?'))}\n"
            f"Senin aksiyon: {hero_action.upper()}  |  "
            f"GTO: {gto_action.upper()}\n"
            f"{verdict}\n"
        )
        self.history.append(intro)
        try:
            self.history.append("\n" + explain_spot(spot, hero_action))
        except Exception:
            pass
        try:
            result = self.master.run(spot=spot)
            if result.success:
                markdown = result.data.get("markdown", "")
                plain = markdown.replace("**", "").replace("## ", "\n")
                self.history.append("\n" + plain)
        except Exception:
            pass
        self.state.coach_deepdive_context = {}

    def ask(self) -> None:
        prompt = self.input.toPlainText().strip()
        if not prompt:
            return
        ctx_spot = None
        if any(k in prompt.lower() for k in
                ("spot", "el", "bu spot", "selected")):
            ctx_spot = self.state.selected_spot
        answer = coach_chat(prompt, ctx_spot)
        self.history.append(f"\n\n›  Sen: {prompt}\n\n{answer}")
        self.input.clear()

    def explain_selected(self) -> None:
        if self.state.selected_spot:
            self.history.append("\n\n" + explain_spot(self.state.selected_spot))
        else:
            self.history.append(
                "\n\nCoach: Önce bir trainer veya analyzer ekranında spot seç."
            )

    def master_review(self) -> None:
        """Tournament-coach-grade structured analysis via GTOMasterAgent."""
        if not self.state.selected_spot:
            self.history.append(
                "\n\nMaster: Önce bir trainer ekranından spot seç "
                "(Spot Practice / GTO Trainer / ICM / Study Library). "
                "Seçim AppState.selected_spot'a düşer; sonra bu butonu "
                "tekrar bas."
            )
            return
        result = self.master.run(spot=self.state.selected_spot)
        if not result.success:
            self.history.append(f"\n\nMaster: {result.summary}")
            return
        markdown = result.data.get("markdown", "")
        plain = markdown.replace("**", "").replace("## ", "\n")
        self.history.append("\n\n────────────────────────────────────")
        self.history.append("MASTER REVIEW")
        self.history.append("────────────────────────────────────")
        self.history.append(plain)
