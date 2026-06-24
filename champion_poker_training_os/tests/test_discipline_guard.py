"""D309: Disiplin-Kalkanı override-tespiti. Kullanıcı advisor'dan DAHA AGRESİF (over-action =
leak yönü) ise uyar; uyumlu/under-action/belirsiz ise uyarma."""
from app.poker.discipline_guard import override_warning


def test_fold_then_call_is_override():
    ok, disp = override_warning("CALL", "FOLD")
    assert ok and disp == "FOLD"


def test_fold_then_raise_is_override():
    assert override_warning("RAISE", "FOLD")[0]
    assert override_warning("ALL_IN", "FOLD")[0]


def test_check_then_aggr_is_override():
    assert override_warning("RAISE", "CHECK (board tehlikeli)")[0]
    assert override_warning("BET", "CHECK")[0]


def test_call_then_raise_is_override():
    ok, disp = override_warning("RAISE", "CALL")
    assert ok and disp == "CALL"


def test_aligned_no_warning():
    assert not override_warning("FOLD", "FOLD")[0]
    assert not override_warning("CALL", "CALL")[0]
    assert not override_warning("RAISE", "RAISE (AÇ)")[0]
    assert not override_warning("ALL_IN", "JAM")[0]


def test_under_action_not_intercepted():
    # advisor daha agresif, kullanıcı daha pasif (too-tight) → müdahale YOK (sert-onay over-action için)
    assert not override_warning("FOLD", "CALL")[0]
    assert not override_warning("FOLD", "JAM")[0]
    assert not override_warning("CHECK", "BET (semi-blöf)")[0]
    assert not override_warning("CALL", "RAISE")[0]


def test_no_advisor_no_warning():
    assert not override_warning("CALL", None)[0]
    assert not override_warning("CALL", "")[0]
