# Soyrac — Test & Optimizasyon Düzeni (kalıcı bilimsel döngü)

> Kullanıcı: *"soru üret, hipotez üret, test et, optimize et, kontrol et — böyle çalış."*
> Bu doküman o döngüyü ve onu yürüten araçları (agent sistemleri + scriptler) tek yerde toplar.
> Amaç: sistem **hatasız** ve **+EV-MAX** kalsın; her değişiklik **kanıtla** girsin, **kazanmazsa geri alınsın**.

## 0. Değişmez disiplin (her test bunlara uyar)
- **+EV = TOPLAM EV.** Tek kova/tek senaryo iyileşmesi yetmez; toplam cash/MTT bakılır.
- **Kazanmazsa geri al.** Bir tweak deterministik A/B'de net kazanmıyorsa REVERT (sıfır istisna).
- **Cash tweak'i tek koşuyla onaylama.** En az çok-hücre + çok-seed.
- **base chip-EV / SHCP range'lerine DOKUNMA.** ICM/exploit/okuma ayrı KATMAN; advice-only (bot/sim default kapalı → fidelity 0-sapma).
- **bot = advisor = kitap.** Üçü aynı kararı vermeli (delege yok). `test_advisor_book_consistency` + `soyrac_audit_book` bunu bekçiler.
- **%100 insan-hesaplanabilir.** Masada MC/solver/ICM-delege YASAK; precompute/heuristik OK.
- **GTO-accuracy ÖLÇER, hedef DEĞİL.** Gerekçeli (+EV) sapma hata değildir.
- **SİMÜLASYON = GERÇEK OYNATMA.** Sonucu varsayma; oynat, ölç.

## 1. Döngü (5 adım)
1. **SORU** — net, ölçülebilir. ("50bb/1000'de küçük çiftler sızdırıyor mu?")
2. **HİPOTEZ** — yön + mekanizma. ("Küçük çift 3-bet/squeeze -EV; set-mine call +EV.")
3. **TEST** — aşağıdaki araçlardan uygun olanı; **deterministik** (aynı seed önce/sonra).
4. **OPTİMİZE** — yalnız kanıt +EV ise; advice-katmanı tercih, base'e dokunma.
5. **KONTROL** — regresyon yok mu (matrix re-run), fidelity 0 mu, kitap=sistem mi; değilse geri al.

## 2. Araçlar (standing test/optimizer sistemi)

| Araç | Ne yapar | Ne zaman |
|---|---|---|
| `tools/soyrac_audit_book.py` | Kitaptaki HER sayıyı motora karşı doğrular (SHCP/eşik/tier). Çıkış 1 = hata. | Kitap her düzenlemesinden sonra |
| `tests/test_advisor_book_consistency.py` | advisor↔kitap tutarlılık CI-guard'ı | Her commit |
| `tools/soyrac_matrix_sim.py` | Cash+SNG çok-hücre **deterministik** +EV ölçümü (profil×masa×stack) | Her base/postflop tweak |
| `tools/soyrac_realistic_mtt.py` | Gerçekçi alan MTT (ITM/ROI, top-heavy ödeme) | MTT stratejisi |
| `tools/soyrac_hand_logger.py` + `soyrac_hand_report.py` | El-el / el-sınıfı / pozisyon / aşama kâr dökümü (leak avı) | "Hangi el/hat sızdırıyor?" |
| `scratchpad/wf_decision_tree.js` (workflow) | Çok-ajanlı **denetim** (GTO+exploit, çekişmeli doğrulama) + **öğretim üretimi** | Kapsamlı "sistem mükemmel mi" + kitap bölümü |
| `tests/test_bot_archetype_fidelity` (script) | Bot davranışı 0-sapma bekçisi | Her bot-dokunuşu |

### Deterministik A/B kalıbı (D286)
`cash_table/run_cash/run_sng` koşu başında `random.seed(seed)` → deck deterministik.
A/B: aynı seed seti ile önce (toggle OFF) ve sonra (ON) koş, farkı oku. **Non-deterministik koşuda tek-hücre/küçük-fark OKUNAMAZ** (yalnız grand-mean + yön güvenilir).

### Çok-ajanlı denetim workflow'u
`Workflow({scriptPath: ".../wf_decision_tree.js", args: {...motor-gerçeği...}})`.
Fazlar: **Denetim** (her karar-düğümü GTO+exploit açısından) → **Doğrula** (her sızıntı adayı çekişmeli çürütülür: +EV ise hata değil) → **Öğret** (sokak-sokak neden-li tablolu HTML üretir). Ajanların TEK kaynağı motor-gerçeği (uydurma yok); çıktı motora karşı tekrar doğrulanır.

## 3. Bilinen +EV-FRONTIER (sızıntı SANMA — "kovala, kazanmıyorsa dokunma")
Bunlar defalarca denendi, **kazanmadı → geri alındı**. Tekrar "fix" deneme:
- **vs-3bet pot negatifliği** (D290-291) — yapısal açış-maliyeti + varyans; sıkılaştırma toplam cash'i bozar.
- **Derin bluff-catch sıkılaştırma** (D311) + **shallow value-cap** (D309) + **small-ball sizing** (D320) — saha öder, küçültmek -EV.
- **ICM-postflop survival lever** (D225) — ITM'i min-cash'e takas eder, top-heavy'de yanlış yön.
- **Küçük-alan (45-kişi) micro** zayıf — kod-bug değil, STRATEJİ: 180+ alan oyna.

## 4. Geçmişe dönük "kontrol" listesi (regresyon checklist)
Her değişiklik sonrası: ☐ `soyrac_audit_book.py` temiz ☐ `test_advisor_book_consistency` 7/7 ☐ fidelity 0 ☐ matrix grand-mean düşmedi ☐ kitap=advisor ☐ kazanan değilse REVERT.
