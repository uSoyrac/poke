"""Hero el-aralığı chart picker — motor seçili ellerden deal eder."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.engine.bot_brain import hand_key
from app.engine.game_loop import PokerGame


def _hero_key(game) -> str:
    cards = game.players[game.hero_seat].hole_cards
    return hand_key(cards[0], cards[1])


# ── MOTOR: özel el kümesinden deal ───────────────────────────────────
def test_custom_set_deals_only_selected():
    """hero_range_filter = {'AA','KK'} → hero hep AA ya da KK alır."""
    game = PokerGame(num_players=6, starting_stack=100,
                     hero_range_filter={"AA", "KK"})
    for _ in range(15):
        game.start_hand()
        assert _hero_key(game) in ("AA", "KK"), _hero_key(game)


def test_full_set_means_no_filter():
    """169 elin tamamı seçili → filtre yok (her el gelebilir)."""
    from app.ui.components.hand_range_selector import all_hand_keys
    game = PokerGame(num_players=6, starting_stack=100,
                     hero_range_filter=all_hand_keys())
    keys = set()
    for _ in range(40):
        game.start_hand()
        keys.add(_hero_key(game))
    assert len(keys) > 5            # filtre olsaydı tek/çok az el olurdu


def test_empty_set_means_no_filter():
    """Boş küme → filtre yok (sonsuz döngü / kilitlenme olmaz)."""
    game = PokerGame(num_players=6, starting_stack=100, hero_range_filter=set())
    game.start_hand()              # patlamaz / takılmaz
    assert len(game.players[0].hole_cards) == 2


def test_string_preset_still_works():
    """Geriye dönük: preset adı (str) hâlâ çalışır."""
    game = PokerGame(num_players=6, starting_stack=100,
                     hero_range_filter="Premium")
    for _ in range(10):
        game.start_hand()
        assert _hero_key(game) in {"AA", "KK", "QQ", "JJ", "AKs", "AKo"}


# ── SELECTOR widget ──────────────────────────────────────────────────
@pytest.fixture(scope="module")
def qapp():
    from app.main import prepare_qt_platform_plugins
    prepare_qt_platform_plugins()
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_selector_default_all_then_clear(qapp):
    from app.ui.components.hand_range_selector import HandRangeSelector
    s = HandRangeSelector()
    assert len(s.selected_hands()) == 169 and s.is_full()
    s.clear_all()
    assert len(s.selected_hands()) == 0
    s.set_selected({"AA", "AKs"})
    assert s.selected_hands() == {"AA", "AKs"}
    assert not s.is_full()


def test_selector_toggle(qapp):
    from app.ui.components.hand_range_selector import HandRangeSelector
    s = HandRangeSelector()
    s.clear_all()
    s._toggle("AA")
    assert "AA" in s.selected_hands()
    s._toggle("AA")
    assert "AA" not in s.selected_hands()
