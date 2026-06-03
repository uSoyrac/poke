"""MTT Trainer QSS kapsam guard'ı (nav audit G).

Push/fold kartının stylesheet'i çıplak 'QFrame{...}' kullanırsa stil gömülü
LivePokerTable'ın _Seat QFrame'lerine sızar → seat'ler dev kutu olup üst üste
biner. Selektör objectName ile sınırlı (QFrame#PfCard) kalmalı.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from app.main import prepare_qt_platform_plugins
    prepare_qt_platform_plugins()
except Exception:
    pass


def test_pushfold_card_stylesheet_is_objectname_scoped():
    from PySide6.QtWidgets import QApplication, QFrame
    from app.core.app_state import AppState
    from app.ui.screens.mtt_trainer import MTTTrainerScreen
    QApplication.instance() or QApplication([])
    scr = MTTTrainerScreen(AppState())
    card = scr.findChild(QFrame, "PfCard")
    assert card is not None, "PfCard objectName'i kayboldu"
    ss = card.styleSheet()
    # Çıplak 'QFrame{' DEĞİL, '#PfCard' ile sınırlı olmalı
    assert "#PfCard" in ss, ss
    assert "QFrame{" not in ss.replace(" ", ""), "çıplak QFrame selektörü → seat'lere sızar"
