# Solver-Anchored Elit Bot — Plan (çok-oturumluk)

**Hedef:** "GTO Expert / Solver Bot" gerçekten daha iyi KARAR versin → edge
emergent + hak edilmiş olsun (etiket değil). Kullanıcı gerçek pro'ya karşı
antren etsin.

## Fizibilite duvarı (kritik)
- Real-time CFR/TexasSolver simde İMKANSIZ (spot başına saniyeler; 180k el).
- TexasSolver adapter (arms-length subprocess) yalnız **Solver Sandbox** için.
- ⇒ Bot için **precomputed / solver-anchored** strateji şart (real-time çözüm değil).
- **Deneyle öğrenildi (geri alındı):** loose get_action range'lerini bota vermek
  ONU KÖTÜLEŞTİRDİ (geniş preflop + zayıf postflop → chip sızdırır). Preflop
  genişliğini postflop yetkinlik DESTEKLEMELİ.

## İki bağlam
- (a) Kitlesel sim (analiz) → hafif, precomputed strateji.
- (b) Canlı antrenman masası (Pro Klasmanı, 5-8 bot, tek masa) → karar başına
  daha ağır hesap affordable (ileride opsiyonel TexasSolver anchor).

## Mimari — solver-ANCHORED (real-time CFR değil)
- **Preflop:** solver-kalite, SIKI/disiplinli chart'lar (loose get_action DEĞİL).
  Mevcut profile-sized open + D102 PFR-fix iyi başlangıç; 3bet/4bet disiplini ekle.
- **Postflop:** `postflop_gto.cbet_strategy` (polarizasyon/MDF/board-texture) +
  `defend_strategy` (MDF/equity) + `range_advantage` (kim bahis atmalı). Solver-
  prensipli, feasible.

## Fazlar (her biri SİMLE doğrulanır — kazanmıyorsa iterate/revert)
- **Faz 1:** GTO Expert postflop'unu cbet/defend_strategy'ye route et (preflop
  sıkı kalır). Gated. Sim: GTO Expert win/ITM yükseldi mi? ← BURADAYIZ
- **Faz 2:** 3bet/4bet preflop disiplini (light call/4bet yok → spew azalt).
- **Faz 3:** Solver Bot + ICM Expert'e genişlet; bubble'da icm_tighten.
- **Faz 4 (ops):** Canlı Pro masasında TexasSolver-anchor (few-bot, real-time).

## Değişmez kurallar
- Her adım: fidelity 0-sapma + test_gto_accuracy korunur, simle DOĞRULA (varsayma).
- Gated: yalnız GTO arketipleri değişir → diğer fidelity bozulmaz.
- Kazanmayan değişiklik = geri al (Faz-0 deneyi gibi).
