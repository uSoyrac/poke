"""Render the oval table to a PNG so a human can VISUALLY verify cards.

Run:
    QT_QPA_PLATFORM=offscreen .venv/bin/python -m tests.screenshot_oval
Output:
    /tmp/oval_table_proof.png
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout
from PySide6.QtGui import QImage
from PySide6.QtCore import QSize

from app.main import prepare_qt_platform_plugins
prepare_qt_platform_plugins()


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    from app.ui.components.oval_table import OvalTable

    spot = {
        "position": "BTN",
        "hero_cards": "As9c",
        "stack_bb": 100,
        "pot_bb": 1.5,
        "street": "preflop",
        "pot_type": "SRP",
    }
    ot = OvalTable()
    ot.populate_from_spot(spot)
    ot.resize(1200, 600)
    ot.show()
    app.processEvents(); app.processEvents()

    img = QImage(ot.size(), QImage.Format_ARGB32)
    img.fill(0xFF0A0E14)
    ot.render(img)
    out = "/tmp/oval_table_proof.png"
    img.save(out)
    print(f"Saved: {out}  ({img.width()}x{img.height()})")

    # Sample colors at suspected card positions (centre-bottom area)
    cx = img.width() // 2
    cy = int(img.height() * 0.72)
    print(f"\nSample colours around hero-cards anchor ({cx},{cy}):")
    for dx in range(-50, 51, 20):
        for dy in range(-25, 26, 25):
            c = img.pixel(cx + dx, cy + dy)
            r, g, b = (c >> 16) & 0xFF, (c >> 8) & 0xFF, c & 0xFF
            tag = "WHITE-CARD" if (r > 240 and g > 240 and b > 240) else \
                  "RED"   if (r > 200 and g < 80 and b < 80) else \
                  "BLUE"  if (b > 200 and r < 80 and g < 80) else \
                  "GREEN" if (g > 150 and r < 80 and b < 80) else \
                  ""
            print(f"  ({cx+dx:4d},{cy+dy:4d}) #{r:02X}{g:02X}{b:02X}  {tag}")


if __name__ == "__main__":
    main()
