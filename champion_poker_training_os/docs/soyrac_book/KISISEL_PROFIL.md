# Senin Soyrac+ Kişisel Profilin

## 1. Özet

Sen Soyrac kitabından ellerin **%18'inde** sapıyorsun (2960 elin 532'si). Kritik bulgu: sapma oranın kazanılan turnuvalarda da elenmiş turnuvalarda da neredeyse **aynı (%19 vs %18)** — yani seni batıran "ne kadar saptığın" değil, **hangi sapma**. Sapmalarının bir kısmı gerçek **+EV touch** (soft field'e karşı doğru exploit, KORU); bir kısmı ise gerçek **-EV leak** (özellikle blind defense kaosu ve junk savunma, DÜZELT). İş, bu ikisini birbirinden ayırıp doğru tarafı kesmek.

---

## 2. Senin Dokunuşun (KORU)

Bunlar veriyle kanıtlanmış +EV exploit'lerin. Nit'e dönüp bunları öldürme.

| Touch | Veri | İnsan-kuralı (KORU) |
|---|---|---|
| **Loose call (sen CALL, Soyrac FOLD)** | 63 sapma, sadece 8 bust (%13 — tüm datadaki **EN DÜŞÜK** bust oranı) | Fold çizgisinin biraz altında call et — **AMA SADECE**: in position + suited/connected + station villain. Pozisyon dışıysa veya el çöpse → fold. |
| **Spekülatif eli raise yerine flat (sen CALL, Soyrac RAISE)** | 144 sapma, 22 bust (%15 — baseline %18'in **altında**) | Tek raiser'a karşı pair/suited-connector/suited-ace: **effective stack ÷ call maliyeti ≥ 10** ise VE 2+ rakip flop görecekse VEYA raiser station ise FLAT. Ucuz flop gör, station'lardan implied odds topla. |
| **Multiway'de korkutucu overcard turn'de "rakipte A var" varsayımı** | Self-flagged, doğru | Multiway + scary overcard turn → top pair'i değer eli sanma, A'yı varsay. |
| **Tight UTG range'e karşı two-pair'i ödememek** | Self-flagged, doğru | Tight UTG opener big pot kurarken marjinal/orta gücü pay-off etme. |

**Temel mantra:** İndirimli fiyat (pot-odds) dominasyonu düzeltmez — ama station'a karşı **playable** orta eli ucuz flop için flat etmek doğru exploit.

---

## 3. Senin Leak'lerin (DÜZELT)

Maliyet sırasına göre (bust katkısı + hacim).

| # | Leak | Veri | Düzeltme-kuralı (integer, insan-hesabı) |
|---|---|---|---|
| **1** | **Junk/spekülatif over-defend (J2s, Q4s, K6o)** | 96 sapma, **25 bust (%26 — en yüksek bust payı)**; vsRFI-BB'de %70 sapma | Çöpü SADECE: **BB + son aksiyon + pot'ta 2+ kişi** varken indirimle savun. Başka her şey → FOLD. BB call eşiği SHCP **6 base**, opener'la yükselir: **+4 vs UTG/UTG+1, +3 vs MP/LJ, +2 vs HJ, +1 vs CO, +0 vs BTN/SB, +1 turnuvada**. UTG'ye karşı gerçek barın **11**. J2s ~5 puan → her barın altında → KATLA. |
| **2** | **Too-wide open (eşik altı RFI)** | 56 sapma, **24 bust (%43 — datadaki EN KÖTÜ oran, baseline'ın 2 katı)** | RFI saf pozisyon eşiği: **UTG 15, UTG+1 15, MP 14, LJ 13, HJ 12, CO 11, BTN 8, SB 9.** Pozisyon puana EKLENMEZ, sadece barı belirler. Stack barı yükseltir: **≤40bb +1, ≤25bb +2.** Score < bar → FOLD. **İstisna:** turnuvada late position (CO/BTN/SB) pre-empt/steal katmanı barı bilerek indirir (yarım pre-empt width) — bu meşru, leak değil. Erken/orta koltuk ve cash'i denetle. |
| **3** | **Raise yerine flat'i tersine çevirme (sen RAISE, Soyrac CALL)** | 72 sapma, 19 bust (%26) | Set-miner/connector'ı raise'e çevirme. 3-bet for value SADECE: el raiser'ın **calling range'inin önündeyse (JJ+/AQs+/AK)** veya late opener'a karşı blocker-bluff (A5s-A2s/Kxs). "Jam yerse nefret edeceğim bir el" raise ediyorsan → flat. Agresyon **value 3-bet'lerinde ve steal'lerinde** olmalı, set-miner'da değil. |
| **4** | **3-bet pot over-call (non-premium)** | 39 sapma, 10 bust (%26) | Başlatmadığın 3-bet pot'ta SHCP'den **B4 blocker eksenine** geç. **4-BET sadece B4 ≥ 2 (QQ+/AK + A5s-A2s).** FLAT sadece güçlü continue tier (**SHCP ≥ 18: JJ+/AQs+/KQs**). Derin (>45bb) value-4bet barı 27 ve B4 ≥ 2 gate'li → TT-88 set için call-or-fold. Gerisi FOLD. Mantra: **"3-bet pot'ta A5s, AJs'yi döver — A5s AA/AK'yı blocklar, AJs hiçbir şeyi blocklamaz ve dominated."** |
| **5** | **Over-3bet (non-premium)** | 22 sapma, 0 bust | Station'a fold equity yok. 3-bet: premium VEYA wheel-ace/Kxs blocker (late opener'a) — arası YOK. Aradakini → flat veya fold. |
| **6** | **Over-tight (sen FOLD, Soyrac CALL)** | 24 sapma, 0 bust | "Güvenli" ama soft field'de para masada bırakıyor. Non-ICM ve station'a karşı call çizgisine GÜVEN. Ekstra sıkılığı **sadece bubble/FT** için sakla (D208: turnuvada call_t +3 ICM doğru). |
| **7** | **Missed value open (çok tight)** | 14 sapma, 0 bust | Eşiği tam karşılayan eli muck etme. Late position steal istiyorsun ama bazen meşru open'ı pas geçiyorsun. **Score ≥ RFI eşiği → aç, sinir yüzünden tighter yapma.** |
| **8** | **Over-4bet (non-premium)** | 3 sapma | Hacim ihmal edilebilir ama kategorik leak. 4-bet sadece **QQ+/AK** veya derin (40bb+) wide 3-bettor'a karşı wheel-ace blocker-bluff. |

**Çıplak gerçek:** #1 (junk-defend, 25 bust) ve #2 (too-wide open, 24 bust) tek başına bust'larının yarısı. İkisi de blind/eşik disiplini. Diğer her şeyden önce bu ikisi.

---

## 4. Drill Planı

| Hedef | Drill | Başarı metriği | Öncelik |
|---|---|---|---|
| **Junk blind-defend (#1 bust-leak)** | Academy M3 vsRFI, zorluk 2. Günde 40 spot BB/SB tek open'a karşı. Cevaptan önce SHCP skoru + koltuk call eşiğini **sesli söyle**. Yanlışları "junk pile"a at, spaced-rep ile yeniden test et. | vsRFI-BB sapma %70→<%20; junk-defend/1000 el ~32→<12; junk-pile re-test M3 mastery (≥%85, streak 6); bust listesinde junk-defend 25→tek haneye. | **5** |
| **SB/BB blind defense kaosu** | Academy M3, SB only, zorluk 3. Günde 30 spot. Her eli aksiyondan ÖNCE **3-BET / FLAT / FOLD** kovasına at. SB OOP → flat tuzak kova. "Flat dedim ama kitap FOLD dedi" anlarını logla. | vsRFI-SB sapma %47→<%25; loose-call sayısı (63) yarıya. SB Academy M3 mastery. SB call ≥ SHCP 9 (+opener-adj, +1 turnuva, SB -1 delta), 3-bet ≥ 17. | **5** |
| **Too-wide open (#2 bust-leak)** | Academy M2 RFI flashcard, tüm pozisyonlar, zorluk 2. Günde 50 spot, ağırlık UTG/MP/HJ. Önce eşiği söyle, SONRA el skoru, sonra karar. | RFI sapma <%10; too-wide open 56→<20/2960 el; bust'taki too-wide 24→<8; M2 mastery. (Late-position turnuva steal'ini denetleme — meşru.) | **4** |
| **3-bet pot over-call** | Academy M4 vs-3bet, zorluk 2-3. Günde 30 spot. Her ele B4 skoru söyle, 4-BET/CALL/FOLD ata. Derin 100bb tuzak elleri (JJ-88, AJs/KQs) özel drill. Call edip kitap fold dediğin spotları yeniden çalış. | 3-bet pot over-call 39→<15; bust katkısı 10→<4; M4 mastery. | **4** |
| **Flat/raise inversion (her iki yön)** | Academy M3 vsRFI, zorluk 3, karışık pozisyon, günde 30 spot. İki bar: call ≥ call_t, 3-bet ≥ raise_t. Tek skorla → bandı bul. Üst band RAISE, orta band FLAT (touch'ı korur), call_t altı FOLD. "Should've raised" / "should've flatted" iki sütun tut. | Birleşik inversion 216→<120; over-3bet 22→<8; bust katkısı 41→yarıya; M3 karışık mastery. | **3** |
| **Anti-nit guard (touch'ları koru)** | Haftalık M2/M3/M7 karışık seans. YANLIŞ fold'ları yakala — sıkılaşan içgüdün FOLD derken kitap CALL/RAISE diyorsa. Haftada 20 spot. Cash/soft → orta band kalır; turnuva late → steal kalır. | Over-tight+missed-open (24+14=38) DİĞER leak'ler düşerken YÜKSELMESİN; aligned% %82→%90+ olurken VPIP/agresyon çökmesin. | **2** |

---

## 5. Tek cümle

**Top-1% için en yüksek kaldıraçlı tek değişiklik: blind disiplini — özellikle BB'de J2s tipi çöpü savunmayı ve eşik altı open'ları kes (bust'larının yarısı bu ikisi), ama loose-call ve ucuz-flop touch'ını ASLA nit'e dönüştürerek öldürme.**