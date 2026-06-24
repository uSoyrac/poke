# SAYIM-MVP — Soyrac Rakip Okuma-Sayacı (Tasarım Blueprint)

> 16-agent ordusu (9 uzman + keşif + sentez + 3 düşmanca-denetçi + revize) çıktısı.
> Düşmanca-denetimden geçen savunulabilir çekirdek. Kaynak: workflow soyrac-opponent-read-system.

## Özet
SAYIM-MVP, reddedilen "60 değişkenli sahte tek-sayaç" tasarımının savunulabilir çekirdeğidir: masada villain başına SADECE bir tamsayı R taşınır ve R yalnız EL-İÇİ DİZİ sinyallerinden (check-raise, limp-3bet, cbet-checkledi, flat) güncellenir — bunlar tek elde gözlenir, örneklem gerektirmez, güven-kapısından MUAFTIR. Frekans-istatistiği (overfolder/station), shrunk_estimate, timing, Bayes-showdown, tazelik ve 4-hash payda çetelesi masadan TAMAMEN ÇIKARILIP HUD/panel/post-session katmanına taşınır; insan kafasından silinir. R'nin ölçeği range_narrowing._apply'daki sdelta motoruyla BİREBİR hizalanır (flat=−2, check-raise=+2 — motor tek-kaynak, cheatsheet motora uydurulur), böylece panel ve insan AYNI sayıyı bulur. +EV iddiası "log-olabilirlik toplamı" gibi kanıtlanmamış matematikten "kabaca-monoton güç-proxy" diline indirilir (DÜŞÜK-GÜVEN işaretli); korelasyonlu eş-sokak sinyalleri toplanmaz, max alınır (çift-sayım önlenir). Read-gated/advice-only kalır: villain yoksa R=prior, |R|<2 → identity → bot fidelity 0-sapma korunur.

