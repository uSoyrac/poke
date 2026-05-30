"""Havuz dağıtıcı — % kompozisyonla profil dağıtımı (sample_field + FieldPicker)."""
from __future__ import annotations

import os
import random

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.engine.bot_brain import BOT_ARCHETYPES, KARMA_MIX, sample_field


@pytest.fixture(scope="module")
def qapp():
    from app.main import prepare_qt_platform_plugins
    prepare_qt_platform_plugins()
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


# ── sample_field (saf mantık) ────────────────────────────────────────
def test_default_all_random_from_pool():
    rng = random.Random(1)
    f = sample_field(8, None, rng=rng)
    assert len(f) == 8
    assert all(a in BOT_ARCHETYPES for a in f)      # hepsi geçerli profil
    assert all(a in KARMA_MIX for a in f)           # varsayılan → Karma havuzu


def test_explicit_allocation_is_exact_with_token():
    """random_token verilince açık atama TAM oransal (kalan = token)."""
    rng = random.Random(2)
    f = sample_field(10, {"Shark": 40}, rng=rng, random_token="R")
    assert f.count("Shark") == 4          # round(10*0.4)=4, kalan token
    assert f.count("R") == 6


def test_multi_archetype_proportions():
    rng = random.Random(3)
    f = sample_field(10, {"Shark": 60, "Nit": 30}, rng=rng, random_token="R")
    assert f.count("Shark") == 6
    assert f.count("Nit") == 3
    assert f.count("R") == 1              # kalan %10


def test_unknown_archetype_ignored():
    rng = random.Random(4)
    f = sample_field(5, {"YokBöyleBiri": 80, "Fish": 40}, rng=rng, random_token="R")
    assert f.count("Fish") == 2           # round(5*0.4)=2; bilinmeyen yok sayıldı
    assert "YokBöyleBiri" not in f


def test_zero_bots():
    assert sample_field(0, {"Shark": 50}) == []


# ── FieldPicker dağıtıcı (UI) ────────────────────────────────────────
def test_distributor_accumulates_and_caps(qapp):
    from app.ui.components.field_picker import FieldPicker
    fp = FieldPicker(default_bots=8)
    fp._dist_combo.setCurrentText("Shark"); fp._dist_pct.setValue(70); fp._add_weight()
    fp._dist_combo.setCurrentText("Nit"); fp._dist_pct.setValue(50); fp._add_weight()
    # toplam %100'ü aşamaz → Nit %30'a kırpılır
    assert fp._weights["Shark"] == 70
    assert fp._weights["Nit"] == 30
    assert sum(fp._weights.values()) <= 100


def test_distributor_populates_seats(qapp):
    from app.ui.components.field_picker import FieldPicker
    fp = FieldPicker(default_bots=8)
    fp._dist_combo.setCurrentText("Shark"); fp._dist_pct.setValue(50); fp._add_weight()
    fp._apply_distribution()
    arch = fp.get_archetypes()
    assert len(arch) == 8
    # 50% of 8 = 4 sabit Shark koltuğu (kalan random ek shark getirebilir → ≥4)
    assert arch.count("Shark") >= 4


def test_distributor_clear_resets_to_random(qapp):
    from app.ui.components.field_picker import FieldPicker
    fp = FieldPicker(default_bots=6)
    fp._dist_combo.setCurrentText("Shark"); fp._dist_pct.setValue(50); fp._add_weight()
    fp._clear_weights()
    assert fp._weights == {}


def test_full_pool_selectable_in_distributor(qapp):
    """Dağıtıcı combosu havuzdaki HER profili içermeli (kullanıcı herkesten seçebilir)."""
    from app.ui.components.field_picker import FieldPicker
    fp = FieldPicker(default_bots=6)
    items = {fp._dist_combo.itemText(i) for i in range(fp._dist_combo.count())}
    assert set(BOT_ARCHETYPES.keys()) <= items
