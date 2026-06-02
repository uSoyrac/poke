"""Strateji Playbook — tek doğru kaynak (cash + MTT uzun-vade ilkeleri).

UI ekranı (app/ui/screens/strategy_playbook) ve AI Koç (app/ai) bu modülden
besenir; böylece kullanıcının gördüğü saha rehberi ile koçun referans aldığı
ilkeler BİREBİR aynıdır — koç "playbook'taki X ilkesi" derken ekranla tutarlı.

Saf veri + metin renderer (Qt/DB bağımsız). İçerik modern solver-çağı pro
konsensüsüne dayanır; her ilke 'neden'iyle gelir (ezber değil anlayış).
"""
from __future__ import annotations

# Vurgu renkleri yalnız UI içindir; veri tarafında zararsız string olarak durur.
_ACCENT = "#5ad17a"
_INFO = "#5ad1ce"
_WARN = "#d6c668"
_DANGER = "#e87474"


CASH_PLAYBOOK = [
    {
        "title": "1 · Bankroll & Masa Seçimi — uzun vadede #1 edge",
        "accent": _ACCENT,
        "frame": "Para kazanmak oynadığın masayı seçmekle başlar, oynadığın "
                 "ellerle değil. En iyi GTO bile kötü masada zar zor kazanır.",
        "rules": [
            ("Cash için en az 30-40 buy-in bankroll tut (NL'de 40 BI ideal).",
             "Varyans gerçek; düşük roll = korkak/yanlış kararlar + iflas riski."),
            ("Masaya oturmadan önce 2 dk izle: ortalama pot, limp sayısı, "
             "kim çok kalıyor (station), kim çok 3bet'liyor.",
             "Zayıf-pasif (çok limp/call) masa = en kârlı masa. Reg-dolu "
             "masada edge'in sıfıra yakındır."),
            ("Zayıf oyuncu pozisyon olarak sağında olsun (sen ondan sonra "
             "konuşursun).",
             "Pozisyon parayı yönlendirir; zayıf parayı pozisyonla avlarsın."),
            ("Kötü oturumu 'geri kazanma' modunda uzatma. Stop-loss koy "
             "(örn. 3 buy-in) ve kalk.",
             "Tilt + yorgunluk EV'ni negatife çevirir; yarın aynı masa var."),
        ],
        "link": ("Reports — kendi winrate/varyansını izle", "Reports"),
    },
    {
        "title": "2 · Preflop İskelet — pozisyon kralı",
        "accent": _INFO,
        "frame": "Cash 100bb derinde preflop'u pozisyona göre otomatikleştir. "
                 "Doğru açılış range'i tüm sokakları kolaylaştırır.",
        "rules": [
            ("Pozisyon geçtikçe aç: UTG ~%15, MP ~%18, CO ~%27, BTN ~%45, "
             "SB ~%40 (raise-or-fold, limp yok).",
             "Geç pozisyonda daha az oyuncu arkanda + pozisyon avantajı = "
             "daha geniş kârlı açılış."),
            ("3bet'i polarize tut: değer (QQ+, AK) + blöf (A5s-A2s, suited "
             "connector). Orta elleri (AJo, KQo) çoğunlukla call/fold.",
             "Düz (linear) 3bet sömürülür; polarize range hem fold equity "
             "hem 4bet'e karşı koruma verir."),
            ("BB'den geniş savun ama pozisyonsuz olduğunu unutma: BTN "
             "açılışına ~%40+ defend, UTG'ye çok daha dar.",
             "İndirimli giriş + pot odds geniş defend'i haklı çıkarır; ama "
             "UTG range'i güçlü, fazla savunma sızıntıdır."),
            ("Limp'leme. Açılırsan raise'le; oynamayacaksan fold.",
             "Limp inisiyatifi verir, pot'u çok-yönlü yapar, range'ini zayıf "
             "gösterir."),
        ],
        "link": ("Preflop Range Trainer — ezberle + reflekse çevir", "Preflop Range Trainer"),
    },
    {
        "title": "3 · Postflop Sistemi — range vs nut avantajı",
        "accent": _ACCENT,
        "frame": "Her flop'ta iki soru: (1) range avantajı kimde? (2) nut "
                 "avantajı kimde? C-bet kararın bunlardan çıkar.",
        "rules": [
            ("Açan sensin ve board kuru/yüksek (A-K-x, K-Q-x) ise küçük "
             "(%25-33 pot) yüksek frekansta c-bet at.",
             "Range avantajı sende (preflop açan AK/AQ/KK içerir); küçük "
             "size tüm range'inle ucuza baskı kurar."),
            ("Islak/orta board (9-8-6, J-T-8) bağlandığında c-bet frekansını "
             "düşür, polarize ol (güçlü + güçlü draw).",
             "Bu boardlar BB'nin call range'ine yarar; otomatik c-bet para "
             "yakar."),
            ("Turn'de barrel'ı equity + range ile seç: nut'larını ve iyi "
             "draw'larını çift-fişekle, havasız blöfleri bırak.",
             "Turn pot'u büyütür; disiplinsiz turn barrel en pahalı cash "
             "sızıntısıdır."),
            ("River'da değer/blöf dengesi: ince değeri bas (rakip daha kötü "
             "call'larla), blöfü unblocker'larla seç.",
             "İyi oyuncular check'lerini yakalar; ince değer ve dengeli blöf "
             "uzun-vade winrate'i yapar."),
        ],
        "link": ("Postflop & River Trainer — board okuma pratiği", "Postflop Trainer"),
    },
    {
        "title": "4 · Pot Kontrol & Hat Seçimi",
        "accent": _WARN,
        "frame": "Elinin gücü değil, RAKİP RANGE'İNE karşı gücü önemli. "
                 "Orta-güç eller pot'u küçük tutar.",
        "rules": [
            ("Tek-çift pair (top pair zayıf kicker) ile 3 sokak değer "
             "avlamaya çalışma — check/call hattı seç.",
             "Büyük pot'ta orta el genelde ya daha iyiyi call ettirir ya da "
             "daha kötüyü kaçırır (ters seçim)."),
            ("Nut'a yakın elinle pot'u büyüt; zincirleme bet planı kur "
             "(flop-turn-river kaç bet, hangi size).",
             "Değer maksimizasyonu planlıdır; river'a kadar düşünmek 'şimdi "
             "ne kadar?' panikini önler."),
            ("Bluff-catch'te MDF'yi ve rakibin blöf eğilimini birlikte "
             "düşün; pasif rakibe karşı over-fold et.",
             "GTO MDF dengeli rakip içindir; gerçek hayatta çoğu rakip "
             "river'da yeterince blöf yapmaz → fold kârlı."),
        ],
        "link": ("Math Lab — pot odds, MDF, EV refleksi", "Math Lab"),
    },
    {
        "title": "5 · Sömürü (Exploit) — gerçek masada GTO'dan sapmak",
        "accent": _INFO,
        "frame": "GTO temelin; para sömürüden gelir. Tip oku, dengeyi BİLEREK boz.",
        "rules": [
            ("Station'a (çok call eden) karşı: blöfü kes, değeri ince bas, "
             "büyük size'la değer al.",
             "Fold etmeyen rakibe blöf para yakar; o senin değer bahislerini "
             "ödeyen ATM'dir."),
            ("Nit'e (çok fold eden) karşı: c-bet/3bet blöfünü artır, "
             "showdown'a kadar gitmeden pot'ları topla.",
             "Aşırı fold = bedava pot; güçlü eli zaten belli eder."),
            ("Maniac'a (aşırı agresif) karşı: trap kur, geniş call/check-raise, "
             "marjinali sabit tut.",
             "O senin yerine blöf yapar; sen sadece güçlü tutup ödeme alırsın."),
        ],
        "link": ("Opponent Profiles — arketip okuma", "Opponent Profiles"),
    },
    {
        "title": "6 · Mental Oyun & Uzun-Vade Disiplin",
        "accent": _DANGER,
        "frame": "Cash'te kazanan oyuncu en zeki değil, en TUTARLI olandır. "
                 "Varyans seni test eder; süreç odaklı kal.",
        "rules": [
            ("Sonucu değil KARARI değerlendir. Doğru fold edip rakip blöf "
             "gösterse bile karar doğruydu.",
             "Sonuç-odaklı düşünce en büyük gelişim engelidir; EV doğru → "
             "uzun vadede para gelir."),
            ("Tilt sinyali (kalp hızı, 'illa kazanmalıyım') → 5 dk ara veya "
             "kalk. Tilt'te oynanan her el negatif EV.",
             "Bir öfke oturumu bir haftanın kârını siler."),
            ("Oturum sayısı değil, EL HACMİ + çalışma saati biriktir.",
             "Beceri hacim×geri-bildirim ile artar; sadece oynamak platoda "
             "tutar."),
        ],
        "link": ("Study Planner — haftalık rutin kur", "Study Planner"),
    },
]

