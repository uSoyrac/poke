"""D296 (kullanıcı tezi "küçük çift büyük call olmamalı" + Thread-A field-split sim-kanıtı):
vs-3bet küçük/orta-çift (77-99) SET-MINE CALL'ı READ-GATED. Set-mine ALANA BAĞLI:
- soft/fish/pasif 3-bettor set'i ÖDER → CALL +EV (soft 100bb baseline +65.8 bb/100) → KORU.
- yetkin-AGRESİF 3-bettor (yüksek 3bet% + barrel) set'i ödemez + atar → CALL −EV → FOLD
  (tough/orta 100bb: fold +79.6 vs call −75.5 bb/100).
Thread-A universal/stack-gated fold VERİYLE DESTEKLENMEDİ (gürültülü, field-dependent) →
geri alındı; doğru yer = read-gated katman (sim karar-yolunda exploit YOK → D254/D293 statüsü).
TT+ (eq daha iyi) ve 33-66 (zaten D236 fold) etkilenmez; no-read → identity."""
from app.poker.opponent_typology import classify_hellmuth
from app.poker.soyrac_advisor import _preflop_exploit, soyrac_advice

_TOUGH = {"vpip": 26, "pfr": 22, "aggression": 2.8, "three_bet": 9, "obs_hands": 80}   # Lion (TAG)
_STATION = {"vpip": 46, "pfr": 9, "aggression": 0.8, "three_bet": 3, "obs_hands": 80}  # Elephant/öder
_NIT = {"vpip": 12, "pfr": 9, "aggression": 1.1, "three_bet": 2, "obs_hands": 80}      # Mouse/öder
_JACKAL = {"vpip": 32, "pfr": 23, "aggression": 2.0, "three_bet": 12, "obs_hands": 80}  # spewy/öder


def test_tough_is_lion_or_eagle():
    """Fixture sağlığı: _TOUGH yetkin (Lion/Eagle), _JACKAL spewy (Jackal) sınıflanmalı."""
    assert classify_hellmuth(26, 22, 2.8, 0)[1] in ("Lion", "Eagle")
    assert classify_hellmuth(32, 23, 2.0, 0)[1] == "Jackal"


def test_tough_aggressor_folds_setmine():
    """YETKİN-agresif (Lion/Eagle) 3-bettor'a karşı 77-99 set-mine CALL → FOLD + set-mine notu."""
    for hk in ("77", "88", "99"):
        fa, note = _preflop_exploit("CALL", "BTN", _TOUGH, hk, scenario="vs 3-bet")
        assert fa == "FOLD", f"{hk} vs Lion/Eagle FOLD olmalı: {fa}"
        assert "set-mine" in note and "barrel" in note


def test_jackal_deep_keeps_setmine_call():
    """SPEWY-agresif (Jackal) DERİN (>50bb) → B2 (fold) KAPSAMAZ + B1 (jam) mid-stack-gated →
    CALL KORUNUR (set'i öder, bluff-range'e over-fold etme; derin jam over-bet)."""
    for hk in ("77", "88", "99"):
        fa, note = _preflop_exploit("CALL", "BTN", _JACKAL, hk, scenario="vs 3-bet", stack_bb=100)
        assert fa == "CALL" and note is None, f"{hk} vs Jackal derin CALL kalmalı: {fa}"


def test_jackal_midstack_jams_midpair():
    """D297 (B1, jackal-field A/B-doğrulandı): SPEWY-agresif (Jackal) MID-STACK (26-50bb) →
    88-TT set-mine CALL yerine JAM (4-BET) — fold-equity + geniş-range'e domine değil."""
    for hk in ("88", "99", "TT"):
        fa, note = _preflop_exploit("CALL", "BTN", _JACKAL, hk, scenario="vs 3-bet", stack_bb=40)
        assert fa == "4-BET", f"{hk} vs jackal mid-stack JAM olmalı: {fa}"
        assert "jam" in note.lower()


def test_jackal_77_not_jammed():
    """77 B1 kapsamı (88-TT) DIŞINDA → jackal mid-stack'te de CALL kalır."""
    fa, _ = _preflop_exploit("CALL", "BTN", _JACKAL, "77", scenario="vs 3-bet", stack_bb=40)
    assert fa == "CALL"


