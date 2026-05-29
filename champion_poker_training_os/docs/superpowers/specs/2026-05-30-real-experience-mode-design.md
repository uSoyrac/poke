# Phase D1 — Real Experience Mode + Decision Grading

**Tarih:** 2026-05-30
**Durum:** Onaylandı (kullanıcı: "optimal ve en yararlı olanı seç ve devam et")

## Problem

Kullanıcı gerçek oyun deneyimi istiyor: turnuva/play sırasında ekranda GTO
önerisini görmek istemiyor (spoiler). GTO geri bildirimini **el bitince, yeni
ele geçmeden önce** istiyor — kararını notlandırılmış olarak görmek istiyor.

Mevcut durum (tutarsız):
- `play_session`: buton %'leri zaten gizli (`lbl()` cevabı sızdırmıyor),
  `gto_range` paneli `reveal_action=False` ile "? KARARINI VER" gösteriyor.
- `tournament_simulator`: `gto_range.update_range(...)` `reveal_action=True`
  (varsayılan) → "AA RAISE 100%" badge'i mid-hand sızdırıyor (kullanıcının
  ekran görüntüsündeki leak).
- El sonu `GTODecisionReveal` paneli var ama notlandırma yok; bloklamıyor.

## Çözüm — iki parça

### 1. Notlandırma motoru (`app/poker/decision_grade.py`) — saf fonksiyon

UI'dan bağımsız, test edilebilir. D1 (reveal) + D2 (skor kartı) + persist üçü
de kullanır.

```
@dataclass DecisionGrade: letter (A-F), score (0-100), ev_loss (bb), note
grade_decision(snap: dict) -> DecisionGrade
grade_hand(decisions: list[dict]) -> HandGrade(letter, score, n_decisions, ev_loss_total)
```

**Kural** (snapshot: fold/call/raise/allin GTO %, equity, pot_bb, to_call_bb,
hero_action):
- `hero_freq` = GTO'nun hero'nun aldığı aksiyona verdiği % (CHECK→call slot)
- En yüksek-frekans GTO aksiyonu seçildi **veya** `hero_freq ≥ 60` → **A**
- `hero_freq ≥ 35` → **B** · `≥ 15` → **C** · `< 15` → **D**
- EV overlay: `ev_loss > 1.5bb` → en fazla C'ye düşür; `ev_loss > 4bb` → **F**
- `available=False` (postflop solver yok) → notlandırma yok (None/N/A)
- Harf→puan: A=100, B=80, C=60, D=35, F=10. El skoru = ortalama.

### 2. Real Experience Mode (toggle + gizleme + bloklayan grade'li reveal)

- **State:** `AppState.real_experience: bool = False`.
- **Toggle:** topbar'da tıklanır hücre (`REAL` yeşil / `TRAIN` muted),
  `experience_toggled` Signal → `MainWindow` aktif ekranın
  `apply_experience_mode()`'unu çağırır.
- **Gizleme:** her iki ekranın `gto_range` güncelleme bloğu — `real_experience`
  açıkken panel tamamen gizli (`setVisible(False)`); kapalıyken görünür +
  `reveal_action=False` (tournament tutarsızlığı da düzeltilir). Butonlar zaten
  temiz; pot/stack/board normal.
- **Bloklayan reveal:** `GTODecisionReveal.show_decisions(decisions, graded)` —
  `graded=True` iken üstte **el skoru başlığı** (harf + %) + her satırda grade
  rozeti + "SPACE → sonraki el" ipucu. El sonu zaten `next_btn` gösterip space
  bekliyor → doğal blocking. Tek istisna: **fold→space hızlı-ileri** yolu
  (`_fast_forward_then_next`) `real_experience` açıkken reveal'ı atlamamalı:
  ilk space fast-forward + reveal göster, ikinci space sonraki el.
  `real_experience` kapalıyken bugünkü hızlı davranış korunur (#41).

## Mimari / izolasyon

- `decision_grade.py` saf fonksiyon, hiçbir Qt/DB bağımlılığı yok.
- Reveal widget grade'i import edip render eder; grading mantığını içermez.
- Gizleme mantığı her ekranın kendi `apply_experience_mode()`'unda; topbar
  sadece flag'i çevirir + sinyal yayar (gizleme bilgisi yok).

## Test

- `tests/test_decision_grade.py`: A/B/C/D/F sınırları, EV overlay, en-yüksek-frekans
  kuralı, available=False, grade_hand ortalaması.
- Offscreen PNG render: real_experience ON play_session (gto_range gizli) +
  graded reveal görünümü → UI empati kontrolü.
- Mevcut suite + feature audit regresyon.

## Kapsam dışı (sonraki fazlar)

- D2 session skor kartı ekranı, D3 postflop board-texture GTO beyni,
  D4 hatadan drill. D1 motoru + mode bunların temelini atar.
