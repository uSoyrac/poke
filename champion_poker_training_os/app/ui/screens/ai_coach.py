from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QVBoxLayout, QWidget,
)

from app.agents import GTOMasterAgent
from app.ai.coach_engine import coach_chat, explain_spot
from app.core.app_state import AppState
from app.data.pro_profiles import PROS, format_pro, lookup_pro


class AiCoachScreen(QWidget):
    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.master = GTOMasterAgent()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        title = QLabel("🤖  AI Poker Coach")
        title.setObjectName("Title")
        layout.addWidget(title)

        intro = QLabel(
            "Üç koç tek panelde:\n"
            "  • Sohbet — Türkçe Q&A (98 terim sözlüğü + 14 pro profili entegre)\n"
            "  • Spot Açıkla — seçili spot için 7-bölüm GTO analizi\n"
            "  • Master Review — turnuva-koç seviyesi: range, blocker, "
            "texture, leak warning + drill önerisi"
        )
        intro.setObjectName("Muted")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        # ── Pro/term quick-access bar ───────────────────────────────
        quick_row = QHBoxLayout()
        quick_row.addWidget(QLabel("⚡ Hızlı bilgi:"))

        # Pro selector
        self.pro_combo = QComboBox()
        self.pro_combo.addItem("— Pro oyuncu seç —")
        for p in PROS:
            self.pro_combo.addItem(p["name"])
        self.pro_combo.setMinimumWidth(220)
        self.pro_combo.currentIndexChanged.connect(self._on_pro_picked)
        quick_row.addWidget(self.pro_combo)

        # Common terms quick buttons
        for term in ["GTO", "MDF", "ICM", "Pot Odds", "Blocker", "Range"]:
            b = QPushButton(term)
            b.setStyleSheet(
                "QPushButton{background:#0F141C;color:#22D3EE;"
                "border:1px solid #1E2733;border-radius:0;padding:6px 12px;"
                "font-size:11px;font-weight:700;}"
                "QPushButton:hover{border-color:#22D3EE;background:#0D2030;}"
            )
            b.clicked.connect(lambda _=False, t=term: self._quick_term(t))
            quick_row.addWidget(b)
        quick_row.addStretch(1)
        layout.addLayout(quick_row)

        self.history = QTextEdit()
        self.history.setReadOnly(True)
        self.history.setPlainText(
            "Hazır. Soru yaz, pro seç veya sözlük terimi tıkla.\n"
            "Trainer'dan spot seçtikten sonra 'Master Review' → pro-koç analizi alırsın."
        )
        self.input = QTextEdit()
        self.input.setMaximumHeight(88)
        self.input.setPlaceholderText(
            "Soru yaz: 'preflop UTG ile ne yapayım?', 'ivey ne yapardı?', "
            "'MDF nedir?', 'leak'lerim ne?', 'plan ver'..."
        )

        row = QHBoxLayout()
        ask = QPushButton("💬 Coach'a Sor")
        ask.setObjectName("PrimaryButton")
        ask.clicked.connect(self.ask)

        explain = QPushButton("📖 Seçili Spotu Açıkla")
        explain.clicked.connect(self.explain_selected)

        master_btn = QPushButton("🎓  Master Review")
        master_btn.setObjectName("PrimaryButton")
        master_btn.clicked.connect(self.master_review)

        clear_btn = QPushButton("🗑 Temizle")
        clear_btn.clicked.connect(self._clear_history)

        row.addWidget(ask)
        row.addWidget(explain)
        row.addWidget(master_btn)
        row.addStretch(1)
        row.addWidget(clear_btn)
        layout.addWidget(self.history, 1)
        layout.addWidget(self.input)
        layout.addLayout(row)

    # ── Quick-access handlers ────────────────────────────────────────
    def _on_pro_picked(self, idx: int) -> None:
        if idx == 0:
            return
        pro_name = self.pro_combo.currentText()
        pro = lookup_pro(pro_name)
        if pro:
            self.history.append(f"\n\n{format_pro(pro)}\n")
        # Reset to placeholder
        self.pro_combo.setCurrentIndex(0)

    def _quick_term(self, term: str) -> None:
        answer = coach_chat(term)
        self.history.append(f"\n\nSoru: {term}\n{answer}")

    def _clear_history(self) -> None:
        self.history.clear()

    def showEvent(self, event) -> None:
        """Auto-trigger a deep-dive analysis if Spot Trainer set context."""
        super().showEvent(event)
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
        verdict     = "✅ Doğru karar" if correct else f"❌ Yanlış karar (−{ev_loss:.2f}bb)"
        intro = (
            "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🤖  DEEP-DIVE COACH\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Spot: {spot.get('name', spot.get('id', '?'))}\n"
            f"Senin aksiyon: {hero_action.upper()}  |  GTO: {gto_action.upper()}\n"
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
        # Spot context only when 'spot' or 'el' references
        ctx_spot = None
        if any(k in prompt.lower() for k in ("spot", "el", "bu spot", "selected")):
            ctx_spot = self.state.selected_spot
        answer = coach_chat(prompt, ctx_spot)
        self.history.append(f"\n\n💬 Sen: {prompt}\n\n{answer}")
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
                "\n\nMaster: Önce bir trainer ekranından spot seç (Spot Practice / "
                "GTO Trainer / ICM / Study Library). Seçim AppState.selected_spot'a "
                "düşer; sonra bu butonu tekrar bas."
            )
            return
        result = self.master.run(spot=self.state.selected_spot)
        if not result.success:
            self.history.append(f"\n\nMaster: {result.summary}")
            return
        markdown = result.data.get("markdown", "")
        plain = markdown.replace("**", "").replace("## ", "\n")
        self.history.append("\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        self.history.append("🎓  MASTER REVIEW")
        self.history.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        self.history.append(plain)
