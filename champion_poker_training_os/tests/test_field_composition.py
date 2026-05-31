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


def test_preset_tough_loads_sharks(qapp):
    from app.ui.components.field_picker import FieldPicker, FIELD_PRESETS
    tough = dict(FIELD_PRESETS)["🦈 Tough"]
    fp = FieldPicker(default_bots=8)
    fp._apply_preset(tough)
    assert fp._weights.get("Shark", 0) == 60
    arch = fp.get_archetypes()
    assert arch.count("Shark") >= 4              # 60% of 8 ≈ 5 sabit shark
    assert len(arch) == 8


def test_preset_karisik_clears_to_random(qapp):
    from app.ui.components.field_picker import FieldPicker
    fp = FieldPicker(default_bots=6)
    fp._dist_combo.setCurrentText("Shark"); fp._dist_pct.setValue(50); fp._add_weight()
    fp._apply_preset({})                          # 🎲 Karışık
    assert fp._weights == {}


def test_all_presets_valid_and_capped(qapp):
    from app.ui.components.field_picker import FieldPicker, FIELD_PRESETS
    fp = FieldPicker(default_bots=8)              # MAX_BOTS = 8
    for label, weights in FIELD_PRESETS:
        fp._apply_preset(weights)
        assert sum(fp._weights.values()) <= 100, f"{label} %100 aştı"
        assert all(a in BOT_ARCHETYPES for a in fp._weights), f"{label} geçersiz profil"
        assert len(fp.get_archetypes()) == 8      # her preset masayı doldurur


def test_full_random_default_is_varied(qapp):
    """Varsayılan (hiçbir şey seçilmemiş) → koltuklar full random; get_archetypes
    her seferinde Karma havuzundan çözer (özel seçim YOK)."""
    from app.ui.components.field_picker import FieldPicker
    fp = FieldPicker(default_bots=8)
    assert fp._weights == {}                          # atama yok = full random
    seen = set()
    for _ in range(20):
        seen.update(fp.get_archetypes())              # her çağrı Random'ı yeniden örnekler
    assert len(seen) >= 4, f"full random çeşitli olmalı: {seen}"
    assert seen <= set(KARMA_MIX)                     # hepsi Karma havuzundan


def test_specific_selection_genuinely_distributes(qapp):
    """%30 Shark + %30 GTO Expert = %60 → ~%60 o tipler, kalan random.
    Kullanıcının '30 shark 30 gto seçince %60'ı böyle gelsin' isteği."""
    from app.ui.components.field_picker import FieldPicker
    fp = FieldPicker(default_bots=8)                   # MAX_BOTS = 8
    fp._dist_combo.setCurrentText("Shark"); fp._dist_pct.setValue(30); fp._add_weight()
    fp._dist_combo.setCurrentText("GTO Expert"); fp._dist_pct.setValue(30); fp._add_weight()
    fp._apply_distribution()
    arch = fp.get_archetypes()
    assert len(arch) == 8
    # 30% of 8 = round(2.4)=2 sabit Shark + 2 sabit GTO Expert = 4 (kalan 4 random)
    assert arch.count("Shark") >= 2
    assert arch.count("GTO Expert") >= 2
    fixed = arch.count("Shark") + arch.count("GTO Expert")
    assert fixed >= 4                                  # %60 sabit atandı, kalan random


def test_full_pool_selectable_in_distributor(qapp):
    """Dağıtıcı combosu havuzdaki HER profili içermeli (kullanıcı herkesten seçebilir)."""
    from app.ui.components.field_picker import FieldPicker
    fp = FieldPicker(default_bots=6)
    items = {fp._dist_combo.itemText(i) for i in range(fp._dist_combo.count())}
    assert set(BOT_ARCHETYPES.keys()) <= items
