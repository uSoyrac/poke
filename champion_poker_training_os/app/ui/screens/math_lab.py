from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.core.app_state import AppState
from app.db.seed_data import generate_math_drills

# ─── Category metadata ─────────────────────────────────────────────────────────
CATEGORIES = [
    {"id": "pot_odds",  "name": "Pot Odds",     "short": "PO",  "color": "#5ad17a"},
    {"id": "alpha",     "name": "Alpha",         "short": "AL",  "color": "#7abaff"},
    {"id": "mdf",       "name": "MDF",           "short": "MDF", "color": "#f4c842"},
    {"id": "ev",        "name": "Exp. Value",    "short": "EV",  "color": "#ff8c5a"},
    {"id": "icm",       "name": "ICM Math",      "short": "ICM", "color": "#c77dff"},
    {"id": "combos",    "name": "Combos",        "short": "CB",  "color": "#ff6b9d"},
    {"id": "push_fold", "name": "Push / Fold",   "short": "PF",  "color": "#4ecdc4"},
    {"id": "gto_freq",  "name": "GTO Freq",      "short": "GTO", "color": "#ffe66d"},
    {"id": "bayes",     "name": "Bayes Update",  "short": "BY",  "color": "#f4785a"},
]

_CAT_BY_ID = {c["id"]: c for c in CATEGORIES}

# Cevabı 0..1 oran olan (yüzde gösterilecek) kategoriler
_PERCENT_CATS = {"pot_odds", "alpha", "mdf", "icm", "push_fold", "gto_freq", "bayes"}

# "Nasıl düşün" — masada hesap yapmadan kestirme/sezgi ipuçları (öğretici)
_THINK_TIPS = {
    "pot_odds": ("Gereken equity = call / (pot + 2·call). KESTİRME eşikler: "
                 "yarım-pot bahis → ~%25, 2/3-pot → ~%29, pot bahis → ~%33. "
                 "Bu eşikleri ezberle, masada bölme yapma."),
    "alpha": ("Blöfün anında kâr etmesi için gereken fold = bahis / (bahis+pot). "
              "Yarım-pot blöf → %33, pot blöf → %50 fold yeterli."),
    "mdf": ("MDF = pot / (pot+bahis) = 1 − alpha. Yarım-pota karşı en az %67, "
            "pota karşı %50 savun — yoksa blöfe açık olursun."),
    "ev": ("EV = kazanma%×kazanç − kaybetme%×risk. Önce İŞARETE bak: + ise al. "
           "Başabaş eşiği = risk / (risk+kazanç)."),
    "icm": ("ICM'de chip-equity yetmez: pay-jump riski 'risk premium' ekler → "
            "call eşiğin yükselir. Bubble'da chipEV call'larını sıkılaştır."),
    "combos": ("Çift = C(4,2)=6 · suited = 4 · offsuit = 12 · toplam = 16. "
               "Board'da kart varsa kalanlardan C(n,2)."),
    "push_fold": ("Kısa stack: jam equity vs call-range. Fold-equity + showdown "
                  "equity. Nash chart eşiklerini pozisyona göre ezberle."),
    "gto_freq": ("Value:blöf oranı bahis boyutuna bağlı: yarım-pot → 2:1, "
                 "pot → 1:1. Dengeli ol ki rakip seni sömüremesin."),
    "bayes": ("Yeni aksiyon geldikçe range'i güncelle: P(el|aksiyon) ∝ "
              "P(aksiyon|el)×P(el). Agresif hat → güçlü range'e kayar."),
}

_DIFF_ACTIVE = (
    "QPushButton { background: #5ad17a; color: #0a0c0a; border: none; "
    "padding: 3px 10px; font-size: 11px; font-weight: 700; }"
)
_DIFF_INACTIVE = (
    "QPushButton { background: #1a1e19; color: #5a5e54; border: 1px solid #23271f; "
    "padding: 3px 10px; font-size: 11px; }"
    "QPushButton:hover { background: #23271f; color: #f4f5ee; }"
)
_CAT_ACTIVE = (
    "QPushButton { background: #131613; color: #5ad17a; border-left: 3px solid #5ad17a; "
    "text-align: left; padding: 8px 14px; font-size: 12px; font-weight: 600; }"
)
_CAT_INACTIVE = (
    "QPushButton { background: transparent; color: #898d80; border: none; "
    "border-left: 3px solid transparent; text-align: left; padding: 8px 14px; font-size: 12px; }"
    "QPushButton:hover { background: #131613; color: #f4f5ee; }"
)