## Karar-Sayma Mekaniği
### Sayaçlar
- R = OKUMA-SAYACI (villain başına TEK yürüyen tamsayı, el-başı tip-prior ile başlar, value-pozitif/zayıf-negatif). MASADA KAFADA TUTULAN TEK SAYI BUDUR. Motor ölçeğinde: flat −2, check-raise +2.
- TANIDIK-MI bayrağı (ikili, sayaç DEĞİL): 'bu villain'i bu spotta daha önce gördüm mü?' evet/hayır. Tek bit. Frekans paydası DEĞİL — sadece bir his-anahtarı. (NOT: bu bayrak bile opsiyonel; çekirdek dizi-okuması bayrak olmadan da çalışır.)
- KALDIRILAN SAYAÇLAR (artık masada YOK, HUD/panel-only): vpip-fırsat, cbet-karşı-fırsat, açılış-fırsat, showdown-sayısı, tazelik-durumu, Bayes-prior-güncellemesi. Bunlar 9 rakip × 4 payda + tazelik = 60+ değişken patlamasının kaynağıydı; motor/panel hesaplar, insan kafasında taşımaz.
### Artış Kuralları
- EL BAŞI PRIOR (R'yi tipe göre kur, tek-kaynak opponent_typology.HELLMUTH_ANIMALS['prior']): 🐘 Elephant R=+1, 🐭 Mouse/🦅 Eagle R=+1 (disiplinli/polar), 🦁 Lion R=0, 🐺 Jackal R=−1. Tip yoksa (MTT/ilk el) mikro-popülasyon prior R=0 (NÖTR — uydurma edge yok; veri yokken GTO-baza yakın dur). Prior ±1 ile sınırlı: tek başına |R|≥2 eşiğini AÇMAZ, sapma her zaman GÖZLENEN dizi gerektirir.
- DİZİ SİNYALİ — TEK GÜÇLÜ KAYNAK (motor _apply ile birebir, kapısız): preflop flat (3bet-yapmadı) = capped = −2 (motor sdelta −2.0); flop+ agresörün check'i (cbet YAPMADI) = give-up cap = −1; barrel/cbet = +1 (motor +0.8/+0.5 → round +1); check-raise / limp-3bet = POLARİZE-güçlü = +2 (motor +2.0); donk-lead = −0 (motor −0.3 → round 0, ihmal). Bunlar TEK ELDE gözlenir, örneklem-bağımsız, GÜVEN-KAPISINDAN MUAF.
- ÇİFT-SAYIM ÖNLEME (çekirdek kural): AYNI sokakta korelasyonlu iki zayıf-sinyal (örn. flat SONRA o sokakta cbet-checkledi) için sadece EN GÜÇLÜ olanı say (max |delta|, toplama YOK). 'flat −2' zaten 'capped'i söyler; arkasından gelen 'check −1' aynı bilgiyi tekrar saymaz → R şişmez.
- BOYUT SİNYALİ (DÜŞÜK ağırlık, tip-BAĞIMSIZ polar): overbet/büyük-bet (≥pot) = mevcut R'nin İŞARETİNİ büyüt (R>0 ise value-doğrula +1, R<0 ise zayıf-doğrula −1), YÖN SEÇTİRMEZ (tip prior'da zaten sayıldı, çift-çarpma yok). |R|=0 ise overbet'i ihmal et (belirsiz). Küçük/block-bet (≤1/3 pot) = −1 (capped). Yarım-pot = 0.
- TIMING SİNYALİ — VARSAYILAN KAPALI: multi-tabling'de 'tank' = başka masada aksiyon olabilir (sistematik yanlış-pozitif) → kullanıcı 2-3 masa oynadığını beyan ettiğinden timing DEFAULT OFF. Yalnız kullanıcı tek-masa modunu açıkça seçerse aktif (snap-call +1 / tank-call −1, asla tek başına ±2). Bot/panel hesaplamasında timing yok.
### Karar Kuralı
KARAR ANI (her sokak, özellikle river): (1) |R| < 2 → POSTERIOR BELİRSİZ → GTO-BAZ oyna (MDF/pot-odds, soyrac base advice). Bu varsayılan; uydurma edge önlenir. (2) R ≥ +2 (gözlenen dizi ile, prior tek başına değil) → villain VALUE-ağır/güçlü → bluff-catch BIRAK, marjinal fold, kendi blöfünü kes, büyük bahsine SAYGI. (3) R ≤ −2 → villain CAPPED/zayıf → ince value-bet'i büyüt + blöfle (give-up/capped), büyük bahsine saygı YOK. (4) DİZİ-KİLİDİ: check-raise veya limp-3bet gördün (R+2) → tek başına bile value-kilit, marjinali bırak (mikro'da neredeyse hiç blöf değil — bu en yüksek-sinyal/en düşük-varyans okuma). (5) GÜRÜLTÜ koruması: prior +1/−1 TEK BAŞINA sapma açmaz; eşik her zaman ≥1 gözlenen dizi-sinyali ister. Yanlış-prior şüphesinde (showdown çelişkisi) o oturum o villain için eşiği |R|≥3'e yükselt.

## Abdüktif Prosedür (masada)
1. 1) EL BAŞI: HUD'da zaten görünen classify_hellmuth(vpip,pfr,af) tipinden R prior'unu kur (🐘+1 🐺−1 🦁0, veri yok→0). Bu TEK bakış; payda çetelesi EZBERLEMEZSİN — onu HUD/panel tutar.
2. 2) BAŞLANGIÇ RANGE'İ (negatif çıkarım, range_narrowing.starting_range): villain açtı mı / flat mı / 3bet mi? Flat → premium SİL (capped, R−2 motor sdelta). 3bet → polarize (R kabaca nötr, polar-shape). Tek elde, kapısız.
3. 3) HER VILLAIN AKSİYONUNDA — NE YAPMADIĞINA bak (bridge negatif-çıkarım, _apply): cbet yapmadı → güçlü-value cap (−1); barrel attı → value (+1); check-raise → polar-güçlü (+2). SADECE R'yi güncelle, adımları kafanda tutma (panel rc_steps gösterir; sen sayıyı taşı). Çift-sayım önleme: aynı sokakta uyumlu iki sinyalden sadece en güçlüsü.
4. 4) RANGE-BİÇİMİ (range_narrowing._shape): biriken R + dizi → capped / polarized / strong / weak. Bu, P(range | tip-prior, gözlenen-dizi) posterior'unun insan-okunur etiketi — DÜŞÜK-GÜVEN: tamsayı puanlar kalibre olasılık değil, kabaca-monoton güç-proxy'si.
5. 5) KARAR: |R|<2 → GTO-baz. |R|≥2 (gözlenen dizi ile) → sapma (decision_rule). Prior tek başına yetmez.
6. 6) (POST-SESSION, masada DEĞİL) FREKANS KALİBRASYONU: overfolder/station, shrunk_estimate, showdown-Bayes, tazelik → oturum sonrası read_trainer/coach_engine katmanı bunları HUD-verisinden hesaplar ve tip-prior'u güncellenmiş haliyle BİR SONRAKİ oturuma taşır. İnsan masada yapmaz; sistem arka planda yapar.

