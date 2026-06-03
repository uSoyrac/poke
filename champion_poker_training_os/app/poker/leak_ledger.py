"""Leak-ledger — kalıcı öz-bilgi + spaced-repetition (advanced-poker-coach skill).

Drill/karar sonuçlarını leak kategorisine göre zaman içinde biriktirir; bir
leak "çözüldü" sayılmaz ta ki GECİKMELİ bir re-test'i geçene kadar (skill ilkesi).
Bu modül SAF durum/aralık mantığını tutar (DB persistence repository'de).

next_review: streak büyüdükçe aralık uzar (SM-2 sezgisi). status: yeni / aktif
leak / düzeliyor / sağlamlaşıyor (re-test bekliyor) / çözüldü.
"""
from __future__ import annotations

_DAY = 86400.0

# Streak → bir sonraki re-test aralığı (saat). Doğru cevap arttıkça uzar.
_INTERVAL_HOURS = {0: 0, 1: 4, 2: 12, 3: 24, 4: 72}
_MAX_INTERVAL_H = 168   # 5+ streak → 7 gün

_MIN_ATTEMPTS = 8       # bu altında "yeni"
_RESOLVE_ACC = 0.78     # çözülme için min doğruluk
_RESOLVE_STREAK = 5     # çözülme için min ardışık doğru


def next_review_hours(streak: int) -> int:
    """Streak'e göre bir sonraki re-test aralığı (saat) — spaced repetition."""
    if streak >= 5:
        return _MAX_INTERVAL_H
    return _INTERVAL_HOURS.get(max(0, streak), 0)


def compute_status(attempts: int, correct: int, streak: int,
                   first_seen: float, last_seen: float, now: float) -> dict:
    """Bir leak kategorisinin durumu. Zamanlar epoch-saniye.

    'çözüldü' YALNIZCA: yüksek doğruluk + uzun streak + GECİKMELİ re-test
    (ilk görülme ile son arasında ≥1 gün) → tek oturumda çözülmüş sayılmaz.
    """
    acc = (correct / attempts) if attempts else 0.0
    span_days = (last_seen - first_seen) / _DAY if last_seen >= first_seen else 0.0
    delayed_ok = span_days >= 1.0          # gecikmeli re-test geçti mi

    if attempts < _MIN_ATTEMPTS:
        status = "🆕 yeni (veri topluyor)"
        resolved = False
    elif acc < 0.55:
        status = "🔴 aktif leak"
        resolved = False
    elif acc < _RESOLVE_ACC:
        status = "🟡 düzeliyor"
        resolved = False
    elif streak >= _RESOLVE_STREAK and delayed_ok:
        status = "🟢 çözüldü (gecikmeli re-test geçti)"
        resolved = True
    else:
        status = "🟡 sağlamlaşıyor (gecikmeli re-test bekliyor)"
        resolved = False

    return {
        "accuracy": round(100 * acc, 1),
        "status": status,
        "resolved": resolved,
        "next_review_hours": next_review_hours(streak),
        "due": now >= (last_seen + next_review_hours(streak) * 3600.0),
        "span_days": round(span_days, 1),
    }
