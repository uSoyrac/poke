"""D311-fix REGRESYON: turnuva ilk elden SONRA takılmamalı.

Bug: D309 Disiplin-Kalkanı edit'i _hero_action'ın completion-kuyruğunu
(`if hand.is_complete: advance + _on_hand_complete`) yanlışlıkla _discipline_ok
metodunun `return False`'ından SONRA orphan/ölü-kod bıraktı → hero aksiyonu eli
bitirince _on_hand_complete çağrılmıyordu → auto-deal yok → "ilk elden sonra takıldı".
Bu test el-akışının 1. elden sonra devam ettiğini garantiler.
"""
from app.main import prepare_qt_platform_plugins

prepare_qt_platform_plugins()
from PySide6.QtWidgets import QApplication  # noqa: E402
from app.core.app_state import AppState  # noqa: E402
from app.engine.hand_state import ActionType  # noqa: E402
from app.ui.screens.tournament_simulator import TournamentSimulatorScreen  # noqa: E402

_app = QApplication.instance() or QApplication([])


def test_tournament_flows_past_first_hand():
    """Turnuva başlat → hero fold-akışıyla en az 6 ele ulaşmalı (takılma yok)."""
    s = TournamentSimulatorScreen(AppState())
    s.isVisible = lambda: True  # görünür-mod (gerçek app akışı)
    s.field_picker.set_composition(
        ["Fish", "TAG", "Reg", "Nit", "Shark", "LAG", "Maniac", "Calling Station"])
    s._start_tournament()
    seen = 0
    for _ in range(2500):
        g = s.tournament.game
        if g.is_waiting_for_hero:
            s._hero_action(ActionType.FOLD)
        elif g.current_hand and not g.current_hand.is_complete:
            s._tick_bot()
        if getattr(s, "_between_hands", False):
            s._maybe_auto_deal_next()      # QTimer yerine elle pump
        _app.processEvents()
        seen = max(seen, s.tournament.state.hands_total)
        if seen >= 6:
            break
    assert seen >= 6, f"turnuva 1. elden sonra takıldı — sadece {seen} ele ulaşıldı"


def test_hero_action_has_completion_tail():
    """_hero_action gövdesi _on_hand_complete çağrısını İÇERMELİ (orphan değil) —
    kaynak-düzeyi guard: _discipline_ok'tan SONRA ölü _on_hand_complete kalmasın."""
    import inspect
    from app.ui.screens import tournament_simulator as TS
    src = inspect.getsource(TS.TournamentSimulatorScreen._hero_action)
    assert "_on_hand_complete" in src, "_hero_action completion-kuyruğunu kaybetmiş (orphan bug)"
