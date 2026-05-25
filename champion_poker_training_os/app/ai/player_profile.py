"""Oyuncu profili — DB'deki tüm istatistikleri okuyup Gemini'ye bağlam olarak gönderir.

Her Gemini mesajına önce bu profil eklenir:
  build_profile_text() → str

Profil şunları içerir:
  • VPIP / PFR / AF / WTSD / W$SD  (HUD istatistikleri)
  • BB/100 ve kar/zarar trendi
  • Otomatik tespit edilen leak'ler (severity ile)
  • Son 10 elin özeti
  • Oyuncu tipi sınıflandırması (TAG / LAG / Nit / Fish)
"""
from __future__ import annotations

from app.db.repository import get_leak_analysis, get_player_stats, get_session_history


def _classify_player(vpip: float, pfr: float, af: float) -> str:
    """VPIP/PFR/AF'ye göre oyuncu tipi."""
    aggression = af >= 2.0
    tight = vpip < 20
    loose = vpip > 30

    if tight and aggression:
        return "TAG (Tight-Aggressive) — temel GTO oyuncu tipi"
    if tight and not aggression:
        return "Nit (Tight-Passive) — çok az el oynuyor, yeterli baskı uygulamıyor"
    if loose and aggression:
        return "LAG (Loose-Aggressive) — geniş range, yüksek baskı"
    if loose and not aggression:
        return "Fish/Calling Station — çok geniş range, pasif; EV kaybı yüksek"
    return "Balanced Reg — dengeli, geliştirilebilir"


def _trend(recent: list[dict]) -> str:
    """Son 5 elin trendi."""
    if not recent:
        return "veri yok"
    profits = [h.get("hero_profit", 0) for h in recent[:5]]
    total = sum(profits)
    if total > 10:
        return f"+{total:.1f}bb ↑ pozitif seri"
    if total < -10:
        return f"{total:.1f}bb ↓ negatif seri"
    return f"{total:+.1f}bb → nötr"


def _biggest_hands(recent: list[dict], n: int = 3) -> str:
    """En büyük kazanç ve kayıplar."""
    if not recent:
        return ""
    sorted_h = sorted(recent, key=lambda h: abs(h.get("hero_profit", 0)), reverse=True)
    lines = []
    for h in sorted_h[:n]:
        p = h.get("hero_profit", 0)
        sign = "✓" if p >= 0 else "✗"
        cards = h.get("hero_cards", "??")
        board = h.get("community", "") or "preflop"
        lines.append(f"  {sign} {p:+.1f}bb  {cards}  |  {board}")
    return "\n".join(lines)


def build_profile_text() -> str:
    """Gemini'ye gönderilecek oyuncu profili metni. Yetersiz data varsa boş döner."""
    try:
        stats = get_player_stats()
    except Exception:
        return ""

    total = stats.get("total_hands", 0)
    if total < 5:
        return f"[Oyuncu veri yetersiz: {total} el oynandı. Profil için en az 5 el gerekli.]"

    try:
        leaks = get_leak_analysis()
    except Exception:
        leaks = []

    try:
        recent = get_session_history(limit=20)
    except Exception:
        recent = []

    vpip = stats["vpip"]
    pfr  = stats["pfr"]
    af   = stats["af"]
    wtsd = stats["wtsd"]
    wsd  = stats["wsd"]
    bb100 = stats["bb_per_100"]
    profit = stats["profit_bb"]
    win_rate = stats["win_rate"]
    player_type = _classify_player(vpip, pfr, af)
    trend = _trend(recent)

    # ── Leak özeti
    critical_leaks = [l for l in leaks if l.get("severity") in ("Critical", "High")]
    medium_leaks   = [l for l in leaks if l.get("severity") == "Medium"]
    no_major       = not critical_leaks and not medium_leaks

    leak_lines = []
    for l in critical_leaks[:3]:
        leak_lines.append(f"  🔴 {l['name']}: {l.get('detail','')}")
    for l in medium_leaks[:2]:
        leak_lines.append(f"  🟡 {l['name']}: {l.get('detail','')}")
    if no_major:
        leak_lines.append("  ✅ Büyük leak tespit edilmedi — gelişim alanları mevcut")

    # ── En büyük eller
    big_hands_str = _biggest_hands(recent)

    profile = f"""╔══════════════════════════════════════╗
║       OYUNCU PROFİLİ (canlı)        ║
╚══════════════════════════════════════╝
Oyuncu tipi : {player_type}
Toplam el   : {total}  |  BB/100: {bb100:+.1f}  |  Toplam: {profit:+.1f}bb
Kazanma     : {win_rate:.0f}%  |  Son 5 el trendi: {trend}

HUD İSTATİSTİKLERİ
  VPIP {vpip:.0f}%  ·  PFR {pfr:.0f}%  ·  AF {af:.1f}
  WTSD {wtsd:.0f}%  ·  W$SD {wsd:.0f}%

TESPİT EDİLEN LEAK'LER
{chr(10).join(leak_lines)}
"""

    if big_hands_str:
        profile += f"\nEN BÜYÜK HAREKETLER (son 20 el)\n{big_hands_str}\n"

    profile += "══════════════════════════════════════\n"
    profile += "Bu profili dikkate alarak kişiselleştirilmiş analiz ver.\n"

    return profile


def short_profile() -> str:
    """Çok kısa profil özeti — token tasarrufu için basit soru/cevaplarda kullan."""
    try:
        stats = get_player_stats()
        leaks = get_leak_analysis()
    except Exception:
        return ""

    if stats.get("total_hands", 0) < 5:
        return ""

    top_leak = leaks[0]["name"] if leaks else "yok"
    return (
        f"[Profil kısa: VPIP {stats['vpip']:.0f}% PFR {stats['pfr']:.0f}% "
        f"BB/100 {stats['bb_per_100']:+.1f} | Ana leak: {top_leak}]"
    )