class MathLabScreen(QWidget):
    coach_message = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self._all_drills = generate_math_drills()  # all 135+ drills
        self._category = CATEGORIES[0]["id"]
        self._difficulty = "all"
        self._drills: list[dict] = []
        self._idx = 0
        # progress[cat_id][drill_id] = True/False/None
        self._progress: dict[str, dict[str, bool | None]] = {
            c["id"]: {} for c in CATEGORIES
        }
        self._session_correct = 0
        self._session_answered = 0

        self._build_ui()
        self._select_category(CATEGORIES[0]["id"])

    # ─── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header bar ──────────────────────────────────────────────────────
        header = QFrame()
        header.setObjectName("TopBar")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(20, 10, 20, 10)
        h_layout.setSpacing(12)

        title = QLabel("Math Lab")
        title.setObjectName("Title")
        h_layout.addWidget(title)

        h_layout.addStretch(1)

        # Difficulty filter
        diff_lbl = QLabel("DIFFICULTY:")
        diff_lbl.setObjectName("Muted")
        h_layout.addWidget(diff_lbl)

        self._diff_btns: dict[str, QPushButton] = {}
        for key, label in [("all", "All"), ("easy", "Easy"), ("medium", "Medium"), ("hard", "Hard")]:
            btn = QPushButton(label)
            btn.setFixedHeight(26)
            btn.clicked.connect(lambda checked=False, k=key: self._set_difficulty(k))
            self._diff_btns[key] = btn
            h_layout.addWidget(btn)

        # Session score
        self._score_lbl = QLabel("0 / 0")
        self._score_lbl.setObjectName("Mono")
        self._score_lbl.setStyleSheet("font-size: 12px; color: #5ad17a;")
        h_layout.addWidget(self._score_lbl)

        root.addWidget(header)

        # ── Body: left sidebar + right panel ────────────────────────────────
        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        root.addWidget(body, 1)

        # ── LEFT — category sidebar ──────────────────────────────────────────
        left = QFrame()
        left.setObjectName("Sidebar")
        left.setFixedWidth(200)
        left.setStyleSheet("QFrame#Sidebar { background: #0f1210; border-right: 1px solid #23271f; }")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 16, 0, 16)
        left_layout.setSpacing(2)

        cat_hdr = QLabel("CATEGORIES")
        cat_hdr.setObjectName("NavGroupLabel")
        cat_hdr.setContentsMargins(16, 0, 0, 8)
        left_layout.addWidget(cat_hdr)

        self._cat_btns: dict[str, QPushButton] = {}
        self._cat_progress_lbls: dict[str, QLabel] = {}

        for cat in CATEGORIES:
            row = QWidget()
            row_l = QVBoxLayout(row)
            row_l.setContentsMargins(0, 0, 0, 0)
            row_l.setSpacing(0)

            btn = QPushButton(cat["name"])
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.clicked.connect(lambda checked=False, cid=cat["id"]: self._select_category(cid))
            self._cat_btns[cat["id"]] = btn
            row_l.addWidget(btn)

            prog = QLabel("0 / 0")
            prog.setStyleSheet(
                f"color: {cat['color']}; font-family: 'JetBrains Mono',monospace; "
                "font-size: 9px; padding-left: 20px; padding-bottom: 2px;"
            )
            self._cat_progress_lbls[cat["id"]] = prog
            row_l.addWidget(prog)

            left_layout.addWidget(row)

        left_layout.addStretch(1)

        # Total pill
        self._total_lbl = QLabel("— drills")
        self._total_lbl.setObjectName("Muted")
        self._total_lbl.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(self._total_lbl)

        body_layout.addWidget(left)

        # ── RIGHT — stacked drill panel / table panel ────────────────────────
        self._right_stack = QStackedWidget()
        body_layout.addWidget(self._right_stack, 1)

        self._drill_page = self._build_drill_page()
        self._table_page = self._build_table_page()
        self._right_stack.addWidget(self._drill_page)
        self._right_stack.addWidget(self._table_page)

        self._update_diff_buttons()

    def _build_drill_page(self) -> QWidget:
        page = QScrollArea()
        page.setWidgetResizable(True)
        page.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        page.setWidget(inner)

        layout = QVBoxLayout(inner)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)

        # Drill ID + category + difficulty badges
        self._drill_header = QLabel()
        self._drill_header.setObjectName("Mono")
        self._drill_header.setStyleSheet("font-size: 10px; color: #5a5e54;")
        layout.addWidget(self._drill_header)

        # Prompt
        prompt_frame = QFrame()
        prompt_frame.setObjectName("DataPanel")
        prompt_layout = QVBoxLayout(prompt_frame)
        prompt_layout.setContentsMargins(20, 18, 20, 18)
        self._prompt_lbl = QLabel()
        self._prompt_lbl.setObjectName("SectionTitle")
        self._prompt_lbl.setWordWrap(True)
        self._prompt_lbl.setStyleSheet("font-size: 16px; line-height: 1.5;")
        prompt_layout.addWidget(self._prompt_lbl)
        layout.addWidget(prompt_frame)

        # Çoktan seçmeli cevap şıkları (kafadan ondalık hesaplamak yerine SEÇ)
        choices_label = QLabel("Doğru cevabı seç:")
        choices_label.setObjectName("Muted")
        choices_label.setStyleSheet("font-size: 12px; padding: 4px 0;")
        layout.addWidget(choices_label)
        self._choices_grid = QGridLayout()
        self._choices_grid.setSpacing(8)
        layout.addLayout(self._choices_grid)

        # Feedback
        self._feedback_lbl = QLabel("Bir şık seç — doğru/yanlış anında, neden'iyle açıklanır.")
        self._feedback_lbl.setObjectName("Muted")
        self._feedback_lbl.setWordWrap(True)
        self._feedback_lbl.setStyleSheet("font-size: 13px; padding: 8px 0;")
        layout.addWidget(self._feedback_lbl)

        # "Nasıl düşün" — kategori sezgi ipucu (cevaptan sonra)
        self._think_lbl = QLabel()
        self._think_lbl.setWordWrap(True)
        self._think_lbl.setStyleSheet(
            "color: #7abaff; font-family: 'JetBrains Mono',monospace; font-size: 11px; "
            "padding: 6px 10px; background: #131613; border-left: 2px solid #7abaff;")
        self._think_lbl.hide()
        layout.addWidget(self._think_lbl)

        # Formula hint (shown after answering)
        self._formula_lbl = QLabel()
        self._formula_lbl.setObjectName("Mono")
        self._formula_lbl.setWordWrap(True)
        self._formula_lbl.setStyleSheet(
            "color: #5ad17a; font-family: 'JetBrains Mono',monospace; "
            "font-size: 11px; padding: 6px 10px; background: #131613; border-left: 2px solid #5ad17a;"
        )
        self._formula_lbl.hide()
        layout.addWidget(self._formula_lbl)

        # Navigation buttons
        nav_row = QHBoxLayout()
        self._prev_btn = QPushButton("← Prev")
        self._prev_btn.clicked.connect(self._go_prev)
        self._next_btn = QPushButton("Next →")
        self._next_btn.setObjectName("PrimaryButton")
        self._next_btn.clicked.connect(self._go_next)
        self._skip_btn = QPushButton("Skip")
        self._skip_btn.clicked.connect(self._go_next)
        self._table_btn = QPushButton("Play at Table  🎲")
        self._table_btn.setStyleSheet(
            "QPushButton { background: #1a2940; color: #7abaff; border: 1px solid #2a4060; "
            "padding: 6px 14px; }"
            "QPushButton:hover { background: #2a3d55; }"
        )
        self._table_btn.clicked.connect(self._show_table_mode)
        nav_row.addWidget(self._prev_btn)
        nav_row.addWidget(self._skip_btn)
        nav_row.addStretch(1)
        nav_row.addWidget(self._table_btn)
        nav_row.addWidget(self._next_btn)
        layout.addLayout(nav_row)

        # Drill grid (dots showing status of all drills in category)
        grid_frame = QFrame()
        grid_frame.setObjectName("Card")
        grid_frame_layout = QVBoxLayout(grid_frame)
        grid_frame_layout.setContentsMargins(16, 12, 16, 12)
        grid_hdr = QLabel("DRILL STATUS")
        grid_hdr.setObjectName("TLabel")
        grid_frame_layout.addWidget(grid_hdr)
        self._dot_grid = QGridLayout()
        self._dot_grid.setSpacing(4)
        grid_frame_layout.addLayout(self._dot_grid)
        layout.addWidget(grid_frame)

        layout.addStretch(1)
        return page

    def _build_table_page(self) -> QWidget:
        """Poker-table view for context-rich drill solving."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Back bar
        back_bar = QFrame()
        back_bar.setObjectName("TopBar")
        back_l = QHBoxLayout(back_bar)
        back_l.setContentsMargins(16, 8, 16, 8)
        back_btn = QPushButton("← Back to Drill")
        back_btn.clicked.connect(self._hide_table_mode)
        back_l.addWidget(back_btn)
        back_l.addStretch(1)
        self._table_mode_lbl = QLabel("Play at Table")
        self._table_mode_lbl.setObjectName("SectionTitle")
        back_l.addWidget(self._table_mode_lbl)
        layout.addWidget(back_bar)

        # Table visual (green felt area)
        table_area = QFrame()
        table_area.setObjectName("FeltTable")
        table_area.setFixedHeight(280)
        table_layout = QVBoxLayout(table_area)
        table_layout.setAlignment(Qt.AlignCenter)

        self._table_pot_lbl = QLabel()
        self._table_pot_lbl.setObjectName("SectionTitle")
        self._table_pot_lbl.setAlignment(Qt.AlignCenter)
        self._table_pot_lbl.setStyleSheet("font-size: 26px; color: #f4f5ee;")

        self._table_bet_lbl = QLabel()
        self._table_bet_lbl.setAlignment(Qt.AlignCenter)
        self._table_bet_lbl.setStyleSheet("font-size: 16px; color: #f4c842;")

        self._table_ctx_lbl = QLabel()
        self._table_ctx_lbl.setAlignment(Qt.AlignCenter)
        self._table_ctx_lbl.setObjectName("Muted")
        self._table_ctx_lbl.setWordWrap(True)

        # Board + hero kartları (somut spot + doğru cevapta board run-out)
        cards_holder = QFrame()
        self._table_cards_row = QHBoxLayout(cards_holder)
        self._table_cards_row.setAlignment(Qt.AlignCenter)
        self._table_cards_row.setSpacing(4)

        table_layout.addStretch(1)
        table_layout.addWidget(self._table_pot_lbl)
        table_layout.addWidget(cards_holder)
        table_layout.addWidget(self._table_bet_lbl)
        table_layout.addWidget(self._table_ctx_lbl)
        table_layout.addStretch(1)
        layout.addWidget(table_area)

        # Drill panel below the table
        drill_frame = QFrame()
        drill_frame.setObjectName("DataPanel")
        drill_l = QVBoxLayout(drill_frame)
        drill_l.setContentsMargins(24, 16, 24, 16)
        drill_l.setSpacing(12)

        self._table_prompt_lbl = QLabel()
        self._table_prompt_lbl.setObjectName("SectionTitle")
        self._table_prompt_lbl.setWordWrap(True)
        self._table_prompt_lbl.setStyleSheet("font-size: 14px;")
        drill_l.addWidget(self._table_prompt_lbl)

        ans_row = QHBoxLayout()
        self._table_answer_spin = QDoubleSpinBox()
        self._table_answer_spin.setDecimals(3)
        self._table_answer_spin.setRange(-9999, 9999)
        self._table_answer_spin.setSingleStep(0.01)
        self._table_answer_spin.setFixedHeight(38)
        self._table_submit_btn = QPushButton("Check")
        self._table_submit_btn.setObjectName("PrimaryButton")
        self._table_submit_btn.setFixedHeight(38)
        self._table_submit_btn.clicked.connect(self._check_table_answer)
        ans_row.addWidget(self._table_answer_spin, 1)
        ans_row.addWidget(self._table_submit_btn)
        drill_l.addLayout(ans_row)

        self._table_feedback_lbl = QLabel("Enter your answer.")
        self._table_feedback_lbl.setObjectName("Muted")
        self._table_feedback_lbl.setWordWrap(True)
        drill_l.addWidget(self._table_feedback_lbl)

        layout.addWidget(drill_frame, 1)
        return page

    # ─── State management ───────────────────────────────────────────────────────

    def _select_category(self, cat_id: str) -> None:
        self._category = cat_id
        # Update category button styles
        for cid, btn in self._cat_btns.items():
            btn.setStyleSheet(_CAT_ACTIVE if cid == cat_id else _CAT_INACTIVE)
        # Filter drills
        self._apply_filter()
        self._right_stack.setCurrentIndex(0)

    def _set_difficulty(self, diff: str) -> None:
        self._difficulty = diff
        self._update_diff_buttons()
        self._apply_filter()

    def _apply_filter(self) -> None:
        cat_drills = [d for d in self._all_drills if d["category"] == self._category]
        if self._difficulty != "all":
            cat_drills = [d for d in cat_drills if d.get("difficulty") == self._difficulty]
        self._drills = cat_drills
        self._idx = 0
        self._load_drill()
        self._rebuild_dot_grid()
        self._update_cat_progress()
        total = sum(len([d for d in self._all_drills if d["category"] == c["id"]]) for c in CATEGORIES)
        self._total_lbl.setText(f"{total} drills total")

    def _update_diff_buttons(self) -> None:
        for key, btn in self._diff_btns.items():
            btn.setStyleSheet(_DIFF_ACTIVE if key == self._difficulty else _DIFF_INACTIVE)

    def _update_cat_progress(self) -> None:
        for cat in CATEGORIES:
            cat_drills = [d for d in self._all_drills if d["category"] == cat["id"]]
            prog = self._progress[cat["id"]]
            correct = sum(1 for d in cat_drills if prog.get(d["id"]) is True)
            answered = sum(1 for d in cat_drills if prog.get(d["id"]) is not None)
            total = len(cat_drills)
            self._cat_progress_lbls[cat["id"]].setText(
                f"{correct} correct · {answered}/{total}"
            )
        # Update session score label
        if self._session_answered > 0:
            pct = int(100 * self._session_correct / self._session_answered)
            self._score_lbl.setText(f"{self._session_correct}/{self._session_answered}  {pct}%")
        else:
            self._score_lbl.setText("0 / 0")

    def _rebuild_dot_grid(self) -> None:
        """Rebuild the drill status dot grid for current category."""
        # Clear existing dots
        while self._dot_grid.count():
            item = self._dot_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        prog = self._progress[self._category]
        cols = 15
        for i, drill in enumerate(self._drills):
            status = prog.get(drill["id"])
            if status is True:
                color = "#5ad17a"   # correct
                text = "✓"
            elif status is False:
                color = "#ff5a5a"   # wrong
                text = "✗"
            elif i == self._idx:
                color = "#f4c842"   # current
                text = "→"
            else:
                color = "#23271f"   # not done
                text = "·"
            dot = QLabel(text)
            dot.setAlignment(Qt.AlignCenter)
            dot.setFixedSize(20, 20)
            dot.setStyleSheet(
                f"color: {color}; font-size: 12px; "
                f"background: {'#1a1e19' if i == self._idx else 'transparent'};"
            )
            dot.setToolTip(f"{drill['id']} · {drill.get('difficulty','')}")
            self._dot_grid.addWidget(dot, i // cols, i % cols)

    # ─── Drill display ──────────────────────────────────────────────────────────

    def _load_drill(self) -> None:
        if not self._drills:
            self._prompt_lbl.setText("No drills match the selected filter.")
            self._drill_header.setText("")
            self._feedback_lbl.setText("")
            self._formula_lbl.hide()
            return

        drill = self._drills[self._idx % len(self._drills)]
        cat = _CAT_BY_ID.get(drill["category"], {})
        cat_name = cat.get("name", drill["category"])
        cat_color = cat.get("color", "#5ad17a")
        diff = drill.get("difficulty", "")

        self._drill_header.setText(
            f"{drill['id']}  ·  "
            f"<span style='color:{cat_color}'>{cat_name.upper()}</span>  ·  "
            f"{diff.upper()}"
        )
        self._drill_header.setTextFormat(Qt.RichText)
        self._prompt_lbl.setText(drill["prompt"])
        self._feedback_lbl.setObjectName("Muted")
        self._feedback_lbl.setStyleSheet("font-size: 13px; padding: 8px 0; color: #898d80;")
        self._feedback_lbl.setText("Doğru cevabı seç — anında geri bildirim + neden.")
        self._formula_lbl.hide()
        self._think_lbl.hide()
        self._render_choices(drill)
        self._rebuild_dot_grid()

        # Sync table page too
        self._table_prompt_lbl.setText(drill["prompt"])
        self._table_answer_spin.setValue(0.0)
        self._table_feedback_lbl.setText("Enter your answer.")
        self._table_feedback_lbl.setStyleSheet("color: #898d80;")
        self._update_table_visual(drill)

    @staticmethod
    def _deterministic_cards(drill: dict) -> tuple[list[str], list[str]]:
        """Drill id'den deterministik 5 board + 2 hero kartı (çakışmasız)."""
        import random as _r
        ranks, suits = "AKQJT98765432", "shdc"
        deck = [rk + su for rk in ranks for su in suits]
        rng = _r.Random(hash(drill.get("id", "")) & 0xFFFFFFFF)
        rng.shuffle(deck)
        return deck[:5], deck[5:7]

    def _render_table_cards(self, board: list[str], hero: list[str],
                            revealed: int) -> None:
        """Board'un ilk `revealed` kartı açık, kalanı kapalı; hero açık."""
        from app.ui.components.card_view import CardView
        while self._table_cards_row.count():
            it = self._table_cards_row.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        for i, c in enumerate(board):
            self._table_cards_row.addWidget(CardView(c, face_down=(i >= revealed), size="sm"))
        spacer = QLabel("  ")
        self._table_cards_row.addWidget(spacer)
        for c in hero:
            self._table_cards_row.addWidget(CardView(c, face_down=False, size="sm"))

    def _update_table_visual(self, drill: dict) -> None:
        """Update the poker table visual context from the drill data."""
        prompt = drill.get("prompt", "")
        cat = drill["category"]

        # Somut spot kartları: facing-bet (PO/MDF/alpha) → flop göster (3),
        # doğru cevapta turn+river run-out. Preflop kategoriler → board yok.
        board, hero = self._deterministic_cards(drill)
        self._table_board, self._table_hero = board, hero
        preflop_cats = {"combos", "push_fold"}
        revealed = 0 if cat in preflop_cats else 3
        self._table_revealed = revealed
        self._render_table_cards(board, hero, revealed)

        # Try to extract pot and bet from common drill patterns
        import re
        pot_m = re.search(r"[Pp]ot\s+(\d+(?:\.\d+)?)bb", prompt)
        bet_m = re.search(r"bets?\s+(\d+(?:\.\d+)?)bb", prompt)
        call_m = re.search(r"call\s+(\d+(?:\.\d+)?)bb", prompt)
        stack_m = re.search(r"(\d+(?:\.\d+)?)bb\s+stack", prompt)

        pot = float(pot_m.group(1)) if pot_m else None
        bet = float(bet_m.group(1)) if bet_m else (float(call_m.group(1)) if call_m else None)
        stack = float(stack_m.group(1)) if stack_m else None

        if pot and bet:
            self._table_pot_lbl.setText(f"POT  {pot}bb")
            self._table_bet_lbl.setText(f"Villain bets  {bet}bb  →  Call = {bet}bb")
            self._table_ctx_lbl.setText(f"Category: {_CAT_BY_ID.get(cat,{}).get('name', cat)}")
        elif pot:
            self._table_pot_lbl.setText(f"POT  {pot}bb")
            self._table_bet_lbl.setText("")
            self._table_ctx_lbl.setText(f"Category: {_CAT_BY_ID.get(cat,{}).get('name', cat)}")
        elif stack:
            self._table_pot_lbl.setText(f"STACK  {stack}bb")
            self._table_bet_lbl.setText("Push / Fold Decision")
            self._table_ctx_lbl.setText("Evaluate push equity vs calling range.")
        else:
            self._table_pot_lbl.setText(drill["id"])
            self._table_bet_lbl.setText("")
            self._table_ctx_lbl.setText(_CAT_BY_ID.get(cat, {}).get("name", cat))

        self._table_mode_lbl.setText(f"Play at Table · {_CAT_BY_ID.get(cat,{}).get('name', cat)}")

    # ─── Answer checking ────────────────────────────────────────────────────────

    # ─── Çoktan seçmeli cevap ────────────────────────────────────────────────────
    @staticmethod
    def _fmt_choice(val: float, cat: str) -> str:
        if cat == "combos":
            return f"{val:.0f}"
        if cat == "ev":
            return f"{val:+.1f} bb"
        return f"%{val * 100:.0f}"          # oran → yüzde

    @staticmethod
    def _answer_choices(drill: dict) -> list:
        """Doğru cevap + 3 makul çeldirici (deterministik, kategoriye göre)."""
        import random as _r
        ans = float(drill["answer"]); cat = drill["category"]
        rng = _r.Random(hash(drill["id"]) & 0xFFFFFFFF)
        cands: list = []
        if cat in _PERCENT_CATS:
            for m in (ans * 1.5, ans * 0.6, 1 - ans, ans + 0.12, ans - 0.10):
                v = round(max(0.0, min(0.99, m)), 3)
                if abs(v - ans) > 0.02:
                    cands.append(v)
        elif cat == "ev":
            for m in (-ans, ans * 0.4, ans + 3.0, ans - 3.0, ans + 1.5):
                v = round(m, 1)
                if abs(v - ans) > 0.4:
                    cands.append(v)
        else:  # combos vb. tamsayı
            for m in (ans * 2, ans * 0.5, ans + (4 if ans < 20 else ans * 0.3),
                      max(0, ans - 3)):
                v = round(m)
                if v != round(ans) and v >= 0:
                    cands.append(v)
        # benzersiz çeldiriciler
        seen, uniq = set(), []
        for v in cands:
            if v not in seen:
                seen.add(v); uniq.append(v)
        rng.shuffle(uniq)
        opts = [round(ans, 3)] + uniq[:3]
        i = 0
        while len(opts) < 4:                # garanti 4 şık
            opts.append(round(ans + (0.07 + 0.05 * i), 3)); i += 1
        rng.shuffle(opts)
        return opts

    def _render_choices(self, drill: dict) -> None:
        while self._choices_grid.count():
            it = self._choices_grid.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self._answered = False
        cat = drill["category"]
        for i, val in enumerate(self._answer_choices(drill)):
            btn = QPushButton(self._fmt_choice(val, cat))
            btn.setObjectName("")
            btn.setFixedHeight(48)
            btn.setStyleSheet(
                "QPushButton { background:#1a1e19; color:#f4f5ee; border:1px solid #2a3140; "
                "font-family:'JetBrains Mono',monospace; font-size:18px; font-weight:700; "
                "border-radius:6px; } QPushButton:hover { background:#23271f; }")
            btn.clicked.connect(lambda _=False, v=val, b=btn: self._choose(v, b))
            self._choices_grid.addWidget(btn, i // 2, i % 2)

    def _choose(self, val: float, btn) -> None:
        if getattr(self, "_answered", False):
            return
        self._answered = True
        drill = self._drills[self._idx % len(self._drills)]
        ok = abs(val - float(drill["answer"])) <= float(drill.get("tolerance", 0.02))
        self._record(drill["id"], ok)
        cat = drill["category"]
        correct_txt = self._fmt_choice(float(drill["answer"]), cat)
        # Şıkları renklendir: doğru yeşil, yanlış seçim kırmızı
        for i in range(self._choices_grid.count()):
            b = self._choices_grid.itemAt(i).widget()
            if not b:
                continue
            b.setEnabled(False)
            if b.text() == correct_txt:
                b.setStyleSheet("QPushButton { background:#12331f; color:#5ad17a; "
                                "border:2px solid #5ad17a; border-radius:6px; font-size:18px; "
                                "font-weight:700; font-family:'JetBrains Mono',monospace; }")
            elif b is btn:
                b.setStyleSheet("QPushButton { background:#3a1414; color:#ff6b6b; "
                                "border:2px solid #ff6b6b; border-radius:6px; font-size:18px; "
                                "font-weight:700; font-family:'JetBrains Mono',monospace; }")
        if ok:
            self._feedback_lbl.setStyleSheet("font-size:14px; padding:8px 0; color:#5ad17a; font-weight:700;")
            self._feedback_lbl.setText(f"✓  Doğru! Cevap: {correct_txt}")
        else:
            self._feedback_lbl.setStyleSheet("font-size:14px; padding:8px 0; color:#ff6b6b; font-weight:700;")
            self._feedback_lbl.setText(f"✗  Doğru cevap: {correct_txt}")
        self._formula_lbl.setText(f"Formül: {drill.get('formula','—')}\n{drill.get('explanation','')}")
        self._formula_lbl.show()
        self._think_lbl.setText("💡 Nasıl düşün: " + _THINK_TIPS.get(cat, ""))
        self._think_lbl.setVisible(bool(_THINK_TIPS.get(cat)))
        self._update_cat_progress()

    def _check_table_answer(self) -> None:
        if not self._drills:
            return
        drill = self._drills[self._idx % len(self._drills)]
        value = self._table_answer_spin.value()
        ok = abs(value - drill["answer"]) <= drill["tolerance"]
        self._record(drill["id"], ok)

        if ok:
            self._table_feedback_lbl.setStyleSheet("color: #5ad17a; font-weight: 600;")
            self._table_feedback_lbl.setText(f"✓  Correct! Answer: {drill['answer']}")
            # Board run-out: doğru cevapta kalan sokakları (turn/river) aç
            if (getattr(self, "_table_board", None)
                    and getattr(self, "_table_revealed", 0) and self._table_revealed < 5):
                self._table_revealed = 5
                self._render_table_cards(self._table_board, self._table_hero, 5)
        else:
            self._table_feedback_lbl.setStyleSheet("color: #ff5a5a;")
            self._table_feedback_lbl.setText(
                f"✗  Answer: {drill['answer']} — {drill['explanation']}"
            )
        self._update_cat_progress()

    def _record(self, drill_id: str, ok: bool) -> None:
        prev = self._progress[self._category].get(drill_id)
        if prev is None:
            # First attempt — count toward session stats
            self._session_answered += 1
            if ok:
                self._session_correct += 1
        self._progress[self._category][drill_id] = ok

    # ─── Navigation ─────────────────────────────────────────────────────────────

    def _go_next(self) -> None:
        if self._drills:
            self._idx = (self._idx + 1) % len(self._drills)
            self._load_drill()

    def _go_prev(self) -> None:
        if self._drills:
            self._idx = (self._idx - 1) % len(self._drills)
            self._load_drill()

    def _show_table_mode(self) -> None:
        if self._drills:
            drill = self._drills[self._idx % len(self._drills)]
            self._update_table_visual(drill)
            self._table_prompt_lbl.setText(drill["prompt"])
            self._table_answer_spin.setValue(0.0)
            self._table_feedback_lbl.setText("Enter your answer.")
            self._table_feedback_lbl.setStyleSheet("color: #898d80;")
        self._right_stack.setCurrentIndex(1)

    def _hide_table_mode(self) -> None:
        self._right_stack.setCurrentIndex(0)
