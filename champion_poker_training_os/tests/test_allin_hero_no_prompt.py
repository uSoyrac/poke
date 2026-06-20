"""D294 (kullanıcı canlı yakaladı: hero 0bb → UI yalnız FOLD sunup turnuvayı öldürüyor):
ALL-IN / 0-çip oyuncu aksiyon ALAMAZ → step_action onu kuyruktan çıkarır (prompt YOK),
all-in işaretler, board açılır (showdown). is_all_in bayrağı bir yolda kaçsa bile stack<=0
savunma-guard'ı yakalar. Normal-stack hero hâlâ prompt alır (guard over-fire etmez)."""
from app.engine.game_loop import PokerGame
from app.engine.hand_state import ActionType


def _game():
    gl = PokerGame(num_players=3, starting_stack=100.0, small_blind=0.5, big_blind=1.0,
                   ante=0, hero_seat=0, bot_archetypes=["Fish", "Reg"], player_names=["a1", "a2"])
    gl.start_hand()
    return gl


def test_zero_chip_hero_not_prompted():
    """Hero stack 0 + is_all_in bayrağı KAÇMIŞ + kuyrukta → prompt YOK (kuyruktan çıkar)."""
    gl = _game()
    hi = gl.current_hand.hero_idx
    gl.players[hi].stack = 0.0
    gl.players[hi].is_all_in = False
    gl.players[hi].is_folded = False
    gl._action_queue = [hi]
    gl._waiting_for_hero = False
    gl.step_action()
    assert not gl.is_waiting_for_hero, "0-çip hero prompt ALMAMALI (yalnız-FOLD = forfeit bug)"
    assert hi not in gl._action_queue and gl.players[hi].is_all_in


def test_normal_hero_still_prompted():
    """Çipi olan hero kuyrukta → prompt ALIR (guard over-fire etmez)."""
    gl = _game()
    hi = gl.current_hand.hero_idx
    gl.players[hi].stack = 50.0
    gl.players[hi].is_all_in = False
    gl.players[hi].is_folded = False
    gl._action_queue = [hi]
    gl._waiting_for_hero = False
    gl.step_action()
    assert gl.is_waiting_for_hero, "çipi olan hero prompt almalı"


def test_real_allin_completes_without_reprompt():
    """GERÇEK all-in: hero jam'ler → el board açılıp TAMAMLANIR, hero bir daha PROMPT ALMAZ
    (all-in sonrası 0-çip → yeniden sorulup yalnız-FOLD ile turnuvayı öldürmez)."""
    gl = PokerGame(num_players=3, starting_stack=8.0, small_blind=0.5, big_blind=1.0,
                   ante=0, hero_seat=0, bot_archetypes=["Fish", "Reg"], player_names=["a1", "a2"])
    gl.start_hand()
    hi = gl.current_hand.hero_idx
    prompts = 0
    guard = 0
    while guard < 2000:
        guard += 1
        if gl.current_hand and gl.current_hand.is_complete:
            break
        if gl.is_waiting_for_hero:
            prompts += 1
            assert gl.players[hi].stack > 1e-9, "0-çip hero prompt aldı (D294 bug)"
            assert prompts <= 1, "hero all-in sonrası TEKRAR prompt aldı (D294 bug)"
            gl.hero_act(ActionType.ALL_IN, gl.players[hi].stack)   # hero jam → 0 çip
            continue
        if not gl.step_action():
            if not gl.is_waiting_for_hero:
                break
    assert gl.current_hand.is_complete, "all-in el tamamlanmadı (stuck/sonsuz döngü)"
    assert gl.players[hi].stack <= 1e-9 or gl.players[hi].is_all_in or guard < 2000
