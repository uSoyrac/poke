from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.ai.coach_engine import analyze_played_hand, explain_spot
from app.core.app_state import AppState
from app.db.repository import get_imported_hands, get_session_history, get_player_stats, get_leak_analysis
from app.db.seed_data import generate_hands
from app.ui.components.card_view import CardView
from app.ui.components.hand_replay import HandReplay
from app.ui.components.hand_timeline import HandTimeline
from app.ui.components.metric_card import MetricCard
from app.ui.components.poker_table import PokerTableView


class HandAnalyzerScreen(QWidget):
    coach_message = Signal(str)
    navigate_requested = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.demo_hands = generate_hands(100)
        self.played_hands: list[dict] = []

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        scroll.setWidget(body)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        # Header
        header = QHBoxLayout()
        title = QLabel("Hand History Analyzer")
        title.setObjectName("Title")
        header.addWidget(title)

        self.source_combo = QComboBox()
        self.source_combo.addItems(["Imported Hands (DB)", "Played Hands (DB)", "Demo Hands"])
        self.source_combo.currentTextChanged.connect(self._source_changed)
        header.addWidget(self.source_combo)

        self.filter = QComboBox()
        self.filter.addItems(["All", "Wins Only", "Losses Only", "Big Pots (>20bb)", "Showdowns"])
        self.filter.currentTextChanged.connect(self._populate_table)
        header.addWidget(self.filter)

        refresh_btn = QPushButton("🔄 Refresh from DB")
        refresh_btn.clicked.connect(self._load_played_hands)
        header.addWidget(refresh_btn)
        layout.addLayout(header)

        # Stats row
        stats_row = QGridLayout()
        self.stat_hands = MetricCard("Hands Analyzed", "0", "total")
        self.stat_profit = MetricCard("Total Profit", "0bb", "session", "Green")
        self.stat_winrate = MetricCard("Win Rate", "—", "showdown", "Cyan")
        self.stat_biggest = MetricCard("Biggest Pot", "0bb", "won/lost", "Amber")
        stats_row.addWidget(self.stat_hands, 0, 0)
        stats_row.addWidget(self.stat_profit, 0, 1)
        stats_row.addWidget(self.stat_winrate, 0, 2)
        stats_row.addWidget(self.stat_biggest, 0, 3)
        layout.addLayout(stats_row)

        # Main area
        top = QHBoxLayout()
        # Replace static table view with the rich HandReplay widget on the left
        self.replay = HandReplay()
        self.replay.coach_message.connect(self.coach_message)
        self.replay.practice_requested.connect(self._practice_from_replay)
        top.addWidget(self.replay, 3)
        self.table_view = PokerTableView()  # kept for legacy, hidden under replay
        self.table_view.setVisible(False)

        panel = QFrame()
        panel.setObjectName("DataPanel")
        panel_layout = QVBoxLayout(panel)

        self.summary = QLabel("Select a hand to analyze.")
        self.summary.setWordWrap(True)
        self.summary.setObjectName("SectionTitle")
        panel_layout.addWidget(self.summary)

        # Hero cards display
        self.hero_cards_row = QHBoxLayout()
        panel_layout.addLayout(self.hero_cards_row)

        # AI analysis
        self.analysis_label = QLabel()
        self.analysis_label.setWordWrap(True)
        self.analysis_label.setObjectName("Muted")
        panel_layout.addWidget(self.analysis_label)

        # Action buttons
        btn_row = QHBoxLayout()
        for label, action in [
            ("🔍 AI Review", self._ai_review),
            ("📊 Leak Check", self._leak_check),
            ("▶ Practice Similar", lambda: self.navigate_requested.emit("Spot Practice Trainer")),
            ("🤖 Ask Coach", lambda: self.navigate_requested.emit("AI Poker Coach")),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(action)
            btn_row.addWidget(btn)
        panel_layout.addLayout(btn_row)

        self.timeline = HandTimeline([])
        panel_layout.addWidget(self.timeline)
        top.addWidget(panel, 2)
        layout.addLayout(top)

        # Hand table
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["#", "Hero Cards", "Board", "Pot", "Profit", "Winner", "Streets"])
        self.table.setAlternatingRowColors(True)
        self.table.cellClicked.connect(self._select_row)
        layout.addWidget(self.table)

        # Leak summary at bottom
        self.leak_frame = QFrame()
        self.leak_frame.setObjectName("Card")
        self.leak_layout = QVBoxLayout(self.leak_frame)
        self.leak_title = QLabel("📊 Auto Leak Analysis (from played hands)")
        self.leak_title.setObjectName("SectionTitle")
        self.leak_layout.addWidget(self.leak_title)
        self.leak_content = QLabel("Play hands in Play Session first, then refresh.")
        self.leak_content.setWordWrap(True)
        self.leak_content.setObjectName("Muted")
        self.leak_layout.addWidget(self.leak_content)
        layout.addWidget(self.leak_frame)

        self._load_played_hands()

    def showEvent(self, event):  # type: ignore[override]
        """If we were navigated here with an imported hand selected, auto-load the replay."""
        super().showEvent(event)
        spot = getattr(self.state, "selected_spot", None)
        if spot and isinstance(spot, dict) and spot.get("external_id") and spot.get("preflop_actions") is not None:
            # Switch source to imported and show this hand in the replay
            for i in range(self.source_combo.count()):
                if "Imported" in self.source_combo.itemText(i):
                    self.source_combo.setCurrentIndex(i)
                    break
            self._show_imported_hand(spot)

    def _load_played_hands(self) -> None:
        """Load played + imported hands from SQLite."""
        try:
            self.played_hands = get_session_history(100)
        except Exception:
            self.played_hands = []
        try:
            self.imported_hands_cache = get_imported_hands(200)
        except Exception:
            self.imported_hands_cache = []
        self._populate_table()
        self._update_stats()
        self._update_leaks()

    def _source_changed(self) -> None:
        self._populate_table()
        self._update_stats()

    def _get_active_hands(self) -> list[dict]:
        text = self.source_combo.currentText()
        if "Imported" in text:
            return getattr(self, "imported_hands_cache", []) or []
        if "Demo" in text:
            return self.demo_hands
        return self.played_hands

    def _populate_table(self) -> None:
        hands = self._get_active_hands()
        filt = self.filter.currentText() if hasattr(self, "filter") else "All"
        text = self.source_combo.currentText()
        is_imported = "Imported" in text
        is_played = "Played" in text

        if is_played:
            if "Wins" in filt:
                hands = [h for h in hands if h.get("hero_won")]
            elif "Losses" in filt:
                hands = [h for h in hands if not h.get("hero_won")]
            elif "Big" in filt:
                hands = [h for h in hands if abs(h.get("pot", 0)) > 20]
            elif "Showdown" in filt:
                hands = [h for h in hands if h.get("streets_seen", 0) >= 4]
        elif is_imported:
            if "Wins" in filt:
                hands = [h for h in hands if (h.get("hero_profit_bb") or 0) > 0]
            elif "Losses" in filt:
                hands = [h for h in hands if (h.get("hero_profit_bb") or 0) < 0]
            elif "Big" in filt:
                hands = [h for h in hands if abs(h.get("pot_bb") or 0) > 20]
            elif "Showdown" in filt:
                hands = [h for h in hands if (h.get("river_actions") or "")]

        self.table.setRowCount(len(hands))
        self.table.setProperty("rows", hands)

        for row, hand in enumerate(hands):
            if is_imported:
                items = [
                    str(hand.get("external_id", row + 1)),
                    hand.get("hero_cards", "??"),
                    hand.get("board", ""),
                    f"{hand.get('pot_bb', 0):.1f}",
                    f"{hand.get('hero_profit_bb', 0):+.1f}",
                    hand.get("hero_position", ""),
                    hand.get("pot_type", ""),
                ]
            elif is_played:
                items = [
                    str(hand.get("hand_id", row + 1)),
                    hand.get("hero_cards", "??"),
                    hand.get("community", ""),
                    f"{hand.get('pot', 0):.1f}",
                    f"{hand.get('hero_profit', 0):+.1f}",
                    hand.get("winner_hand_name", ""),
                    str(hand.get("streets_seen", 0)),
                ]
            else:
                items = [
                    str(hand.get("id", row + 1)),
                    hand.get("hero_cards", "??"),
                    hand.get("board", ""),
                    f"{hand.get('spot', {}).get('pot_bb', 0):.1f}",
                    f"{hand.get('result_bb', 0):+.1f}",
                    hand.get("biggest_mistake", ""),
                    hand.get("format", ""),
                ]
            for col, val in enumerate(items):
                self.table.setItem(row, col, QTableWidgetItem(val))

    def _select_row(self, row: int, _col: int) -> None:
        rows = self.table.property("rows") or []
        if row >= len(rows):
            return
        hand = rows[row]
        text = self.source_combo.currentText()

        if "Imported" in text:
            self._show_imported_hand(hand)
        elif "Played" in text:
            self._show_played_hand(hand)
        else:
            self._show_demo_hand(hand)

    def _practice_from_replay(self, hand: dict) -> None:
        """When user clicks 'Practice similar' on the replay, find 5 similar spots
        from the drill pool, register each in the adaptive engine as a mistake-
        priority drill, queue them via state.pending_spot_queue, and navigate to
        Spot Trainer (which will pop them one by one)."""
        from app.training.similar_spots import find_similar_spots

        self.state.selected_spot = hand
        try:
            engine = self.state.adaptive_engine()
            replay_id = hand.get("_replay_spot_id") or f"REPLAY-{hand.get('external_id', '?')}"
            # Register the original replay anchor first
            engine.record_attempt(
                spot_id=replay_id,
                correct=False,
                ev_loss=0.5,
                tags=("replay", hand.get("hero_position", ""), hand.get("pot_type", "")),
            )

            # Build a similar-spots drill pack from the seed pool
            from app.db.seed_data import generate_spot_drills
            similar = find_similar_spots(hand, generate_spot_drills(120), n=5)
            queue = []
            for spot in similar:
                sid = str(spot.get("id", ""))
                if not sid:
                    continue
                queue.append(sid)
                # Pre-register as a mistake so adaptive engine surfaces them first
                engine.record_attempt(
                    spot_id=sid,
                    correct=False,
                    ev_loss=0.4,
                    tags=("replay-similar", spot.get("position", ""), spot.get("pot_type", "")),
                )

            self.state.pending_spot_queue = queue
            if queue:
                # First spot drives the immediate jump; the rest pop after each answer
                self.state.pending_spot_id = queue[0]

            engine.save_to_db()

            self.coach_message.emit(
                f"Replay → Drill set: {hand.get('external_id', '?')} hand'inden {len(similar)} benzer spot "
                f"adaptive engine'e mistake-öncelikli olarak eklendi. Spot Practice Trainer'da sırayla "
                f"çözeceksin: {', '.join(queue) if queue else '(no matches)'}"
            )
        except Exception:
            pass
        self.navigate_requested.emit("Spot Practice Trainer")

    def _show_imported_hand(self, hand: dict) -> None:
        """Open the rich replay for a parsed PokerStars / CoinPoker hand."""
        self.state.selected_spot = hand
        self.replay.load_hand(hand)
        profit = float(hand.get("hero_profit_bb", 0) or 0)
        won = profit >= 0
        self.summary.setText(
            f"#{hand.get('external_id', '?')} | {hand.get('hero_cards', '??')} | "
            f"{hand.get('hero_position', '?')} | {'WON' if won else 'LOST'} {profit:+.1f}bb | "
            f"{hand.get('pot_type', '?')} pot {float(hand.get('pot_bb') or 0):.1f}bb"
        )
        self.summary.setObjectName("Green" if won else "Red")
        self.summary.style().unpolish(self.summary)
        self.summary.style().polish(self.summary)
        self.analysis_label.setText(
            "Replay yüklendi. Street tab'ları ile gez, 🤖 Full AI Review ile tüm el için yorum al."
        )

    def _show_played_hand(self, hand: dict) -> None:
        hero_cards = hand.get("hero_cards", "??")
        community = hand.get("community", "")
        profit = hand.get("hero_profit", 0)
        won = hand.get("hero_won", False)

        self.table_view.set_hand(hero_cards, community, hand.get("pot", 0))

        _clear_layout(self.hero_cards_row)
        for part in hero_cards.split():
            if len(part) >= 2:
                self.hero_cards_row.addWidget(CardView(part))

        color = "Green" if won else "Red"
        self.summary.setText(
            f"Hand #{hand.get('hand_id', '?')} | {hero_cards} | Board: {community} | "
            f"{'WON' if won else 'LOST'} {profit:+.1f}bb | Pot: {hand.get('pot', 0):.1f}bb | "
            f"Winner: {hand.get('winner_hand_name', '?')}"
        )
        self.summary.setObjectName(color)
        self.summary.style().unpolish(self.summary)
        self.summary.style().polish(self.summary)

        self.analysis_label.setText("Click 'AI Review' for detailed analysis of this hand.")

    def _show_demo_hand(self, hand: dict) -> None:
        self.state.selected_spot = hand.get("spot")
        self.table_view.set_hand(hand["hero_cards"], hand.get("board", ""), hand.get("spot", {}).get("pot_bb", 0))
        self.timeline.set_events(hand.get("timeline", []))

        _clear_layout(self.hero_cards_row)
        for part in hand["hero_cards"].split():
            if len(part) >= 2:
                self.hero_cards_row.addWidget(CardView(part))

        self.summary.setText(
            f"{hand['id']} vs {hand.get('villain', '?')} | Result {hand.get('result_bb', 0):+.1f}bb | "
            f"EV loss {hand.get('ev_loss', 0):.2f}bb | Biggest mistake: {hand.get('biggest_mistake', '-')}"
        )

    def _ai_review(self) -> None:
        rows = self.table.property("rows") or []
        if not rows:
            return
        current_row = self.table.currentRow()
        if current_row < 0 or current_row >= len(rows):
            return
        hand = rows[current_row]
        is_played = "Played" in self.source_combo.currentText()

        if is_played:
            review = analyze_played_hand(hand)
        else:
            review = explain_spot(hand.get("spot", hand))

        self.analysis_label.setText(review)
        self.coach_message.emit(review)

    def _leak_check(self) -> None:
        try:
            leaks = get_leak_analysis()
            parts = ["📊 Leak Analysis from your played hands:\n"]
            for leak in leaks:
                parts.append(f"  {'🔴' if leak['severity'] in ('Critical','High') else '🟡'} "
                           f"{leak['name']} ({leak['severity']})")
                parts.append(f"     {leak.get('detail', '')}")
                if leak.get("fix"):
                    parts.append(f"     Fix: {leak['fix']}")
            msg = "\n".join(parts)
            self.analysis_label.setText(msg)
            self.coach_message.emit(msg)
        except Exception:
            self.coach_message.emit("Leak analysis requires played hands in the database.")

    def _update_stats(self) -> None:
        hands = self._get_active_hands()
        is_played = "Played" in self.source_combo.currentText()

        if is_played and hands:
            total = len(hands)
            profit = sum(h.get("hero_profit", 0) for h in hands)
            wins = sum(1 for h in hands if h.get("hero_won"))
            biggest = max((abs(h.get("pot", 0)) for h in hands), default=0)
            _update_card(self.stat_hands, str(total), "from DB")
            _update_card(self.stat_profit, f"{profit:+.1f}bb", "total")
            _update_card(self.stat_winrate, f"{100*wins/total:.0f}%" if total else "—", "win rate")
            _update_card(self.stat_biggest, f"{biggest:.1f}bb", "biggest pot")
        else:
            _update_card(self.stat_hands, str(len(hands)), "demo hands")
            _update_card(self.stat_profit, "—", "demo mode")

    def _update_leaks(self) -> None:
        try:
            leaks = get_leak_analysis()
            parts = []
            for leak in leaks:
                severity_icon = "🔴" if leak["severity"] in ("Critical", "High") else "🟡" if leak["severity"] == "Medium" else "ℹ️"
                parts.append(f"{severity_icon} {leak['name']}: {leak.get('detail', '')} → {leak.get('fix', '')}")
            self.leak_content.setText("\n".join(parts) if parts else "No leaks detected.")
        except Exception:
            self.leak_content.setText("Play hands first to enable leak analysis.")


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w:
            w.deleteLater()


def _update_card(card: MetricCard, value: str, detail: str) -> None:
    for child in card.findChildren(QLabel):
        if child.objectName() == "MetricValue":
            child.setText(value)
        elif child.objectName() in ("Cyan", "Green", "Amber", "Red"):
            child.setText(detail)
