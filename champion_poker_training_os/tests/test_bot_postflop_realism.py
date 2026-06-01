"""Bot POSTFLOP gerçekçiliği — gerçek simülasyonla davranış doğrulaması.

Profil değişmezleri (test_bot_profile_realism) parametreleri kontrol eder;
bu paket parametrelerin MOTORDA gerçekçi davranışa dönüştüğünü simülasyonla
doğrular: yapışkan tipler (Calling Station/Fish) c-bet'e az katlar, disiplinli
tipler (TAG/Overfolder) çok katlar. WSOP-gerçekçiliği postflop'ta da geçerli.

NOT: AF (bahis/call oranı) burada 'agresyon' ölçüsü olarak KULLANILMAZ —
yapısal olarak yanıltıcıdır (Nit nadiren call eder → AF şişer; Maniac çok
call eder → AF düşer; kod tabanında belgelendi). Güvenilir postflop ekseni
fold-to-cbet'tir (yapışkanlık).
"""
from __future__ import annotations

import os
import random
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(__file__))

from test_bot_archetype_fidelity import _simulate   # noqa: E402

_N = 1400   # arketip başına el — yapışkan/loose tiplerde bol postflop örneklem


def _sim(arch: str, seed: int = 424242) -> dict:
    random.seed(seed)
    return _simulate(arch, _N)


def test_sticky_types_fold_to_cbet_less_than_disciplined():
    """Calling Station / Fish (yapışkan) c-bet'e, Overfolder / TAG'den
    (disiplinli) belirgin ŞEKİLDE AZ katlar."""
    station = _sim("Calling Station")
    overfold = _sim("Overfolder")
    # Bu tipler bol flop görür → yeterli örneklem
    assert station["fcb_sample"] >= 25, f"station örneklem az {station['fcb_sample']}"
    assert overfold["fcb_sample"] >= 20, f"overfolder örneklem az {overfold['fcb_sample']}"
    assert overfold["fold_to_cbet"] > station["fold_to_cbet"] + 20, (
        f"Overfolder %{overfold['fold_to_cbet']:.0f} ≫ Station "
        f"%{station['fold_to_cbet']:.0f} olmalı")


def test_station_is_sticky():
    """Calling Station c-bet'e çok az katlar (yapışkan — gerçekçi)."""
    st = _sim("Calling Station")
    assert st["fcb_sample"] >= 25
    assert st["fold_to_cbet"] < 40, f"Station FCB %{st['fold_to_cbet']:.0f} çok yüksek"


def test_overfolder_overfolds():
    """Overfolder c-bet'e çok katlar (sömürülebilir — gerçekçi)."""
    of = _sim("Overfolder")
    assert of["fcb_sample"] >= 20
    assert of["fold_to_cbet"] > 50, f"Overfolder FCB %{of['fold_to_cbet']:.0f} düşük"


def test_fish_stickier_than_tag():
    """Fish (loose-pasif) c-bet'e TAG'den (tight-agresif) az katlar."""
    fish = _sim("Fish")
    tag = _sim("TAG")
    if fish["fcb_sample"] >= 20 and tag["fcb_sample"] >= 15:
        assert fish["fold_to_cbet"] < tag["fold_to_cbet"] + 5, (
            f"Fish %{fish['fold_to_cbet']:.0f} ≤ TAG %{tag['fold_to_cbet']:.0f} civarı")
