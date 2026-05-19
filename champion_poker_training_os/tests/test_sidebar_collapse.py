"""SidebarNav collapse-state regression tests."""
from __future__ import annotations

import os
import pytest


def _qt():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _sidebar():
    app = _qt()
    from app.main import NAV_ITEMS
    from app.ui.components.sidebar import SidebarNav
    kbd = {NAV_ITEMS[i]: f"⌃{i + 1}" for i in range(9)}
    sb = SidebarNav(NAV_ITEMS, shortcuts=kbd)
    sb.show()
    app.processEvents()
    return sb, app


def test_default_expanded_232_wide():
    sb, app = _sidebar()
    assert not sb.is_collapsed()
    assert sb.width() == sb.EXPANDED_WIDTH == 232


def test_toggle_collapses_to_56_and_emits_signal():
    sb, app = _sidebar()
    received: list[bool] = []
    sb.collapse_toggled.connect(received.append)
    sb.toggle_collapsed()
    app.processEvents()
    assert sb.is_collapsed()
    assert sb.width() == sb.COLLAPSED_WIDTH == 56
    assert received == [True]
    # Round-trip back to expanded
    sb.toggle_collapsed()
    app.processEvents()
    assert not sb.is_collapsed()
    assert sb.width() == sb.EXPANDED_WIDTH
    assert received == [True, False]


def test_set_collapsed_no_op_when_same_state():
    sb, app = _sidebar()
    received: list[bool] = []
    sb.collapse_toggled.connect(received.append)
    sb.set_collapsed(False)   # already expanded
    assert received == []
    sb.set_collapsed(True)
    sb.set_collapsed(True)    # second call should not re-emit
    assert received == [True]
