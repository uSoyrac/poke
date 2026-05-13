"""Keyboard shortcuts for action buttons (1/2/3/4 → Fold/Call/Raise/Jam).

Verifies the new attach_action_shortcuts() helper actually wires QShortcut
to the matching button across action-name variations.
"""
from __future__ import annotations

import os
import pytest

PYSIDE6 = pytest.importorskip("PySide6", reason="PySide6 not installed")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_shortcut_keys_map_covers_all_4_digits():
    from app.ui.components.action_buttons import SHORTCUT_KEYS
    assert set(SHORTCUT_KEYS.keys()) == {"1", "2", "3", "4"}


def test_attach_shortcuts_creates_qshortcuts(qapp):
    from app.ui.components.action_buttons import (
        GtoActionButton, attach_action_shortcuts, action_display,
    )
    from PySide6.QtGui import QShortcut

    parent = QWidget()
    buttons = [
        GtoActionButton(action_display("fold"),  "fold"),
        GtoActionButton(action_display("call"),  "call"),
        GtoActionButton(action_display("raise"), "raise"),
        GtoActionButton(action_display("jam"),   "jam"),
    ]
    attach_action_shortcuts(parent, buttons)

    shortcuts = parent.findChildren(QShortcut)
    assert len(shortcuts) == 4, f"Expected 4 shortcuts, got {len(shortcuts)}"


def test_shortcut_for_3bet_action_resolves_to_raise(qapp):
    """'3bet' should be reachable via the '3' digit shortcut."""
    from app.ui.components.action_buttons import (
        GtoActionButton, attach_action_shortcuts,
    )
    from PySide6.QtGui import QShortcut

    parent = QWidget()
    buttons = [
        GtoActionButton("Fold", "fold"),
        GtoActionButton("Call", "call"),
        GtoActionButton("3-Bet 8bb", "3bet"),  # variant
        GtoActionButton("Jam", "jam"),
    ]
    attach_action_shortcuts(parent, buttons)

    shortcuts = parent.findChildren(QShortcut)
    # The '3' shortcut should still get attached because "3bet" is in the
    # raise/bet/3bet/4bet family
    assert any(s.key().toString() == "3" for s in shortcuts)


def test_shortcut_skipped_when_no_matching_button(qapp):
    """If a digit's action family has no button, no shortcut for that digit."""
    from app.ui.components.action_buttons import (
        GtoActionButton, attach_action_shortcuts,
    )
    from PySide6.QtGui import QShortcut

    parent = QWidget()
    buttons = [GtoActionButton("Fold", "fold")]  # only fold, no others
    attach_action_shortcuts(parent, buttons)

    shortcuts = parent.findChildren(QShortcut)
    # Only the '1' (fold) shortcut should exist
    assert len(shortcuts) == 1
    assert shortcuts[0].key().toString() == "1"
