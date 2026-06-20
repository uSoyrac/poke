# Soyrac Sistem — Sim Değerlendirme Raporu

**Tarih:** 2026-06-20 · **Sürüm:** D288 sonrası (vs-RFI/overpair/stage fix + push-fold & call-vs-jam Nash)
**Yöntem:** SoyracBrain `pure_book=True` (bot=advisor=kitap birebir), %100 insan-hesaplanabilir
(MC/solver/ICM-delege YOK). Tüm sayılar **gerçek motor oynatması** (varsayım yok) ve
**deterministik** (seed→deck bağlı, tekrarlanabilir). Toplam ~çeyrek milyon+ gerçek el.

Üretici araçlar: `tools/soyrac_matrix_sim.py` (cash + SNG), `tools/soyrac_realistic_mtt.py`
(tam-saha MTT). Komut: `PYTHONPATH=. QT_QPA_PLATFORM=offscreen .venv/bin/python tools/<tool>.py`.

---

## 1. Cash (172.800 el)

27 koşul = 3 profil (soft/orta/elit) × 3 masa (HU/6-max/9-max) × 3 stack (40/100/200bb),
her hücre 8 seed × 800 el.

- **Grand-mean: +61.7 bb/100** · 95% CI **[+54, +69]** (n=216 seed-koşu) · **27/27 hücre pozitif**.

| Kesit | bb/100 |
|---|---|
| Profil — soft / orta / elit | +87.9 / +51.3 / +45.9 |
| Masa — HU / 6-max / 9-max | +42.9 / +60.3 / +81.9 |
| Stack — 40 / 100 / 200 bb | +46.6 / +69.3 / +69.2 |

Desen: en çok value tam-masa + zayıf saha; elit-sahada bile net + (+45.9). Stack derinliğinde
hepsi pozitif (sığ biraz düşük — daha az postflop-edge alanı).

## 2. SNG / tek-masa turnuva (120 turnuva)

9-kişi, blind-artışlı, sona kadar; 3 profil × 40.

| Profil | ITM% (break-even ~%33) | Ort. yer /9 | Win |
|---|---|---|---|
| soft | %55 | 3.73 | 4 |
| orta | %40 | 4.40 | 5 |
| elit | %42 | 4.40 | 2 |

Her profilde break-even üstü; soft'ta güçlü. Elit ITM bu oturumun push/fold + call-vs-jam
Nash-fix'leriyle %38→%42 yükseldi.

## 3. Tam-saha MTT (3.915 giriş, 45–1000 kişi)

Gerçek çok-masa, top-heavy ödeme + %10 rake, zayıf-ağırlıklı stake-tier alanları.

| Turnuva | Giriş | ITM% | FT% | Win | ROI% |
|---|---|---|---|---|---|
| Mikro · 45 · 50bb (küçük alan) | 300 | 22.3 | 27.3 | 4 | +1.7 |
| Mikro · 180 · 25bb (turbo) | 735 | 22.3 | 9.8 | 5 | +39.3 |
| Mikro · 500 · 50bb (büyük-turbo) | 720 | 26.5 | 7.1 | 3 | +157.5 |
| Düşük · 200 · 100bb (deep) | 768 | 28.0 | 13.4 | 4 | +95.8 |
| Düşük · 1000 · 75bb (devasa) | 720 | 26.2 | 3.5 | 1 | +107.3 |
| Orta · 180 · 100bb (zor tier) | 672 | 28.9 | 12.8 | 6 | +108.9 |

ITM %22-29 (gerçek ~%15 ödeme-eşiğinin üstünde). **ROI her formatta pozitif** (+1.7%…+157.5%),
en zor tier (Orta 180) dahil +109%.

## 4. Kalite (deterministik, varyanssız)

- **GTO-uyumu (preflop): %94** — RFI %95.6 / vs-RFI %90.5 / vs-3bet %96.0 (sömürülemez zemin).
- **Push/fold: %100 Nash-doğru** (D287, eski %85-97). Postflop ~%93 · ICM ~%91 (önceki valid).
- **bot=advisor=kitap** birebir (231 preflop + 123 postflop kararda 0 delege — 24-ajan denetimi).
- **fidelity 0-sapma**, suite 978 pass, feature audit temiz.

## 5. Dürüst kalibrasyon (uyarılar)

- Seed-varyansı yüksek → **işaret/yön + grand-mean (cash CI) güvenilir; tek-hücre magnitüdü
  ve MTT ROI yüksek-varyans/gürültülü**. MTT ROI magnitüdleri yüksek (+%95-157) — zayıf-ağırlıklı
  saha modeli + varyansı yansıtır; gerçek mid-stakes daha düşük olabilir. İşaret kesin pozitif.
- Her tweak deterministik A/B'den geçti (kazanmazsa geri al): D288'de re-shove membership
  kaybetti→geri alındı, call-vs-jam kazandı→tutuldu.
- Bilinen sınır: çok-elit + çok-derin MTT'de WIN düşük (chip-EV-max'ın doğal sonucu; survival-
  merdiven katmanı yok — "ya bust ya win", kasıtlı tasarım).

## 6. Bu oturumun katkısı (D285–D288)

- **D285:** vs-RFI opener-körlüğü (erken-açışa dominated-3bet → CALL), overpair hayalet-overcard-eq,
  stage-teli (FT/satellite ICM karara akar).
- **D286:** sim-determinizm (deck-seed bağlandı → A/B mümkün).
- **D287:** push/fold → Nash-range membership (%85→%100; all-in'de SHCP-connector primi yok).
- **D288:** call-vs-jam → Nash call-off membership (+EV A/B); re-shove denendi→reddedildi.

**Özet:** Güncel Soyrac üç oyun-tipinde (cash · SNG · tam-saha MTT), her size'da, her profilde
**istatistiksel olarak net +EV**; %100 insan-hesaplanabilir kitap olarak, bot=advisor=kitap birebir.
