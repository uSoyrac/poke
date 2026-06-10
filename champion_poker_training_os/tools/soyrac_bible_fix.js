export const meta = {
  name: 'soyrac-bible-fix-v3',
  description: '17 ASCII bolumu tam-Turkce diyakritikle + bol flowchart yeniden yaz (v3)',
  phases: [ { title: 'Yazim', detail: '17 bolum tam Turkce' } ],
}

const FACTS = `
=== SOYRAC SISTEMI — GERCEK DOGRULANMIS VERILER (uydurma YOK, hepsi koddan/simden) ===

FELSEFE: Bridge HCP (A=4,K=3..) ve Blackjack Hi-Lo kart-sayma analojisi. Insan-kafadan-yapilabilir, cok-tutarli (totolojik), ama GERCEKTEN kazanan bir poker karar sistemi. TEK ALTIN ILKE: elin gucu (equity) TEK eksendir; POZISYON/BOARD/SPR/ICM bu sayiya EKLENMEZ, sadece KARAR ESIGINI kaydirir. (Bridge de A hep 4 tur; degisen acis esigidir.) Felsefe: optimal degil ama uygulanabilir (Hi-Lo gibi) — solver mukemmel ama insan kafasi degil; bu sistem mukemmelin ~%93 unu kafadan verir.

SHCP PREFLOP PUAN (iki kart toplanir):
- Kart puani: A=10, K=8, Q=6, J=5, T=4, 9=3, 8=2, 7=1, 6=1, 5=1, 4=1, 3=0, 2=0
- Suited (ayni renk) +4; ek olarak iclerinde As varsa +2 daha (nut-flush blocker primi)
- Connector/gap (sira yakinligi, gap=aradaki bosluk): bitisik(gap0)+3, 1-gap+2, 2-gap+1, 4+gap -2
- Cift (pair): 16 + 2*(rank indeksi, 2=0..A=12). Yani AA=40, KK=38, QQ=36, JJ=34 ... 22=16
- Ornek skorlar: AA=40, AKs~27, A5s~15-17, 98s~12, 72o~-1 (gercek skorlar shcp_score fonksiyonundan; yukaridaki kurallar birebir)

RFI ACIS ESIKLERI @100bb (puan >= esik -> ac/RAISE; pozisyon=esik):
UTG 15, UTG+1 15, MP 14, LJ 13, HJ 12, CO 11, BTN 8, SB 9 ; HEADS-UP (2 kisi) 3
-> Erken pozisyon yuksek esik (dar), gec pozisyon dusuk esik (genis). Cunku gec pozisyonda daha az kisi arkanda + bilgi/inisiyatif avantaji.

vs RFI (onunde 1 acis var) CIFT ESIK (call_esik, 3bet_esik):
BB (6,16), SB (9,17), BTN (9,16), CO (10,16), HJ (11,16), LJ (12,17), MP (12,17), UTG (13,18)
-> puan>=3bet_esik: 3-BET; >=call_esik: CALL; altinda: FOLD.

vs 3-BET (3-bet pot, 3BP) — BLOCKER EKSENI (burada saf equity siralamasi COKER):
B4 blocker skoru: AA/KK=3, QQ/AKs/AKo=2, JJ=1; + Ax-suited-tekerlek(diger kart 5/4/3/2) +2; + Kx-suited-dusuk +1.
B4>=2 -> 4-BET (value+bluff); degilse score>=call_esik(=vs_RFI[poz][0]+2) -> CALL; altinda FOLD.
-> KRITIK ORNEK: A5s, AJs i DOVER. A5s: As+5 blocker (rakibin AA/AK sini blokluyor) + tekerlek yedek-equity -> 4-BET bluff. AJs: hicbir sey bloklamaz, dominated -> CALL. Saf equity AJs>A5s der; vs-3bet te TERS.

STACK DERINLIGI:
- <=40bb: esik +1 (biraz daha siki; implied odds azalir, spekulatif el deger kaybeder)
- <15bb: PUSH/FOLD modu (equity ekseni) — score>=16 JAM, yoksa FOLD (HU>=10). Nash push-fold mantigi.
- ICM (turnuva baski): esik +1 (elenme pahaliysa sikis).

POSTFLOP — 7-KADEME EL-GUCU (board a bakip 2 saniyede ata; gercek _hand_strength degerleri):
NUT: set/trips+ (0.88), iki cift (0.78) -> her zaman value, yigini ortaya koy (stack-off OK)
GUCLU: overpair (0.62), top-two -> value bet/raise
ORTA: top-pair iyi kicker (AK-K72=0.686) -> 1-2 sokak value, overbet e fold
ZAYIF-MADE: top-pair zayif kicker (A2-A72=0.612), orta-cift -> 1 ince value veya check-call, 3-barrel a fold
BLUFF-CATCH: under-pair (22=0.30, ust kart board da varsa 0.58), ace-high -> tek kucuk bahse call, polarize buyuk bahse FOLD
DRAW: OESD=8 out, flush=9 out, gutshot=4 out -> semi-bluff veya pot-odds varsa call. Rule of 2&4: flop ta out*4, turn de out*2 ~ equity%.
HAVA: hicbiri -> give-up veya tek-sokak blof.
equity ekseni: eq = strength + 0.45*draws. Savunmada eq-0.16 haircut (bir kademe asagi say — rakip range i daha gucludur).

POSTFLOP ALTIN KURALLAR:
1) COMMIT-GATE (_COMMIT_FRAC=0.70): yigininin %70 ini riske atan bahis/raise e SADECE strength>=0.60 (top-2/iyi-overpair+) VEYA draws>=0.30 (flush/OESD) ile gir. Yoksa check/call. -> cople stack-off spew unu yapisal keser (en cok kazandiran kural).
2) FLOP RANGE-CBET: preflop yukselten BENSEM + board KURU (wetness<0.30: gokkusagi/kopuk) -> RANGE-CBET (elin ne olursa olsun kucuk bas 1/3-pot; GTO kuru board da yuksek frekans blof-cbet yapar). ISLAK board -> polarize (sadece guclu el/cekme bas 3/4-pot, gerisi check).
3) BET SIZING 3-kova: kuru 1/3, deger-koruma 1/2, islak/polarize 3/4. Raise: nut-ish polarize buyuk(1.6x), ince kucuk(1.25x).
4) POT-ODDS: gereken equity = to_call/(pot+to_call). Yarim-pot bahis -> %33, pot bahis -> %50, 2/3-pot -> %40.
5) SONRAKI SOKAK BIR KADEME ASAGI SAY: turn/river geldikce el degerini bir tier dusur (haircut un kafa-formu).

BET SIZING — KESIN KURALLAR (koddan, EN ONEMLI: boyut MUTLAK degil GORELIdir):
PREFLOP boyut = KARSILASTIGIN BAHSIN kati (mutlak bb degil):
- Acis (RFI): ~2.3 x buyuk kor (2.2-2.5x). 1bb korde -> ~2.3bb. Neden: fold alacak + pot kuracak kadar, az riskle.
- 3-bet / 4-bet: karsilastigin yukseltmenin 3 KATI (3.0 x onundeki bahis), stack ile sinirli.
  Ornek zinciri: rakip 2.3bb acti -> sen 3-bet ~7bb (3x2.3). Rakip 7bb 3-bet yapti -> sen 4-bet ~20bb (3x7).
  ISTE "neden bir yerde 4bb bir yerde 17bb": AYNI 3x kurali, ama her tur daha buyuk bahisle karsilastigin icin mutlak bb buyur. Kucuk acisa min-3bet ~4-6bb; bir 3-bet uzerine 4-bet ~17-21bb. Tutarsizlik DEGIL; goreli kuralin farkli pot buyuklugundeki hali.
- Squeeze (acis + call uzerine): daha buyuk (acis 3x + her caller +1x); cunku iki rakip + dead money.
- Kisa stack (<15bb): jam (all-in) — boyut karari yok.
POSTFLOP boyut = POTUN kesri (mutlak bb degil):
- Kuru board (wetness<0.35): 1/3 pot (0.33). Neden: range avantaji, ucuz, blof+value ayni kucuk boyut (rakip okuyamaz).
- Yari-islak (0.35-0.6): ~1/2 pot (0.55). Islak/polarize (>0.6): 3/4 pot (0.75); neden: deger maksimize + fold-equity, cekmeleri pahali fiyatla.
- Paired board kucuk (<=0.45). Turn +0.10, River +0.20 -> sonraki sokakta boyut buyur (pot zaten buyudu + polarizasyon artar).
- Raise boyutu: min-raise x 1.25 (normal) veya x 1.6 (polarize/nut).
- COMMIT-GATE: hesaplanan boyut stack'in %70'ini gecer VE el GUCLU+ degilse -> BASMA (check'e duser). Boyut stack-off oluyorsa cople yapma.
- KRITIK SEZGI: AYNI 3/4-pot kurali flop'ta kucuk pot -> 6bb, river'da buyuk pot -> 30bb verir; cunku pot her sokak buyur. Oyuncu "boyutu" mutlak bb diye degil, "potun/bahsin kesri/kati" diye dusunmeli.

DOGRULAMA (gercek GTO motoru get_action argmax + bot sim):
- PREFLOP GTO DOGRULUK %91.1: RFI %94.5, vs-RFI(SRP) %85.5, vs-3bet(3BP) %81.2. Pozisyon: MP/CO %95, UTG %94.4, BTN %91.4, SB %91.3, BB %79.3 (en zor — en genis savunma). Stack: 100bb %91.5, 40bb %90.8.
- ICM DOGRULUK %90.9 (bubble icm_tighten ile).
- POSTFLOP DOGRULUK %92.9: flop-cbet %96.3 (range-cbet kuraliyla %61.5 ten ZIPLADI), flop-defend %96.2, turn cbet %92.5/defend %91.9, river cbet %98.9/defend %84.0 (river bluff-catch en zor).
- OLCEK (RFI): hep-fold %62 (taban), sabit-esik poz-kor %87, Soyrac poz-duyarli %94, mukemmel %100. Spotlarin sadece %5 i mixed (GTO kararsiz, deterministik tavani ~%95).
- BOT SIM (esit masada elitlerle): Cash +46..+80 bb/100 (GTO Expert +20, Solver +21, ICM Expert +54-68 seviyesinde/ustunde; Fish -34, Calling Station -94). SNG: en iyi ITM 20/30, ort.yer 4.00, az win (dusuk varyans sahil makinesi). MTT cok-masa ~strong-tier.
- HIKAYE: v1 postflop board-KOR monte_carlo_equity STUB kullandi (set=76-high=0.5 gurultu) -> -165 bb/100 KAYBETTI; kok-neden bulundu; v2 kazanan _hand_strength pipeline ina delege -> +46..+80 KAZANDI. (Ders: kulaga dogru != kazanan; varsayma OLC.)
- KAZANAN PROFIL DNA: VPIP 22-23, PFR 19, 3-bet 10, AF 3, F-CB 63.

DURUST SINIRLAR: BB savunmasi %79, 3-bet pot %81, river bluff-catch %84 — insan-sadeliginin bedeli, poker in en zor yerleri. Cash bb/100 yuksek varyans. Elit yuksek-stake pro lari yenmez; dusuk-orta stake te solid kazanan.

GTO/ICM TERIM KARSILIKLARI: GTO=Game Theory Optimal (oyun-teorisi-optimal denge); equity=kazanma payi; range=el yelpazesi; pot odds=pot oranlari; MDF=Minimum Defense Frequency; SPR=Stack-to-Pot Ratio; blocker=engelleme karti; polarization=kutuplasma; c-bet=continuation bet; 3-bet/4-bet=ucuncu/dorduncu yukseltme; squeeze=sikistirma 3-bet; ICM=Independent Chip Model; EV=Expected Value; RFI=Raise First In; VPIP=Voluntarily Put In Pot; PFR=Pre-Flop Raise; nuts=en iyi el; SRP=Single Raised Pot; 3BP=3-Bet Pot; OESD=Open-Ended Straight Draw (8 out); gutshot=ic kus cekme (4 out); board=ortak kartlar; texture/wetness=board dokusu/islaklik.
=== GUNCEL DOGRULANMIS RAKAMLAR + KURALLAR (D147-D152) — ESKI "+46-80"i DEGIL BUNLARI KULLAN ===
OLCUM DUZELTMESI: Eski "+46-80 bb/100" SISIKTI (sim-harness pozisyon bug: her el seat0=BTN saniliyordu + balik-agirlikli saha). DUZELTILDI (tek-kalici oyun, buton doner). DOGRU apples-to-apples kanonik leaderboard:
- CASH-6max: Soyrac #1-2/28 (GTO Expert ile yer degistirir, +21..+32 bb/100, Solver Bot/ICM Expert USTUNDE) = ELIT.
- CASH-9max: Soyrac #3/28 (+27, GTO Expert/Solver ardindan) = ELIT.
- MTT: zayif/karma sahada SAMPIYONLUK sansin 2.7-7.6 KATI, final-masa 1.8-3.2 kati, ITM %13-19 (taban-ustu); expert-sahada rekabetci. 200-kisi esit-saha: ortalama ~84/200 (ust %42), profil sirasi ~ust-ceyrek, ITM %25.
KURAL: cash icin "+46-80" YAZMA; "kanonik #1-3, solver-botlari yener" + "MTT sampiyonluk sansin 2.7-7.6 kati" YAZ.

EN ONEMLI YENI KURAL (D152): vs-3BET'te COK DAHA SIKI. Eski sistem 3-bet pot'ta 22-88/broadway call ediyordu = %53 over-call sizinti. YENI: 3-bet'e karsi SADECE premium 4-bet (QQ+/AK + A2s-A5s blocker-blof) VEYA cok guclu flat (JJ+/AQs+/KQs); GERISI FOLD. Accuracy %81->%94. Insan kurali: "3-bet gordun mu? Premium degilse KATLA — 3-bet pot pahalidir, marjinal el para yakar."

RAFINELER (D147-D148): (1) Acan-duyarli BB savunmasi: erken acana (UTG/MP) DAHA SIKI savun, gec acana (BTN/SB) genis. (2) 3-bet blof: A2s-A5s (suited-wheel) ile GEC acana 3-bet blofu (AA/AK bloklar).

FORMAT-AYRIMI (D150, ONEMLI): SHCP loose-aggressive bir CASH sistemidir (fishy sahayi ezer #1-3). TURNUVADA loose stil erken-bust ettirir (reload yok) -> turnuvada DAHA SIKI + ICM-disiplin + short-stack push/fold = AYRI mod. Kural: "Cash'te SHCP loose oyna (balik som); turnuvada SIKILAS + survival + push/fold."

KAYIP-KATEGORILERI (olculdu, COK degerli): Bazi eller GTO/Solver/Shark icin BILE net-kaybettirir (ozellikle BB savunmasinda): suited-connector (-78 bb/100 BB), suited-gapper (-65), offsuit-connector (-71), cop-offsuit (-66). NEDEN: BB'de koru zaten yatirdin; bunlari savunmak "katlamaktan az kaybetmek" = yine -EV. Para KAZANDIRAN: cift (+253 BB!), suited-Ax (+98), suited-broadway (+60). PRATIK KURAL: "BB'de spekulatif copu (suited/offsuit connector, cop) cekinmeden KATLA — savunsan da kaybedersin + zor postflop'tan kacinirsin."

OLCULEN SOYRAC PROFILI (pozisyon-fix'li): VPIP ~%33 (loose, fishy sahada OPTIMAL), PFR ~%24, 3bet ~%5-6, AF saha-adaptif (zayifa 5+, tough'a ~2.8). Kazanan tight-arketipler VPIP 22-24 ama o TOUGH saha icin; fishy sahada Soyrac looseu daha cok kazandirir = #1.

`