MTT_PLAYBOOK = [
    {
        "title": "1 · Stack Derinliği Fazları — turnuva tek oyun değil",
        "accent": _ACCENT,
        "frame": "MTT'de 'doğru' oyun stack derinliğine göre TAMAMEN değişir. "
                 "Önce kaç BB'in var ona bak, sonra karar ver.",
        "rules": [
            ("Derin (>40bb): cash gibi oyna — postflop oyna, suited connector/"
             "küçük pair ile set/draw avla, pozisyon kullan.",
             "Derin stack = ima oranı (implied odds) yüksek; speküle eller "
             "kârlı, postflop edge'ini kullanırsın."),
            ("Orta (20-40bb): 3bet'ler genelde commit eder; range'i sıkılaştır, "
             "draw'larla taşkın oynama, fold equity'yi koru.",
             "Bu derinlikte yanlış commit = turnuvadan eleniş; SPR farkındalığı "
             "kritik."),
            ("Kısa (10-20bb): re-steal jam + open-jam devreye girer; "
             "marjinal postflop yerine net preflop kararlar.",
             "Kısa stackte postflop manevra alanı yok; fold equity en değerli "
             "silahın."),
            ("Push/Fold (<10bb): Nash itme/yatma tablosuna göre oyna; "
             "pozisyon + stack'e göre jam range'i ezberle.",
             "Bu bölge matematiksel olarak çözülmüştür; doğru jam/fold "
             "neredeyse kayıpsızdır, sapma pahalıdır."),
        ],
        "link": ("ICM / PKO Trainer — push/fold + ICM", "ICM / PKO Trainer"),
    },
    {
        "title": "2 · Ante Çağı & Step-Stealing",
        "accent": _INFO,
        "frame": "Ante girince pot büyür → çalmak daha kârlı. Pasif kalmak "
                 "blind+ante'ye yenik düşmektir.",
        "rules": [
            ("Ante varken açılış range'ini genişlet, özellikle geç pozisyon "
             "ve blind'lere karşı steal artır.",
             "Risk/ödül düzelir: aynı raise daha büyük ödülü hedefler → "
             "geniş steal +EV olur."),
            ("Blind'lerden geniş re-steal (3bet jam) yap; sıkı açanları "
             "cezalandır.",
             "Geç pozisyon geniş açar; bunu bilerek matematiksel re-steal "
             "fold equity'den para basar."),
            ("Big blind'den ante ile birlikte daha geniş savun — pot zaten "
             "şişkin, indirimli giriştesin.",
             "Pot odds'un iyileşir; aşırı fold büyük blind sızıntısıdır."),
        ],
        "link": ("MTT Trainer — turnuva spotları", "MTT Trainer"),
    },
    {
        "title": "3 · ICM & Kabarcık (Bubble) & Ödül Sıçramaları",
        "accent": _WARN,
        "frame": "Turnuvada FİŞ ≠ PARA. Chip-EV değil $-EV (ICM) kazanır. "
                 "Bubble'da fişin değeri non-lineer artar.",
        "rules": [
            ("Bubble'a yakın: büyük stack'le baskı kur (herkes para'ya "
             "girmek için sıkışır), kısa stack'le hayatta kal.",
             "ICM baskısı: orta stack'ler çıkmaktan korkar → büyük stack "
             "bedava pot toplar."),
            ("Kısa/orta stackken marjinal coinflip'lerden kaçın; daha kötü "
             "stack'ler önce patlasın.",
             "Eleniş = $0 katkı; 'doğru' chip-EV call bile bubble'da $-EV "
             "olabilir (ICM punt)."),
            ("Pay jump'lar büyükse (final table, satellite) fold marjı çok "
             "genişler — premium dışını bırak.",
             "Satellite'te 1. ile 10. aynı bileti alır → sadece hayatta "
             "kalmak hedef; agresif call felaket."),
        ],
        "link": ("ICM / PKO Trainer — bubble & pay-jump", "ICM / PKO Trainer"),
    },
    {
        "title": "4 · Final Table & Heads-Up",
        "accent": _ACCENT,
        "frame": "Para final table'da yapılır. ICM en serttir; HU'da oyun "
                 "tamamen değişir (her el oyna).",
        "rules": [
            ("Final table'da stack dağılımını sürekli oku: kim ICM'den "
             "sıkışıyor, kime baskı kurabilirsin.",
             "Orta stack'ler en çok sıkışan; onların blind'lerini hedef al, "
             "büyük stack'le çatışmaktan kaçın."),
            ("Heads-up'a kalınca range'i AÇ: BTN/SB'den çok geniş aç, "
             "BB'den çok geniş savun.",
             "2 oyuncuda blind'ler her el sana mal olur; pasiflik HU'da "
             "hızlı eleniştir."),
            ("HU postflop'ta agresyon + pozisyon kralı; aggressor kalmaya "
             "çalış, check'leri yakala.",
             "Range'ler geniş → çoğu el zayıf; agresyon ve okuma farkı "
             "yaratır."),
        ],
        "link": ("Tournament Simulator — FT/HU senaryosu", "Tournament Simulator"),
    },
    {
        "title": "5 · PKO / Bounty Ayarı",
        "accent": _INFO,
        "frame": "Bounty (kelle parası) pot'a görünmez ek değer katar → "
                 "elemeye oynamaya value yükler.",
        "rules": [
            ("Rakibi ELEYEBİLECEK stack'teysen call/jam range'ini genişlet — "
             "ödül = pot + bounty.",
             "Bounty fişle ölçülmez ama gerçek $; covering stack ile call "
             "eşiği belirgin düşer."),
            ("Kendin kısa ve covered isen normal ICM gibi sıkı oyna — "
             "bounty'i sen değil rakip kovalıyor.",
             "Bounty değeri sadece eleyebilen tarafta; covered taraf yine "
             "hayatta kalmaya oynar."),
        ],
        "link": ("ICM / PKO Trainer — bounty hesabı", "ICM / PKO Trainer"),
    },
    {
        "title": "6 · Bankroll, Varyans & Hacim (gerçek-hayat MTT)",
        "accent": _DANGER,
        "frame": "MTT varyansı CANAVAR. Yetenekli oyuncu bile aylarca "
                 "kazanmayabilir. Roll + zihniyet bunu taşımalı.",
        "rules": [
            ("MTT için 100+ buy-in bankroll tut (yüksek alan = daha çok BI).",
             "MTT'de top-heavy ödül + büyük alan = uzun downswing kaçınılmaz; "
             "yetersiz roll = iflas."),
            ("Late-reg / re-entry kararını ICM + alan kalitesiyle ver, "
             "duyguyla değil.",
             "Geç kayıt bazen daha sığ ama daha net push/fold demek; "
             "re-entry sadece +EV alanda mantıklı."),
            ("Sonucu değil kararı izle; ITM% + ROI'yi uzun örneklemde oku "
             "(yüzlerce turnuva).",
             "Tek turnuva sonucu gürültü; 'kötü oynadım mı' sorusunu el "
             "review'da yanıtla, sonuçta değil."),
        ],
        "link": ("Tournament Analysis — ROI/ITM + karar review", "Tournament Analysis"),
    },
]


