"""Render every key screen to PNG so we can eyeball the UI changes.

Outputs to docs/screens/*.png. Run from repo root:

    .venv/bin/python3 tests/render_ui_screens.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from app.main import prepare_qt_platform_plugins
prepare_qt_platform_plugins()

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QMainWindow

from app.core.app_state import AppState
from app.ui.components.field_picker import FieldPicker
from app.ui.components.multi_session_tabs import MultiSessionTabs
from app.ui.screens.play_session import PlaySessionScreen
from app.ui.screens.tournament_simulator import TournamentSimulatorScreen
from app.ui.theme.theme_manager import apply_dark_theme


OUT = Path(__file__).resolve().parents[1] / "docs" / "screens"
OUT.mkdir(parents=True, exist_ok=True)


def _render(widget, name: str, size=(1500, 900)) -> Path:
    w, h = size
    widget.resize(w, h)
    widget.show()
    QApplication.processEvents()
    QApplication.processEvents()
    pix = widget.grab()
    out = OUT / f"{name}.png"
    pix.save(str(out), "PNG")
    print(f"  → {out.name}  ({pix.width()}×{pix.height()})")
    return out


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    apply_dark_theme(app)
    state = AppState()

    print("Rendering UI screens to docs/screens/ …")

    # 1. Play Session — fresh setup (FieldPicker visible)
    host_play = MultiSessionTabs(
        screen_factory=lambda: PlaySessionScreen(state),
        title_prefix="Session",
    )
    # Add a second tab so the multi-tab strip is visible & non-trivial
    host_play.add_tab()
    _render(host_play, "01_play_session_setup_multitab")

    # 2. Tournament Simulator — setup with FieldPicker
    host_tour = MultiSessionTabs(
        screen_factory=lambda: TournamentSimulatorScreen(state),
        title_prefix="Tournament",
    )
    host_tour.add_tab()
    host_tour.add_tab()
    _render(host_tour, "02_tournament_setup_multitab")

    # 3. Tournament mid-play — start a tourney to show the meta bar + end button
    ts = host_tour.active_screen()
    if ts is None:
        ts = TournamentSimulatorScreen(state)
    ts.field_picker.set_composition(["TAG", "Fish", "Maniac", "Nit", "Reg"])
    ts._confirm_abort = lambda: True   # offscreen: modal onayını atla (hang guard)
    ts._start_tournament()
    QApplication.processEvents()
    QApplication.processEvents()
    _render(host_tour, "03_tournament_midplay_end_button")
    ts._end_and_restart()

    # 4. Standalone FieldPicker — closeup of the +/- picker
    fp = FieldPicker(default_bots=6)
    fp.set_composition(["TAG", "LAG", "Fish", "Calling Station", "Maniac", "Random (Karma)"])
    _render(fp, "04_field_picker_closeup", size=(700, 400))

    # 5. Play Session — actually started, to show the live table
    host_play2 = MultiSessionTabs(
        screen_factory=lambda: PlaySessionScreen(state),
        title_prefix="Session",
    )
    ps = host_play2.active_screen()
    ps.field_picker.set_composition(["TAG", "Fish", "Maniac"])
    ps._start()
    QApplication.processEvents()
    QApplication.processEvents()
    _render(host_play2, "05_play_session_live")

    print("\nDone — open the PNGs to inspect the UI.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