const STYLE = `
HTML CIKTI KURALLARI (temiz montaj icin ZORUNLU):
- SADECE govde fragmani uret: <h2> ile basla, <html>/<head>/<body> YOK, markdown fence YOK.
- Basliklar <h2> bolum, <h3> alt-bolum, <h4> madde. Paragraf <p>. Liste <ul><li>.
- Tablo: <table class="tbl"><thead><tr><th>..</th></tr></thead><tbody><tr><td>..</td></tr></tbody></table>. BOL tablo kullan.
- Cikartma kutulari (bol): <div class="note">Not: ...</div> · <div class="why">Neden: ...</div> · <div class="example">Ornek: ...</div> · <div class="gto">GTO karsiligi: ...</div> · <div class="icm">ICM karsiligi: ...</div> · <div class="keyrule">Altin kural: ...</div>
- Terim ilk gecince: <span class="term"><b>RFI</b> (Raise First In — ilk giren yukseltir/acis)</span>.
- Sekil yeri: <div class="figref" data-fig="ad">[Sekil: kisa aciklama]</div> (montajda SVG eklenecek).
- DIL: KUSURSUZ, TAM TURKCE — proper diyakritik ZORUNLU (s/g/u/o/c/i harflerinin Turkce hallerini kullan: s-cedilla, g-breve, u-umlaut, o-umlaut, c-cedilla, i-dotless ve I-dotted). "Bolum" DEGIL dogru Turkce yaz; "gucu/onsoz/icindekiler/esik" gibi kelimeleri TAM diyakritikle yaz. Bu bir kitap; imla kusursuz olmali.
- Terimler INGILIZCE + parantez Turkce aciklama. Sicak ogretici koc tonu. Cok ORNEK, cok NEDEN. SAYI verince (ozellikle bet boyutu) NEDEN o boyut oldugunu acikla (goreli kural: potun kesri / bahsin kati).
- KOLAY-OGRENME + KARAR-CIZELGELERI (ZORUNLU): Bu kitap KOLAY ogrenilmeli. Her bolumde BOL <div class="figref" data-fig="AD"> karar-akisi/flowchart yer-tutucu koy (montajda gercek SVG eklenir; onerilen AD: preflop-decision, vs3bet-decision, bb-defense, postflop-decision, sizing-decision, format-decision, tier-ladder). Kademeli + basit dille (once en basit hali, sonra detay), kisa cumleler. Her kural icin "masada nasil:" tek-satir. KARAR-TABLOLARI: "X gorursen -> Y yap" (if-then) formatinda bol kullan. Bir cocuga anlatir netlik ama icerik tam.
- font-size/renk verme; sadece yapisal HTML + class. Her bolum DOLU (4-7 sayfa hedef).
`

const SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: {
    chapter_html: { type: 'string', description: 'Bolumun tam HTML fragmani (<h2> ile baslar)' },
    glossary: { type: 'array', items: { type: 'object', additionalProperties: false,
      properties: { term: { type: 'string' }, tr: { type: 'string' } }, required: ['term', 'tr'] } },
    figures: { type: 'array', items: { type: 'string' } },
  },
  required: ['chapter_html', 'glossary', 'figures'],
}


const CH = [
  { n: 1, t: `Onsoz, Bu Kitap Nasil Okunur, Bir Bakista Ozet`, spec: `Kime icin (bridge+blackjack bilen, kafadan-uygulanabilir kazanan sistem isteyen oyuncu). Kitabin yapisi. Sistemin 1-sayfalik ozeti: SHCP preflop puan + pozisyon esigi + 7-kademe postflop + 3 altin kural. Dogrulama ozeti (%91 preflop/%93 postflop GTO-uyum; cash KANONIK #1-3 ELIT solver-botlari yener; MTT sampiyonluk sansin 2.7-7.6 kati). KARAR-CIZELGESI: sistemin 1-bakista akis semasi. Nasil pratik edilir.` },
  { n: 2, t: `Felsefe: Neden Bir Puan Sistemi?`, spec: `Bridge HCP ve Blackjack Hi-Lo analojisi DERINLEMESINE. TEK-EKSEN ilkesi: equity tek sayi, pozisyon/board/SPR/ICM ESIGI kaydirir (puana eklenmez) — neden matematiksel olarak dogru (AA her pozisyonda 40). Totolojik/tutarli olmak neden onemli. Optimal-vs-uygulanabilir felsefesi. Neden kazandiriyor.` },
  { n: 3, t: `Poker Temelleri ve Terimler I`, spec: `Oyun akisi (preflop/flop/turn/river), pozisyonlar (UTG..BTN/SB/BB neden onemli), bahis aksiyonlari (fold/call/raise/check/bet/all-in), kor yapisi. Temel terimler: GTO, equity, range, pot, EV, nuts. Her birini ornekle. Pozisyon NEDEN bu kadar onemli (bilgi+inisiyatif).` },
  { n: 4, t: `Ileri Terimler II`, spec: `pot-odds (hesap+ornek), MDF, SPR, blocker, polarization, c-bet, 3-bet/4-bet, squeeze, ICM, RFI/VPIP/PFR, SRP/3BP, OESD/gutshot, board texture/wetness. Her terim: tanim + neden onemli + masa-ornegi.` },
  { n: 5, t: `SHCP Preflop Puanlama Sistemi`, spec: `Kart puanlari tablosu (A=10..) ve NEDEN top-heavy + equity-kalibre. Suited +4 (+As 2), connector/gap bonuslari, cift formulu (16+2*rank). NEDEN bu bonuslar (implied-odds, blocker). 6-8 EL icin adim-adim puan hesabi (AA, AKs, A5s, 98s, KQo, 72o, JTs, 22). Kafadan pratik kisayollar.` },
  { n: 6, t: `Pozisyon = Esik (Puana Eklenmez)`, spec: `Neden pozisyon puana EKLENMEZ, esigi kaydirir. Her pozisyon RFI esigi tablosu (UTG 15..BTN 8) + NEDEN. GTO karsiligi: solver acis genislikleri (UTG ~%15, BTN ~%48) ile eslesme. Accuracy pozisyon bazli (MP/CO %95, BB %79). Flowchart: preflop acis karari.` },
  { n: 7, t: `Preflop Senaryolar I: RFI ve vs-RFI`, spec: `RFI tam akis. vs-RFI cift esik (call/3bet) her pozisyon. Acan-duyarli BB savunmasi (erken acana siki). KAYIP-KATEGORILERI ICGORUSU: BB'de spekulatif cop (suited/offsuit-connector, cop-offsuit) GTO icin BILE -EV (-66..-78 bb/100) -> cekinmeden KATLA; para cift(+253)/suited-Ax(+98)/broadway'den gelir. preflop-decision + bb-defense FLOWCHART. accuracy %85.5. 3-4 EL ornegi.` },
  { n: 8, t: `Preflop Senaryolar II: vs 3-Bet Blocker Ekseni, 4-Bet, Squeeze`, spec: `vs-3bet NEDEN equity siralamasi coker -> BLOCKER ekseni. B4 skoru tam. A5s>AJs DERIN ornek. 4-bet value+bluff dengesi. Squeeze mantigi+sizing. 3BP. + YENI KRITIK KURAL (D152): 3-bet'e karsi COK DAHA SIKI — SADECE QQ+/AK 4-bet + A2s-A5s blocker-blof + JJ+/AQs+/KQs flat, GERISI FOLD (eski genis-call %53 over-call sizinti -> accuracy %81->%94). Insan kurali kutusu: '3-bet gordun? Premium degilse KATLA.' vs3bet-decision FLOWCHART. 2-3 EL ornegi.` },
  { n: 9, t: `Stack Derinligi ve Push/Fold`, spec: `100bb/40bb/kisa farklari. Neden <=40bb esik +1. <15bb push/fold (Nash) — score>=16 jam. ICM koprusu. Heads-up modu (esik 3 neden). Tablolar + 2 EL ornegi.` },
  { n: 10, t: `Postflop I: Board Okuma ve 7-Kademe El-Gucu`, spec: `Board texture kuru/islak (wetness), paired, monotone, connected — 2 saniyede okuma. 7-kademe tablo gercek degerlerle. Kicker neden onemli (AK-K72 vs A2-A72). DRAW/outs + rule of 2&4 ornekleri. eq=strength+0.45*draws. 4-5 EL ornegi.` },
  { n: 11, t: `Postflop II: Uc Altin Kural ve Sokak-Sokak Karar`, spec: `COMMIT-GATE %70 derin+neden. FLOP RANGE-CBET (kuru->range, islak->polarize) NEDEN + accuracy sicramasi 61.5->96.3. Pot-odds esikleri. Haircut. Flowchart flop->turn->river. 3-4 EL ornegi. (Bet boyutu DETAYI ayri bolumde — burada sadece deginildi.)` },
  { n: 12, t: `Bet Sizing: Neden Bu Boyutlar? (4bb mi 17bb mi?)`, spec: `EN ONEMLI ILKE: boyut MUTLAK bb degil GORELIdir. PREFLOP boyut = karsilastigin bahsin kati: acis 2.3x kor, 3bet/4bet 3x onundeki bahis. "Neden bir yerde 4bb bir yerde 17bb" TAM CEVAP: ayni 3x kurali ama escalating pot (2.3->7->20bb zinciri). Squeeze daha buyuk. POSTFLOP boyut = potun kesri: kuru 1/3, yari 1/2, islak 3/4, paired kucuk, turn/river buyur. Raise 1.25x/1.6x. Commit-gate boyut sınırı. HER boyutun NEDENi (fold-equity, value cekme, deny-equity, range-bet, polarizasyon, SPR). Worked ornek: ayni 3/4 kurali flop 6bb river 30bb (pot buyudugu icin). Bol tablo + bb-cevirimli ornek.` },
  { n: 14, t: `Oyun Formatlari ve Boyutlar`, spec: `Cash vs turnuva farki (derinlik, ICM, blind artisi). Turnuva boyutlari (SNG/heads-up, 180, 1000) strateji nasil degisir. Stake/field strength (zayif vs guclu saha) — exploit. Degisen pot/bet boyutlari (SPR, commitment). Cash stake leri. + FORMAT-AYRIMI (KRITIK): cash=SHCP loose-aggressive (fishy ez, #1-3) / turnuva=DAHA SIKI+ICM+short-stack push/fold (ayri mod; loose stil turnuvada erken-bust ettirir, reload yok). format-decision FLOWCHART. Sistem her formatta nasil ayarlanir. Tablolar.` },
  { n: 15, t: `GTO ve ICM Karsiliklari, Sistemi Nasil Dogruladik`, spec: `HER kuralin GTO/ICM temeli (ozet matris). Dogrulama metodolojisi: bot+esit masa+accuracy. Accuracy tablolari (preflop %91.1, postflop %92.9, ICM %90.9). Olcek/benchmark (hep-fold %62..Soyrac %94..mukemmel %100, %5 mixed). KANONIK leaderboard apples-to-apples: cash-6max #1-2, cash-9max #3 (solver-botlari yener); MTT sampiyonluk sansin 2.7-7.6 kati. (Eski +46-80 SISIKTI -> harness pozisyon-bug + balik-saha; DUZELTILDI.) KAYIP-KATEGORILERI: suited/offsuit-connector+cop GTO icin BILE -EV (BB'de -78..-66 bb/100); para cift/suited-Ax/broadway'den. v1->v2 board-kor equity hikayesi. DURUST sinirlar.` },
  { n: 16, t: `Ornek El Defteri A (Preflop-Agirlikli)`, spec: `5 TAM EL: (1) UTG AA RFI+3bet pot, (2) BTN 98s acis+kuru flop range-cbet, (3) BB vs CO defense+turn, (4) CO vs MP 3bet A5s 4-bet-bluff, (5) SB squeeze. Her el: kartlar, pozisyon, SHCP puan, karar+NEDEN, bet BOYUTU+neden, GTO/ICM gerekce, sonuc. Sokak-sokak tablo.` },
  { n: 17, t: `Ornek El Defteri B (Postflop ve ICM)`, spec: `5 TAM EL: (1) islak board polarize cbet, (2) river bluff-catch under-pair, (3) flush draw semi-bluff (outs+commit-gate), (4) ICM bubble marjinal fold, (5) multiway disiplin. Her el: kademe atama, commit-gate, pot-odds, bet BOYUTU+neden, NEDEN. Sokak-sokak dusunce.` },
  { n: 18, t: `Hizli Referans, Ezber Tablolari ve Pratik Plani`, spec: `Tek-sayfa ozet (SHCP puan + esikler + 7-kademe + 3 kural + BET SIZING ozeti). Masada uygulama check-list. Yaygin hatalar. 30-gunluk pratik plani. Nasil olcup gelisirsin. Kapanis: ozun tek paragraf.` }
]