## Tipoloji Entegrasyonu
classify_hellmuth (Mouse/Lion/Jackal/Elephant/Eagle) TEK-KAYNAK tipleme çekirdeği kalır ve statik etiketten EL-BAŞI PRIOR sayısına terfi eder (🐘+1 … 🐺−1), AMA prior ±1 ile sınırlanır: tek başına asla |R|≥2 sapma eşiğini açmaz — sapma DAİMA gözlenen el-içi dizi gerektirir. Bu, denetimdeki 'overbet tip-araması = çift-sayım' ve 'prior tek başına edge uydurur' kusurlarını giderir: tip yalnız başlangıç noktasını verir, kararı gözlenen aksiyon verir. opponent_typology.HELLMUTH_ANIMALS'a tek-satır 'prior' alanı (+1/0/−1) eklenir (tek-kaynak R başlangıç tablosu). Veri yokken prior=0 (NÖTR, GTO-baz) — mikro-popülasyon Elephant-eğilimi gibi ölçülmemiş varsayımlar prior'a GÖMÜLMEZ (uydurma edge yasak); o tür popülasyon-eğilimi yalnız post-session frekans katmanında, gerçek HUD verisiyle kalibre edilir. classify_hellmuth bot karar-yoluna (advice_from_hand) ASLA girmez; read-gated, advice-only.

