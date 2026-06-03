from __future__ import annotations

import sys
import os
import shutil
import tempfile
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QDir, QLibraryInfo, Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow, QStackedWidget, QVBoxLayout, QWidget

from app.ai.coach_engine import explain_spot
from app.ai.gemini_client import GeminiCoach
from app.core.app_state import AppState
from app.core.config import APP_NAME
from app.core.logging import configure_logging, log_swallowed
from app.core.rta_guard import RtaGuard
from app.db.repository import initialize_database
from app.ui.components.coach_panel import CoachPanel
from app.ui.components.multi_session_tabs import MultiSessionTabs
from app.ui.components.sidebar import SidebarNav
from app.ui.components.topbar import TopStatusBar
from app.ui.screens.ai_coach import AiCoachScreen
from app.ui.screens.combat_trainer import CombatTrainerScreen
from app.ui.screens.combo_trainer import ComboTrainerScreen
from app.ui.screens.dashboard import DashboardScreen
from app.ui.screens.fast_play_simulator import FastPlaySimulatorScreen
from app.ui.screens.hand_analyzer import HandAnalyzerScreen
from app.ui.screens.hand_history import HandHistoryScreen
from app.ui.screens.icm_trainer import IcmTrainerScreen
from app.ui.screens.knowledge_base import KnowledgeBaseScreen
from app.ui.screens.growth_lab import GrowthLabScreen
from app.ui.screens.leak_finder import LeakFinderScreen
from app.ui.screens.math_lab import MathLabScreen
from app.ui.screens.play_session import PlaySessionScreen
from app.ui.screens.postflop_trainer import PostflopTrainerScreen
from app.ui.screens.range_trainer import RangeTrainerScreen
from app.ui.screens.quiz_trainer import QuizTrainerScreen
from app.ui.screens.solver_sandbox import SolverSandboxScreen
from app.ui.screens.mtt_trainer import MTTTrainerScreen
from app.ui.screens.reports import ReportsScreen
from app.ui.screens.river_trainer import RiverTrainerScreen
from app.ui.screens.settings import SettingsScreen
from app.ui.screens.spot_trainer import SpotTrainerScreen
from app.ui.screens.opponent_profiles import OpponentProfilesScreen
from app.ui.screens.player_profile import PlayerProfileScreen
from app.ui.screens.strategy_playbook import StrategyPlaybookScreen
from app.ui.screens.study_library import StudyLibraryScreen
from app.ui.screens.study_planner import StudyPlannerScreen
from app.ui.screens.tournament_analysis import TournamentAnalysisScreen
from app.ui.screens.tournament_simulator import TournamentSimulatorScreen
from app.ui.theme.theme_manager import apply_dark_theme


def prepare_qt_platform_plugins() -> None:
    """Work around macOS environments where Qt cannot enumerate wheel plugin dirs."""
    if os.environ.get("QT_QPA_PLATFORM_PLUGIN_PATH"):
        return
    try:
        plugin_root = Path(QLibraryInfo.path(QLibraryInfo.PluginsPath))
        platform_dir = plugin_root / "platforms"
        visible = QDir(str(platform_dir)).entryList(["libq*.dylib", "q*.dll", "libq*.so"], QDir.Files)
        if visible or not platform_dir.exists():
            return
        temp_dir = Path(tempfile.gettempdir()) / "champion_poker_training_os_qt_platforms"
        temp_dir.mkdir(parents=True, exist_ok=True)
        for pattern in ("libq*.dylib", "q*.dll", "libq*.so"):
            for plugin in platform_dir.glob(pattern):
                target = temp_dir / plugin.name
                if target.exists():
                    target.unlink()
                shutil.copyfile(plugin, target)
                target.chmod(0o755)
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(temp_dir)
    except Exception:
        return