phase('Yazim')
log('17 bolum tam-Turkce + flowchart yeniden yaziliyor')
const chapters = await parallel(CH.map(c => () =>
  agent(
    `${FACTS}\n\n${STYLE}\n\nMUTLAK DIL KURALI: FACTS metni teknik nedenle DIYAKRITIKSIZ yazildi. SEN ciktini KESINLIKLE tam diyakritikli, kusursuz Turkce yazacaksin. Asla 'Bolum/gucu/esik/icin/dogru/buyur/kayip' gibi ASCII yazma; DOGRUSU: Bolum->Bölüm, Onsoz->Önsöz, gucu->gücü, esik->eşik, icin->için, dogru->doğru, buyur->büyür, karsilastigin->karşılaştığın, yukseltme->yükseltme, kucuk->küçük, kayip->kayıp, sasi->şaşı, cift->çift, savunma->savunma. Tum s/g/u/o/c/i->ş ğ ü ö ç ı İ. Bu bir KITAP; imla kusursuz olacak. Ayrica BOL <div class=\"figref\" data-fig=\"...\"> karar-cizelgesi koy (vs3bet-decision, bb-defense, sizing-decision, format-decision, tier-ladder, preflop-decision, postflop-decision) + 'masada nasil:' tek-satirlar + if-then karar tablolari.\n\nSEN: instructional designer + usta poker kocu. BOLUM ${c.n}: ${c.t}\nKAPSAM: ${c.spec}\n\nSadece bu bolumun HTML fragmanini uret. <h2>Bölüm ${c.n}. ${c.t}</h2> ile basla (BASLIK TAM DIYAKRITIKLI). Gercek verileri kullan, uydurma sayi yok (ozellikle GUNCEL rakamlari kullan: cash #1-3, MTT sampiyonluk sansin 2.7-7.6 kati; ESKI +46-80 YAZMA). KOLAY-OGRENME tonu, bol figref/flowchart, if-then karar tablolari. 4-7 sayfa. TAM DIYAKRITIKLI TURKCE.`,
    { label: `fix-${c.n}`, phase: 'Yazim', schema: SCHEMA }
  )))
return { chapters: chapters.map((c,i)=>({ n: CH[i].n, t: CH[i].t, data: c })) }
