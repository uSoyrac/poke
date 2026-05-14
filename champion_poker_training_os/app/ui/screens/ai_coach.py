from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget

from app.agents import GTOMasterAgent
from app.ai.coach_engine import coach_chat, explain_spot
from app.core.app_state import AppState


class AiCoachScreen(QWidget):
    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.master = GTOMasterAgent()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        title = QLabel("AI Poker Coach")
        title.setObjectName("Title")
        layout.addWidget(title)

        intro = QLabel(
            "Three coaches, one panel:\n"
            "  • Chat — quick Q&A in Turkish (offline mock)\n"
            "  • Explain Spot — structured 9-point breakdown of the selected spot\n"
            "  • Master Review — tournament-coach grade analysis: range, blockers, "
            "texture, leak warning + drill prescription"
        )
        intro.setObjectName("Muted")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.history = QTextEdit()
        self.history.setReadOnly(True)
        self.history.setPlainText(
            "Hazır. Bir trainer ekranından spot seçtikten sonra \"Master Review\" "
            "butonuna bas → pro-koç seviyesinde analiz alacaksın."
        )
        self.input = QTextEdit()
        self.input.setMaximumHeight(88)
        self.input.setPlaceholderText("Leak, spot, matematik veya plan sorusu yazın...")

        row = QHBoxLayout()
        ask = QPushButton("Ask Coach")
        ask.setObjectName("PrimaryButton")
        ask.clicked.connect(self.ask)

        explain = QPushButton("Explain Selected Spot")
        explain.clicked.connect(self.explain_selected)

        master_btn = QPushButton("🎓  Master Review")
        master_btn.setObjectName("PrimaryButton")
        master_btn.clicked.connect(self.master_review)

        row.addWidget(ask)
        row.addWidget(explain)
        row.addWidget(master_btn)
        layout.addWidget(self.history, 1)
        layout.addWidget(self.input)
        layout.addLayout(row)

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
        # Coach engine explanation
        try:
            self.history.append("\n" + explain_spot(spot, hero_action))
        except Exception:
            pass
        # Master review for deeper analysis
        try:
            result = self.master.run(spot=spot)
            if result.success:
                markdown = result.data.get("markdown", "")
                plain = markdown.replace("**", "").replace("## ", "\n")
                self.history.append("\n" + plain)
        except Exception:
            pass
        # Consume the context so next visit doesn't re-trigger
        self.state.coach_deepdive_context = {}

    def ask(self) -> None:
        prompt = self.input.toPlainText().strip()
        if not prompt:
            return
        answer = coach_chat(prompt, self.state.selected_spot if "spot" in prompt.lower() else None)
        self.history.append(f"\nUser: {prompt}\nCoach: {answer}")
        self.input.clear()

    def explain_selected(self) -> None:
        if self.state.selected_spot:
            self.history.append("\nCoach: " + explain_spot(self.state.selected_spot))
        else:
            self.history.append("\nCoach: Önce trainer veya analyzer ekranında bir spot seç.")

    def master_review(self) -> None:
        """Tournament-coach-grade structured analysis via GTOMasterAgent."""
        if not self.state.selected_spot:
            self.history.append(
                "\nMaster: Önce bir trainer ekranından spot seç (Spot Practice / "
                "GTO Trainer / ICM / Study Library). Seçim AppState.selected_spot'a "
                "düşer; sonra bu butonu tekrar bas."
            )
            return
        result = self.master.run(spot=self.state.selected_spot)
        if not result.success:
            self.history.append(f"\nMaster: {result.summary}")
            return
        markdown = result.data.get("markdown", "")
        # Strip simple markdown for QTextEdit display
        plain = markdown.replace("**", "").replace("## ", "\n").replace("\n\n", "\n\n")
        self.history.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        self.history.append("🎓  MASTER REVIEW")
        self.history.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        self.history.append(plain)

