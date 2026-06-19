"""D282 (ultracode workflow: kart-eleme/olasılık pratik sistemi GÖRÜNÜR kılma):
soyrac_postflop_advice GÜVENİLİR kaldıraçları (outs, set-mine implied-odds, KENDİ-blocker
combo) chain_steps'te SALT-DISPLAY öğretici satır olarak gösterir. KURAL: action/tier/eq
DEĞİŞMEZ (fidelity 0-sapma); gösterilen sayı masada birebir tekrarlanabilir
(net-out × çarpan == gösterilen %). Gürültü (deste-yeniden-hesaplama) YOK."""
import re
import types
from app.engine.hand_state import card_from_str, Street
from app.poker.soyrac_advisor import soyrac_postflop_advice
from app.poker.gto_live_advice import _villain_continuing_range


def _mk(hole, board, pot, tc, street, n=2, stack=80.0):
    h = [card_from_str(x) for x in hole]; b = [card_from_str(x) for x in board]
    hero = types.SimpleNamespace(hole_cards=h, stack=stack, is_folded=False, is_eliminated=False)
    vs = [types.SimpleNamespace(hole_cards=[], stack=stack, is_folded=False, is_eliminated=False)
          for _ in range(n - 1)]
    return types.SimpleNamespace(players=[hero] + vs, community=b, street=street,
                                 pot=pot, active_count=n, to_call=lambda i: tc)


def _lines(r, icon):
    return [s for s in r["chain_steps"] if icon in s]


def test_draw_line_human_calculable():
    """🎲 çekme satırı: net-out × çarpan == gösterilen % (insan masada tekrarlar)."""
    r = soyrac_postflop_advice(_mk(["9h", "8h"], ["Th", "7h", "2c"], 10, 5, Street.FLOP), 0)
    dl = _lines(r, "🎲")
    assert dl, "FD+OESD flop'ta 🎲 çekme satırı olmalı"
    m = re.search(r"≈(\d+) temiz-out ×(\d+) = %(\d+)", dl[0])
    assert m, f"satır formatı: {dl[0]}"
    net, mult, pct = int(m.group(1)), int(m.group(2)), int(m.group(3))
    assert net * mult == pct, f"net×mult={net*mult} ≠ gösterilen %{pct}"


def test_no_draw_line_on_made_river():
    """River made-hand (çekme yok) → 🎲 satırı OLMAMALI."""
    r = soyrac_postflop_advice(_mk(["Ad", "Ac"], ["Ks", "9s", "7h", "2d", "3c"], 20, 5, Street.RIVER), 0)
    assert not _lines(r, "🎲")


def test_setmine_line_underpair_only():
    """🎰 set-mine yalnız UNDER-çiftte; OVER-pair (AA) → satır YOK (gate doğrulaması)."""
    under = soyrac_postflop_advice(_mk(["3d", "3c"], ["Kd", "9s", "7h"], 20, 2, Street.FLOP, stack=75), 0)
    over = soyrac_postflop_advice(_mk(["Ad", "Ac"], ["Kd", "9s", "7h"], 20, 2, Street.FLOP, stack=75), 0)
    assert _lines(under, "🎰") and "×" in _lines(under, "🎰")[0]
    assert not _lines(over, "🎰"), "overpair'de set-mine satırı OLMAMALI"


def test_setmine_shallow_says_drop():
    """Sığ (büyük bahis → düşük kalan÷ödeme) → 'bırak' metni."""
    r = soyrac_postflop_advice(_mk(["3d", "3c"], ["Kd", "9s", "7h"], 20, 40, Street.FLOP, stack=42), 0)
    sl = _lines(r, "🎰")
    assert sl and ("bırak" in sl[0] or "sığ" in sl[0])


def test_combo_line_river_hu_with_range_and_invariance():
    """🃏 river combo SADECE villain_range verilince; None → satır YOK + action/tier/eq BYTE-IDENTICAL."""
    hd = _mk(["Ac", "5d"], ["Ad", "Kc", "7h", "2s", "3d"], 20, 10, Street.RIVER)
    vr = _villain_continuing_range(2, bet_frac=0.5)
    r_none = soyrac_postflop_advice(hd, 0, villain_range=None)
    r_vr = soyrac_postflop_advice(hd, 0, villain_range=vr)
    assert _lines(r_vr, "🃏") and "V/" in _lines(r_vr, "🃏")[0] and "blocker" in _lines(r_vr, "🃏")[0]
    assert not _lines(r_none, "🃏")
    assert (r_none["action"], r_none["tier"], r_none["eq"]) == (r_vr["action"], r_vr["tier"], r_vr["eq"])


def test_combo_line_not_multiway():
    """Çok-yollu (3+) river → 🃏 combo satırı YOK (range-okuma multiway güvenilmez)."""
    hd = _mk(["Ac", "5d"], ["Ad", "Kc", "7h", "2s", "3d"], 20, 10, Street.RIVER, n=3)
    r = soyrac_postflop_advice(hd, 0, villain_range=_villain_continuing_range(3, bet_frac=0.5))
    assert not _lines(r, "🃏")


def test_new_lines_no_sizing_substring():
    """🎲/🎰/🃏 satırlarının hiçbiri 'Sizing' içermez (CHECK/FOLD sizing-çelişki guard'ı korunur)."""
    r = soyrac_postflop_advice(_mk(["9h", "8h"], ["Th", "7h", "2c"], 10, 5, Street.FLOP), 0)
    for s in r["chain_steps"]:
        if s[0] in "🎲🎰🃏":
            assert "Sizing" not in s
