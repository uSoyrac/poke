from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.ai.coach_engine import analyze_played_hand, explain_spot
from app.core.app_state import AppState
from app.db.repository import (get_session_history, get_player_stats,
                               get_leak_analysis, save_played_hand)
from app.parsers.pokerstars_parser import parse_pokerstars
from app.db.seed_data import generate_hands
from app.ui.components.card_view import CardView
from app.ui.components.hand_timeline import HandTimeline
from app.ui.components.metric_card import MetricCard
from app.ui.components.poker_table import LivePokerTable
from app.ui.components.spot_table import render_hand_on_table, render_spot_on_table


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
        self.source_combo.addItems(["Played Hands (DB)", "Demo Hands"])
        self.source_combo.currentTextChanged.connect(self._source_changed)
        header.addWidget(self.source_combo)

        self.filter = QComboBox()
        self.filter.addItems(["All", "Wins Only", "Losses Only", "Big Pots (>20bb)", "Showdowns"])
        self.filter.currentTextChanged.connect(self._populate_table)
        header.addWidget(self.filter)

        refresh_btn = QPushButton("🔄 Refresh from DB")
        refresh_btn.clicked.connect(self._load_played_hands)
        header.addWidget(refresh_btn)

        import_btn = QPushButton("📥 Import HH")
        import_btn.setToolTip("Gerçek PokerStars el-geçmişini yapıştır/yükle → "
                              "DB'ye kaydet → leak analizi + drill")
        import_btn.clicked.connect(self._open_import_dialog)
        header.addWidget(import_btn)
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
        self.table_view = LivePokerTable()
        top.addWidget(self.table_view, 2)

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

    def _load_played_hands(self) -> None:
        """Load played hands from SQLite — sadece OYNANAN eller (insta-fold değil)."""
        try:
            # Preflop'ta direkt fold etmediğin gerçek eller (flop+ veya VPIP)
            self.played_hands = get_session_history(200, voluntary_only=True)
        except Exception:
            self.played_hands = []
        self._populate_table()
        self._update_stats()
        self._update_leaks()

    def _import_raw(self, raw: str, hero: "str | None") -> int:
        """PokerStars metnini parse et → played_hands DB'ye kaydet. Kayıt sayısı.
        Değerler dolar-ölçekli + big_blind saklanır → okuma /bb ile bb verir (D97)."""
        if not raw or not raw.strip():
            return 0
        n = 0
        for h in parse_pokerstars(raw, hero_name=hero):
            try:
                save_played_hand({
                    "hand_id": f"PS-{h['hand_id']}",
                    "hero_cards": h.get("hero_cards", ""),
                    "community": h.get("community", ""),
                    "pot": h.get("pot", 0),
                    "hero_invested": h.get("hero_invested", 0),
                    "hero_profit": h.get("hero_profit", 0),
                    "hero_won": h.get("hero_won", False),
                    "winner_hand_name": "",
                    "streets_seen": h.get("streets_seen", 0),
                    "big_blind": h.get("big_blind", 1.0),
                    "game_type": h.get("game_type", "cash"),
                    "hero_vpip": h.get("hero_vpip"),
                    "hero_pfr": h.get("hero_pfr"),
                    "hero_3bet_opp": h.get("hero_3bet_opp"),
                    "hero_3bet": h.get("hero_3bet"),
                    "hero_postflop_aggr": h.get("hero_postflop_aggr"),
                    "hero_postflop_passive": h.get("hero_postflop_passive"),
                })
                n += 1
            except Exception:
                pass
        return n

    def _open_import_dialog(self) -> None:
        """Gerçek el-geçmişi import: yapıştır/dosya → parse → DB → analiz."""
        dlg = QDialog(self)
        dlg.setWindowTitle("El-Geçmişi Import — PokerStars")
        dlg.setMinimumWidth(580)
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel("PokerStars el-geçmişini yapıştır (veya dosyadan yükle):"))
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Hero adı (boş = otomatik):"))
        name_edit = QLineEdit()
        name_edit.setPlaceholderText("örn. HeroGuy")
        name_row.addWidget(name_edit)
        v.addLayout(name_row)
        txt = QPlainTextEdit()
        txt.setPlaceholderText("PokerStars Hand #... metnini buraya yapıştır")
        txt.setMinimumHeight(260)
        v.addWidget(txt)

        def _load_file():
            path, _ = QFileDialog.getOpenFileName(
                dlg, "El-geçmişi dosyası", "", "Text (*.txt);;All files (*)")
            if path:
                try:
                    with open(path, encoding="utf-8", errors="ignore") as f:
                        txt.setPlainText(f.read())
                except Exception:
                    pass

        load_btn = QPushButton("📂 Dosyadan yükle")
        load_btn.clicked.connect(_load_file)
        v.addWidget(load_btn)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        v.addWidget(bb)
        if dlg.exec() != QDialog.Accepted:
            return
        n = self._import_raw(txt.toPlainText(), name_edit.text().strip() or None)
        self.summary.setText(
            f"✓ {n} el import edildi (PokerStars) → DB. Leak analizi hazır."
            if n else "⚠ Geçerli PokerStars eli bulunamadı.")
        if n:
            self.source_combo.setCurrentText("Played Hands (DB)")
            self._load_played_hands()

    def _source_changed(self) -> None:
        self._populate_table()
        self._update_stats()

    def _get_active_hands(self) -> list[dict]:
        if "Demo" in self.source_combo.currentText():
            return self.demo_hands
        return self.played_hands

    def _populate_table(self) -> None:
        hands = self._get_active_hands()
        filt = self.filter.currentText() if hasattr(self, "filter") else "All"
        is_played = "Played" in self.source_combo.currentText()

        if is_played:
            if "Wins" in filt:
                hands = [h for h in hands if h.get("hero_won")]
            elif "Losses" in filt:
                hands = [h for h in hands if not h.get("hero_won")]
            elif "Big" in filt:
                hands = [h for h in hands if abs(h.get("pot", 0)) > 20]
            elif "Showdown" in filt:
                hands = [h for h in hands if h.get("streets_seen", 0) >= 4]
            # Legacy kurtarılamaz çip-ölçekli satırları gizle (big_blind bilinmiyor,
            # pot/bb absürt). bb-normalize edilebilen cash + yeni turnuva eller kalır.
            hands = [h for h in hands
                     if (float(h.get("pot", 0) or 0)
                         / max(float(h.get("big_blind") or 1.0), 1e-9)) <= 2000]

        self.table.setRowCount(len(hands))
        self.table.setProperty("rows", hands)

        for row, hand in enumerate(hands):
            if is_played:
                _bb_div = max(float(hand.get("big_blind") or 1.0), 1e-9)
                items = [
                    str(hand.get("hand_id", row + 1)),
                    hand.get("hero_cards", "??"),
                    hand.get("community", ""),
                    f"{(hand.get('pot', 0) or 0) / _bb_div:.1f}",
                    f"{(hand.get('hero_profit', 0) or 0) / _bb_div:+.1f}",
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
        is_played = "Played" in self.source_combo.currentText()

        if is_played:
            self._show_played_hand(hand)
        else:
            self._show_demo_hand(hand)

    def _show_played_hand(self, hand: dict) -> None:
        hero_cards = hand.get("hero_cards", "??")
        community = hand.get("community", "")
        _bb_div = max(float(hand.get("big_blind") or 1.0), 1e-9)
        profit = (hand.get("hero_profit", 0) or 0) / _bb_div   # bb'ye çevir
        pot_bb = (hand.get("pot", 0) or 0) / _bb_div
        won = hand.get("hero_won", False)

        render_hand_on_table(self.table_view, hero_cards, community, pot_bb)

        _clear_layout(self.hero_cards_row)
        for part in hero_cards.split():
            if len(part) >= 2:
                self.hero_cards_row.addWidget(CardView(part))

        color = "Green" if won else "Red"
        self.summary.setText(
            f"Hand #{hand.get('hand_id', '?')} | {hero_cards} | Board: {community} | "
            f"{'WON' if won else 'LOST'} {profit:+.1f}bb | Pot: {pot_bb:.1f}bb | "
            f"Winner: {hand.get('winner_hand_name', '?')}"
        )
        self.summary.setObjectName(color)
        self.summary.style().unpolish(self.summary)
        self.summary.style().polish(self.summary)

        self.analysis_label.setText("Click 'AI Review' for detailed analysis of this hand.")

    def _show_demo_hand(self, hand: dict) -> None:
        self.state.selected_spot = hand.get("spot")
        spot = hand.get("spot")
        if spot:
            render_spot_on_table(self.table_view, spot)
        else:
            render_hand_on_table(self.table_view, hand["hero_cards"], hand.get("board", ""), hand.get("spot", {}).get("pot_bb", 0))
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
            # Toplam profit/pot bb-NORMALİZE + YALNIZ cash elleri. Turnuva elleri
            # çip-ölçekli + eski kayıtlarda per-hand bb kurtarılamadığı için
            # (big_blind=1.0 default) bb'ye çevrilemez → cash istatistiğine
            # katılmaz. Eskiden hepsi karışıp 'PROFIT 1385167bb' saçmalığı çıkıyordu.
            def _bb(h, field):
                return float(h.get(field, 0) or 0) / max(float(h.get("big_blind") or 1.0), 1e-9)
            cash = [h for h in hands if (h.get("game_type") or "cash") == "cash"]
            cn = len(cash)
            profit = sum(_bb(h, "hero_profit") for h in cash)
            wins = sum(1 for h in cash if h.get("hero_won"))
            biggest = max((abs(_bb(h, "pot")) for h in cash), default=0)
            _update_card(self.stat_hands, str(total), f"{cn} cash · {total-cn} turnuva")
            _update_card(self.stat_profit, f"{profit:+.1f}bb", f"{cn} cash eli")
            _update_card(self.stat_winrate, f"{100*wins/cn:.0f}%" if cn else "—", "cash win rate")
            _update_card(self.stat_biggest, f"{biggest:.1f}bb", "biggest cash pot")
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
