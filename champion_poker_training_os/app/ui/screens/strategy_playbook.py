"""Strateji Planı (Playbook) — gerçek hayatta uygulanabilir uzun-vade
cash game + MTT yol haritası.

Bu ekran bir "antrenör"den çok bir SAHA REHBERİDİR: masaya oturduğunda
kafanda olması gereken karar çerçeveleri. İçerik, modern solver-çağı pro
konsensüsüne (Upswing / GTOWizard / RIO mantığı) dayanır ama EZBER değil
ANLAYIŞ verir — her ilke "neden" ile gelir, böylece gerçek elde karar
verirken uygulayabilirsin.

İki mod: CASH GAME (6-max derin stack) ve MTT (turnuva, ICM duyarlı).
Her bölüm bir kart; kartlar ilgili trainer'a "Pratik yap" ile bağlanır.
"""
from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)

from app.core.app_state import AppState

# ── Tema renkleri (diğer ekranlarla tutarlı) ─────────────────────────
_ACCENT = "#5ad17a"   # yeşil — ana vurgu
_INFO   = "#5ad1ce"   # cyan
_WARN   = "#d6c668"   # amber — dikkat
_DANGER = "#e87474"   # kırmızı — tuzak
_MUTED  = "#898d80"


# ── İÇERİK ───────────────────────────────────────────────────────────
# Her bölüm: başlık, vurgu rengi, kısa çerçeve cümlesi, ilkeler (her biri
# (kural, neden) çifti), ve isteğe bağlı pratik-trainer bağlantısı.

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
            ("Solundaki oyuncu agresif/iyiyse masayı değiştir; zayıf oyuncu "
             "solunda DEĞİL sağında olsun (sen ondan sonra konuşursun? Hayır "
             "— pozisyonu sende olmalı: zayıf oyuncu sağında).",
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
            ("BB'den geniş savun ama sadece pozisyonu olmayan bir savunma "
             "olduğunu unutma: BTN açılışına ~%40+ defend, UTG'ye çok daha dar.",
             "İndirimli giriş (zaten 1bb koydun) + pot odds geniş defend'i "
             "haklı çıkarır; ama UTG range'i güçlü, fazla savunma sızıntıdır."),
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
            ("Bluff-catch'te MDF'yi (minimum defense frequency) ve rakibin "
             "blöf eğilimini birlikte düşün; pasif rakibe karşı over-fold et.",
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
             "Sonuç-odaklı düşünce (results-oriented) en büyük gelişim "
             "engelidir; EV doğru → uzun vadede para gelir."),
            ("Tilt sinyali (kalp hızı, 'illa kazanmalıyım') → 5 dk ara veya "
             "kalk. Tilt'te oynanan her el negatif EV.",
             "Bir öfke oturumu bir haftanın kârını siler."),
            ("Oturum sayısı değil, EL HACMİ + çalışma saati biriktir. "
             "Haftada X bin el + Y saat review hedefle.",
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


# ── Kart bileşeni ────────────────────────────────────────────────────
def _section_card(section: dict, on_link) -> QFrame:
    card = QFrame()
    card.setObjectName("GTOCard")
    accent = section["accent"]
    card.setStyleSheet(
        f"QFrame#GTOCard {{ background:#131613; border:1px solid #33382c; "
        f"border-left:3px solid {accent}; border-radius:6px; }}"
    )
    lay = QVBoxLayout(card)
    lay.setContentsMargins(18, 14, 18, 16)
    lay.setSpacing(10)

    title = QLabel(section["title"])
    title.setStyleSheet(
        f"color:{accent}; font-size:15px; font-weight:700;")
    title.setWordWrap(True)
    lay.addWidget(title)

    frame_lbl = QLabel(section["frame"])
    frame_lbl.setObjectName("Muted")
    frame_lbl.setWordWrap(True)
    frame_lbl.setStyleSheet("font-style:italic; color:#b9bcae; font-size:12px;")
    lay.addWidget(frame_lbl)

    for rule, why in section["rules"]:
        item = QVBoxLayout()
        item.setSpacing(2)
        r = QLabel(f"▸ {rule}")
        r.setWordWrap(True)
        r.setStyleSheet("color:#f4f5ee; font-size:13px; font-weight:600;")
        item.addWidget(r)
        w = QLabel(f"    └ Neden: {why}")
        w.setWordWrap(True)
        w.setStyleSheet("color:#898d80; font-size:12px;")
        item.addWidget(w)
        lay.addLayout(item)

    link = section.get("link")
    if link:
        label, target = link
        btn = QPushButton(f"⟶  Pratik: {label}")
        btn.setObjectName("NavButton")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{accent}; "
            f"border:1px solid {accent}; border-radius:4px; padding:6px 10px; "
            f"font-size:12px; text-align:left; }} "
            f"QPushButton:hover {{ background:{accent}; color:#0d0f0c; }}")
        btn.clicked.connect(lambda _=False, t=target: on_link(t))
        lay.addWidget(btn)

    return card


class StrategyPlaybookScreen(QWidget):
    """Gerçek-hayat uzun-vade cash + MTT strateji rehberi."""

    coach_message = Signal(str)
    navigate_requested = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self._mode = "cash"

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        scroll.setWidget(body)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

        self._layout = QVBoxLayout(body)
        self._layout.setContentsMargins(28, 24, 28, 28)
        self._layout.setSpacing(16)

        # Başlık
        title = QLabel("Strateji Planı — Saha Rehberi")
        title.setObjectName("Title")
        title.setStyleSheet("font-size:22px; font-weight:800; color:#f4f5ee;")
        self._layout.addWidget(title)

        sub = QLabel(
            "Gerçek hayatta masaya oturduğunda kafanda olması gereken uzun-vade "
            "karar çerçeveleri. Ezber değil ANLAYIŞ: her ilke 'neden'iyle gelir. "
            "GTO temelin — para disiplin + sömürüden gelir."
        )
        sub.setObjectName("Muted")
        sub.setWordWrap(True)
        self._layout.addWidget(sub)

        # Mod seçici
        toggle = QHBoxLayout()
        toggle.setSpacing(8)
        self._cash_btn = QPushButton("♠  CASH GAME")
        self._mtt_btn = QPushButton("♣  MTT (Turnuva)")
        for b in (self._cash_btn, self._mtt_btn):
            b.setCursor(Qt.PointingHandCursor)
            b.setCheckable(True)
        self._cash_btn.clicked.connect(lambda: self._set_mode("cash"))
        self._mtt_btn.clicked.connect(lambda: self._set_mode("mtt"))
        toggle.addWidget(self._cash_btn)
        toggle.addWidget(self._mtt_btn)
        toggle.addStretch(1)
        self._layout.addLayout(toggle)

        # İçerik kabı
        self._content = QVBoxLayout()
        self._content.setSpacing(14)
        self._layout.addLayout(self._content)
        self._layout.addStretch(1)

        self._set_mode("cash")

    # ── mod ──
    def _set_mode(self, mode: str) -> None:
        self._mode = mode
        self._cash_btn.setChecked(mode == "cash")
        self._mtt_btn.setChecked(mode == "mtt")
        active = "#5ad17a"
        for b, on in ((self._cash_btn, mode == "cash"),
                      (self._mtt_btn, mode == "mtt")):
            if on:
                b.setStyleSheet(
                    f"QPushButton {{ background:{active}; color:#0d0f0c; "
                    f"border:none; border-radius:5px; padding:9px 18px; "
                    f"font-size:13px; font-weight:700; }}")
            else:
                b.setStyleSheet(
                    "QPushButton { background:#131613; color:#898d80; "
                    "border:1px solid #33382c; border-radius:5px; "
                    "padding:9px 18px; font-size:13px; }")
        self._render()

    def _render(self) -> None:
        while self._content.count():
            it = self._content.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        sections = CASH_PLAYBOOK if self._mode == "cash" else MTT_PLAYBOOK
        for sec in sections:
            self._content.addWidget(_section_card(sec, self._goto))

    def _goto(self, target: str) -> None:
        self.navigate_requested.emit(target)