NAV_ITEMS = [
    "Dashboard",
    "Play Session",
    "My Profile",
    "GTO Study Library",
    "Spot Practice Trainer",
    "Hand History Analyzer",
    "Hand History Archive",
    "Fast Play Simulator",
    "Tournament Simulator",
    "Tournament Analysis",
    "ICM / PKO Trainer",
    "Preflop Range Trainer",
    "Range Quiz",
    "Solver Sandbox",
    "MTT Trainer",
    "Postflop Trainer",
    "River Decision Trainer",
    "Combo Trainer",
    "Math Lab",
    "Combat Trainer",
    "Leak Finder",
    "Growth & Edge Lab",
    "AI Poker Coach",
    "Opponent Profiles",
    "Knowledge Base",
    "Strategy Playbook",
    "Study Planner",
    "Reports",
    "Settings / Compliance Guard",
]

RESTRICTED_WHEN_LOCKED = {
    "Play Session",
    "GTO Study Library",
    "Spot Practice Trainer",
    "Hand History Analyzer",
    "Hand History Archive",
    "Fast Play Simulator",
    "Tournament Simulator",
    "ICM / PKO Trainer",
    "Preflop Range Trainer",
    "Range Quiz",
    "Solver Sandbox",
    "MTT Trainer",
    "Postflop Trainer",
    "River Decision Trainer",
    "Math Lab",
    "Combat Trainer",
    "AI Poker Coach",
}


def _load_dot_env() -> None:
    env_file = Path(__file__).resolve().parents[1] / ".env"
    if not env_file.exists():
        return
    for raw in env_file.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