def section_by_title(title: str) -> dict | None:
    """Başlığa göre playbook bölümünü bul (cash veya MTT)."""
    for sec in CASH_PLAYBOOK + MTT_PLAYBOOK:
        if sec["title"] == title:
            return sec
    return None


# ── Leak → Playbook eşlemesi ─────────────────────────────────────────
# Tespit edilen her leak'i ihlal ettiği uzun-vade ilkeye bağlar. Sıra
# önemli: ilk eşleşen kazanır → daha spesifik anahtarlar önce gelir.
# (book, section_index) — index ilgili listedeki bölüm sırasıdır.
_LEAK_RULES: list = [
    # MTT — kısa stack / push-fold
    (("push/fold", "push", "short stack", "short-stack", "shove", "jam", "nash"),
     "mtt", 0),
    # MTT — ICM / bubble / pay jump
    (("icm", "bubble", "call-off", "pay jump", "final table", "satellite"),
     "mtt", 2),
    # Cash — river / bluff / value (Postflop Sistemi)
    (("river", "overbluff", "thin value", "bluff selection", "blocker"),
     "cash", 2),
    # Cash — c-bet / barrel / board / multiway (Postflop Sistemi)
    (("cbet", "c-bet", "barrel", "turn", "board", "postflop", "multiway"),
     "cash", 2),
    # Cash — over-fold / pasiflik / bluff-catch (Pot Kontrol & Hat Seçimi)
    (("over-fold", "overfold", "over-folding", "pot control", "passiv",
      "pasif", "oop", "bluff-catch", "fold to cbet", "fold-to-cbet"),
     "cash", 3),
    # Cash — over-aggression / spew (Sömürü vs disiplin)
    (("spew", "over-aggress", "over-aggression", "aggression"),
     "cash", 4),
    # Cash — 3bet / squeeze / 4bet (Preflop İskelet)
    (("3bet", "3-bet", "squeeze", "4bet", "4-bet", "cold call", "cold-call"),
     "cash", 1),
    # Cash — preflop açılış / BB defend / steal (Preflop İskelet)
    (("bb ", "underdefend", "defend", "vs rfi", "vs btn", "rfi", "sb ",
      "preflop", "open", "steal", "limp"),
     "cash", 1),
]


