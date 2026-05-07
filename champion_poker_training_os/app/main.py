from __future__ import annotations

import sys
import os
import shutil
import tempfile
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QDir, QLibraryInfo, Qt, QTimer
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow, QStackedWidget, QVBoxLayout, QWidget

from app.ai.coach_engine import explain_spot
from app.core.app_state import AppState
from app.core.config import APP_NAME
from app.core.logging import configure_logging
from app.core.rta_guard import RtaGuard
from app.db.repository import initialize_database
from app.ui.components.coach_panel import CoachPanel
from app.ui.components.sidebar import SidebarNav
from app.ui.components.topbar import TopStatusBar
from app.ui.screens.ai_coach import AiCoachScreen
from app.ui.screens.combat_trainer import CombatTrainerScreen
from app.ui.screens.dashboard import DashboardScreen
from app.ui.screens.fast_play_simulator import FastPlaySimulatorScreen
from app.ui.screens.hand_analyzer import HandAnalyzerScreen
from app.ui.screens.icm_trainer import IcmTrainerScreen
from app.ui.screens.knowledge_base import KnowledgeBaseScreen
from app.ui.screens.leak_finder import LeakFinderScreen
from app.ui.screens.math_lab import MathLabScreen
from app.ui.screens.play_session import PlaySessionScreen
from app.ui.screens.postflop_trainer import PostflopTrainerScreen
from app.ui.screens.range_trainer import RangeTrainerScreen
from app.ui.screens.reports import ReportsScreen
from app.ui.screens.river_trainer import RiverTrainerScreen
from app.ui.screens.settings import SettingsScreen
from app.ui.screens.spot_trainer import SpotTrainerScreen
from app.ui.screens.study_library import StudyLibraryScreen
from app.ui.screens.study_planner import StudyPlannerScreen
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
    "GTO Study Library",
    "Spot Practice Trainer",
    "Hand History Analyzer",
    "Fast Play Simulator",
    "Tournament Simulator",
    "ICM / PKO Trainer",
    "Preflop Range Trainer",
    "Postflop Trainer",
    "River Decision Trainer",
    "Math Lab",
    "Combat Trainer",
    "Leak Finder",
    "AI Poker Coach",
    "Knowledge Base",
    "Study Planner",
    "Reports",
    "Settings / Compliance Guard",
]

RESTRICTED_WHEN_LOCKED = {
    "Play Session",
    "GTO Study Library",
    "Spot Practice Trainer",
    "Hand History Analyzer",
    "Fast Play Simulator",
    "Tournament Simulator",
    "ICM / PKO Trainer",
    "Preflop Range Trainer",
    "Postflop Trainer",
    "River Decision Trainer",
    "Math Lab",
    "Combat Trainer",
    "AI Poker Coach",
}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.state = AppState()
        self.guard = RtaGuard(strict_mode=True)
        initialize_database()

        self.setWindowTitle(APP_NAME)
        self.resize(1500, 920)
        root = QWidget()
        root.setObjectName("RootWindow")
        self.setCentralWidget(root)

        self.sidebar = SidebarNav(NAV_ITEMS)
        self.sidebar.navigation_requested.connect(self.navigate)
        self.topbar = TopStatusBar(self.state)
        self.coach = CoachPanel()
        self.coach.ask_requested.connect(self.explain_selected_spot)
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
        self.coach.setMinimumWidth(330)
        self.coach.setMaximumWidth(390)
        main_col.addLayout(content_row, 1)
        main_col.addWidget(bottom)

        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.sidebar)
        self.sidebar.setFixedWidth(250)
        layout.addLayout(main_col, 1)

        self.scan_compliance()
        self.navigate("Dashboard")
        self.scan_timer = QTimer(self)
        self.scan_timer.timeout.connect(self.scan_compliance)
        self.scan_timer.start(10_000)

    def _create_screens(self) -> None:
        factories = {
            "Dashboard": DashboardScreen,
            "Play Session": PlaySessionScreen,
            "GTO Study Library": StudyLibraryScreen,
            "Spot Practice Trainer": SpotTrainerScreen,
            "Hand History Analyzer": HandAnalyzerScreen,
            "Fast Play Simulator": FastPlaySimulatorScreen,
            "Tournament Simulator": TournamentSimulatorScreen,
            "ICM / PKO Trainer": IcmTrainerScreen,
            "Preflop Range Trainer": RangeTrainerScreen,
            "Postflop Trainer": PostflopTrainerScreen,
            "River Decision Trainer": RiverTrainerScreen,
            "Math Lab": MathLabScreen,
            "Combat Trainer": CombatTrainerScreen,
            "Leak Finder": LeakFinderScreen,
            "AI Poker Coach": AiCoachScreen,
            "Knowledge Base": KnowledgeBaseScreen,
            "Study Planner": StudyPlannerScreen,
            "Reports": ReportsScreen,
            "Settings / Compliance Guard": SettingsScreen,
        }
        for name in NAV_ITEMS:
            screen = factories[name](self.state)
            if hasattr(screen, "coach_message"):
                screen.coach_message.connect(self.coach.set_message)
            if hasattr(screen, "navigate_requested"):
                screen.navigate_requested.connect(self.navigate)
            self.screens[name] = screen
            self.stack.addWidget(screen)

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
        self.stack.setCurrentWidget(self.screens[name])
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

    def explain_selected_spot(self) -> None:
        if self.state.strategy_locked:
            self.coach.set_message("RTA Guard locked coach strategy output while a poker client is detected.")
            return
        if self.state.selected_spot:
            self.coach.set_message(explain_spot(self.state.selected_spot))
        else:
            self.coach.set_message("Önce bir trainer, analyzer veya study spot seç; sonra nedenini birlikte parçalayalım.")


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