def test_lion_midstack_still_folds_b2_b1_no_conflict():
    """B1/B2 çakışmaz: aynı el (88) Lion/Eagle'a karşı mid-stack'te de FOLD (B2), Jackal'a JAM (B1)."""
    fa_lion, _ = _preflop_exploit("CALL", "BTN", _TOUGH, "88", scenario="vs 3-bet", stack_bb=40)
    fa_jackal, _ = _preflop_exploit("CALL", "BTN", _JACKAL, "88", scenario="vs 3-bet", stack_bb=40)
    assert fa_lion == "FOLD" and fa_jackal == "4-BET"


def test_station_keeps_setmine_call():
    """Fish/station (set'i öder) → set-mine CALL KORUNUR."""
    for hk in ("77", "88", "99"):
        fa, note = _preflop_exploit("CALL", "BTN", _STATION, hk, scenario="vs 3-bet")
        assert fa == "CALL" and note is None, f"{hk} vs station CALL kalmalı: {fa}"


def test_nit_keeps_setmine_call():
    """Pasif nit (düşük 3bet%, set'i öder) → set-mine CALL KORUNUR (B2 tetiklenmez)."""
    fa, note = _preflop_exploit("CALL", "BTN", _NIT, "88", scenario="vs 3-bet")
    assert fa == "CALL" and note is None


def test_tt_and_above_not_folded():
    """TT+ (eq daha iyi, set-mine sınırı üstü) yetkin-agresif'e bile CALL kalır."""
    for hk in ("TT", "JJ"):
        fa, _ = _preflop_exploit("CALL", "BTN", _TOUGH, hk, scenario="vs 3-bet")
        assert fa == "CALL", f"{hk} CALL kalmalı (set-mine sınırı üstü): {fa}"


def test_no_read_identity():
    """No-read → değişiklik YOK (set-mine CALL korunur; cash/sim/fidelity etkilenmez)."""
    for hk in ("77", "88", "99"):
        fa, note = _preflop_exploit("CALL", "BTN", None, hk, scenario="vs 3-bet")
        assert fa == "CALL" and note is None


def test_non_vs3bet_scenario_untouched():
    """vs-RFI flat (open'a karşı set-mine) → B2 DOKUNMAZ (open'a set-mine normal +EV)."""
    fa, note = _preflop_exploit("CALL", "CO", _TOUGH, "88", scenario="vs RFI")
    assert fa == "CALL" and note is None, "vs-RFI set-mine'a dokunulmamalı"


def test_d310_small_pair_deep_setmine_allowed():
    """D310 (kullanıcı haklı çıktı — 44 @206bb call'ı +EV): 33-66 vs 3-bet NORMAL/sığ-stack FOLD
    (D236 disiplin), AMA DERİN'de (≥150bb) set-mine CALL'a izin (GTO 44 vs 3-bet %95 call;
    derin SPR implied-odds'u haklı kılar). 88+ etkilenmez (zaten call)."""
    for hk in ("33", "44", "55", "66"):
        a100 = soyrac_advice(hk, "HJ", "vs 3-bet", vs_position="CO", stack_bb=100, n_active=6)["action"]
        a200 = soyrac_advice(hk, "HJ", "vs 3-bet", vs_position="CO", stack_bb=200, n_active=6)["action"]
        assert a100 == "FOLD", f"{hk} @100bb FOLD olmalı (D236 disiplin): {a100}"
        assert a200 == "CALL", f"{hk} @200bb derin set-mine CALL olmalı (D310): {a200}"


def test_lower_pairs_already_folded_by_base():
    """33-66 zaten base'de (D236) FOLD → exploit'e CALL gelmez (gelirse de B2 kapsamı 77+)."""
    # 33-66 idx<=4 → B2 koşulu (5<=pi<=7) dışında; CALL gelse bile B2 dokunmaz.
    fa, _ = _preflop_exploit("CALL", "BTN", _TOUGH, "66", scenario="vs 3-bet")
    assert fa == "CALL", "66 B2 kapsamı dışında (base zaten folder)"
