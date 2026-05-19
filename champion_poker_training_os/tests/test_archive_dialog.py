"""TournamentArchiveDialog + SkillNetworkWidget regression tests."""
from __future__ import annotations

import os
import pytest


def _qt():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_archive_dialog_empty_state_boots():
    """No tournaments yet → dialog shows guidance, no crash."""
    app = _qt()
    from app.ui.components.tournament_archive_dialog import (
        TournamentArchiveDialog,
    )
    # Force an empty archive by monkeypatching load_archive
    import app.ui.components.tournament_archive_dialog as mod
    mod.load_archive = lambda: []
    dlg = TournamentArchiveDialog()
    assert dlg.windowTitle() == "Tournament archive"


def test_archive_dialog_with_records_emits_replay_drill():
    """Dialog renders a card per record and the buttons emit the signals."""
    app = _qt()
    from app.db.tournament_archive import TournamentRecord
    fake = TournamentRecord(
        id="t1",
        started_at="2026-05-01 12:00:00",
        ended_at="2026-05-01 13:30:00",
        tournament_name="Online Turbo Low Stakes",
        field_size=100,
        buyin=50.0,
        starting_stack=2000,
        skill_style="Human-Like",
        skill_level="Medium",
        finish_position=38,
        hands_played=120,
        decisions=85,
        correct_decisions=60,
        total_ev_loss=18.4,
        icm_punts=2,
        cashed=True,
        payout=130.0,
        notable_mistakes=[
            {"position": "BTN", "pot_type": "SRP", "hero_action": "fold",
             "ev_loss": 3.0, "logged_at": "2026-05-01", "id": "m1",
             "stack_bb": 40},
        ],
        hand_history=[],
    )
    import app.ui.components.tournament_archive_dialog as mod
    mod.load_archive = lambda: [fake]
    from app.ui.components.tournament_archive_dialog import (
        TournamentArchiveDialog,
    )
    dlg = TournamentArchiveDialog()
    replays: list = []
    drills: list = []
    dlg.hand_history_requested.connect(replays.append)
    dlg.drill_pack_requested.connect(drills.append)
    # Find the TournamentCard child + click its buttons
    from app.ui.components.tournament_archive_dialog import _TournamentCard
    cards = dlg.findChildren(_TournamentCard)
    assert len(cards) == 1
    cards[0].replay_requested.emit(fake)
    cards[0].drill_requested.emit(fake)
    assert replays == [fake]
    assert drills == [fake]


def test_skill_network_renders_with_demo_data():
    app = _qt()
    from app.training.mastery_model import demo_skill_tree
    from app.ui.components.skill_network import SkillNetworkWidget
    cats = demo_skill_tree().get_summary()["categories"]
    w = SkillNetworkWidget(cats)
    w.resize(360, 320)
    w.show()
    app.processEvents()
    # Grabbing the widget exercises paintEvent — must not crash.
    img = w.grab().toImage()
    assert img.width() > 0 and img.height() > 0
    # Click on the first node's centre should emit `clicked`
    received: list = []
    w.clicked.connect(received.append)
    from PySide6.QtCore import QPointF, QPoint, Qt
    from PySide6.QtGui import QMouseEvent
    # Mouse at the preflop layout point (x=0.18, y=0.18 inside 360x320 + 24 margin)
    margin = 24
    cx = int(margin + 0.18 * (360 - 2 * margin))
    cy = int(margin + 0.18 * (320 - 2 * margin))
    ev = QMouseEvent(
        QMouseEvent.MouseButtonPress,
        QPointF(cx, cy), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier,
    )
    w.mousePressEvent(ev)
    assert received == ["preflop"]
