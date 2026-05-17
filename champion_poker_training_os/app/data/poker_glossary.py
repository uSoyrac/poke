"""Türkçe poker sözlüğü — 100+ terim ve konsept.

Her giriş:
  - term: ana adı (lowercase aliases tarafından bulunabilir)
  - aliases: alternatif yazımlar (Türkçe + İngilizce)
  - category: sınıflandırma (preflop / postflop / math / icm / players / stats / general)
  - short: tek cümlelik özet
  - long: detaylı açıklama (master-coach tonunda Türkçe)
  - examples: somut el örnekleri veya değerler (opsiyonel)

Kullanım:
    from app.data.poker_glossary import lookup, search_glossary
    entry = lookup("3-bet")          # → dict
    matches = search_glossary("bluf")  # → list of partial matches
"""
from __future__ import annotations

from typing import Optional


GLOSSARY: list[dict] = [
    # ─── POSITIONS ──────────────────────────────────────────────────────
    {
        "term": "UTG",
        "aliases": ["under the gun", "first to act", "ilk sırada"],
        "category": "position",
        "short": "Sıralı oyunda BB'nin solundaki ilk pozisyon — eylemi açan kişi.",
        "long": (
            "9-max masada UTG (Under the Gun) BB'nin hemen solunda oturur ve "
            "preflop'ta ilk hareket eden oyuncudur. Arkasında 7-8 oyuncu kaldığı "
            "için en dar açış range'i gerekir: AA-77, AKs-ATs, AKo-AJo, KQs, "
            "QJs, JTs, suited connectors 76s-T9s civarı (yaklaşık %12-15)."
        ),
    },
    {
        "term": "UTG+1",
        "aliases": ["mp", "middle position"],
        "category": "position",
        "short": "UTG'nin solu — middle position. UTG'den biraz daha geniş açış.",
        "long": "UTG'ye benzer ama arkada 1 az oyuncu var. Range %14-18.",
    },
    {
        "term": "LJ",
        "aliases": ["lojack", "hijack-1"],
        "category": "position",
        "short": "Hijack'tan önceki pozisyon — middle position son durağı.",
        "long": "LJ açış range'i ~%18-22. Suited Ax (A9s-A6s), KJs, QTs eklenir.",
    },
    {
        "term": "HJ",
        "aliases": ["hijack"],
        "category": "position",
        "short": "CO'dan önce — late position'ın başlangıcı.",
        "long": "HJ ~%22-25 open. Tüm pocket pairs, suited broadway+gappers.",
    },
    {
        "term": "CO",
        "aliases": ["cutoff", "co"],
        "category": "position",
        "short": "BTN'in sağı — ikinci en güçlü pozisyon.",
        "long": (
            "CO (cutoff) BTN'den hemen önce act eder. Range ~%25-32 — geniş "
            "steal range açılır, suited connectors + suited gappers oyuna dahil. "
            "BTN ve blind'lar zayıfsa daha da geniş açılabilir."
        ),
    },
    {
        "term": "BTN",
        "aliases": ["button", "dealer", "düğme"],
        "category": "position",
        "short": "En güçlü pozisyon — preflop sonrası her el son söz hakkı.",
        "long": (
            "Button hep last to act olur postflop. Geniş steal range: ~%40-50 "
            "açış. Suited any-two-cards, offsuit broadway, low pairs. Blind'larda "
            "tight oyuncu varsa daha da geniş açılabilir."
        ),
    },
    {
        "term": "SB",
        "aliases": ["small blind", "küçük blind"],
        "category": "position",
        "short": "Dealer'dan sonra — zorunlu yarım blind koyar, OOP kalır.",
        "long": (
            "SB en zor pozisyon. Yarım blind zaten yatırılmış, ama post-flop "
            "OOP. Modern GTO: limp/raise mix — limp range'i suited connectors + "
            "düşük pairs, raise range'i premium + bluff polarize. Heads-up "
            "kaldığında BB karşı %30-45 open."
        ),
    },
    {
        "term": "BB",
        "aliases": ["big blind", "büyük blind"],
        "category": "position",
        "short": "Tam blind yatıran pozisyon — defend etmek pot odds avantajı verir.",
        "long": (
            "BB tam BB yatırır, postflop OOP kalır ama preflop closing action var. "
            "Defend range'i geniş: 2.3bb açışa karşı sadece %16 equity yeterli — "
            "playable her el call'lanır. 3-bet polarize: AA-JJ, AKs/o value + "
            "A5s-A2s, KQs blocker bluff."
        ),
    },

    # ─── ACTIONS ────────────────────────────────────────────────────────
    {
        "term": "RFI",
        "aliases": ["raise first in", "ilk açış", "open"],
        "category": "preflop",
        "short": "Kimse açmadan önce yapılan ilk raise — preflop'ta pozisyona özel.",
        "long": (
            "RFI (Raise First In) preflop'ta önündeki herkes fold etmişken "
            "yapılan açış. Sizing: 9-max ~2.3-2.5bb, 6-max ~2.5-3bb. RFI range "
            "pozisyona göre değişir: UTG ~%12, BTN ~%45."
        ),
    },
    {
        "term": "3-bet",
        "aliases": ["3bet", "3 bet", "üç bet", "reraise"],
        "category": "preflop",
        "short": "Açışa karşı yapılan ilk raise — preflop pot'u 3x'e çıkarır.",
        "long": (
            "3-bet açış (1st raise) sonrası ikinci raise. Sizing IP ~3.0-3.3x "
            "(opener'ın boyutuna göre), OOP ~3.8-4.2x. Range polarized: value "
            "(AA-QQ, AKs/o, AQs) + bluff (A5s-A4s, KQs, suited connectors). "
            "Linear 3-bet (merge) zayıf rakibe karşı exploitative."
        ),
        "examples": "BTN 2.5bb açar, BB 9bb 3-bet'ler — 9/2.5 = 3.6x OOP standart.",
    },
    {
        "term": "4-bet",
        "aliases": ["4bet", "4 bet", "dört bet"],
        "category": "preflop",
        "short": "3-bet'e karşı yapılan re-raise — premium + blocker bluff polarize.",
        "long": (
            "4-bet polarize olmalı çünkü post-call SPR çok düşük (~3, commit "
            "ediyorsun). Value: QQ+, AKs/o. Bluff: A5s-A2s (A blocker villain'ın "
            "value combos'unu azaltır). JJ/AQs cold-call > 4-bet — bu eller "
            "5-bet jam'e karşı çok zayıf."
        ),
    },
    {
        "term": "5-bet",
        "aliases": ["5bet", "5 bet"],
        "category": "preflop",
        "short": "4-bet'e karşı re-raise — neredeyse her zaman jam.",
        "long": "5-bet genelde all-in. Range çok dar: QQ+, AKs. Bluff yok.",
    },
    {
        "term": "Squeeze",
        "aliases": ["sqz", "sıkıştır"],
        "category": "preflop",
        "short": "Open + caller varken yapılan 3-bet — iki rakibi de fold'a zorlar.",
        "long": (
            "Pot'ta zaten dead money (open + call) olduğu için bluff equity "
            "yüksek. Sizing pot başına ~3-3.5x. Best position: BB (closing action). "
            "Range polarize: AA-JJ, AKs/o value + A5s, suited connectors bluff."
        ),
    },
    {
        "term": "Iso",
        "aliases": ["isolation", "iso-raise"],
        "category": "preflop",
        "short": "Limper'a karşı raise — zayıf oyuncuyla heads-up kalma denemesi.",
        "long": "Limp + iso ~3-4x BB (3+1 per limper). Zayıf limper'a karşı geniş, sıkı oyuncuya karşı dar.",
    },
    {
        "term": "Limp",
        "aliases": ["flat", "düz çağrı"],
        "category": "preflop",
        "short": "Open raise yerine BB'yi sadece call etmek.",
        "long": (
            "Modern GTO limp'i çoğunlukla -EV görür (raise daha fazla fold "
            "equity verir). Ama SB pozisyonundan limp/raise mix optimal — limp "
            "range suited connectors + medium pairs, raise range premium + bluff."
        ),
    },
    {
        "term": "C-bet",
        "aliases": ["cbet", "c-bet", "continuation bet"],
        "category": "postflop",
        "short": "Preflop raiser'ın flop'ta yaptığı bet — range advantage'ı kullanır.",
        "long": (
            "C-bet sıklığı board texture + range advantage'a bağlı. Dry high-card "
            "board (A72r, K83r): %75-90 c-bet, %33 sizing. Wet coordinated "
            "(T98ss): %40-55 c-bet, %66-75 sizing. Paired (KK7): %30-40 polarize."
        ),
    },
    {
        "term": "Donk bet",
        "aliases": ["donk", "donk-bet", "lead"],
        "category": "postflop",
        "short": "Preflop caller'ın preflop raiser'a karşı flop'ta yaptığı lead.",
        "long": (
            "Donk genelde -EV (range advantage caller'da değil), ama belirli "
            "board'larda OK: paired board, low coordinated board (caller'ın range "
            "advantage'ı var). Modern GTO donk frequency'i sıfırdan fazla ama düşük."
        ),
    },
    {
        "term": "Check-raise",
        "aliases": ["x/r", "checkraise"],
        "category": "postflop",
        "short": "Check ettikten sonra rakibin bet'ine raise — strong line.",
        "long": (
            "Check-raise iki amaca hizmet eder: (1) value protect (set, 2pair+) "
            "(2) fold equity bluff (combo draws, backdoor equity). OOP'da güçlü, "
            "IP'de neredeyse yok. Frequency genelde %10-15."
        ),
    },
    {
        "term": "Float",
        "aliases": ["floating", "süzme"],
        "category": "postflop",
        "short": "Position'da c-bet'e call ve sonraki street'te bet/bluff planı.",
        "long": (
            "Float = flop'ta c-bet'i call edip villain check ederse turn'de bet "
            "atmak. En çok IP'de etkili. Backdoor equity + position avantajı + "
            "villain'ın c-bet frequency'sinin yüksek olması gerek."
        ),
    },
    {
        "term": "Semi-bluff",
        "aliases": ["semibluff", "yarım blöf"],
        "category": "postflop",
        "short": "Equity'si olan elle bluff — kazanmak için iki yol var.",
        "long": (
            "Semi-bluff = ya fold equity ile pot'u şimdi al, ya da equity "
            "realize edip showdown'da kazan. En iyi semi-bluff candidates: "
            "open-ended straight draw + flush draw kombinasyonu (12+ out). "
            "Pure bluff'tan her zaman daha karlı."
        ),
    },

    # ─── MATH ────────────────────────────────────────────────────────────
    {
        "term": "Pot Odds",
        "aliases": ["potoddu", "pot oranı", "oran"],
        "category": "math",
        "short": "Ödenecek miktar / call sonrası toplam pot. Minimum equity gereksinimini verir.",
        "long": (
            "Pot odds = bet / (bet + pot + bet). Half-pot bet → %25 equity, "
            "pot bet → %33, 2x overbet → %40. Ama bu MİNİMUM — implied odds "
            "(gelecek kazanç) ve reverse implied (dominated risk) hesaba kat."
        ),
        "examples": "Pot 10bb, villain bets 5bb → call etmek için %25 equity yeterli (5/(5+10+5)).",
    },
    {
        "term": "Equity",
        "aliases": ["ekvati", "ekıvati", "kazanma şansı"],
        "category": "math",
        "short": "Showdown'a gidersek bu el oranı kaç % kazanır?",
        "long": (
            "Equity = pot'un payını alma olasılığı. AKs vs 22 = ~50%/50% (coinflip). "
            "AA vs KK = 81%/19%. Flush draw + overcards vs top pair = ~45%/55%. "
            "Equity calculator'lar (PokerStove, Equilab) hızlı hesaplar."
        ),
    },
    {
        "term": "Implied Odds",
        "aliases": ["implied", "dolaylı oran"],
        "category": "math",
        "short": "Gelecek street'lerde kazanabileceğin ekstra para — pot odds'a eklenir.",
        "long": (
            "Implied odds bir draw'a call'ı haklı çıkarır. 8-out flush draw "
            "(~%19) pure pot odds'a göre half-pot bet'e call yetmez (gereken "
            "%25), ama villain stack'i derin ve hit edersen big bet ödeyecekse "
            "implied odds call'ı +EV yapar."
        ),
    },
    {
        "term": "Reverse Implied Odds",
        "aliases": ["riom", "ters implied"],
        "category": "math",
        "short": "Hit edersen bile dominated kalma riski — call'ı zayıflatır.",
        "long": (
            "Top pair weak kicker (T9 on T-high board) reverse implied'lı: "
            "kazansan da büyük pot kazanmazsın, ama tek bir over-pair'e all-in "
            "olursan büyük kaybedersin. Bu yüzden bu eller cap edilmiş."
        ),
    },
    {
        "term": "EV",
        "aliases": ["expected value", "beklenen değer"],
        "category": "math",
        "short": "Bir kararın uzun vadede ortalama getirisinin matematiksel beklenti değeri.",
        "long": (
            "EV = Σ (sonuç × olasılık). +EV karar uzun vadede kar getirir, -EV "
            "zarar. Tek bir el sonucu önemli değil — 10,000 el sonrası EV "
            "ortalaması gerçekleşir. Master oyuncular sonuç değil karar kalitesi "
            "değerlendirir."
        ),
    },
    {
        "term": "Fold Equity",
        "aliases": ["fold ekvati", "kıvırma şansı"],
        "category": "math",
        "short": "Bet'ine karşı villain'ın fold etme olasılığı — bluff EV'sinin temeli.",
        "long": (
            "Bluff EV = (Fold% × Pot) − (Call% × Bet). Eğer FE yüksekse "
            "bluff +EV. FE düşükse (calling station) sadece value bet."
        ),
    },
    {
        "term": "MDF",
        "aliases": ["minimum defense frequency", "savunma sıklığı"],
        "category": "math",
        "short": "Villain'ın bluff'larını -EV yapmak için savunman gereken minimum frequency.",
        "long": (
            "MDF = 1 − bet/(bet+pot). Half-pot bet'e MDF %67, pot bet'e %50, "
            "2x overbet'e %33. Bu BASELINE — exploit için ayarlanır."
        ),
    },
    {
        "term": "Alpha",
        "aliases": ["α", "alfa"],
        "category": "math",
        "short": "Bluff'un başarılı olması için gereken minimum fold frequency.",
        "long": (
            "Alpha = bet / (bet + pot). Half-pot bluff için α = %33 — yani "
            "villain'ın range'inin en az %33'ünü fold etmesi gerek bluff'ın +EV "
            "olması için. Alpha + MDF = %100."
        ),
    },
    {
        "term": "SPR",
        "aliases": ["stack to pot ratio", "stack/pot"],
        "category": "math",
        "short": "Flop başına stack/pot oranı — commit kararını belirler.",
        "long": (
            "SPR = effective stack / pot. SPR < 3 → flop'ta committed (top pair "
            "+ ile all-in OK). SPR > 7 → manevra alanı var, marginal ellerle "
            "passive line."
        ),
        "examples": "100bb start, 3-bet pot 20bb → SPR = 80/20 = 4 (orta).",
    },

    # ─── RANGE CONCEPTS ─────────────────────────────────────────────────
    {
        "term": "Range",
        "aliases": ["aralık", "menzil", "el grubu"],
        "category": "general",
        "short": "Bir oyuncunun belirli bir spot'ta sahip olabileceği tüm el kombinasyonları.",
        "long": (
            "Range hand-reading'in temeli. 'Villain'ın elinde AK var' değil, "
            "'Villain'ın range'i {AA-JJ, AKs/o, KQs, AQs, A5s-A4s}' — yani "
            "olası tüm combos. Karar bu range'e karşı verilir."
        ),
    },
    {
        "term": "Polarized",
        "aliases": ["polar", "polarize", "kutuplaşmış"],
        "category": "general",
        "short": "Çok güçlü + çok zayıf (bluff) eller — orta yok.",
        "long": (
            "Polarized range value (nuts/near-nuts) + bluff. Orta eller "
            "check-call'a koyulur. Büyük sizing (pot+) polarize range'le tutarlı. "
            "Bluff:value oranı bet size'a göre — pot bet için 1:2 (33% bluff)."
        ),
    },
    {
        "term": "Linear",
        "aliases": ["merge", "merged"],
        "category": "general",
        "short": "Sadece güçlü eller — value-heavy, bluff az veya sıfır.",
        "long": (
            "Linear range zayıf rakibe karşı exploitative. Küçük sizing (33-50% "
            "pot) ile maksimum thin value. Tight rakipler bunu okuyup folding fazla."
        ),
    },
    {
        "term": "Balanced",
        "aliases": ["dengeli", "gto frequency"],
        "category": "general",
        "short": "Aynı line'da value + bluff ratio'sunun GTO denkliğinde olması.",
        "long": (
            "Balanced range exploitable değildir — villain hangi okumayı yaparsa "
            "yapsın -EV deviation kazanamaz. Ama EXPLOIT mümkün olmayan değil, "
            "sadece optimal değil. Master oyuncular GTO baseline üstüne "
            "exploitative ayar bindirirler."
        ),
    },
    {
        "term": "Range Advantage",
        "aliases": ["range avantajı"],
        "category": "postflop",
        "short": "Bir board'da senin range'in villain'inkinden daha çok eşleştiği durum.",
        "long": (
            "BTN open vs BB call → A-high board'lar BTN'in range avantajı. "
            "Mid-low board'lar BB'in range avantajı (BB'in caller range daha çok "
            "düşük connected hand). Range advantage var → c-bet frequency yüksek."
        ),
    },
    {
        "term": "Nut Advantage",
        "aliases": ["nut avantajı"],
        "category": "postflop",
        "short": "Bir board'da en güçlü combos (set, straight, flush) hangi range'de daha çok?",
        "long": (
            "Nut advantage range advantage'tan farklı. Örnek: 765tt board'da BB "
            "ranges daha çok mid pairs (set advantage) içerir; BTN range daha "
            "çok overpair (oversets). Nut advantage olan range BIG SIZING "
            "kullanabilir (overbets, polarized)."
        ),
    },

    # ─── BOARD TEXTURE ──────────────────────────────────────────────────
    {
        "term": "Dry Board",
        "aliases": ["kuru board"],
        "category": "postflop",
        "short": "Az draw, az coordinate eden flop (örn A72 rainbow).",
        "long": "Dry board'lar preflop raiser favori — küçük sizing ile high frequency c-bet.",
    },
    {
        "term": "Wet Board",
        "aliases": ["ıslak board", "coordinated"],
        "category": "postflop",
        "short": "Bir çok draw'ın olduğu board (örn 987 two-tone).",
        "long": "Wet board'larda equity dağılımı daha yakın — büyük sizing ile polarize line.",
    },
    {
        "term": "Paired Board",
        "aliases": ["eşli board", "trip board"],
        "category": "postflop",
        "short": "İki aynı rank içeren board (örn KK7).",
        "long": (
            "Paired board'lar nut advantage'ı capped range'e (calling) verebilir. "
            "Trips küçük pair'lerde sıklıkla caller'da. C-bet frequency düşük."
        ),
    },
    {
        "term": "Monotone",
        "aliases": ["tek renk", "monoton"],
        "category": "postflop",
        "short": "3 community kart aynı suit (örn ♠ ♠ ♠).",
        "long": "Monotone board'da flush combos kritik — A♠ blocker bluff için çok güçlü.",
    },
    {
        "term": "Rainbow",
        "aliases": ["rng", "üç renk"],
        "category": "postflop",
        "short": "Hepsi farklı suit — flush draw yok.",
        "long": "Rainbow board'lar dry kategorisinde — high frequency c-bet uygun.",
    },

    # ─── ICM & TOURNAMENT ───────────────────────────────────────────────
    {
        "term": "ICM",
        "aliases": ["independent chip model", "icm modeli"],
        "category": "icm",
        "short": "Turnuva chip'lerinin $ değerini hesaplayan model — marginal chip = marginal $ değil.",
        "long": (
            "ICM'de chip'in $ değeri DİFFERENT — kazanılan chip'in marginal $ "
            "değeri kaybedilen chip'ten düşük. Sonuç: chipEV call'ları "
            "sıkılaştırmak (risk premium ekleyerek) doğru."
        ),
    },
    {
        "term": "Bubble",
        "aliases": ["balon", "ödüllü yakın"],
        "category": "icm",
        "short": "ITM (in the money) sınırının hemen üstü — maksimum ICM baskısı.",
        "long": (
            "Bubble'da ICM premium %5-15. Short stack maksimum baskıyı yer "
            "(call range %30 daraltılır). Covering big stack max baskı kurar."
        ),
    },
    {
        "term": "ITM",
        "aliases": ["in the money", "ödülde", "para çizgisi"],
        "category": "icm",
        "short": "Turnuvada ödül kazanmaya hak kazandığın bölge.",
        "long": "ITM sonrası pay jumps her sırada artar — final table'a yaklaştıkça ICM premium yükselir.",
    },
    {
        "term": "FT",
        "aliases": ["final table"],
        "category": "icm",
        "short": "Turnuva 9 oyuncu kalan son masası — her sıra ciddi pay jump.",
        "long": "FT'de ICM premium %20-40 olabilir — chipEV call'lar nadir, fold daha sık.",
    },
    {
        "term": "Pay Jump",
        "aliases": ["payjump", "ödül sıçraması"],
        "category": "icm",
        "short": "İki bitiş sırası arasındaki ödül farkı.",
        "long": "Pay jump $ farkı büyükse ICM baskı yüksek. Mid-stack'in #4 → #3 atlama değeri yüksek olabilir.",
    },
    {
        "term": "Bubble Factor",
        "aliases": ["balon faktörü"],
        "category": "icm",
        "short": "Kaybetmenin / kazanmaya oranı — 1.0 normal, 1.3+ yüksek ICM baskı.",
        "long": "BF 1.3 demek: kaybedilen chip kazanılan chip'ten %30 daha pahalı. Bubble'da BF 1.3-1.5.",
    },
    {
        "term": "Risk Premium",
        "aliases": ["risk premi"],
        "category": "icm",
        "short": "ICM nedeniyle chipEV call'ını yapmak için gereken ekstra equity.",
        "long": "Risk premium %5 demek: chipEV %50 equity yeterken, ICM'de %55 gerek.",
    },
    {
        "term": "Satellite",
        "aliases": ["satellit", "uydu turnuva"],
        "category": "icm",
        "short": "Ödül daha büyük turnuvaya bilet — ICM mantığı çok farklı.",
        "long": (
            "Satellite'de chip kazanma marginal yararsız — sadece kesintide kalmak "
            "lazım. Min-stack sopa yiyene kadar fold-fest. Big stack için chip "
            "biriktirmek -$EV. Stack equalization birkaç all-in sonrası."
        ),
    },
    {
        "term": "PKO",
        "aliases": ["progressive knockout", "bounty"],
        "category": "icm",
        "short": "Her oyuncu bounty taşır — kazanırsan yarısını alır, yarısı senin bounty'ne eklenir.",
        "long": (
            "PKO turnuvada her elden $ kazanma potansiyeli. Big stack'leri "
            "elemek yüksek $EV. Call range açılır — bounty equity chipEV "
            "matematiğine eklenir."
        ),
    },
    {
        "term": "M-Ratio",
        "aliases": ["m", "harrington m"],
        "category": "icm",
        "short": "Stack / (SB + BB + ante × oyuncu) — kaç orbit dayanabilirsin?",
        "long": (
            "Harrington's M zones: M>20 green (deep), 10-20 yellow (ortalama), "
            "5-10 orange (kısa), <5 red (push/fold). M düşürdükçe range açılır, "
            "shove dynamics devreye girer."
        ),
    },

    # ─── PLAYER TYPES ───────────────────────────────────────────────────
    {
        "term": "TAG",
        "aliases": ["tight aggressive", "sıkı agresif"],
        "category": "players",
        "short": "Az el oynar ama oynadıkları zaman agresif — solid winning profili.",
        "long": (
            "TAG: VPIP %20-25, PFR %18-22. Premium odaklı, position aware. "
            "Modern winning regs'in temeli. Exploitable side: 3-bet'lere "
            "fazla fold eder (overfold)."
        ),
    },
    {
        "term": "LAG",
        "aliases": ["loose aggressive", "gevşek agresif"],
        "category": "players",
        "short": "Geniş range oynar, çok 3-bet/aggression — riskli ama yüksek EV potansiyel.",
        "long": (
            "LAG: VPIP %28-35, PFR %22-28, AF 3-4. Çok bluff, çok creativity. "
            "Tilt riski yüksek. Exploit: value-heavy line, hero call sıklığı artırılır."
        ),
    },
    {
        "term": "Nit",
        "aliases": ["nit", "rock", "kaya"],
        "category": "players",
        "short": "Çok dar range oynar — premium only, bluff yok.",
        "long": "Nit: VPIP <%14, PFR <%12. Exploit: nit bet attığında fold, nit check ederse büyük bluff +EV.",
    },
    {
        "term": "Calling Station",
        "aliases": ["station", "kalın kafalı"],
        "category": "players",
        "short": "Her şeyi call eder, fold etmez — bluff ona karşı -EV.",
        "long": "Calling station: VPIP %40+, fold-to-cbet <%30. Exploit: hiç bluff yapma, value-heavy thin value bet'ler.",
    },
    {
        "term": "Maniac",
        "aliases": ["maniyak", "çılgın"],
        "category": "players",
        "short": "Aşırı agresif, her şey raise/bluff — variance kraliyeti.",
        "long": "Maniac: PFR >%30, AF 5+. Exploit: dar tight range ile sabırlı, premium 5-bet jam.",
    },
    {
        "term": "Fish",
        "aliases": ["balık", "amatör"],
        "category": "players",
        "short": "Recreational oyuncu — loose passive, çok call, az aggression.",
        "long": "Fish'e karşı: value-heavy, sizing büyütülebilir, bluff azaltılır. Onunla heads-up kalmaya çalış.",
    },
    {
        "term": "Whale",
        "aliases": ["balina", "deep pocket fish"],
        "category": "players",
        "short": "Deep stack'li, çok loose passive fish — kasanın atması.",
        "long": "Whale'le HU kalmak için her şey: iso wide, c-bet thin, value bet large.",
    },
    {
        "term": "Reg",
        "aliases": ["regular", "düzenli oyuncu"],
        "category": "players",
        "short": "Düzenli grinder — TAG-LAG arası, GTO'ya yakın.",
        "long": "Reg'ler exploit zor — küçük sapma yakalamak için 1000+ el sample gerek.",
    },
    {
        "term": "Shark",
        "aliases": ["köpekbalığı", "pro"],
        "category": "players",
        "short": "Profesyonel seviye — GTO + exploitative bilen, çok az exploitable.",
        "long": "Shark'a karşı: sadece premium spotları savaş, marginal spotları fold. Variance düşürmek odak.",
    },
    {
        "term": "Aggro Fish",
        "aliases": ["spazz", "agresif balık"],
        "category": "players",
        "short": "Loose ve aggressive ama unbalanced — büyük EV potansiyel.",
        "long": "Aggro fish bluff'ları çok — call them light. Value spots premium-only.",
    },
    {
        "term": "Tight Passive",
        "aliases": ["sıkı pasif", "weak tight"],
        "category": "players",
        "short": "Dar range oynar ama agresyon yok — premium dahi check-call eder.",
        "long": "Tight passive'e karşı: thin value, ama bet attığında inanın (rare bluff).",
    },

    # ─── STATS ──────────────────────────────────────────────────────────
    {
        "term": "VPIP",
        "aliases": ["voluntary put money in pot", "vpip yüzdesi"],
        "category": "stats",
        "short": "Gönüllü olarak pot'a $ koyduğu el yüzdesi (BB check değil).",
        "long": "VPIP loose/tight'ı gösterir. Pro regs %22-26, fish %35-50, nit %12-14.",
    },
    {
        "term": "PFR",
        "aliases": ["preflop raise %", "pfr yüzdesi"],
        "category": "stats",
        "short": "Preflop raise yapma yüzdesi — aggression göstergesi.",
        "long": "VPIP - PFR farkı 'cold call gap' — küçük gap (1-4) agresif, büyük gap (10+) passive.",
    },
    {
        "term": "3-bet %",
        "aliases": ["3bet yüzdesi"],
        "category": "stats",
        "short": "Açışlara karşı 3-bet sıklığı — preflop aggression.",
        "long": "Modern regs %8-12 3-bet. <5 tight, >15 LAG/maniac.",
    },
    {
        "term": "Fold to 3-bet",
        "aliases": ["f3b"],
        "category": "stats",
        "short": "3-bet'lere fold etme yüzdesi — overfold leak göstergesi.",
        "long": "F3B %70+ overfold (3-bet bluff'a vulnerable). %50- under-fold (4-bet bluff'a vulnerable).",
    },
    {
        "term": "Fold to C-bet",
        "aliases": ["ftcb", "fcb"],
        "category": "stats",
        "short": "C-bet'e fold etme yüzdesi — bluff catcher kuruluğu.",
        "long": "FTCB %60+ overfold (c-bet bluff +EV her el). %30- station (sadece value c-bet).",
    },
    {
        "term": "AF",
        "aliases": ["aggression factor", "agresyon faktörü"],
        "category": "stats",
        "short": "(Bet + raise) / call oranı — postflop aggression.",
        "long": "AF 1-2 passive, 2-3 normal, 3-4 aggressive, 4+ LAG/maniac. Yüksek AF her zaman iyi değil — balanced olmalı.",
    },
    {
        "term": "WTSD",
        "aliases": ["went to showdown", "showdown oranı"],
        "category": "stats",
        "short": "Flop sonrası showdown'a giden el yüzdesi.",
        "long": "WTSD %25-30 normal, >35 station, <20 nit/folder.",
    },
    {
        "term": "W$SD",
        "aliases": ["won at showdown"],
        "category": "stats",
        "short": "Showdown'a giden ellerde kazanma yüzdesi.",
        "long": "W$SD %52-55 normal. >58 muhtemelen showdown'a güçlü ellerle gidiyor (nit). <48 station.",
    },

    # ─── HAND TYPES ─────────────────────────────────────────────────────
    {
        "term": "Premium",
        "aliases": ["premium eller", "elite"],
        "category": "general",
        "short": "En güçlü preflop eller — AA, KK, QQ, AKs, AKo.",
        "long": "Premium her pozisyondan oynanır, value-bet'e ön sayfa. AA en güçlü ama oyna-üstesinden gel sorun yok.",
    },
    {
        "term": "Broadway",
        "aliases": ["broadway eller"],
        "category": "general",
        "short": "T-A arası kartlar — broadway hands.",
        "long": "Suited broadway (KJs, QTs) playable her pozisyondan. Offsuit broadway (KJo, QTo) late position only.",
    },
    {
        "term": "Suited Connector",
        "aliases": ["sc", "suited connecter", "sıralı suited"],
        "category": "general",
        "short": "Aynı suit'ten ardışık kartlar — 87s, 76s, 65s — flush+straight equity.",
        "long": "Suited connectors mid-low position'dan playable. Düşük equity, yüksek implied (set/flush hit deep stack'te jackpot).",
    },
    {
        "term": "Suited Gapper",
        "aliases": ["sg", "atlama suited"],
        "category": "general",
        "short": "Bir gap'li suited (97s, 86s, 75s) — connector'dan biraz zayıf.",
        "long": "Suited gappers late position'dan açılır. Equity SC'den biraz düşük ama unmasked combo potansiyeli var.",
    },
    {
        "term": "Pocket Pair",
        "aliases": ["pair", "cep çifti"],
        "category": "general",
        "short": "Aynı rank'tan iki kart — preflop sevimli, postflop set-mining odak.",
        "long": (
            "Low pairs (22-66) set-mining için ideal — %12 hit rate, hit edersen "
            "büyük pot. Medium (77-JJ) overpair value spot'larda. Premium (QQ+) "
            "value-bet otomatik."
        ),
    },
    {
        "term": "Set",
        "aliases": ["3 of a kind", "üçlü"],
        "category": "general",
        "short": "Pocket pair + board match = set. Disguised, monster.",
        "long": "Set ~%12 hit rate. SPR yüksekse implied odds büyük, küçükse direct value. Slow-play nadir — value-bet hep.",
    },
    {
        "term": "Top Pair",
        "aliases": ["tp", "üst çift"],
        "category": "general",
        "short": "Board'un en yüksek kartıyla pair — kicker önemli.",
        "long": "TP Top Kicker (TPTK) value-bet 3 street. TP weak kicker (TPWK) thin value veya check.",
    },
    {
        "term": "Overpair",
        "aliases": ["op", "üst çift"],
        "category": "general",
        "short": "Board'un en yüksek kartından büyük pocket pair.",
        "long": "Overpair value-heavy ama set'lere karşı SPR yüksekse dikkat. Wet board'da slow down.",
    },
    {
        "term": "Top Set",
        "aliases": ["top set"],
        "category": "general",
        "short": "Board'un en yüksek kartıyla set — neredeyse nuts.",
        "long": "Top set'i fold etmek 100bb deep'te bile zor — value-bet 3 street, value-raise wet board.",
    },

    # ─── DRAWS ──────────────────────────────────────────────────────────
    {
        "term": "Flush Draw",
        "aliases": ["fd", "renk drawi"],
        "category": "general",
        "short": "4 kart aynı suit, 5. için 9 out, ~%35 to river.",
        "long": "Flush draw semi-bluff için ideal. Nut flush draw (Ax suited) call'ı haklı çıkarır, weak FD (87 of clubs) marginal.",
    },
    {
        "term": "Open-Ended Straight Draw",
        "aliases": ["oesd", "açık uçlu kale"],
        "category": "general",
        "short": "2 yönden tamamlanabilir straight — 8 out, ~%32 to river.",
        "long": "OESD + flush draw = combo draw, ~12-15 out, %50+ equity. Semi-bluff jam'in temeli.",
    },
    {
        "term": "Gutshot",
        "aliases": ["inside straight", "iç straight"],
        "category": "general",
        "short": "Sadece bir kart straight'i tamamlar — 4 out, ~%16 to river.",
        "long": "Gutshot pure call zor. Semi-bluff veya backdoor equity (gutshot + overcard + flush draw) lazım.",
    },
    {
        "term": "Combo Draw",
        "aliases": ["kombo draw"],
        "category": "general",
        "short": "Birden fazla draw aynı anda — flush + straight + overcard.",
        "long": "Combo draw equity %50+ olabilir. Semi-bluff all-in birinci sınıf — fold equity + showdown equity birlikte.",
    },
    {
        "term": "Backdoor",
        "aliases": ["bdr", "gizli draw"],
        "category": "general",
        "short": "Turn + river gerektiren draw (örn flush draw'a ihtiyaç var hem turn hem river için).",
        "long": "Backdoor flush ~%4, ama bluff için extra equity. Combo backdoor (BDFD + gutshot) ekstra +EV.",
    },

    # ─── BLOCKERS ───────────────────────────────────────────────────────
    {
        "term": "Blocker",
        "aliases": ["blok", "engel kart"],
        "category": "general",
        "short": "Elindeki kartın villain'ın belirli combos'unu engellemesi.",
        "long": (
            "Blocker iki şekilde kullanılır: (1) bluff için — villain'ın value "
            "combos'unu blokluyorsan onun call range'i daralır. (2) call için — "
            "villain'ın bluff'larını blokluyorsan call'ı zayıflat (onun bluffs azalır)."
        ),
    },
    {
        "term": "Unblocker",
        "aliases": ["açıcı"],
        "category": "general",
        "short": "Villain'ın bluff'larını BLOK ETMEYEN — bluff candidate için ideal.",
        "long": "Unblocker olarak A♠ monotone board'da → villain'ın nut flush blocker'ı yok → kendi bluff'ım daha sık call'lanır.",
    },
    {
        "term": "Card Removal",
        "aliases": ["kart çıkarma", "combinatorics"],
        "category": "general",
        "short": "Belirli kartların elimde olması, villain'ın kombo sayısını azaltır.",
        "long": "AKs vs villain — board'da A çıkarsa benim AK combos kalmadı ama villain'ın AK combos da daha az. Card removal hand-reading'in matematiği.",
    },

    # ─── EXPLOITS ───────────────────────────────────────────────────────
    {
        "term": "GTO",
        "aliases": ["game theory optimal", "oyun teorisi"],
        "category": "general",
        "short": "Hangi dengesizliği yaparsan kaybetmeyeceğin oyun teori dengesi.",
        "long": (
            "GTO 'en iyi karar' değil, 'exploitable olmayan karar'. Zayıf "
            "rakiplere karşı GTO suboptimal — exploit daha kazançlı. Ama "
            "GTO baseline olmadan exploit kötü execute edilir."
        ),
    },
    {
        "term": "Exploitative",
        "aliases": ["exploit", "sömürü"],
        "category": "general",
        "short": "Villain'ın spesifik leak'lerini hedefleyen +EV sapma — GTO'dan ayrılır.",
        "long": (
            "Exploitative play higher variance + higher EV. Calling station'a "
            "karşı bluff fold = exploit. Nit'e karşı bluff increase = exploit. "
            "Master'lar GTO baseline'a exploit binder."
        ),
    },
    {
        "term": "Overfold",
        "aliases": ["aşırı fold"],
        "category": "general",
        "short": "Bir spot'ta MDF'in altında fold etmek — bluff'a vulnerable.",
        "long": "Overfold leak'i tespit etmek için stats: FTCB %65+, F3B %75+, FT4B %85+.",
    },
    {
        "term": "Overcall",
        "aliases": ["aşırı call"],
        "category": "general",
        "short": "MDF'in üstünde call etmek — value'ya vulnerable.",
        "long": "Overcaller'a karşı: hiç bluff yapma, value'yu thin'e kadar getir.",
    },
    {
        "term": "Hero Call",
        "aliases": ["kahraman call"],
        "category": "general",
        "short": "Marjinal bluffcatcher ile villain'a karşı call — exploit move.",
        "long": "Hero call: villain'ın over-bluff'larına karşı. Stat support gerek (high bluff frequency). Random hero call -EV.",
    },

    # ─── GENERAL CONCEPTS ───────────────────────────────────────────────
    {
        "term": "Variance",
        "aliases": ["varyans", "şans dalgası"],
        "category": "general",
        "short": "Aynı kararlardan farklı sonuçlar — sample size küçükse büyük etki.",
        "long": (
            "Variance kısa vadede her şey. 100 el sonrası winrate ölçülemez. "
            "10,000 el cash, 1000 turnuva minimum sample. Variance'ı 'kötü "
            "oynadım' diye yorumlamak tilt başlangıcı."
        ),
    },
    {
        "term": "Tilt",
        "aliases": ["öfke", "kontrol kaybı"],
        "category": "general",
        "short": "Duygusal durumun karar kalitesini bozması — variance'a en büyük düşman.",
        "long": (
            "Tilt types: revenge (kaybedince loose play), despair (kötü "
            "stretch'te nit play), entitlement (\"benim sıram\"). Anti-tilt: "
            "100bb+ loss sonrası oturum kapat, 5 dk dinlen, fresh karar."
        ),
    },
    {
        "term": "Bankroll",
        "aliases": ["kasa", "para yönetimi"],
        "category": "general",
        "short": "Poker için ayrılan toplam $ — variance'ı absorbe eden buffer.",
        "long": "Cash NL 30-50 buy-in, MTT 100-200 buy-in, SnG 40-60 buy-in. Move-up için 30+ BI hedef bankroll.",
    },
    {
        "term": "Winrate",
        "aliases": ["bb/100", "kazanma oranı"],
        "category": "general",
        "short": "100 elde ortalama kar (bb cinsinden).",
        "long": "Cash NL'de 5-10bb/100 solid, 10-20 elite. MTT'de ROI ölçülür (%20+ pro level).",
    },
    {
        "term": "Hand History",
        "aliases": ["hh", "el geçmişi"],
        "category": "general",
        "short": "Oynanan ellerin kayıtları — review için altın madeni.",
        "long": "HH review en hızlı leak tespit yöntemi. Bu app'te Tournament Play sonrası 📁 Past → çift tık → frame-by-frame replay.",
    },
    {
        "term": "Solver",
        "aliases": ["GTO çözücü", "PioSolver"],
        "category": "general",
        "short": "Spot'lara GTO çözüm üreten yazılım — PioSolver, MonkerSolver, GTO Wizard.",
        "long": "Solver inputs: stack, pot, ranges, bet sizes. Output: frequency distribution per action. Solver çıktısı baseline, exploit binder.",
    },
    {
        "term": "Equity Calculator",
        "aliases": ["pokerstove", "equilab"],
        "category": "general",
        "short": "Hand vs hand veya hand vs range equity hesaplama aracı.",
        "long": "Equity calculator otomatik: AKs vs 22 = 50/50, AKs vs JJ = 45/55, AKs vs {AA,KK,QQ} = 26/74.",
    },
]