def playbook_ref_for_leak(name: str, category: str = "") -> dict | None:
    """Bir leak'i (ad + kategori) en uygun Playbook bölümüne eşle.

    Döndürür: {"format": "cash"|"mtt", "section": başlık, "principle": çerçeve,
    "screen": "Strategy Playbook"} veya eşleşme yoksa None. Leak Finder bunu
    "ihlal ettiğin ilke" olarak gösterir + ekrana yönlendirir.
    """
    hay = f"{name} {category}".lower()
    for keys, book_name, idx in _LEAK_RULES:
        if any(k in hay for k in keys):
            book = CASH_PLAYBOOK if book_name == "cash" else MTT_PLAYBOOK
            if 0 <= idx < len(book):
                sec = book[idx]
                return {
                    "format": book_name,
                    "section": sec["title"],
                    "principle": sec["frame"],
                    "screen": "Strategy Playbook",
                }
    return None


def playbook_reference_text(max_rules: int = 2) -> str:
    """Playbook'u AI Koç sistem prompt'una gömülecek KOMPAKT metne çevir.

    Her bölümün başlığı + çerçevesi + ilk ``max_rules`` ilkesi alınır (token
    tasarrufu). Koç bu ilkelere ismen atıf yapabilsin diye başlıklar korunur.
    """
    lines: list[str] = []

    def _emit(header: str, book: list) -> None:
        lines.append(header)
        for sec in book:
            lines.append(f"• {sec['title']}: {sec['frame']}")
            for rule, why in sec["rules"][:max_rules]:
                lines.append(f"   - {rule} (Neden: {why})")

    _emit("CASH GAME PLAYBOOK (uzun-vade):", CASH_PLAYBOOK)
    lines.append("")
    _emit("MTT PLAYBOOK (turnuva, uzun-vade):", MTT_PLAYBOOK)
    return "\n".join(lines)
