"""Turnuva meta bar + field strip (D revizyonu).

D3: AVG STACK üst izlencede BB cinsinden + DOĞRU hesap — MTT'de toplam çip /
    kalan oyuncu (eskiden hero masasının çipini saha sayısına bölüp '4bb' gibi
    saçma değer veriyordu).
D2: field strip'te masadaki rakiplerin ortalama oyun-stili (VPIP/PFR).
"""
from __future__ import annotations

import os
import random

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from app.main import prepare_qt_platform_plugins
    prepare_qt_platform_plugins()
except Exception:
    pass


def _started_screen():
    from PySide6.QtWidgets import QApplication
    from app.core.app_state import AppState
    from app.ui.screens.tournament_simulator import TournamentSimulatorScreen
    QApplication.instance() or QApplication([])
    random.seed(7)
    s = TournamentSimulatorScreen(AppState())
    s.field_picker.set_composition(
        ["GTO Expert", "ICM Expert", "Daniel Negreanu", "Fish",
         "TAG", "Maniac", "Reg", "Nit"])
    s._start_tournament()
    from PySide6.QtWidgets import QApplication as QA
    for _ in range(60):
        QA.processEvents()
        try:
            s._tick_bot()
        except Exception:
            pass
    s._refresh_table()
    s._refresh_field_strip()
    QA.processEvents()
    # _end_and_restart() canlı (tamamlanmamış) turnuvada _confirm_abort() ile
    # modal QMessageBox açar; offscreen test'te onu kapatacak kullanıcı yok →
    # exec() nested event-loop'ta SONSUZA kadar bloke olur (hang, fail değil).
    # Docstring'in işaret ettiği gibi onayı monkeypatch'leyip otomatik 'Yes'
    # yap — timer-temizliği yapan gerçek _end_and_restart akışı korunur.
    s._confirm_abort = lambda: True
    return s


def test_avg_stack_is_in_bb_and_sensible():
    s = _started_screen()
    val = s.meta_cells["AVG"]._value_label.text()
    assert val.strip().endswith("bb"), f"AVG STACK BB cinsinden olmalı: {val!r}"
    # Başlangıçta avg ≈ starting_chips/bb (kimse elenmedi) — 4bb gibi saçma DEĞİL
    bb_num = float(val.replace("bb", "").strip())
    assert bb_num >= 50, f"avg stack saçma derecede küçük: {bb_num}bb"
    s._end_and_restart()


def test_field_strip_shows_table_playstyle():
    s = _started_screen()
    strip = s._fs_label.text()
    assert "masa oyun" in strip and "VPIP" in strip, strip
    assert s._field_vpip > 0
    s._end_and_restart()
