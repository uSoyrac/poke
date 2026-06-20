"""D295 (kullanıcı D294-freeze sonrası: 'turnuva bug yüzünden kaybolmamalı'): devam-eden
turnuva autosave + resume. Round-trip: oyna → snapshot → restore → state BİREBİR korunur
(stack'ler, blind-level, el-sayısı, alan/mtt_field) ve turnuva DEVAM EDER (el dağıtılır)."""
import random

from app.simulator.tournament_runner import Tournament, TournamentConfig
from app.simulator.mtt_field import MTTField
from app.simulator import tournament_save


def _played_tournament(seed=7):
    random.seed(seed)
    cfg = TournamentConfig(name="$22 Bounty Hunter", field_size=9, starting_chips=2000,
                           structure="regular", buyin=22.0, payout_key="9-max",
                           hands_per_level=12, bot_mix=["Fish", "TAG", "Reg", "Nit",
                                                        "LAG", "Shark", "Maniac", "Calling Station"])
    t = Tournament(cfg)
    for _ in range(25):                      # birkaç el oyna (state ilerlesin)
        if t.is_complete:
            break
        t.start_hand()
        guard = 0
        while guard < 400:
            guard += 1
            if t.game.current_hand and t.game.current_hand.is_complete:
                break
            prog = t.game.step_action()
            if t.game.is_waiting_for_hero:
                t.hero_act(__import__("app.engine.hand_state", fromlist=["ActionType"]).ActionType.FOLD, 0)
            elif not prog:
                break
    return t


def test_tournament_roundtrip_preserves_state():
    t = _played_tournament()
    d = t.to_dict()
    t2 = Tournament.from_dict(d)
    assert t2.state.level_idx == t.state.level_idx
    assert t2.state.hands_total == t.state.hands_total
    assert t2.state.players_left == t.state.players_left
    assert t2.game.dealer_idx == t.game.dealer_idx
    s1 = [round(p.stack, 2) for p in t.game.players]
    s2 = [round(p.stack, 2) for p in t2.game.players]
    assert s1 == s2, f"stack'ler korunmadı: {s1} vs {s2}"
    el1 = [p.is_eliminated for p in t.game.players]
    el2 = [p.is_eliminated for p in t2.game.players]
    assert el1 == el2
    # blind seviyesi korundu
    assert t2.state.current_level.bb == t.state.current_level.bb


def test_restored_tournament_can_continue():
    """Restore edilen turnuva DEVAM EDER — yeni el dağıtılır, çökmez."""
    t = _played_tournament()
    t2 = Tournament.from_dict(t.to_dict())
    h = t2.start_hand()
    assert h is not None and t2.game.current_hand is not None


def test_mtt_field_roundtrip():
    f = MTTField(field_size=200, buyin=22.0, structure="regular", hero_table_size=9,
                 starting_chips=2000)
    f._bg = {"weak": 70, "mid": 40, "strong": 23}
    f._hero_table_remaining = 7
    d = f.to_dict()
    f2 = MTTField.from_dict(d)
    assert f2.field_size == 200 and f2.starting_chips == 2000
    assert f2._bg == f._bg and f2._hero_table_remaining == 7
    assert f2.players_remaining == f.players_remaining


def test_save_load_clear_roundtrip(tmp_path, monkeypatch):
    """Disk save/load/clear/has — JSON round-trip."""
    monkeypatch.setattr(tournament_save, "_PATH", tmp_path / "resume.json")
    assert not tournament_save.has_snapshot()
    snap = {"tournament": _played_tournament().to_dict(),
            "mtt_field": MTTField(field_size=200, starting_chips=2000).to_dict(), "meta": 1}
    assert tournament_save.save_snapshot(snap)
    assert tournament_save.has_snapshot()
    loaded = tournament_save.load_snapshot()
    assert loaded["meta"] == 1 and loaded["tournament"]["config"]["field_size"] == 9
    tournament_save.clear_snapshot()
    assert not tournament_save.has_snapshot()
