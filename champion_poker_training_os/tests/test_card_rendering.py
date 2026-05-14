"""Card-rendering audit: headlessly paints every card-bearing widget and
verifies non-blank pixels in card areas. Run with:

    QT_QPA_PLATFORM=offscreen python -m tests.test_card_rendering
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QPainter
from PySide6.QtCore import QSize


def _render(widget) -> QImage:
    widget.resize(widget.sizeHint().expandedTo(QSize(900, 600)))
    widget.show()
    # Let layout settle
    app = QApplication.instance()
    if app is not None:
        app.processEvents()
        app.processEvents()
    img = QImage(widget.size(), QImage.Format_ARGB32)
    img.fill(0xFF000000)
    widget.render(img)
    return img


def _nonblack_ratio(img: QImage) -> float:
    nb = 0
    total = 0
    for y in range(0, img.height(), 4):
        for x in range(0, img.width(), 4):
            c = img.pixel(x, y)
            r, g, b = (c >> 16) & 0xFF, (c >> 8) & 0xFF, c & 0xFF
            if r + g + b > 60:
                nb += 1
            total += 1
    return nb / max(1, total)


def _has_white_card(img: QImage) -> bool:
    """Scan for any pure-white card body — clear visual signal cards are rendering."""
    for y in range(0, img.height(), 2):
        for x in range(0, img.width(), 2):
            c = img.pixel(x, y)
            r, g, b = (c >> 16) & 0xFF, (c >> 8) & 0xFF, c & 0xFF
            if r > 240 and g > 240 and b > 240:
                return True
    return False


def test_card_view():
    from app.ui.components.card_view import CardView
    fails = []
    for txt in ["As", "Kh", "Td", "2c", "Ah", "Qs"]:
        cv = CardView(txt)
        img = _render(cv)
        if not _has_white_card(img):
            fails.append(f"CardView('{txt}') has no visible white body")
    # Face-down
    cv = CardView("", face_down=True)
    img = _render(cv)
    if _nonblack_ratio(img) < 0.05:
        fails.append("CardView face-down rendered blank")
    return fails


def test_oval_table_hero_cards():
    from app.ui.components.oval_table import OvalTable
    fails = []
    # Spots covering different hero positions
    spots = [
        {"position": "BTN", "hero_cards": "AsKh", "stack_bb": 100, "pot_bb": 1.5},
        {"position": "BB",  "hero_cards": "9c9d", "stack_bb": 40,  "pot_bb": 3.5,
         "name": "BB DEF vs BTN OPEN", "pot_type": "SRP"},
        {"position": "UTG", "hero_cards": "QhJh", "stack_bb": 25,  "pot_bb": 1.5},
        {"position": "SB",  "hero_cards": "TsTd", "stack_bb": 30,  "pot_bb": 6.0,
         "name": "SB 3-BET vs BTN", "pot_type": "3BP"},
    ]
    for spot in spots:
        ot = OvalTable()
        ot.populate_from_spot(spot)
        ot.resize(900, 500)
        img = _render(ot)
        if not _has_white_card(img):
            fails.append(f"OvalTable hero cards missing for {spot['position']} {spot['hero_cards']}")
    return fails


def test_oval_table_community():
    from app.ui.components.oval_table import OvalTable
    fails = []
    ot = OvalTable()
    ot.populate_from_spot({"position": "BTN", "hero_cards": "AsKh", "stack_bb": 100, "pot_bb": 5})
    ot.set_community_cards(["Ah", "Kd", "7s"])
    ot.resize(900, 500)
    img = _render(ot)
    if not _has_white_card(img):
        fails.append("OvalTable community flop not rendered as white cards")
    return fails


def test_spot_trainer():
    from app.core.app_state import AppState
    from app.ui.screens.spot_trainer import SpotTrainerScreen
    fails = []
    state = AppState()
    sc = SpotTrainerScreen(state)
    sc.resize(1400, 900)
    img = _render(sc)
    if not _has_white_card(img):
        fails.append("SpotTrainer renders no visible cards")
    return fails


def test_welcome():
    from app.core.app_state import AppState
    from app.ui.screens.welcome import WelcomeScreen
    fails = []
    w = WelcomeScreen(AppState())
    w.resize(1400, 900)
    img = _render(w)
    if _nonblack_ratio(img) < 0.2:
        fails.append(f"Welcome too dark (nonblack ratio {_nonblack_ratio(img):.2%})")
    # Check that BigCard frames are present
    from PySide6.QtWidgets import QFrame
    cards = w.findChildren(QFrame, "BigCard")
    if len(cards) != 3:
        fails.append(f"Welcome expected 3 BigCard, got {len(cards)}")
    for c in cards:
        if not c.isVisible() or c.size().width() < 100 or c.size().height() < 100:
            fails.append(f"Welcome BigCard not visible/sized: {c.size().width()}x{c.size().height()}")
    return fails


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    all_fails = []
    for name, fn in [
        ("CardView",          test_card_view),
        ("OvalTable hero",    test_oval_table_hero_cards),
        ("OvalTable comm",    test_oval_table_community),
        ("Welcome screen",    test_welcome),
        ("Spot trainer",      test_spot_trainer),
    ]:
        try:
            fails = fn()
        except Exception as e:
            fails = [f"{name} crashed: {e!r}"]
        status = "✓ PASS" if not fails else "✗ FAIL"
        print(f"{status}  {name}")
        for f in fails:
            print(f"    – {f}")
        all_fails.extend(fails)
    print()
    if all_fails:
        print(f"❌ {len(all_fails)} issues found")
        return 1
    print("✅ All card rendering checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