# ─── Aliases lookup ──────────────────────────────────────────────────────

def _build_alias_map() -> dict[str, dict]:
    """Build a lookup map from any alias (lowercase) → entry."""
    out = {}
    for entry in GLOSSARY:
        out[entry["term"].lower()] = entry
        for alias in entry.get("aliases", []):
            out[alias.lower()] = entry
    return out


_ALIAS_MAP = _build_alias_map()


def lookup(term: str) -> Optional[dict]:
    """Exact term or alias lookup (case-insensitive)."""
    return _ALIAS_MAP.get((term or "").strip().lower())


def search_glossary(query: str, max_results: int = 8) -> list[dict]:
    """Partial-match search across terms + aliases. Returns up to N entries."""
    q = (query or "").strip().lower()
    if not q:
        return []
    seen_ids = set()
    out = []
    # Exact alias first
    if q in _ALIAS_MAP:
        e = _ALIAS_MAP[q]
        out.append(e); seen_ids.add(id(e))
    # Substring match
    for alias, entry in _ALIAS_MAP.items():
        if id(entry) in seen_ids:
            continue
        if q in alias:
            out.append(entry)
            seen_ids.add(id(entry))
        if len(out) >= max_results:
            break
    return out


def category_index() -> dict[str, list[dict]]:
    """Group all entries by category."""
    out: dict[str, list[dict]] = {}
    for entry in GLOSSARY:
        out.setdefault(entry["category"], []).append(entry)
    return out


def format_entry(entry: dict) -> str:
    """Master-coach style Türkçe formatlı tek-block string."""
    out = [
        f"📖  {entry['term'].upper()}",
        f"     {entry.get('short', '')}",
        "",
        entry.get("long", ""),
    ]
    if entry.get("examples"):
        out.append("")
        out.append(f"💡 Örnek: {entry['examples']}")
    return "\n".join(out)