class MainWindow(QMainWindow):
    BASELINE_W: int = 1440   # design-reference width — scale = actual_w / BASELINE_W

    def __init__(self):
        super().__init__()
        _load_dot_env()
        self.state = AppState()
        self.guard = RtaGuard(strict_mode=True)
        self.gemini = GeminiCoach()
        initialize_database()

        self.setWindowTitle(APP_NAME)
        self.resize(1440, 900)
        self.setMinimumSize(720, 520)   # allows resizing down to a compact floating layout
        root = QWidget()
        root.setObjectName("RootWindow")
        self.setCentralWidget(root)

        self.sidebar = SidebarNav(NAV_ITEMS)
        self.sidebar.navigation_requested.connect(self.navigate)
        self.topbar = TopStatusBar(self.state)
        self.topbar.experience_toggled.connect(self._on_experience_toggled)
        self.coach = CoachPanel()
        self.coach.ask_requested.connect(self.explain_selected_spot)
        self.coach.chat_requested.connect(self.chat_with_coach)
        self.stack = QStackedWidget()
        self.screens: dict[str, QWidget] = {}
        self._create_screens()

        bottom = QFrame()
        bottom.setObjectName("BottomBar")
        bottom_layout = QHBoxLayout(bottom)
        bottom_layout.setContentsMargins(16, 7, 16, 7)
        self.bottom_label = QLabel("Progress: 0 drills | Shortcuts: 1-4 action buttons, Ctrl+F search | Source confidence visible in each strategy result")
        self.bottom_label.setObjectName("Muted")
        bottom_layout.addWidget(self.bottom_label)
        bottom_layout.addStretch(1)

        main_col = QVBoxLayout()
        main_col.setContentsMargins(0, 0, 0, 0)
        main_col.setSpacing(0)
        main_col.addWidget(self.topbar)
        content_row = QHBoxLayout()
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(10)
        content_row.addWidget(self.stack, 1)
        content_row.addWidget(self.coach, 0)
        # CoachPanel manages its own width (expanded / collapsed) — don't override.
        main_col.addLayout(content_row, 1)
        main_col.addWidget(bottom)

        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.sidebar)
        # SidebarNav manages its own fixed width — don't force a value here.
        layout.addLayout(main_col, 1)

        # ── KEYBOARD SHORTCUTS ─────────────────────────────────────
        # Single source of truth lives in app/ui/components/shortcuts.py
        # (the same file feeds the ? cheat-sheet dialog).
        from app.ui.components.shortcuts import ShortcutsDialog
        QShortcut(QKeySequence("Ctrl+B"), self, activated=self.sidebar.toggle_collapsed)
        QShortcut(QKeySequence("Ctrl+J"), self, activated=self.coach.toggle_collapsed)
        # Cheat sheet — ? key (Shift+/) AND the footer button both trigger it
        QShortcut(QKeySequence("?"), self, activated=self._show_shortcuts)
        QShortcut(QKeySequence("Shift+?"), self, activated=self._show_shortcuts)
        self.sidebar.shortcuts_btn.clicked.connect(self._show_shortcuts)
        # Direct navigation — Ctrl+1..9 jump to the first 9 nav items
        for idx, name in enumerate(NAV_ITEMS[:9], start=1):
            QShortcut(
                QKeySequence(f"Ctrl+{idx}"), self,
                activated=lambda n=name: (
                    self.sidebar.set_active(n),
                    self.navigate(n),
                ),
            )

        # ── PROPORTIONAL SCALING ───────────────────────────────────────────
        # A 120 ms debounce timer avoids flooding setStyleSheet on every pixel
        # of a live resize drag.
        self._current_scale: float = 1.0
        self._scale_timer = QTimer(self)
        self._scale_timer.setSingleShot(True)
        self._scale_timer.setInterval(120)
        self._scale_timer.timeout.connect(self._apply_scale)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        new_scale = max(0.50, min(2.40, self.width() / self.BASELINE_W))
        if abs(new_scale - self._current_scale) > 0.02:
            self._current_scale = new_scale
            self._scale_timer.start()

    def _apply_scale(self) -> None:
        from app.ui.theme.theme_manager import generate_scaled_theme
        QApplication.instance().setStyleSheet(
            generate_scaled_theme(self._current_scale)
        )

    def _show_shortcuts(self) -> None:
        from app.ui.components.shortcuts import ShortcutsDialog
        dlg = ShortcutsDialog(self)
        dlg.exec()

        self.scan_compliance()
        self.navigate("Dashboard")
        self.scan_timer = QTimer(self)
        self.scan_timer.timeout.connect(self.scan_compliance)
        self.scan_timer.start(10_000)

    def _create_screens(self) -> None:
        # Screens wrapped in MultiSessionTabs so the user can keep N parallel
        # cash sessions / tournaments running at once.
        state = self.state
        multi_factories = {
            "Play Session": lambda: MultiSessionTabs(
                screen_factory=lambda: PlaySessionScreen(state),
                title_prefix="Session",
            ),
            "Tournament Simulator": lambda: MultiSessionTabs(
                screen_factory=lambda: TournamentSimulatorScreen(state),
                title_prefix="Tournament",
            ),
        }
        single_classes = {
            "Dashboard": DashboardScreen,
            "My Profile": PlayerProfileScreen,
            "GTO Study Library": StudyLibraryScreen,
            "Spot Practice Trainer": SpotTrainerScreen,
            "Hand History Analyzer": HandAnalyzerScreen,
            "Hand History Archive": HandHistoryScreen,
            "Fast Play Simulator": FastPlaySimulatorScreen,
            "Tournament Analysis": TournamentAnalysisScreen,
            "ICM / PKO Trainer": IcmTrainerScreen,
            "Preflop Range Trainer": RangeTrainerScreen,
            "Range Quiz": QuizTrainerScreen,
            "Solver Sandbox": SolverSandboxScreen,
            "MTT Trainer": MTTTrainerScreen,
            "Postflop Trainer": PostflopTrainerScreen,
            "River Decision Trainer": RiverTrainerScreen,
            "Combo Trainer": ComboTrainerScreen,
            "Math Lab": MathLabScreen,
            "Combat Trainer": CombatTrainerScreen,
            "Leak Finder": LeakFinderScreen,
            "Growth & Edge Lab": GrowthLabScreen,
            "AI Poker Coach": AiCoachScreen,
            "Opponent Profiles": OpponentProfilesScreen,
            "Knowledge Base": KnowledgeBaseScreen,
            "Strategy Playbook": StrategyPlaybookScreen,
            "Study Planner": StudyPlannerScreen,
            "Reports": ReportsScreen,
            "Settings / Compliance Guard": SettingsScreen,
        }
        # LAZY: ekranları sıfır-argümanlı factory'lerde tut; gerçekten
        # gezildiğinde kur. Hepsini açılışta kurmak ~4.8 sn sürüyordu →
        # talep üzerine kurmak boot'u anlık yapar (26 ekranın çoğu hiç
        # açılmayabilir).
        self._screen_factories: dict = dict(multi_factories)
        for nm, cls in single_classes.items():
            self._screen_factories[nm] = (lambda c=cls: c(self.state))
        # İlk görünen ekranı hemen kur ki açılışta içerik anında gelsin.
        self._ensure_screen(NAV_ITEMS[0])

    def _ensure_screen(self, name: str):
        """Ekranı (lazily) kurar, sinyalleri bağlar, stack'e ekler, cache'ler.
        Zaten kuruluysa cache'ten döner."""
        if name in self.screens:
            return self.screens[name]
        screen = self._screen_factories[name]()
        if hasattr(screen, "coach_message"):
            screen.coach_message.connect(self.coach.set_message)
        if hasattr(screen, "hand_completed"):
            screen.hand_completed.connect(self.on_hand_completed)
        if hasattr(screen, "navigate_requested"):
            screen.navigate_requested.connect(self.navigate)
        if hasattr(screen, "tournament_advice_requested"):
            screen.tournament_advice_requested.connect(self.on_tournament_advice)
        if hasattr(screen, "analysis_requested"):
            screen.analysis_requested.connect(
                lambda prompt, s=screen: self._gemini_for_screen(prompt, s)
            )
        # Yeni kurulan ekran mevcut Real Experience modunu almalı (lazy
        # olduğu için toggle anında var olmayabilir).
        if getattr(self.state, "real_experience", False) and \
                hasattr(screen, "apply_experience_mode"):
            try:
                screen.apply_experience_mode(True)
            except Exception as e:
                log_swallowed(f"ensure_screen.apply_experience_mode({name})", e)
        self.screens[name] = screen
        self.stack.addWidget(screen)
        return screen

    def _on_experience_toggled(self, real: bool) -> None:
        """Real Experience Mode değişti → tüm play/tournament ekranlarını tazele.

        GTO range panelinin görünürlüğü her ekranın ``apply_experience_mode``
        metodunda yönetilir (multi-tab çocukları dahil).
        """
        def _apply(widget) -> None:
            if hasattr(widget, "apply_experience_mode"):
                try:
                    widget.apply_experience_mode(real)
                except Exception:
                    pass
            if hasattr(widget, "screens"):   # MultiSessionTabs
                try:
                    for child in widget.screens():
                        _apply(child)
                except Exception:
                    pass
        for scr in self.screens.values():
            _apply(scr)
        self.coach.set_message(
            "🎭 REAL EXPERIENCE MODE açık — oyun sırasında GTO ipucu yok. "
            "Kararını ver, el bitince notlandırılmış GTO geri bildirimini gör."
            if real else
            "📚 Eğitim modu — GTO range bağlamı tekrar görünür."
        )

    def on_tournament_advice(self, briefing_prompt: str) -> None:
        """Forward tournament briefing prompt to Gemini and pipe response to coach."""
        if self.state.strategy_locked:
            return
        if self.gemini.available:
            self.coach.set_thinking()
            self.gemini.ask_async(briefing_prompt, self.coach.set_message)
        else:
            self.coach.set_message(
                "Yeni turnuva başladı. (Gemini API key girilince turnuva-spesifik "
                "AI tavsiyesi burada görünecek — Settings ekranından gir.)"
            )

    def _gemini_for_screen(self, prompt: str, screen) -> None:
        """Send a prompt to Gemini and pipe the result back to a specific screen."""
        if not self.gemini.available:
            if hasattr(screen, "show_analysis_result"):
                screen.show_analysis_result(
                    "Gemini API bağlantısı yok.\n"
                    "Settings ekranından GEMINI_API_KEY gir, ardından tekrar dene."
                )
            return
        self.coach.set_thinking()
        def _on_result(txt: str) -> None:
            if hasattr(screen, "show_analysis_result"):
                screen.show_analysis_result(txt)
            self.coach.set_message(txt)
        self.gemini.ask_async(prompt, _on_result)

    def navigate(self, name: str) -> None:
        if self.state.strategy_locked and name in RESTRICTED_WHEN_LOCKED:
            self.coach.set_message(
                "RTA Guard Strict Mode strategy ekranlarını kilitledi. "
                "Poker client kapanana kadar sadece rapor, plan ve compliance ekranları kullanılabilir."
            )
            name = "Settings / Compliance Guard"
        self.state.active_mode = name
        self.sidebar.set_active(name)
        self.topbar.set_mode(name)
        target = self._ensure_screen(name)
        # Leak Finder gerçek el verisinden beslenir → ekrana her girişte tazele
        if hasattr(target, "reload"):
            try:
                target.reload()
            except Exception as e:
                log_swallowed(f"navigate.reload({name})", e)
        self.stack.setCurrentWidget(target)
        self.bottom_label.setText(
            f"Progress: {self.state.completed_drills} drills | Accuracy {self.state.accuracy:.0f}% | "
            f"Session EV loss {self.state.ev_loss_total:.2f}bb | Source confidence shown per result"
        )

    def scan_compliance(self) -> None:
        status = self.guard.scan_processes()
        self.state.strategy_locked = status.locked
        self.topbar.compliance.set_status(status)
        if status.locked and self.state.active_mode in RESTRICTED_WHEN_LOCKED:
            self.navigate("Settings / Compliance Guard")

    def _analyse_last_hand(self, data: dict) -> None:
        s = data.get("session", {})
        prompt = (
            f"EL ANALİZİ:\n\n"
            f"Hero: {data['hero_position']} | El: {data['hero_cards']} | Stack: {data['hero_stack_bb']}bb\n"
            f"Board: {data['community']}\n"
            f"Pot: {data['pot']}bb | Yatırıldı: {data['hero_invested']}bb | "
            f"Sonuç: {'KAZANDI ✓' if data['hero_won'] else 'KAYBETTİ ✗'} ({data['hero_profit']:+.1f}bb)\n"
            f"Kazanan el: {data['winner_hand_name']} | Sokak: {data['streets_seen']}\n"
            f"Aksiyonlar: {data['actions']}\n"
            f"Session: {s.get('hands', 0)} el, {s.get('profit_bb', 0):+.1f}bb, "
            f"VPIP {s.get('vpip', 0):.0f}%, Win {s.get('win_rate', 0):.0f}%\n\n"
            "Bu ele özel 3 madde:\n"
            "1. Preflop/postflop kararları doğru mu?\n"
            "2. En kritik karar noktası?\n"
            "3. Bir sonraki benzer elde yapılacak somut değişiklik.\n"
            "Kısa tut (6-8 satır)."
        )
        self.coach.set_thinking()
        self.gemini.ask_async(prompt, self.coach.set_message)

    def _tournament_context_block(self) -> str:
        """Format live tournament context as a prompt prefix for Gemini.

        Empty string when no tournament is running — the coach falls back
        to cash-game advice automatically.
        """
        tc = self.state.tournament_context
        if not tc or not tc.get("active"):
            return ""
        bubble_tag = ""
        if tc.get("on_bubble"):
            bubble_tag = " · BUBBLE!"
        elif tc.get("bubble_distance", 99) <= 3:
            bubble_tag = f" · Bubble'a {tc['bubble_distance']} kişi"
        return (
            f"[TURNUVA BAĞLAMI]\n"
            f"Event: {tc['event']} · Struct: {tc['structure']} · Buy-in: ${tc['buyin']:.0f}\n"
            f"Level {tc['level']} · Blinds {tc['blinds']} (ante {tc['ante']}) · "
            f"Sonraki level: {tc['hands_until_next_level']} el\n"
            f"Field: {tc['players_remaining']}/{tc['field_size']} kaldı · "
            f"Hero {tc['hero_bb']}bb ({tc['stack_pressure']}) · Avg {tc['avg_bb']}bb · "
            f"Ödül havuzu: ${tc['prize_pool']:.0f} ({tc['payouts_paid']} ödüllü){bubble_tag}\n"
            f"TAVSİYE TURNUVA SPESİFİK OLSUN: ICM/stack depth/bubble pressure/blind level ışığında konuş.\n\n"
        )

    def _gto_context_block(self) -> str:
        """O anki canlı GTO advice'ı prompt prefix'i olarak biçimlendir.

        live_gto play/tournament ekranlarınca her hero kararında doldurulur.
        Boşsa "" döner.
        """
        g = getattr(self.state, "live_gto", None)
        if not g:
            return ""
        block = (
            f"[GTO CANLI ANALİZ — {g.get('tier','')}]\n"
            f"Spot: {g.get('scenario','')} · El: {g.get('hand','')} · "
            f"Stack: {g.get('stack_bb',0):.0f}bb\n"
            f"GTO frekansları → FOLD %{g.get('fold',0):.0f} · "
            f"CALL %{g.get('call',0):.0f} · RAISE %{g.get('raise',0):.0f} · "
            f"ALLIN %{g.get('allin',0):.0f}\n"
        )
        # ── SOMUT POT-MATEMATİĞİ — bu spotun gerçek sayıları ──
        # Koç teoriyi değil, BU spotun rakamlarını öğretsin.
        pot = float(g.get("pot_bb", 0) or 0)
        to_call = float(g.get("to_call_bb", 0) or 0)
        if to_call > 0 and pot > 0:
            pot_odds = to_call / (pot + to_call)          # call maliyeti / toplam pot
            be_equity = pot_odds                          # break-even equity = pot odds
            risk_reward = (pot + to_call) / to_call       # kaç-1 alıyorum
            block += (
                f"[BU SPOTUN POT-MATEMATİĞİ]\n"
                f"Pot: {pot:.1f}bb · Call maliyeti: {to_call:.1f}bb\n"
                f"Pot odds = {to_call:.1f} / ({pot:.1f}+{to_call:.1f}) = "
                f"%{pot_odds*100:.1f}  →  call için break-even equity %{be_equity*100:.1f}\n"
                f"Risk/ödül: {risk_reward:.1f}-e-1 (call başına {risk_reward:.1f}bb kazanma şansı)\n"
            )
            # Bet potun yüzdesi kadarsa MDF/alpha — rakip bet attıysa
            bet = to_call  # hero call'a bakıyorsa karşıdaki bet ≈ to_call
            mdf = pot / (pot + bet)
            alpha = bet / (pot + bet)
            block += (
                f"Rakip {bet:.1f}bb bet attı → MDF = {pot:.1f}/({pot:.1f}+{bet:.1f}) = "
                f"%{mdf*100:.0f} (bu kadar range'i savunmalıyım, daha fazla fold = "
                f"exploit edilirim) · Bluff'un break-even fold oranı (alpha) = %{alpha*100:.0f}\n"
            )
        plan = g.get("plan_note")
        if plan:
            block += (
                f"[ÇOK-SOKAKLI PLAN — 'izole karar değil, plan']\n{plan}\n"
                f"Bu planı kullanarak size/aksiyon gerekçesini açıkla: kaç sokak "
                f"value, hangi kartlar devam/scare.\n"
            )
        radv = g.get("range_adv_note")
        if radv:
            block += (
                f"[RANGE AVANTAJI — flop/turn 'kim bahis atmalı']\n{radv}\n"
                f"Bunu kullanarak c-bet frekansını/size'ını açıkla: range+nut "
                f"avantajı kimdeyse o daha sık/agresif bahis atar.\n"
            )
        combo = g.get("combo_note")
        if combo:
            block += (
                f"[COMBO SAYIMI — river bluff-catch (elit koç: 'tek el değil combo say')]\n"
                f"{combo}\n"
                f"Bu combo/blocker sayımını kullanarak villain'ın YETERİNCE bluff'u "
                f"olup olmadığını ve elinin onun value mi bluff mu blokladığını açıkla.\n"
            )
        sz = g.get("sizing")
        if sz:
            block += (
                f"BET-SIZING (GTO-standart): {sz.get('label','')} "
                f"(~{sz.get('rec_bb',0):.1f}bb). {sz.get('note','')}\n"
                f"Eğer hero raise/bet yapıyorsa boyutunu da değerlendir: "
                f"seçtiği size GTO-standarda ne kadar yakın, kaç bb EV bırakıyor? "
                f"Örn '5bb yerine 12bb daha iyi olurdu çünkü...' tarzı somut sizing leak ver.\n"
            )
        block += (
            f"[KOÇLUK TARZI — NASIL DÜŞÜNMELİ ÖĞRET]\n"
            f"Hero'ya optimal kararı doğrudan dayatma; ona NASIL düşüneceğini öğret. "
            f"Yukarıdaki BU spotun gerçek sayılarını kullanarak adım adım yürüt:\n"
            f"1) Elimin tahmini equity'si bu range'e karşı kabaca ne? "
            f"2) Pot odds'un istediği break-even equity'yi geçiyor muyum? "
            f"3) Geçmiyorsam fold; geçiyorsam call/raise — implied/fold equity ekle. "
            f"4) Karar mixed'se neden (indifference / dengeli range) açıkla.\n"
            f"Sonra hero'nun gerçek kararını GTO frekanslarıyla karşılaştır: "
            f"doğru mu, kaç-puan sapma, hangi matematik adımı kaçırmış? Kısa ve somut sayılarla.\n\n"
        )
        return block

    def explain_selected_spot(self) -> None:
        if self.state.strategy_locked:
            self.coach.set_message("RTA Guard locked coach strategy output while a poker client is detected.")
            return
        # Önce oynanan el varsa onu analiz et
        if self.state.last_hand:
            self._analyse_last_hand(self.state.last_hand)
            return
        # Turnuva çalışıyorsa ve seçili spot yoksa — turnuva durumu üzerinden tavsiye ver
        if self.state.tournament_context and self.state.tournament_context.get("active"):
            ctx = self._tournament_context_block()
            prompt = (
                ctx +
                "Hero şu an aksiyon beklemeden masa hakkında genel turnuva tavsiyesi istiyor. "
                "Konuş: bu spotta nasıl oynamalı (stack derinliği, ICM, blind structure), "
                "hangi rakipleri targetlemeli, nelerden kaçınmalı? Kısa (6-8 satır), maddeleştir."
            )
            if self.gemini.available:
                self.coach.set_thinking()
                self.gemini.ask_async(prompt, self.coach.set_message)
            else:
                self.coach.set_message(ctx + "(Offline mod — Gemini API key girilince tavsiye gelir)")
            return
        if not self.state.selected_spot:
            self.coach.set_message("Önce bir trainer spot seç veya bir el oyna, sonra buraya gel.")
            return
        spot = self.state.selected_spot
        baseline = explain_spot(spot)
        if self.gemini.available:
            prompt = (
                f"Şu poker spotunu analiz et:\n{baseline}\n\n"
                "Kısa analiz: range avantajı, matematik, en iyi aksiyon, 1 gelişim önerisi."
            )
            self.coach.set_thinking()
            self.gemini.ask_async(prompt, self.coach.set_message)
        else:
            self.coach.set_message(baseline)

    def on_hand_completed(self, data: dict) -> None:
        """Store hand data — Gemini analizi sadece kullanıcı sorduğunda yapılır."""
        self.state.last_hand = data
        # Sidebar mini profili tazele (yeni el DB'ye yazıldı)
        QTimer.singleShot(300, self.sidebar.refresh_profile)
        # Review isteği gelirse (Review Last butonu) analiz et
        if data.get("source") == "review_request" and not self.state.strategy_locked:
            self._analyse_last_hand(data)

    def chat_with_coach(self, prompt: str) -> None:
        if self.state.strategy_locked:
            self.coach.set_message("RTA Guard: canlı oyun sırasında strateji koçu devre dışı.")
            return
        # Inject tournament context FIRST (most important for ICM-aware advice)
        full_prompt = self._tournament_context_block()
        # Then live GTO advice for the current decision (if any)
        full_prompt += self._gto_context_block()
        # Then last-hand context if available
        if self.state.last_hand:
            h = self.state.last_hand
            full_prompt += (
                f"[Bağlam — son oynanan el: {h['hero_position']} | {h['hero_cards']} | "
                f"Board: {h['community']} | Pot: {h['pot']}bb | "
                f"Sonuç: {'Kazandı' if h['hero_won'] else 'Kaybetti'} ({h['hero_profit']:+.1f}bb)]\n\n"
            )
        full_prompt += prompt
        self.coach.set_thinking()
        self.gemini.ask_async(full_prompt, self.coach.set_message)


def main() -> int:
    configure_logging()
    prepare_qt_platform_plugins()
    app = QApplication(sys.argv)
    apply_dark_theme(app)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