## Okuma → Sapma
- DİZİ-KİLİDİ (örneklemsiz, en yüksek-güven, MASADA): check-raise / limp-3bet gördün → R+2 → tek elde bile value-kilit, marjinali bırak, kendi blöfünü kes (mikro'da bu hatların blöf payı çok düşük; pot-odds altı → fold +EV — DÜŞÜK-GÜVEN sayısal frekans, yön sağlam).
- FLAT-CAPPED (örneklemsiz, MASADA): villain önündeki raise'e 3bet-YAPMADI → R−2 (capped) → premium yok varsay; ince value-bet'i büyüt, büyük bahsine daha az saygı. range_narrowing 'capped' shape.
- CBET-GIVE-UP (örneklemsiz, MASADA): agresör flop'ta cbet YAPMADI (checkledi) → R−1 → range zayıfladı; bahse alan/blöf ekle.
- |R|<2 VEYA hiç dizi yok → GTO-BAZ: MDF/pot-odds, soyrac base advice. Posterior belirsiz → GTO'ya çök (varyans-cezası önlenir, uydurma edge yok).
- ÇİFT-SAYIM YASAK: aynı sokakta korelasyonlu uyumlu iki sinyal (flat + sonra check) → sadece en güçlüsünü say (max), TOPLAMA — yoksa R yapay şişer ve eşiği hak etmeden geçer.
- FREKANS-OKUMASI (overfolder/station/3bet-maniac) MASADA DEĞİL → HUD'a bak (cbet≥30, 3bet≥60, river-blöf≥80 el motor-eşikleri panelin işi). İnsan payda saymaz; panel yeşil 'yeterli veri' / gri 'az veri → GTO' ikili rozeti gösterir. shrunk_estimate, timing, Bayes-showdown, tazelik HEPSİ panel/post-session — masadan çıkarıldı.
- MTT (örneklem yok): el-içi DİZİ-okuması (range_narrowing) tek masada-yapılabilir MTT katmanı olarak çalışır; popülasyon-evre prior'u ölçülmemişse R=0 (nötr) — denetimdeki 'kapı micro'da hiç açılmaz = net-sıfır' kusuru, kapıyı dizi-sinyalinden KALDIRARAK çözülür (dizi örneklem istemez).

## Masa Cheatsheet
- SAYIM-MVP — masada villain başına TEK sayı R taşı (value+ / zayıf−)
- EL BAŞI PRIOR (±1, tek başına sapma AÇMAZ): 🐘+1  🐭/🦅+1  🦁 0  🐺−1  (veri yok→0)
- DİZİ (TEK güçlü kaynak, örneklemsiz): flat=capped −2 · cbet-checkledi −1 · barrel +1 · check-raise/limp-3bet +2
- ÇİFT-SAYMA: aynı sokakta uyumlu iki zayıf-sinyal → sadece EN GÜÇLÜSÜ (max, toplama yok)
- BOYUT (düşük, tip-bağımsız): overbet → mevcut R'nin işaretini ±1 büyüt · block/küçük −1 · yarım-pot 0
- TIMING: VARSAYILAN KAPALI (multi-table gürültü) — yalnız tek-masa modunda aç
- KARAR: R≥+2 (gözlenen dizi ile) → FOLD marjinal, blöf kes | R≤−2 → ince value+blöf | |R|<2 → GTO
- DİZİ-KİLİT: check-raise/limp-3bet tek başına = value-kilit, marjinali bırak
- FREKANS/payda/showdown-kalibre → MASADA DEĞİL, panele/HUD'a bırak (yeşil=veri var, gri=GTO)

## Mimari
**Modüller:**
- YENİ app/poker/read_count.py (saf, advice-only): read_count(villain_type, events, *, prior_table=None) -> ReadCount{R:int, prior:int, shape:str, confidence:'low/high', read:str, deviation:str, steps:[...]}. range_narrowing.narrow()'ın running_count/rc_steps motorunu YENİDEN KULLANIR (sdelta ölçeği TEK-KAYNAK), üstüne SADECE (a) tip-prior başlatma (±1 cap), (b) çift-sayım-önleme (eş-sokak korelasyonlu sinyalde max), (c) ikili confidence (gözlenen dizi var mı). FREKANS/shrunk/timing/Bayes BU MODÜLDE YOK — onlar ayrı post-session katman.
- HİZALAMA TESTİ (D-A'dan ÖNCE, denetim talebi): test_read_count_scale_alignment — range_narrowing._apply'ın HER branch'i için int(round(sdelta)) == cheatsheet değeri (flat→−2, check-raise→+2, barrel→+1, cbet-check→−1, donk→0). Panel ve insan asla farklı sayı bulamaz; motor değişirse test kırılır.
- GENİŞLET opponent_typology: HELLMUTH_ANIMALS'a 'prior' alanı (🐘+1 🐭+1 🦁0 🐺−1 🦅+1), prior ±1 ile sınırlı. Tek-kaynak R başlangıç tablosu.
- AYRI KATMAN (post-session, masada-değil) exploit_advice.deviation_index + YENİ shrunk_estimate(observed,opps,prior_mean,prior_strength) + recency_weight: bunlar HUD/panel tarafında çalışır, read_count'a el-içi GİRMEZ. DEVIATION_INDEX min_hands eşikleri (cbet30/3bet60/river80) KORUNUR ama yalnız FREKANS rozetini (yeşil/gri) sürer; DİZİ okumasını ASLA gate'lemez.
- GENİŞLET read_trainer: yeni drill 'R tahmin et' (aksiyon-dizisi ver → kullanıcı R + sapma söyler). Frekans/timing/showdown-kalibrasyonu post-session öğretim olarak burada kalır (masada değil).
- GENİŞLET SoyracCoachPanel 3. mod: tek-sayı R + rc_steps (kafadan-toplamı doğrula) + ikili güven rozeti (yeşil 'dizi gözlendi' / gri 'GTO-baz') + read→sapma satırı. Payda/shrunk sayıları KULLANICIYA gösterilmez (yalnız yeşil/gri).

**Veri-modeli:** ReadCount dataclass {R:int, prior:int, shape:str, confidence:'low/high', read:str, deviation:str, steps:List[str]}. confidence = (gözlenen el-içi dizi-sinyali var mı?) ikili türetimi — payda eşiği DEĞİL. FREKANS katmanı AYRI: deviation_index çıktısı {live, pending, need_more} panel-only. Timing alanı decision_capture'a opsiyonel eklenir ama VARSAYILAN OFF (multi-table). Showdown ifşaları post-session kalibrasyon için toplanır; el-içi R'ye girmez. R'nin ölçeği range_narrowing.sdelta ile birebir (tek veri-kaynağı).

**Koç-hook:** soyrac_explain(villain_stats verildiğinde) read_count'u EK katman olarak çağırır → çıktıya 'read_count' alanı (R, shape, read, deviation, steps) + ikili confidence. gto_live_advice.LiveAdvice'a exploit_note YANINDA 'read_count_note'. _villain_continuing_range (bet-boyutu) zaten var → R'nin boyut-deltasını (tip-bağımsız polar) besler. soyrac base advice_from_hand'e ASLA dokunulmaz; villain yok → R=prior, |R|<2 → identity (GTO-baz döner). FREKANS rozeti ayrı hook'tan (deviation_index) gelir, R-akışına karışmaz.

**Fidelity:** KESİN read-gated: read_count yalnız soyrac_explain'in villain_stats yolundan akar (advice-only). Bot-vs-bot simde villain_type/villain_stats beslenmez → R=prior(0), |R|<2 → identity → sapma 'GTO' kalır → test_bot_archetype_fidelity 0-sapma KORUNUR. read_count saf fonksiyon, advice_from_hand'i import etmez. Prior ±1 cap + dizi-zorunluluğu, prior'un tek başına bot-yolunu kıpırdatmasını da imkansız kılar. Guard testleri: test_read_count_identity (villain yok→GTO), test_read_count_scale_alignment (motor=cheatsheet), test_read_count_prior_alone_no_deviation (prior tek başına |R|<2), test_bot_archetype_fidelity DEĞİŞMEDEN geçer.

## Uygulama Planı
- **[D-A0]** ÖNCE hizalama testi (denetim şartı): test_read_count_scale_alignment yaz — range_narrowing._apply'ın her branch'i için int(round(sdelta)) cheatsheet değerine eşit (flat=−2, check-raise=+2, barrel=+1, cbet-check=−1, donk=0). Bu test geçmeden D-A'ya BAŞLAMA; motor=panel=insan tek ölçek garantisi.
- **[D-A]** read_count.py iskeleti: range_narrowing.narrow()'ı sar (sdelta tek-kaynak), opponent_typology.HELLMUTH_ANIMALS['prior'] (±1) ile R başlat, R+shape+steps+ikili-confidence döndür. Saf, advice-only, frekans/timing/showdown YOK. Test: prior tablosu + identity (villain yok→R=0→GTO) + prior-tek-başına-sapma-yok.
- **[D-B]** Çift-sayım önleme + boyut deltası: eş-sokak korelasyonlu sinyalde max(|delta|) (toplama yok); overbet tip-BAĞIMSIZ polar (mevcut R işaretini ±1 büyüt, yön seçtirmez). Test: worked_example — flat+sonra-check tek −2 kalır (şişmez); overbet R>0 iken +1, R<0 iken −1, R=0 iken ihmal.
- **[D-C]** DİZİ vs FREKANS ayrımı: read_count confidence='high' ASLA payda istemez (dizi gözlendiyse high). exploit_advice.deviation_index + shrunk_estimate AYRI panel-katman; min_hands eşikleri yalnız FREKANS rozetini (yeşil/gri) sürer, dizi-okumasını gate'LEMEZ. Test: n=2 fold-to-cbet %100 → frekans rozeti gri (pending) AMA check-raise dizi-okuması yine R+2 (kapıdan muaf).
- **[D-D]** soyrac_explain + gto_live_advice hook: villain_stats verildiğinde read_count'u EK katman olarak çağır, çıktıya read_count_note ekle. base advice_from_hand'e dokunma. timing VARSAYILAN OFF. Test: test_advice_consistency'ye R-katmanı eklenir, test_bot_archetype_fidelity değişmeden geçer.
- **[D-E]** SoyracCoachPanel 3. mod + read_trainer 'R tahmin et' drill'i + post-session kalibrasyon (frekans/showdown/tazelik coach_engine'de, masada değil). Panel: tek-sayı R + rc_steps + ikili yeşil/gri rozet + read→sapma. Payda/shrunk sayıları kullanıcıya GÖSTERME. UI empati render (PNG) ile doğrula (MEMORY kuralı).

## Kitap Taslağı
- Böl X.1 — SAYIM-MVP felsefesi: blackjack analojisinin SINIRI (true-count tektir; poker'de villain-başına ayrı sayaç → masada SADECE el-içi dizi taşınır, frekans HUD'un işi)
- Böl X.2 — Tek sayı R: el-başı prior (tipten, ±1) + dizi-deltası (motor ölçeği: flat −2, check-raise +2)
- Böl X.3 — Dizi-okuması neden örneklem-istemez: check-raise/limp-3bet/flat tek elde okunur; en yüksek-sinyal en düşük-varyans
- Böl X.4 — Çift-sayım tuzağı: korelasyonlu eş-sokak sinyalleri toplama, max al
- Böl X.5 — Karar eşiği: |R|<2 GTO-baz (belirsizde uydurma edge yok), |R|≥2 sapma; prior tek başına yetmez
- Böl X.6 — MASADA OLMAYANLAR: frekans-stat, shrunk_estimate, timing (multi-table gürültü), Bayes-showdown, tazelik → HUD/panel/post-session
- Böl X.7 — +EV gerekçesi (DÜŞÜK-GÜVEN dilinde): kabaca-monoton güç-proxy, kanıtlanmış log-LR DEĞİL; belirsizde GTO'ya çökme varyansı kontrol eder
- Böl X.8 — Read-gated güvenlik: okuma yoksa identity, bot fidelity 0-sapma
- Böl X.9 — Masa fişi (cheatsheet) + 'R tahmin et' drill'i

## Açık Sorular
- Prior'u veri-yokken 0 (nötr) tutmak güvenli ama mikro-popülasyonun gerçekten Elephant-eğilimli olup olmadığı ölçülmeli (post-session HUD agregasyonu): eğer gerçek veriyle kanıtlanırsa popülasyon-prior +1'e çekilebilir — ama ÖNCE ölçüm, sonra prior (uydurma edge yasak).
- Motor sdelta ölçeği (flat −2) ile insan-sezgisi (flat 'biraz zayıf' ≈ −1) arasındaki uçurum: hizalama testi motoru kaynak yapıyor ama kullanıcı −2'yi fazla agresif bulursa motor sdelta'ları yeniden kalibre edilmeli (test de güncellenir) — hangisi öğretimde daha sağlam, masa-testiyle ölç.
- Çift-sayım için 'korelasyonlu eş-sokak sinyali' tanımı netleştirilmeli: hangi sinyal çiftleri korelasyonlu sayılır (flat+check evet; flat+sonraki-sokak-barrel hayır)? read_count._apply içinde açık bir korelasyon-grubu tablosu gerekir.
- İkili confidence ('dizi gözlendi mi') yeterince ayrıştırıcı mı, yoksa 'kaç dizi-sinyali' (1 vs 2+) üç-kademeli mi olmalı? Tek dizi-sinyalinden sapma bazı spotlarda hâlâ riskli olabilir — masa-simiyle test et.
- Timing varsayılan-OFF doğru ama kullanıcı gerçekten tek-masa oynadığında değerli sinyal kaybı var; tek-masa modu otomatik algılanabilir mi (aktif-masa sayısı) yoksa manuel beyan mı?
- Post-session frekans katmanının tip-prior'u bir sonraki oturuma taşıması (showdown-Bayes) gerçek HUD veri-yoğunluğunda anlamlı kalibrasyon sağlıyor mu, yoksa mikro-örneklemde gürültü mü — gerçek oturum verisiyle doğrulanmalı.