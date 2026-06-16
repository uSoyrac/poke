"""MTT PLAYBOOK (D242) — turnuva format-katmanının TEK KAYNAĞI.

MİMARİ KARAR (kullanıcı): "tek çekirdek + iki playbook". Paylaşılan çekirdek
(SHCP puanı, el-değerlendirme, 7-kademe postflop) format-bağımsız; ÜSTÜNE iki
ayrı-ölçülen format-katmanı oturur. Bu modül MTT katmanının çekirdeğidir.

ÇÖZÜLEN BUG: stage (evre) tespiti 3 yerde FARKLI eşiklerle yapılıyordu —
  • tournament_simulator _maybe_icm_coach: bubble = icm >= 0.85
  • tournament_simulator soyrac_explain çağrısı: bubble = icm >= 0.6, FT = rem <= 9
  • mtt_exploit._phase: avg-stack proxy
→ koç "bubble" derken push/fold mantığı "değil" diyebiliyordu (tutarsız strateji).
``mtt_stage`` artık TEK KAYNAK; gerçek-yer (kalan-vs-ödeme) > icm > derinlik öncelik.

İki fonksiyon:
  • ``mtt_stage(...)``  → kanonik evre (early/mid/late/bubble/itm/final table) + kaynak.
  • ``stage_plan(...)`` → o evrenin STRATEJİK önceliği (playbook içeriği; koç/kitap/akademi).
SADECE advice/koç + tespit-birleştirme — bot frekanslarına dokunmaz (fidelity 0-sapma).
"""
from __future__ import annotations

import math


def mtt_stage(players_remaining=None, paid_places=None, players_total=None,
              icm_pressure: float = 0.0, avg_stack_bb: float = 0.0,
              hero_stack_bb: float = 0.0, table_size: int = 9) -> dict:
    """Kanonik MTT evresi — TEK KAYNAK. Sinyal önceliği: gerçek-yer > ICM > derinlik.

    Döner: ``{"stage": str, "label": str, "source": str}``.
    stage ∈ {early, mid, late, bubble, itm, final table}.
    """
    rem = int(players_remaining) if players_remaining else 0
    paid = int(paid_places) if paid_places else 0

    # 1) GERÇEK-YER (en güvenilir): kalan oyuncu vs ödeme-yeri
    if rem > 0:
        if rem <= 9:
            return {"stage": "final table", "label": "Final Masa", "source": "remaining"}
        if paid > 0:
            # bubble = paranın hemen üstü (~%15 + 1 bant); itm = parada, FT-öncesi
            bubble_top = int(math.ceil(paid * 1.15)) + 1
            if paid < rem <= bubble_top:
                return {"stage": "bubble", "label": "Bubble", "source": "remaining"}
            if rem <= paid:
                return {"stage": "itm", "label": "Para-içi (ITM)", "source": "remaining"}
        # para-öncesi (rem büyük) → derinlikle early/mid/late

    # 2) ICM-baskısı (gerçek-yer yoksa) — fuzzy ama yön verir
    if icm_pressure and icm_pressure > 0 and rem == 0:
        if icm_pressure >= 0.8:
            return {"stage": "bubble", "label": "Bubble", "source": "icm"}
        if 0.3 <= icm_pressure < 0.8:
            return {"stage": "itm", "label": "Para-içi (ITM)", "source": "icm"}

    # 3) DERİNLİK (alan-ortalama stack proxy'si) → early/mid/late
    depth = avg_stack_bb if avg_stack_bb and avg_stack_bb > 0 else hero_stack_bb
    if depth <= 0:
        return {"stage": "mid", "label": "Orta evre", "source": "default"}
    if depth >= 45:
        return {"stage": "early", "label": "Erken (derin)", "source": "depth"}
    if depth >= 22:
        return {"stage": "mid", "label": "Orta evre", "source": "depth"}
    return {"stage": "late", "label": "Geç (sığ)", "source": "depth"}


# ── PLAYBOOK İÇERİĞİ: her evrenin stratejik önceliği (koç/kitap/akademi kaynağı) ──
_STAGE_PLAN = {
    "early": {
        "headline": "🌱 Erken · biriktir, ucuz risk al",
        "priorities": [
            "Derin (≥45bb) → implied-odds oyna: set-mine, suited-connector ucuz gör.",
            "Marjinal pot-şişirmeden kaçın; postflop edge'i kullan (yüksek SPR).",
            "Steal'a abanma — alan loose, value-ağırlıklı kal.",
        ],
    },
    "mid": {
        "headline": "⏳ Orta · ante girdi, steal'ı aç",
        "priorities": [
            "Ante pot'u büyütür → geç-pozisyon açışını GENİŞLET (mtt_ranges ante-aware).",
            "15-25bb re-jam oyununu kur (geç açışlara fold-equity'li 3-bet-jam).",
            "Bloated multiway pot'tan kaç; inisiyatifi al.",
        ],
    },
    "late": {
        "headline": "🩳 Geç · push/fold disiplini",
        "priorities": [
            "≤15bb → Nash jam/fold (pozisyon-duyarlı, mtt_jam_pct).",
            "Önünde jam varsa CALL/FOLD ekseni (re-jam çoğu zaman imkânsız).",
            "Fold-equity penceresini kaçırma — 8-12bb'de ilk-giren ol.",
        ],
    },
    "bubble": {
        "headline": "💎 Bubble · ICM-baskısı + alan-exploit",
        "priorities": [
            "Para-baskısı AKTİF: marjinal coin-flip'ten KAÇ (call take-point yükselir).",
            "Stack-rolü: big=baskı uygula, orta=en kırılgan (ladder bekle), kısa=+cEV jam.",
            "Orta-stack'lerin over-fold'unu sömür; yumuşak-call yapışkan → barrel bırak.",
        ],
    },
    "itm": {
        "headline": "🎟 Para-içi · ladder bilinci",
        "priorities": [
            "Para geçildi → küçük baskı azalır ama pay-jump'lar yaklaşıyor, gözle.",
            "Accumulation penceresi: kısa-stack'ler ladder'a oynar → onları sömür.",
            "Büyük pay-jump öncesi yeniden ICM-sıkı moda gir.",
        ],
    },
    "final table": {
        "headline": "🏆 Final Masa · pay-jump maksimum",
        "priorities": [
            "Her elenme büyük $-sıçraması → bubble-factor en yüksek, call'ı çok sıkı tut.",
            "Big-stack: orta-stack'lere acımasız baskı (onlar ladder'a kilitli).",
            "Kısa-stack: jam'i geniş, call'ı dar; doğru anı bekle (ICM-defens).",
        ],
    },
}


def stage_plan(stage: str, hero_stack_bb: float = 0.0, avg_stack_bb: float = 0.0) -> dict:
    """Evrenin stratejik playbook'u → {"stage","headline","priorities":[...]}.
    Bilinmeyen evre → mid. Koç/kitap/akademi tek kaynaktan beslensin diye."""
    stg = (stage or "").lower().strip()
    plan = _STAGE_PLAN.get(stg) or _STAGE_PLAN["mid"]
    return {"stage": stg or "mid", "headline": plan["headline"],
            "priorities": list(plan["priorities"])}
