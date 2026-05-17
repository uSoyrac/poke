"""Pro Poker Oyuncu Profilleri — efsane ve modern dahiler.

Her profil:
  - name (kanonik isim)
  - aliases (alternatif anılan adlar)
  - era (yılları / dönemi)
  - style_tag (TAG / LAG / Hyper-LAG / Balanced / GTO Hybrid / Old School)
  - achievements (önemli başarılar, kısa)
  - philosophy (oyun felsefesi, koç tonu Türkçe)
  - range_tendencies (preflop range yaklaşımı)
  - decision_style (karar verme süreci)
  - strengths (güçlü yönleri)
  - exploitable (zayıflıkları, kullanılabilir patternlar)
  - signature_quote (ünlü sözü, Türkçe çeviri)
  - according_to (\"Bu spotta X olsa ne yapardı\" — generic kural seti)

Kullanım:
    from app.data.pro_profiles import lookup_pro, list_pros, format_pro

    pro = lookup_pro("Phil Ivey")
    print(format_pro(pro))
"""
from __future__ import annotations

from typing import Optional


PROS: list[dict] = [
    {
        "name": "Doyle Brunson",
        "aliases": ["doyle", "brunson", "texas dolly"],
        "era": "1970-2010 (efsane, 10x WSOP bracelet)",
        "style_tag": "Old School Hyper-Aggressive",
        "achievements": (
            "10x WSOP bracelet, 2x Main Event şampiyonluğu (1976, 1977). "
            "'Super/System' (1979) modern pokerin İncil'i — herkes onun "
            "çerçevelerinden öğrendi."
        ),
        "philosophy": (
            "\"Saldır — onları reflexive defens'e zorla\". Doyle pokeri psikolojik "
            "savaş olarak görür: rakibin elini değil, rakibin KARARINI hedefle. "
            "Stack baskısı + sürekli aggression rakibe nefes aldırmaz."
        ),
        "range_tendencies": (
            "Range LAG-tarafı: T9s, J8s gibi 'küçük suited connectors'ı 'altın "
            "el' sayar (postflop oynanabilirliği yüksek). Doyle ünlü 'top "
            "5%' içinde T2 (her ikisi suited değil) bile oynar imaj/leverage için."
        ),
        "decision_style": (
            "Sezgisel + presence-based. Rakibin nefes alış-veriş ritmini, eldeki "
            "chip sıkıştırma şeklini, bakışını okur. Modern GTO'ya değil pattern "
            "recognition'a dayanır."
        ),
        "strengths": [
            "Mental dominance — rakibi tilt'e iter",
            "Stack pressure — sürekli reraise, sürekli baskı",
            "Bluff timing — boş anlarda büyük bluff'lar",
        ],
        "exploitable": [
            "Modern solver-based oyuncuya karşı eski okul polarized line'ı "
            "frequency'leri optimal değil — sızıntı verir",
            "Çok agresif olduğu için thin value spotlarda hero call'a vulnerable",
        ],
        "signature_quote": (
            "\"Poker'in en güzel yanı para kazanmanın bir yan ürün olmasıdır. "
            "Asıl iş psikolojik savaştır.\""
        ),
        "according_to": (
            "Doyle'a göre: 'Eğer ne yapacağına emin değilsen, raise et. Çağrı en zayıf "
            "harekettir.' Marginal preflop spotlarda Doyle agresyon seçer; check-call "
            "yerine donk-bet veya check-raise tercih eder."
        ),
    },
    {
        "name": "Daniel Negreanu",
        "aliases": ["dnegs", "negreanu", "daniel"],
        "era": "1997-günümüz (6x WSOP, 2x WPT, kid poker)",
        "style_tag": "Hand-Reading Master / Small-Ball",
        "achievements": (
            "6x WSOP bracelet, 2x WPT şampiyon, 2x Player of the Year. Lifetime "
            "kazancı $50M+. 'Hold'em Wisdom for All Players' yazarı."
        ),
        "philosophy": (
            "\"Small-ball strategy: küçük pot'larda çok karar, büyük pot'larda "
            "minimum karar.\" Daniel preflop küçük açışlar (2.2-2.5x), postflop "
            "iz bırakmamaya çalışır — varyansı minimize eder."
        ),
        "range_tendencies": (
            "Geniş preflop range ama küçük sizing. Suited connectors, suited Ax "
            "her pozisyondan. Tüm pocket pairs, broadway suited her zaman. "
            "Postflop tight — bluff frekansı normalden düşük."
        ),
        "decision_style": (
            "Hand-reading legenddir — preflop'tan başlayıp street başına villain'in "
            "range'ini progressively daraltır. 'I felt your hand' tekniği — "
            "her aksiyona göre olası combos'ı eler."
        ),
        "strengths": [
            "Pre-flop hand reading — opponent's exact range derived from action",
            "Small-ball varyans yönetimi",
            "Live tells — voice tone, breathing, betting tempo",
        ],
        "exploitable": [
            "Postflop tight olduğu için MDF altında defend ediyor — overfold leak",
            "Bluff frequency düşük — bet'leri value-heavy okunabilir",
        ],
        "signature_quote": (
            "\"Ben rakibin elinin ne olduğunu biliyorum çoğunlukla. Bu doğru "
            "kararı vermenin tek yolu.\""
        ),
        "according_to": (
            "Daniel'e göre: 'Bir el oynamadan önce villain'in range'ini görmeden "
            "asla aksiyon alma. Eğer range'i hayal edemiyorsan elindeki bilgi "
            "yetersiz — daha çok info topla.'"
        ),
    },
    {
        "name": "Phil Hellmuth",
        "aliases": ["hellmuth", "phil", "poker brat"],
        "era": "1989-günümüz (rekortmen 17x WSOP bracelet)",
        "style_tag": "Old School TAG / White Magic",
        "achievements": (
            "17x WSOP bracelet (rekor), 1989 Main Event şampiyonu (24 yaşında en "
            "genç). 'Play Poker Like the Pros' yazarı."
        ),
        "philosophy": (
            "\"Beyaz büyü: oyuncuların kafasında imaj kurarım, sonra o imajı "
            "kullanırım.\" Hellmuth tight-aggressive — premium beklemek, sonra "
            "maksimum value almak. Yavaş ama agressive timing."
        ),
        "range_tendencies": (
            "Sıkı — Premium pocket pairs (TT+), strong broadway (AK, AQ). "
            "Çok az suited connector. Çok az 3-bet bluff. Range solid value-heavy."
        ),
        "decision_style": (
            "Patient. Saatlerce sıkıcı oynar, sonra büyük spot'ta inanılmaz hero "
            "call yapar. Live reads + history (oturumun başından beri biriken "
            "pattern observation)."
        ),
        "strengths": [
            "Live tell reading — yüz okuma, conversation manipulation",
            "Variance management — tight ranges, value-focused",
            "Reputation leverage — herkes ondan korkar, sağladığı baskı",
        ],
        "exploitable": [
            "Çok tight olduğu için %72o gibi marginal hand 3-bet'le fold ediyor",
            "Tilt riski yüksek — sözel baskı ile karar kalitesini düşürebilirsin",
            "Modern GTO frequency'lerinden uzak — predictable polarized lines",
        ],
        "signature_quote": (
            "\"Eğer kıçımın altında dünyanın en kötü değeri bile olsa raise "
            "etmeseydim, ben Phil Hellmuth değildim.\""
        ),
        "according_to": (
            "Hellmuth'a göre: 'Disipline öncelikli. 5 saat fold etsen bile, "
            "6. saatte premium gelirse maksimum chip al. Sabırsızlık poker'in "
            "en pahalı leak'idir.'"
        ),
    },
    {
        "name": "Phil Ivey",
        "aliases": ["ivey", "phil ivey", "no home jerome"],
        "era": "1996-günümüz (modern era best all-around)",
        "style_tag": "Hyper-Aggressive Balanced / Intuitive",
        "achievements": (
            "10x WSOP bracelet (2nd all-time), 1x WPT, $5M+ Big One for One Drop. "
            "Online + live hem cash hem MTT zirve."
        ),
        "philosophy": (
            "\"Ben rakibim hangi line'i seçerse seçsin kazanmanın yolunu bulurum.\" "
            "Ivey adaptive — TAG'a karşı LAG, LAG'a karşı trap. Multiple line "
            "paradigm: her el için 3-4 plan B."
        ),
        "range_tendencies": (
            "Position-aware geniş aralık. BTN/CO'dan suited any-two-cards, "
            "BB'den polarized 3-bet, OOP tight + trap. Postflop creative — "
            "check-raise frequency yüksek wet board'larda."
        ),
        "decision_style": (
            "Pattern recognition + GTO awareness + real-time exploit binder. "
            "Heads-up rakibe focus eder, 50 elin sonunda zayıflıklarını mapler. "
            "Sonra aynı zayıflığı sürekli sömürür."
        ),
        "strengths": [
            "Adaptive aggression — opponent type'a göre style switch",
            "Pressure stamina — 14 saat marathon session'larda focus düşmez",
            "Bet sizing artistry — sizing villain'ın range'ine tailored",
        ],
        "exploitable": [
            "Çok agresif olduğu için bazı thin value spotlarda hero-callable",
            "Spec hands ile loose pre-flop call'lar bazen reverse implied'lı",
        ],
        "signature_quote": (
            "\"Önemli olan kart değil — önemli olan rakibinin elinin ne "
            "olduğunu anlaman.\""
        ),
        "according_to": (
            "Ivey'e göre: 'Bir spot'ta karar vermeden önce 3 senaryo düşün — "
            "'eğer raise edersem, eğer call edersem, eğer fold edersem' — "
            "hangisi en yüksek EV verir? Bu refleks haline gelene kadar her el düşün.'"
        ),
    },
    {
        "name": "Tom Dwan",
        "aliases": ["durrrr", "dwan", "tom"],
        "era": "2007-günümüz (online crusher, high stakes cash legend)",
        "style_tag": "Hyper-LAG / Fearless",
        "achievements": (
            "Online HU NL'de zirve (2008-2010). $11M $50/$100+ kazanç. "
            "\"durrrr Challenge\" — Patrik Antonius'a karşı meydan okuma. "
            "WSOP bracelet yok ama high stakes cash'in efsanesi."
        ),
        "philosophy": (
            "\"Eğer kaybetmekten korkuyorsan, kazanamazsın.\" Tom hyper-LAG — "
            "her spot'ta maksimum baskı, range her zaman wide, aggression %35+. "
            "Variance kabul, frekans önemli."
        ),
        "range_tendencies": (
            "Aşırı geniş. BTN'den any-two playable, suited gappers, junk "
            "hands too. 3-bet frequency %12-15. 4-bet bluff sıklığı çok yüksek. "
            "Postflop barrel sıklığı %70+."
        ),
        "decision_style": (
            "Fearless creativity. Multi-street bluff'lar, big sizing, "
            "thin value bet'ler, 4-bet bluff her oturum. Mental capacity'si "
            "olağanüstü — aynı anda 4 yüksek stakes table."
        ),
        "strengths": [
            "Aggression — opponent'lar reactive defense'e geçer",
            "Sizing variation — her sizing farklı range gizler",
            "Mental stamina — variance'ı tilt'e dönüşmez",
        ],
        "exploitable": [
            "Aşırı bluff yapıyor — hero call frequency yükseltilir",
            "4-bet bluff'a karşı 5-bet jam light call yapabilir",
            "Tight + sabırlı oyuncuya karşı bluff variance kazandırmaz",
        ],
        "signature_quote": (
            "\"En iyi oyuncular sonucu değil kararı düşünür.\""
        ),
        "according_to": (
            "Dwan'a göre: 'Her el agresif olmak zorunda. Pasif oyun zaman "
            "kaybı. Bluff'a fold ederek pot'u rakibe verirsen, sırasında "
            "value bet'le geri alabileceğini düşünmemiş olursun.'"
        ),
    },
    {
        "name": "Erik Seidel",
        "aliases": ["seidel", "erik"],
        "era": "1988-günümüz (9x WSOP bracelet, Poker HoF)",
        "style_tag": "Balanced / Theory + Intuition Hybrid",
        "achievements": (
            "9x WSOP bracelet, 1x Aussie Millions Main Event, $40M+ lifetime "
            "earnings. Poker Hall of Fame inductee 2010."
        ),
        "philosophy": (
            "\"Poker matematik + psikoloji eşit ağırlıkta.\" Erik tight ama "
            "agresif tempo'da — premium spots'ta maksimum value, marginal "
            "spots'ta disiplinli fold. Variance management ustası."
        ),
        "range_tendencies": (
            "Pozisyon disiplini sıkı. UTG-MP %12 range, late position %30-35. "
            "3-bet polarize, 4-bet sadece QQ+. Solid GTO frequency'lerine yakın."
        ),
        "decision_style": (
            "Mathematical foundation + intuition. Pot odds, MDF, alpha "
            "calculations reflex; intuition exploit ayarı için. Live tell "
            "reading güçlü — physical timing + verbal cues."
        ),
        "strengths": [
            "Longevity — 35 yıldır profitable, hiç ciddi downstreak yok",
            "Variance discipline — tilt nadiren görünür",
            "Big-spot decision quality — final table mastery",
        ],
        "exploitable": [
            "Çok disiplinli — MDF'in altında defend ediyor (3-bet bluff +EV)",
            "Bluff frequency düşük — bet'i value-heavy okunabilir",
        ],
        "signature_quote": (
            "\"Poker'i 30 yıl kazanabilmek için 1 yıl crusher olmak yetmez — "
            "her gün yeniden iyi karar verebilmek lazım.\""
        ),
        "according_to": (
            "Seidel'e göre: 'Her karar marginal mı? Eğer öyleyse fold'a yatkın "
            "ol. Marginal call'lar kümülatif olarak kasayı yer. Disiplin lüks değil, gereklilik.'"
        ),
    },
    {
        "name": "Daniel Cates",
        "aliases": ["jungleman", "jungleman12", "cates"],
        "era": "2009-günümüz (modern HU cash crusher, MTT switch)",
        "style_tag": "Analytical Hyper-LAG / GTO Pioneer",
        "achievements": (
            "Online HU NL #1 (2010-2013). PLO Player of the Year 2021. "
            "$15M+ lifetime. WSOP Players Championship $50K back-to-back 2021-2022."
        ),
        "philosophy": (
            "\"Solver çıktısı yön, gerçek karar exploit'tedir.\" Dan modern "
            "GTO + exploit dengesi — solver baseline'ı çalıştır, sonra "
            "village'ın leak'ini hedefle."
        ),
        "range_tendencies": (
            "Solver-derived ranges, ama exploit binmesi sürekli. HU'da 4-bet "
            "bluff frequency %25+. Mixed strategy heavy — aynı el bazen raise "
            "bazen call. Postflop balanced ama sapma agresif."
        ),
        "decision_style": (
            "Pre-game solver study + real-time exploit detection. Villain'ın "
            "spesifik leak'ini ilk 50 elde tespit eder, sonra sömürü modu. "
            "Mental load yüksek — focus shift skill."
        ),
        "strengths": [
            "Solver mastery — tüm common spotları GTO frequency'siyle biliyor",
            "Exploit detection — opponent's leak'ini hızlı mapler",
            "Multi-table cognitive capacity — 4 HU table simultane",
        ],
        "exploitable": [
            "GTO'ya çok bağlı bazen exploit'i kaçırır — recreational oyuncuya "
            "karşı over-bluff",
            "PLO'da NL'den daha az dominant — sample size küçük",
        ],
        "signature_quote": (
            "\"Solver bir araç, cevap değil. Cevap her zaman 'bu villain'a karşı "
            "ne işe yarar?'.\""
        ),
        "according_to": (
            "Cates'e göre: 'Bir spot'ta karar verirken iki layer düşün: (1) GTO "
            "baseline frequency ne, (2) bu villain'in deviation pattern'i ne. "
            "İkisini birleştir.'"
        ),
    },
    {
        "name": "Fedor Holz",
        "aliases": ["holz", "fedor", "crownupguy"],
        "era": "2014-günümüz (modern MTT prodigy, 23 yaşında retire açıklaması)",
        "style_tag": "Modern GTO Hybrid",
        "achievements": (
            "WSOP One Drop High Roller 2016 ($4.9M). $30M+ lifetime, 23 yaşında "
            "tarihinin en kazançlı oyuncusu. Pokerstars/Run It Once eski coaching."
        ),
        "philosophy": (
            "\"GTO temel, exploit performans tavanı.\" Fedor solver eğitimi "
            "geniş, ama oyunda 'human game' — opponent'un emotional state'ini "
            "okuyup mathematical edge üstüne emotional edge bindiriyor."
        ),
        "range_tendencies": (
            "Solver-aligned ama position'a göre dinamik. HJ %20, CO %28, BTN "
            "%48. 3-bet frequency lineer %9-12. Postflop frequency'leri "
            "calibrated."
        ),
        "decision_style": (
            "Pre-game study + post-game review heavy. Solver çıktılarını "
            "ezberlemiş, gerçek zamanlı pattern matching yapıyor. Mental game "
            "coaching aldı — emotional regulation pro level."
        ),
        "strengths": [
            "Modern GTO awareness + practical execution",
            "Mental game — anti-tilt, emotional regulation",
            "MTT life ROI %30+ (high stakes — istisnai)",
        ],
        "exploitable": [
            "GTO baseline'a sıkı bağlı olduğu için exploit-pure oyunculara "
            "karşı bazı thin spotlarda EV bırakır",
        ],
        "signature_quote": (
            "\"Poker'de kazanmak için sadece iyi karar vermek yetmez — iyi "
            "kararı zor durumda verebilmek lazım.\""
        ),
        "according_to": (
            "Fedor'a göre: 'Her oturum öncesi son 5 spot'u solver'la kontrol et. "
            "Bilgi taze olmadan exploit'in temel zayıf.'"
        ),
    },
    {
        "name": "Justin Bonomo",
        "aliases": ["zeebo", "bonomo", "justin"],
        "era": "2005-günümüz (high roller circuit dominance)",
        "style_tag": "GTO Mastermind",
        "achievements": (
            "All-time tournament earnings #1 ($63M+). Big One for One Drop 2018 "
            "$10M. 3x WSOP bracelet, multi WPT."
        ),
        "philosophy": (
            "\"GTO unexploitable baseline'dır. Buradan başla, sonra dünya seni "
            "tanıdığı anda exploit'e geç.\" Justin solver-pure üstüne tactical "
            "adjustments."
        ),
        "range_tendencies": (
            "Solver-derived. Frequency'lere milimetrik bağlı. Mixed strategy "
            "her seviyede. Postflop bet sizing standardized — solver'ın "
            "verdiği size aralıkları."
        ),
        "decision_style": (
            "Real-time GTO calculation + opponent model. Mental capacity "
            "olağanüstü — multiple solver charts head'inde simultaneous."
        ),
        "strengths": [
            "GTO frequency precision",
            "Solver-prep work ethic — 4-6 saat günlük study",
            "Final table closing strength",
        ],
        "exploitable": [
            "Tamamen exploit-pure oyuncuya karşı bazen GTO over-frequency kaybedebilir",
        ],
        "signature_quote": (
            "\"Hiçbir spot 'instinct' değil. Her spot bir matematik probleminin "
            "approximation'ıdır.\""
        ),
        "according_to": (
            "Bonomo'ya göre: 'Bir karar verdiğinde, kendine sor: \"Solver bunu "
            "ne sıklıkta yapardı?\" Eğer cevap %0 veya %100 ise, %5 sapmaya "
            "izin ver — pure stratejiler tehlikeli.'"
        ),
    },
    {
        "name": "Patrik Antonius",
        "aliases": ["antonius", "patrik"],
        "era": "2005-günümüz (high stakes cash legend)",
        "style_tag": "Aggressive Big-Pot Specialist",
        "achievements": (
            "Online + live high stakes cash zirve (2008-2015). $25M+ lifetime. "
            "EPT Final Table, Pot Limit Omaha master."
        ),
        "philosophy": (
            "\"Büyük pot'lar büyük edge ister.\" Patrik thin value odakları için "
            "değil, big pot için yaşar. SPR<2 spotlarında specialty — commit "
            "kararları kristal."
        ),
        "range_tendencies": (
            "Loose-aggressive ama disipline edilmiş. Wide preflop, ama "
            "postflop big pot'larda dar value range. PLO'da double-suited "
            "connectors, rundowns favori."
        ),
        "decision_style": (
            "Big-pot focus — küçük pot'larda passive, büyük pot'larda all "
            "aggression. Live tells + physical reads güçlü."
        ),
        "strengths": [
            "Big pot mastery — SPR<3 spotlarında commit kararları",
            "Live tell game — Finnish hockey player intensity",
            "Stamina — uzun cash session'larda focus düşmez",
        ],
        "exploitable": [
            "Çok agresif olduğu için big pot bluff frequency'si bazen yüksek",
            "PLO'da NL'den daha read-able pattern'ler",
        ],
        "signature_quote": (
            "\"Eğer dünyanın en iyi oyuncuları seninle aynı table'da değilse, "
            "yanlış yerdesin.\""
        ),
        "according_to": (
            "Patrik'e göre: 'Bir el'i hızlı oynamadan önce, son hand'i analiz "
            "et. Her el bağımsız değil — son 10 el imaj birikir.'"
        ),
    },
    {
        "name": "Phil Galfond",
        "aliases": ["galfond", "phil galfond", "ofc galfond"],
        "era": "2007-günümüz (theory legend, Run It Once founder)",
        "style_tag": "Theory-Driven Analytical",
        "achievements": (
            "3x WSOP bracelet, Run It Once Poker founder, Galfond Challenge "
            "kazançlı (PLO 1v1 challenge series). PLO teorisi öncüsü."
        ),
        "philosophy": (
            "\"Anlama derinliği execution'dan önemli.\" Phil her spot'u "
            "theoretical first principles'a indirir — solver çıktılarını ezberlemekten "
            "ziyade WHY'larını öğrenmiş."
        ),
        "range_tendencies": (
            "PLO master — NL'de de güçlü ama PLO'da efsane. Position-aware, "
            "blocker-heavy postflop game. Solver-aligned ama deep understanding."
        ),
        "decision_style": (
            "First-principles thinking. Standart yerine 'why is this the "
            "standard?' diye sorar. Coaching tone matter — Run It Once "
            "videos teorinin altın standart'ı."
        ),
        "strengths": [
            "Theory depth — concepts'i first-principles'tan türetir",
            "Teaching ability — Run It Once kursları pioneer",
            "PLO 5-card mastery — modern mix games crusher",
        ],
        "exploitable": [
            "Theory-focused olduğu için bazı pratik exploit'leri overthink eder",
            "PLO live high stakes oyuncusu olarak daha az aktif (variance)",
        ],
        "signature_quote": (
            "\"Bir spot'u sadece 'ne yapacağını' bilmek yetmez — 'neden' yapacağını "
            "bilmek poker'in özüdür.\""
        ),
        "according_to": (
            "Galfond'a göre: 'Yeni bir spot öğrenince, '%80'i durumlarda doğru' "
            "yetmez. 'Neden bu doğru?' soru çiğne. Concept anladığında 100 "
            "varyasyonu çözebilirsin.'"
        ),
    },
    {
        "name": "Stephen Chidwick",
        "aliases": ["chidwick", "stephen", "chid"],
        "era": "2008-günümüz (high roller circuit, HU/HR specialist)",
        "style_tag": "Balanced Modern Pro",
        "achievements": (
            "$50M+ lifetime, 2x Poker Masters champion, US Poker Open dominance. "
            "Heads-up High Roller events specialty."
        ),
        "philosophy": (
            "\"Konsistans yetenekten daha önemli.\" Stephen daily routine, "
            "consistent prep, recovery emphasis. Mental fatigue'i variance "
            "kadar ciddi alır."
        ),
        "range_tendencies": (
            "GTO-baseline ama exploit binder. Final table'larda tight call-off, "
            "early stage'lerde wide steal. ICM aware her zaman."
        ),
        "decision_style": (
            "Methodical. Her spot için range/sizing/blocker/MDF mental "
            "checklist. Variance düşürmeyi kar maksimize etmenin önüne geçirir."
        ),
        "strengths": [
            "Mental routine — pre/post session protocols disiplinli",
            "ICM mastery — bubble + FT navigation",
            "Decision consistency — high variance spotlarında bile aynı kalite",
        ],
        "exploitable": [
            "Çok disiplinli olduğu için occasional creative play eksik",
        ],
        "signature_quote": (
            "\"Bir günde pro olmazsın. 5 yıl her gün aynı çalışmayı yaparsan olursun.\""
        ),
        "according_to": (
            "Chidwick'e göre: 'Her oturum öncesi 30 dk solver review yapma "
            "alışkanlık. Her oturum sonrası 15 dk en pahalı 3 spot review. Bu "
            "ritüel iki yıl içinde seni tanınmaz hale getirir.'"
        ),
    },
    {
        "name": "Bryn Kenney",
        "aliases": ["kenney", "bryn"],
        "era": "2007-günümüz (high roller dominance)",
        "style_tag": "Loose Aggressive Big-Pot",
        "achievements": (
            "$60M+ lifetime (#2 all-time). 1x WSOP bracelet, multiple super "
            "high roller wins. WPT, EPT runs."
        ),
        "philosophy": (
            "\"Risk almaktan korkma — koruyucu oyun sana mediocrity getirir.\" "
            "Bryn loose-aggressive heavy big-pot fokus."
        ),
        "range_tendencies": (
            "Wide ranges her pozisyondan. 3-bet frequency yüksek. Postflop "
            "aggression çok — barrel sıklığı %65+."
        ),
        "decision_style": (
            "Intuitive + risk-tolerant. Pre-game solver study OK, ama oyunda "
            "real-time creative deviations. High variance accept."
        ),
        "strengths": [
            "Big-stack pressure — chip leader olduğunda dominance",
            "Sample size'da tutarlı winrate",
        ],
        "exploitable": [
            "Wide range nedeniyle bazı thin value spotlarda hero call vulnerable",
            "Bluff frequency yüksek — over-bluff diagnose edilince exploit edilebilir",
        ],
        "signature_quote": (
            "\"Para kazanmak için riski almalısın. Korkulu oyuncular orta sıralardan "
            "yukarı çıkamaz.\""
        ),
        "according_to": (
            "Kenney'e göre: 'Big stack iken sürekli baskı kur. Short stack'in fold "
            "equity'sini sömür — onlar her el potential elimination, sen onlar değil.'"
        ),
    },
    {
        "name": "Linus Loeliger",
        "aliases": ["loeliger", "linus", "linus loeliger"],
        "era": "2013-günümüz (online HU cash GOAT, modern era)",
        "style_tag": "GTO-Pure / Solver Master",
        "achievements": (
            "Online HU NL crusher 2017-günümüz. Estimated $10M+ online cash. "
            "GOAT-tier modern era HU player."
        ),
        "philosophy": (
            "\"Solver senin antrenmen, oyun senin sınavın.\" Linus solver-pure "
            "approach — exploit'i bile GTO frame'den türetir."
        ),
        "range_tendencies": (
            "Mixed strategy heavy. Frequency'ler precise (mass solver study). "
            "Postflop bet sizing range conditioned — aynı sizing range daraltma "
            "ile tutarlı."
        ),
        "decision_style": (
            "Full solver immersion — günlük 4-6 saat solver work. Real-time "
            "decisions solver-derived approximations. Düşük variance, yüksek "
            "consistency."
        ),
        "strengths": [
            "GTO precision — pre-flop ve postflop solver-tier frequency",
            "Pre-game preparation — 1000+ saat solver study",
            "Online HU — modern era zirve",
        ],
        "exploitable": [
            "Live tells kullanmaz (online focus) — physical world'de zayıflık",
            "Solver-pure olduğu için fish vs fish spotlarda EV bırakır",
        ],
        "signature_quote": (
            "\"Bir karar verdiğimde, solver'ın aynı kararı vereceğini biliyorum. "
            "Bu confidence kazanır.\""
        ),
        "according_to": (
            "Linus'a göre: 'Solver'ın söylediği şeyi sadece ezberleme — yapısını "
            "anla. Aynı yapı 1000 farklı spot'ta tekrarlar.'"
        ),
    },
]


