"""HandHistoryImportDialog regression tests.

Guards the topbar IMPORT flow: paste a PokerStars hand, the dialog parses
+ persists it, ``result_summary`` reflects what happened.
"""
from __future__ import annotations

import os
import pytest


def _ensure_qt() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


_FAKE_HAND = """\
PokerStars Hand #1234567890: Tournament #5555, $10+$1 USD Hold'em No Limit \
- Level I (10/20) - 2025/05/19 12:34:56 ET
Table 'Test 1' 9-max Seat #5 is the button
Seat 1: HeroSeat (1500 in chips)
Seat 5: VillainSeat (1500 in chips)
HeroSeat: posts small blind 10
VillainSeat: posts big blind 20
*** HOLE CARDS ***
Dealt to HeroSeat [Ah Kh]
HeroSeat: raises 40 to 60
VillainSeat: folds
Uncalled bet (40) returned to HeroSeat
HeroSeat collected 40 from pot
HeroSeat: doesn't show hand
*** SUMMARY ***
Total pot 40 | Rake 0
Seat 1: HeroSeat (small blind) collected (40)
Seat 5: VillainSeat (big blind) folded before Flop
"""


def test_dialog_boots_clean():
    _ensure_qt()
    pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from app.ui.components.import_dialog import HandHistoryImportDialog
    dlg = HandHistoryImportDialog()
    assert dlg.windowTitle() == "Import hand history"
    assert dlg.result_summary["saved"] == 0


def test_paste_text_parses_and_saves(tmp_path, monkeypatch):
    """Paste a PokerStars hand → import button parses + persists."""
    _ensure_qt()
    pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])

    # Use a sandbox DB so we don't pollute the user's data
    db_path = tmp_path / "test_import.sqlite"
    from app.db import repository
    # repository uses module-level DB_PATH (a pathlib.Path); redirect it.
    monkeypatch.setattr(repository, "DB_PATH", db_path)
    repository.initialize_database()

    from app.ui.components.import_dialog import HandHistoryImportDialog
    dlg = HandHistoryImportDialog()
    dlg._paste_box.setPlainText(_FAKE_HAND)
    dlg._do_import()
    # Dialog should report success
    assert dlg.result_summary["saved"] >= 1
    # And the persisted count matches
    assert repository.imported_hands_count() >= 1


def test_empty_input_shows_status_no_save():
    _ensure_qt()
    pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from app.ui.components.import_dialog import HandHistoryImportDialog
    dlg = HandHistoryImportDialog()
    dlg._do_import()
    # With no files and no paste text the dialog must not 'save 0' silently.
    assert "Pick file" in dlg.status.text() or "paste" in dlg.status.text().lower()
    assert dlg.result_summary["saved"] == 0
