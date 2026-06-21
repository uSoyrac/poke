"""D308 (kullanıcı: 'cash'te her eli boşlukla geçmek zorundayım'): cash (+MTT) OTO-AKIŞ.
El bitince sonraki el otomatik dağıtılır (turnuva D133 emsali); SPACE/Next manuel gerekmez.
Toggle ('Oto-akış') ile kapatılır (el-el çalışma/inceleme). Real-XP'de kapalı (notlandırılmış)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from app.main import prepare_qt_platform_plugins

prepare_qt_platform_plugins()
from PySide6.QtWidgets import QApplication

from app.core.app_state import AppState
from app.ui.screens.play_session import PlaySessionScreen

_app = QApplication.instance() or QApplication([])


def _screen():
    s = PlaySessionScreen(AppState())
    s._start_cash()
    return s


def test_autoflow_default_on():
    s = _screen()
    assert hasattr(s, "autoflow_chk") and s.autoflow_chk.isChecked()
    assert s._auto_flow is True


def test_guard_deals_when_between_hands():
    """Oto-akış açık + next_btn görünür (el-arası) → sonraki el dağıtılır."""
    s = _screen()
    fired = {"n": 0}
    s._deal_next = lambda: fired.__setitem__("n", fired["n"] + 1)
    s.next_btn.show()
    s._auto_deal_guarded(s._deal_next, s.next_btn)
    assert fired["n"] == 1


def test_guard_skips_when_hand_in_progress():
    """next_btn gizli (el sürüyor / zaten dağıtıldı) → deal ETMEZ (çift-deal yok)."""
    s = _screen()
    fired = {"n": 0}
    s._deal_next = lambda: fired.__setitem__("n", fired["n"] + 1)
    s.next_btn.hide()
    s._auto_deal_guarded(s._deal_next, s.next_btn)
    assert fired["n"] == 0


def test_toggle_off_stops_autoflow():
    """Toggle kapalı → el-arası olsa bile oto-deal ETMEZ (manuel SPACE/Next)."""
    s = _screen()
    fired = {"n": 0}
    s._deal_next = lambda: fired.__setitem__("n", fired["n"] + 1)
    s.autoflow_chk.setChecked(False)
    assert s._auto_flow is False
    s.next_btn.show()
    s._auto_deal_guarded(s._deal_next, s.next_btn)
    assert fired["n"] == 0


def test_real_xp_no_autoflow_schedule():
    """Real-XP → _maybe_auto_flow zamanlama YAPMAZ (notlandırılmış inceleme, manuel)."""
    s = _screen()
    fired = {"n": 0}
    s._deal_next = lambda: fired.__setitem__("n", fired["n"] + 1)
    s.next_btn.show()
    s._maybe_auto_flow(True, s._deal_next, s.next_btn)   # real_xp=True → schedule yok
    _app.processEvents()
    assert fired["n"] == 0
