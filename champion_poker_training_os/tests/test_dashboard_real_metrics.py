"""D128 guard: dashboard sahte sabit metrik göstermesin — gerçek repository'den.

Bug (audit rank#4): dashboard_metrics() tamamen sabitti (skill 742, streak 6,
uydurma 7-gün trendi) → kullanıcının KENDİ performansı gibi sunuluyordu.
Fix: hero_decisions + played_hands'ten hesapla; veri yoksa dürüst 0/boş-durum.
"""
from __future__ import annotations
from app.db.seed_data import dashboard_metrics

_KEYS = ["daily_goal", "drills_today", "preflop_accuracy", "postflop_accuracy",
         "river_score", "icm_discipline", "math_reflex", "ev_loss_per_100",
         "skill_score", "streak", "progress_7d", "expensive_spots"]


def test_no_fabricated_constants():
    m = dashboard_metrics()
    assert m["skill_score"] != 742, "sahte 742 hala var"
    assert m["progress_7d"] != [62, 65, 67, 66, 71, 74, 78], "uydurma trend var"


def test_structure_safe_for_rendering():
    m = dashboard_metrics()
    for k in _KEYS:
        assert k in m, f"eksik anahtar: {k}"
    assert isinstance(m["progress_7d"], list) and len(m["progress_7d"]) >= 1, \
        "progress_7d non-empty olmalı (dashboard [-1] kullanıyor)"
    assert isinstance(m["ev_loss_per_100"], float)
    assert isinstance(m["expensive_spots"], list)


def test_derived_from_real_or_zero():
    """skill_score gerçek doğruluğa bağlı; veri yoksa 0, sabit değil."""
    m = dashboard_metrics()
    assert 0 <= m["skill_score"] <= 1000
    assert m["skill_score"] == m["math_reflex"] * 10 or m["skill_score"] == 0
