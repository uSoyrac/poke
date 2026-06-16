"""D240: leak'e özel drill'ler DOĞRU cevabı (soyrac_advice) taşır — sabit 'call' DEĞİL.
Eski bug: junk-over-defend drill'i best_action='call' veriyordu → leak'i pekiştiriyordu."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from app.main import prepare_qt_platform_plugins
prepare_qt_platform_plugins()
from PySide6.QtWidgets import QApplication
_app = QApplication.instance() or QApplication([])
from app.training.drill_library import DrillLibrary


def _gen(name):
    return DrillLibrary.instance().generate_from_leak(
        {"name": name, "category": "Preflop", "fix": "x"}, count=5)


def test_junk_over_defend_drill_teaches_fold():
    """Çöp-over-defend drill'i junk eller + DOĞRU=fold (call DEĞİL — yoksa leak pekişir)."""
    ds = _gen("Çöp/spekülatif over-defend")
    assert all(d["best_action"] == "fold" for d in ds), [d["best_action"] for d in ds]
    assert all(d["street"] == "preflop" for d in ds)


def test_3bet_overcall_drill_teaches_fold():
    """3-bet pot over-call drill'i küçük çift + DOĞRU=fold (D236)."""
    ds = _gen("3-bet pot over-call")
    assert all(d["best_action"] == "fold" for d in ds), [d["best_action"] for d in ds]


def test_best_action_engine_not_hardcoded():
    """best_action SABİT 'call' değil — leak'e göre değişir (junk=fold)."""
    junk = _gen("Çöp/spekülatif over-defend")
    assert not all(d["best_action"] == "call" for d in junk)
    assert all(d["source_confidence"].startswith("Soyrac engine") for d in junk)