# ─── Lookup helpers ──────────────────────────────────────────────────────

def _build_alias_map() -> dict[str, dict]:
    out = {}
    for p in PROS:
        out[p["name"].lower()] = p
        for alias in p.get("aliases", []):
            out[alias.lower()] = p
    return out


_ALIAS_MAP = _build_alias_map()


def lookup_pro(name: str) -> Optional[dict]:
    """Exact name or alias lookup (case-insensitive)."""
    return _ALIAS_MAP.get((name or "").strip().lower())


def search_pros(query: str) -> list[dict]:
    """Partial-match search."""
    q = (query or "").strip().lower()
    if not q:
        return []
    seen = set(); out = []
    for alias, pro in _ALIAS_MAP.items():
        if id(pro) in seen: continue
        if q in alias:
            out.append(pro); seen.add(id(pro))
    return out


def list_pros() -> list[dict]:
    return list(PROS)


def format_pro(pro: dict) -> str:
    """Türkçe master-coach style formatlı string."""
    out = [
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"🃏  {pro['name'].upper()}",
        f"     {pro['era']}  ·  Stil: {pro['style_tag']}",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        f"🏆  BAŞARILAR",
        f"     {pro['achievements']}",
        "",
        f"💭  FELSEFE",
        f"     {pro['philosophy']}",
        "",
        f"🎯  PREFLOP YAKLAŞIMI",
        f"     {pro['range_tendencies']}",
        "",
        f"🧠  KARAR SÜRECİ",
        f"     {pro['decision_style']}",
        "",
        f"⭐  GÜÇLÜ YÖNLER",
    ]
    for s in pro.get("strengths", []):
        out.append(f"     • {s}")
    out.append("")
    out.append(f"⚠  KULLANILABİLİR ZAYIFLIK (exploit pattern)")
    for e in pro.get("exploitable", []):
        out.append(f"     • {e}")
    out += [
        "",
        f"🗨  EFSANE SÖZÜ",
        f"     {pro['signature_quote']}",
        "",
        f"📚  {pro['name'].upper()}'A GÖRE",
        f"     {pro['according_to']}",
    ]
    return "\n".join(out)


def quick_advice(pro_name: str, topic: str = "") -> str:
    """Quick 'according to X' style advice for a topic."""
    pro = lookup_pro(pro_name)
    if not pro:
        return f"'{pro_name}' adında bir oyuncu bulunamadı."
    return (
        f"📚  {pro['name'].upper()}'A GÖRE"
        + (f"  ({topic})" if topic else "")
        + f":\n\n     {pro['according_to']}\n\n"
        f"💭  Stil: {pro['style_tag']}  ·  Felsefe: {pro['philosophy']}"
    )
