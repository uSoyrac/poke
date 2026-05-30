from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.core.app_state import AppState
from app.db.seed_data import bot_profiles


# ─── Rich archetype profiles ─────────────────────────────────────────────────

_PROFILES: list[dict] = [
    {
        "id": "nit",
        "name": "Nit",
        "tag": "TIGHT PASSIVE",
        "color": "#7abaff",
        "description": (
            "The Nit plays an extremely narrow preflop range (top 10–14% of hands) "
            "and rarely shows aggression post-flop. They fold to most pressure and only "
            "continue with very strong holdings. Afraid of volatility, they often leave "
            "chips on the table by folding profitable spots."
        ),
        "tell": "Checks or calls when they miss; only bets/raises the nuts or near-nuts.",
        "exploit": [
            "Steal their blinds relentlessly — they fold >70% of the time.",
            "Continuation bet almost every flop they don't 3bet preflop.",
            "When they do raise, give them enormous credit — fold marginal hands.",
            "Never bluff on the river unless you have blockers AND they checked twice.",
        ],
        "counter": (
            "Position is decisive. Attack their BB from any late position. "
            "Avoid thin value against them (they only call with the goods)."
        ),
        "common_mistake": "Bluffing them — they rarely fold when they have something.",
    },
    {
        "id": "tight_passive",
        "name": "Tight Passive",
        "tag": "ROCK",
        "color": "#aaaaaa",
        "description": (
            "Similar to the Nit but slightly wider in range. Calls more often rather than "
            "raising. Passive postflop — checks back strong hands on the flop, giving free "
            "cards. Difficult to get value from because they rarely build the pot."
        ),
        "tell": "Calls a lot but rarely raises. Shows down medium-strength hands.",
        "exploit": [
            "Value bet thinner — they call down with second-pair.",
            "Do not slow-play; they often check back for free cards.",
            "Steal freely preflop from late positions.",
            "Large river bets get paid off more than small ones.",
        ],
        "counter": (
            "Build big pots when you have the range advantage. "
            "Don't bluff rivers — their passive calling range is wide."
        ),
        "common_mistake": "Trying to bluff them off medium-strength holdings.",
    },
    {
        "id": "calling_station",
        "name": "Calling Station",
        "tag": "FISH — LOOSE PASSIVE",
        "color": "#ff8c5a",
        "description": (
            "Calling Stations play a wide preflop range and never fold to bets — they call "
            "every street with any pair, draw, or even overcards. They rarely bluff and rarely "
            "raise. Their stack leaks to every value bet across the session."
        ),
        "tell": "Calls every street with any piece. Almost never raises or folds.",
        "exploit": [
            "Value bet every street with two-pair or better — they call it all.",
            "Never bluff. Period. They cannot be bluffed off hands.",
            "Bet larger for value — sizing up does not make them fold.",
            "Play position on them; multiway pots against them are fine with strong hands.",
        ],
        "counter": (
            "Your implied odds go through the roof. Set-mine aggressively. "
            "Accept coolers gracefully — they will occasionally hold."
        ),
        "common_mistake": "Bluffing. Every single bluff loses EV against them.",
    },
    {
        "id": "maniac",
        "name": "Maniac",
        "tag": "HYPER AGGRESSIVE",
        "color": "#ff3333",
        "description": (
            "The Maniac fires bets and raises on every street with an enormous range. "
            "They bluff constantly and apply relentless pressure. High variance, but "
            "they give enormous action. If they hold a strong hand, they will stack you. "
            "Against good players they leak huge amounts when their bluffs are called."
        ),
        "tell": "3bets, check-raises and overbets frequently. Rarely checks back or calls.",
        "exploit": [
            "Trap with strong hands — let them bet into you.",
            "Widen your call-down range significantly (they're over-bluffing).",
            "Avoid re-bluffing; their range is often capped but they will call bluff-catchers.",
            "Give them lots of rope — slow-play and let them hang themselves.",
        ],
        "counter": (
            "Play IP as much as possible. Avoid 3bet/fold lines — they rarely fold to 3bets. "
            "Call down wider with bluff-catchers."
        ),
        "common_mistake": "Getting into bluff wars or folding too often to their aggression.",
    },
    {
        "id": "lag",
        "name": "Loose Aggressive",
        "tag": "LAG — SKILLED",
        "color": "#c77dff",
        "description": (
            "The LAG plays a wide range aggressively, mixing value and bluffs across all "
            "streets. Unlike the Maniac, the skilled LAG balances their aggression well. "
            "They build pots, collect dead money, and apply maximum pressure on opponents. "
            "Hardest archetype to exploit."
        ),
        "tell": "Aggressive but structured. Sizing tells reveal bluff vs value tendencies.",
        "exploit": [
            "Look for sizing patterns (large = nutted or polarized, small = weak).",
            "Trap them with premium hands — they hate giving up aggression.",
            "3bet them light in position to balance and take initiative.",
            "Track their river bluff frequency to calibrate call-down threshold.",
        ],
        "counter": (
            "Play back in position. Use your position advantage. "
            "Don't let them run you over — have a pre-defined call-down plan."
        ),
        "common_mistake": "Folding too much to their aggression or never fighting back.",
    },
    {
        "id": "solid_reg",
        "name": "Solid Reg",
        "tag": "BALANCED — REGULAR",
        "color": "#5ad17a",
        "description": (
            "A well-rounded regular player who understands GTO concepts, "
            "balances ranges, and avoids major leaks. Their VPIP/PFR spread is tight "
            "(25/19), they C-bet appropriately, and they don't give up easily. "
            "Hard to get large edges against without good reads."
        ),
        "tell": "Consistent sizing. Reads strong in position; weak out of position.",
        "exploit": [
            "Find small population tendencies — most regs over-fold rivers.",
            "Apply ICM pressure when stakes are high.",
            "Exploit any positional leak or sizing tell at the micro level.",
            "Mix in occasional balanced 3bets to prevent them from running over you.",
        ],
        "counter": (
            "Play balanced, information-efficient poker. "
            "Use position aggressively. Track stats for any frequency leak."
        ),
        "common_mistake": "Trying to bluff them too often without blockers.",
    },
    {
        "id": "gto_reg",
        "name": "GTO-Style Reg",
        "tag": "THEORETICALLY BALANCED",
        "color": "#ffe66d",
        "description": (
            "The GTO-style reg runs near-unexploitable strategies built on solver outputs. "
            "They mix frequencies, balance ranges, and are almost impossible to exploit via "
            "pure frequency analysis. The edge against them comes from real-time adaptation "
            "and table-specific dynamics they may not fully adjust to."
        ),
        "tell": "Balanced sizing, mixed ranges. Boring to play against — by design.",
        "exploit": [
            "Look for real-time tells and emotional reactions that solvers cannot replicate.",
            "Apply ICM deviations near bubbles — GTO regs sometimes run chipEV instincts.",
            "Fish for live poker timing tells they may not control.",
            "Accept reduced edge and focus on table selection instead.",
        ],
        "counter": (
            "Near-zero EV edge at the strategy level. "
            "Win edge through game-selection, table position, and tilt monitoring."
        ),
        "common_mistake": "Trying to out-GTO them — play exploitative vs others at the table.",
    },
    {
        "id": "overfolder",
        "name": "Overfolder",
        "tag": "SCARED MONEY",
        "color": "#aabbaa",
        "description": (
            "The Overfolder is paranoid about being outdrawn. They fold too frequently "
            "to bets on the turn and river, rarely defending optimally. High fold-to-cbet "
            "numbers make them prime candidates for multi-street barrels and blind steals."
        ),
        "tell": "Folds to second barrels almost always. Checks back when unsure.",
        "exploit": [
            "Barrel 3 streets even with air — they fold more than MDF requires.",
            "Steal their blinds in position with any two cards.",
            "Turn raises and river overbets fold out even strong one-pair hands.",
            "Avoid slowplaying — just bet big and they'll fold or pay.",
        ],
        "counter": (
            "Never bluff them off made hands. "
            "They only continue with strong holdings when they do call."
        ),
        "common_mistake": "Value-betting thin — they only call with strong hands.",
    },
    {
        "id": "overbluffer",
        "name": "Overbluffer",
        "tag": "SPEW MACHINE",
        "color": "#ff6b9d",
        "description": (
            "Overbluffers deviate from GTO by firing too many bluffs across all streets. "
            "Their river bluff frequency far exceeds 33%, making their bets easy to call down. "
            "They often misread blocker situations and fire into calling ranges."
        ),
        "tell": "Large river bets with missed draws. Timing: fast bets often signal weak.",
        "exploit": [
            "Call them down wider — bluff-catch with any pair or backdoor blocker.",
            "Do NOT fold rivers to large bets without the best blockers.",
            "Record their river bluff showdowns to adjust your calling threshold.",
            "Widen your river calling range by 15–25% vs their river leads.",
        ],
        "counter": (
            "Your calls are +EV against them. "
            "Avoid fancy plays — just call and let them bluff into you."
        ),
        "common_mistake": "Folding the river to their overbet with a bluff-catcher.",
    },
    {
        "id": "icm_scared",
        "name": "ICM-Scared Medium Stack",
        "tag": "BUBBLE RISK-AVERSE",
        "color": "#4ecdc4",
        "description": (
            "Near pay jumps and tournament bubbles, this player freezes. They fold hands "
            "with +chipEV expectation to avoid risk. Medium stack pressure is their worst "
            "nightmare. They give away enormous amounts of tournament equity through passive play."
        ),
        "tell": "Folds marginal spots near bubbles. Checks back strong hands for survival.",
        "exploit": [
            "Apply relentless pressure on their blinds near the bubble.",
            "3bet them light in position — they fold ATo and below facing risk.",
            "Attack their stack when you are the covering stack.",
            "Steal their antes aggressively in late position.",
        ],
        "counter": (
            "Stack them on the bubble. They will not defend correctly. "
            "Large bets fold them out of profitable spots."
        ),
        "common_mistake": "Letting them cruise through the bubble — attack early and often.",
    },
    {
        "id": "big_stack_bully",
        "name": "Big Stack Bully",
        "tag": "CHIP LEADER AGGRESSOR",
        "color": "#f4c842",
        "description": (
            "With a big stack, this player applies maximum pressure on medium and short stacks. "
            "They raise and 3bet liberally, knowing medium stacks can't call without risk of "
            "elimination. Their aggression is +EV but exploitable when you hold a premium."
        ),
        "tell": "Opens wide, 3bets liberally, and continues on most boards.",
        "exploit": [
            "Trap with premiums — 4bet jam with QQ+/AK when they 3bet.",
            "Do not fold strong hands fearing their stack size.",
            "Attack their limps in position — they limp wide to steal later.",
            "Let short stacks go broke to them; pick your spots carefully.",
        ],
        "counter": (
            "Avoid marginal all-ins. Wait for premium spots. "
            "Use their aggression against them with traps and 4bet jams."
        ),
        "common_mistake": "Cold-calling their 3bets OOP with hands like AJo.",
    },
    {
        "id": "jam_fold_bot",
        "name": "Short Stack Jam/Fold",
        "tag": "PUSH-FOLD SPECIALIST",
        "color": "#ff8c5a",
        "description": (
            "A short stack (5–15bb) who plays pure jam/fold: either goes all-in or folds, "
            "never raising smaller. They know their push ranges well and are hard to exploit "
            "via range manipulation. Calling decisions vs them require accurate equity math."
        ),
        "tell": "Always either jams or folds — never a standard open or call.",
        "exploit": [
            "Use pot-odds-based calling ranges — don't tighten against them.",
            "They are often balanced preflop — focus on covering stacks instead.",
            "Do NOT hero-fold to their jam with any hand you'd normally open.",
            "Call wider in the BB when the pot odds are favorable (25%+ equity).",
        ],
        "counter": (
            "Calculate required equity before folding to jams. "
            "Calling off 15bb+ hands like KJo, A8s is often correct."
        ),
        "common_mistake": "Over-folding to their jams because of stack size pressure.",
    },
    # ── UZMAN tipler ──────────────────────────────────────────────────────────
    {
        "id": "gto_expert", "name": "GTO Expert", "tag": "SOLVER — DENGELİ",
        "color": "#5ad17a",
        "description": (
            "Solver-yakını oynar: dengeli value/blöf oranları, polarize sizing'ler, "
            "pozisyona ve board dokusuna göre doğru frekanslar. Neredeyse "
            "exploit edilemez — leak vermez, sömürmeye çalışmaz, dengede kalır."
        ),
        "tell": "Pattern yok. Sizing'leri tutarlı ve doku-mantıklı.",
        "exploit": [
            "Onu exploit edemezsin — kendi oyununu dengele, leak verme.",
            "Karşılığında SEN de GTO oyna; küçük EV farkları için riske girme.",
            "Hata onun değil senin tarafında çıkar — disiplinli ol.",
        ],
        "counter": "Dengeli oyna; bu rakip seni eğitmek için en iyi referanstır.",
        "common_mistake": "Onu 'kandırmaya' çalışıp kendini dengeden çıkarmak.",
    },
    {
        "id": "icm_expert", "name": "ICM Expert", "tag": "TURNUVA — ICM USTASI",
        "color": "#c77dff",
        "description": (
            "Bubble ve final-table'da pay-jump baskısını ustaca kullanır: risk "
            "premium'a göre sıkı call eder, büyük stack'le kısa stack'lere max "
            "baskı uygular, chipEV değil $EV oynar."
        ),
        "tell": "Bubble'da agresyona aşırı katlar; chip-leader'ken acımasız bask.",
        "exploit": [
            "Sen chip-leader'sen onun ICM korkusunu sömür — sürekli baskı.",
            "Bubble'da marjinal jam'lerle fold-equity topla.",
            "Kısa stack'ken ona karşı over-fold etme; o da ICM'den çekiniyor.",
        ],
        "counter": "ICM'i sen de hesapla; pay-jump'larda risk premium'a saygı duy.",
        "common_mistake": "Bubble'da onun baskısına ICM'i abartıp aşırı katlamak.",
    },
    {
        "id": "exploit_expert", "name": "Exploit Expert", "tag": "ADAPTİF — MAKS EXPLOIT",
        "color": "#ff8c5a",
        "description": (
            "GTO'dan bilinçli sapar: rakibin leak'ine göre maksimum exploit. "
            "Station'a value, nit'e blöf, fold'çuya baskı. Sürekli not alır ve "
            "stratejisini sana göre ayarlar."
        ),
        "tell": "Sana özel ayar çeker — pattern'ini bulursan o pattern'i sömürür.",
        "exploit": [
            "Dengeli/okunmaz oyna — sabit pattern verme ki ayar çekemesin.",
            "Onun sana karşı ayarını fark et ve ters-exploit et (counter-adjust).",
            "Stilini periyodik değiştir; statik kalma.",
        ],
        "counter": "Dengeli kal; o sapınca (over-exploit) sen ters yönde ceza ver.",
        "common_mistake": "Aynı hattı tekrarlayıp ona okunabilir hâle gelmek.",
    },
    # ── EFSANE oyuncular (gerçek stil + nasıl oynanır) ──────────────────────────
    {
        "id": "doyle_brunson", "name": "Doyle Brunson", "tag": "EFSANE — LOOSE AGGRESSIVE",
        "color": "#f4c842",
        "description": (
            "'Texas Dolly' — modern agresif pokerin babası. Loose-aggressive, "
            "durmak bilmez pozisyonel baskı, any-two-cards agresyon (10-2 onun "
            "efsane eli). Pot'ları sürekli şişirir, rakibi karar vermeye zorlar."
        ),
        "tell": "Geniş açar, sürekli barrel'lar; zayıflık gösterince hemen basar.",
        "exploit": [
            "Call'larına BLÖF yapma — acımasız value-bet ile ödül al.",
            "Steal'lerini 3-bet ile yavaşlat; pozisyon savaşını ona bırakma.",
            "Geniş range'ine karşı güçlü ellerle pot şişir.",
            "Bluff-catch eşiğini düşür — çok blöf yapar ama doğru spotta.",
        ],
        "counter": "Pozisyon + güçlü range ile karşı baskı; ince blöfleri ona bırak.",
        "common_mistake": "Sürekli baskısına panikleyip iyi elleri fold etmek.",
        "concepts_title": "SUPER/SYSTEM KAVRAMLARI",
        "concepts": [
            "Power Poker felsefesi: agresyon kazandırır, pasif oyun para kaybettirir. "
            "İnisiyatifi al, rakibi karar vermeye zorla.",
            "Rakip okuma: oyuncunun NE YAPTIĞI, ne söylediğinden önemlidir — "
            "betting pattern + timing tell'lerini izle.",
            "Pozisyon = güç. No-Limit'te küçük kartlarla bile pozisyon+agresyonla "
            "pot çalınır (10-2 efsanesi).",
            "Tipoloji: oyuncuları tight/loose × passive/aggressive matrisine yerleştir; "
            "'gambler', 'rock', 'sucker' sınıflarına göre hat seç.",
        ],
    },
    {
        "id": "phil_ivey", "name": "Phil Ivey", "tag": "EFSANE — KOMPLE / OKUYUCU",
        "color": "#5ad1ce",
        "description": (
            "Tüm zamanların en iyilerinden. Korkusuz, cerrahi el-okuma, dengeli "
            "ama exploit kenarı olan oyun. Geride olunca büyük el bile bırakır, "
            "önde olunca maksimum baskı kurar. Masadaki en zor rakip."
        ),
        "tell": "Pattern neredeyse yok; gözünü sana diker, zayıflığını avlar.",
        "exploit": [
            "Onu exploit etmek çok zor — önce leak vermemeye odaklan.",
            "Dengeli oyna; ince/marjinal spotlarda ona karşı riske girme.",
            "Blöf-yakalama hattında disiplinli ol — sezgisi güçlü.",
        ],
        "counter": "Hatasız + dengeli oyna; variance'ı düşür, net spotları al.",
        "common_mistake": "Ona 'fazla yaratıcı' oynayıp kendini zora sokmak.",
        "concepts_title": "IVEY OKUMA KAVRAMLARI",
        "concepts": [
            "Game flow okuma: spot'u izole değerlendirme — rakibin o anki ruh hali, "
            "geçmiş eller ve masa dinamiğine göre uyarla.",
            "Korkusuz agresyon + disiplinli fold: büyük el bile geride olunca bırakılır; "
            "'sonuç odaklı değil, karar odaklı' düşün.",
            "Canlı tell ustası: bahis zamanlaması (timing) ve sizing tutarsızlıkları "
            "value/blöf ayrımını ele verir.",
            "Her sokakta bilgi topla, range'ini sürekli güncelle; pattern verme.",
        ],
    },
    {
        "id": "phil_hellmuth", "name": "Phil Hellmuth", "tag": "EFSANE — TIGHT / MTT",
        "color": "#7abaff",
        "description": (
            "'Poker Brat' — 17 WSOP bilezikli canlı/turnuva uzmanı. Ultra-disiplinli, "
            "sabırlı, 'white magic' okumalar, büyük eli bile fold edebilir, "
            "varyanstan kaçar. Küçük-orta potlarda kontrollü, premium-ağırlıklı."
        ),
        "tell": "Çok katlar; bahis yaptığında genelde gerçek değeri vardır.",
        "exploit": [
            "Blöf yapma — sezer ve doğru fold/call'ı bulur.",
            "İnce value al; pozisyonla sürekli bas, bloodlarını çal.",
            "Steal frekansını artır — fold-equity yüksek.",
            "Büyük pot riskine sokma; o varyanstan kaçtığı için baskıya katlar.",
        ],
        "counter": "Pozisyon + sabırlı value; blöf hattını ona karşı kapat.",
        "common_mistake": "Onu blöfle kovmaya çalışmak (en pahalı hata).",
        "concepts_title": "HELLMUTH'UN HAYVAN TİPLERİ (kitabından)",
        "concepts": [
            "🐭 MOUSE (Fare): çok sıkı-pasif, sadece premium oynar, riskten kaçar. "
            "EXPLOIT: körlerini çal, blöfle kovalа, baskı uygula.",
            "🦁 LION (Aslan): sıkı-agresif, disiplinli solid pro. Masadaki en zorlardan; "
            "ona karşı dengeli oyna, leak verme.",
            "🐺 JACKAL (Çakal): loose-aggressive maniac, kaotik ve öngörülemez. "
            "EXPLOIT: güçlü elle bekle, geniş range'ine value al, bluff-catch et.",
            "🐘 ELEPHANT (Fil): loose-passive calling station, her şeyi takip eder. "
            "EXPLOIT: acımasız value-bet, ASLA blöf yapma.",
            "🦅 EAGLE (Kartal): en üst %1 — dünya klası, az sayıda. Masaya oturma, "
            "oturduysan minimum çatışma.",
            "Top-10 el + sabır felsefesi: turnuvada varyanstan kaç, premium-ağırlıklı "
            "oyna, doğru anı bekle.",
        ],
    },
    {
        "id": "daniel_negreanu", "name": "Daniel Negreanu", "tag": "EFSANE — SMALL BALL / OKUYUCU",
        "color": "#ff6b9d",
        "description": (
            "'Kid Poker' — range-okuma dehası. Small-ball: küçük potlar, çok flop "
            "görür, kontrollü agresyon, kapalı kartını okumakla ünlü. Variance'ı "
            "düşük tutar, bilgi toplar, doğru anda baskı kurar."
        ),
        "tell": "Çok flop görür, kontrollü bahisler; ani büyük overbet = polarize.",
        "exploit": [
            "Kapalı kartını ele verme — küçük tell'lerden range'ini daraltır.",
            "Net value hattı tut; small-ball'una ince value ile karşılık ver.",
            "Büyük overbet'lerine hazır ol — polarize oynar.",
            "Çok-flop eğilimini c-bet baskısıyla cezalandır.",
        ],
        "counter": "Bilgi sızdırma; dengeli + net hatlarla küçük pot savaşını kazan.",
        "common_mistake": "Konuşmasına/okumasına kapılıp range'ini ona göstermek.",
        "concepts_title": "POWER HOLD'EM — KAVRAMLAR (kitabından)",
        "concepts": [
            "SMALL BALL: küçük açış/bahis boyutları, çok flop gör, ucuz bilgi topla, "
            "büyük varyanstan kaçın — pozisyon ve okuma ile küçük potları biriktir.",
            "RANGE OKUMA (hand reading): rakibi tek ele değil ARALIĞA koy; her sokakta "
            "(preflop→river) aksiyona göre aralığı daralt. Modern range-bazlı "
            "düşüncenin popülerleştiricisi.",
            "Aralık daraltma adımları: açış pozisyonu → preflop aksiyon → board dokusu "
            "→ bet sizing → timing; her bilgi range'i keser.",
            "Live tell + profilleme: oyuncuyu tipine göre sınıfla, ona göre exploit hattı seç.",
        ],
    },
]

# Map seed_data names to profile IDs
_NAME_TO_PROFILE = {
    "Nit": "nit",
    "Tight passive": "tight_passive",
    "Calling station": "calling_station",
    "Maniac": "maniac",
    "Loose aggressive": "lag",
    "Solid reg": "solid_reg",
    "GTO-style reg": "gto_reg",
    "Overfolder": "overfolder",
    "Overbluffer": "overbluffer",
    "ICM scared medium stack": "icm_scared",
    "Big stack bully": "big_stack_bully",
    "Short stack jam/fold bot": "jam_fold_bot",
}
_PROFILE_BY_ID = {p["id"]: p for p in _PROFILES}

_CAT_ACTIVE = (
    "QPushButton { background: #131613; color: #5ad17a; border-left: 3px solid #5ad17a; "
    "text-align: left; padding: 8px 14px; font-size: 12px; font-weight: 600; }"
)
_CAT_INACTIVE = (
    "QPushButton { background: transparent; color: #898d80; border: none; "
    "border-left: 3px solid transparent; text-align: left; padding: 8px 14px; font-size: 12px; }"
    "QPushButton:hover { background: #131613; color: #f4f5ee; }"
)


def _stat_chip(label: str, value: str, color: str = "#5ad17a") -> QLabel:
    lbl = QLabel(f"{label} <b style='color:{color}'>{value}</b>")
    lbl.setTextFormat(Qt.RichText)
    lbl.setObjectName("Mono")
    lbl.setStyleSheet(
        f"background: #131613; border: 1px solid #23271f; "
        f"padding: 4px 10px; font-size: 11px;"
    )
    return lbl


class OpponentProfilesScreen(QWidget):
    coach_message = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self._bot_stats = {b["name"]: b for b in bot_profiles()}
        self._selected_id = _PROFILES[0]["id"]

        self._build_ui()
        self._select_profile(_PROFILES[0]["id"])

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── LEFT sidebar: archetype list ──────────────────────────────────────
        left = QFrame()
        left.setObjectName("Sidebar")
        left.setFixedWidth(210)
        left.setStyleSheet("QFrame#Sidebar { background: #0f1210; border-right: 1px solid #23271f; }")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        hdr = QLabel("OPPONENT\nARCHETYPES")
        hdr.setObjectName("NavGroupLabel")
        hdr.setContentsMargins(16, 16, 0, 8)
        left_layout.addWidget(hdr)

        self._arch_btns: dict[str, QPushButton] = {}
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_body = QWidget()
        scroll_body_l = QVBoxLayout(scroll_body)
        scroll_body_l.setContentsMargins(0, 4, 0, 4)
        scroll_body_l.setSpacing(0)

        for profile in _PROFILES:
            btn = QPushButton(profile["name"])
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.clicked.connect(lambda checked=False, pid=profile["id"]: self._select_profile(pid))
            self._arch_btns[profile["id"]] = btn
            scroll_body_l.addWidget(btn)

        scroll_body_l.addStretch(1)
        scroll.setWidget(scroll_body)
        left_layout.addWidget(scroll, 1)

        count_lbl = QLabel(f"{len(_PROFILES)} archetypes")
        count_lbl.setObjectName("Muted")
        count_lbl.setAlignment(Qt.AlignCenter)
        count_lbl.setContentsMargins(0, 8, 0, 12)
        left_layout.addWidget(count_lbl)

        root.addWidget(left)

        # ── RIGHT detail panel ────────────────────────────────────────────────
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.NoFrame)
        self._detail_body = QWidget()
        right_scroll.setWidget(self._detail_body)
        self._detail_layout = QVBoxLayout(self._detail_body)
        self._detail_layout.setContentsMargins(28, 24, 28, 28)
        self._detail_layout.setSpacing(18)
        self._detail_layout.addStretch(1)
        root.addWidget(right_scroll, 1)

    def _select_profile(self, pid: str) -> None:
        self._selected_id = pid
        for aid, btn in self._arch_btns.items():
            btn.setStyleSheet(_CAT_ACTIVE if aid == pid else _CAT_INACTIVE)
        self._render_detail(pid)

    def _render_detail(self, pid: str) -> None:
        # Hide immediately + schedule deletion — prevents ghost widgets during re-render
        while self._detail_layout.count():
            item = self._detail_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.deleteLater()

        profile = _PROFILE_BY_ID.get(pid)
        if not profile:
            return

        color = profile["color"]

        # ── Profile header ────────────────────────────────────────────────────
        header = QFrame()
        header.setObjectName("Card")
        header.setStyleSheet(f"QFrame#Card {{ border-left: 4px solid {color}; }}")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(24, 20, 24, 20)

        title_col = QVBoxLayout()
        name_lbl = QLabel(profile["name"].upper())
        name_lbl.setObjectName("Title")
        name_lbl.setStyleSheet(f"font-size: 24px; color: {color};")
        tag_lbl = QLabel(profile["tag"])
        tag_lbl.setObjectName("BrandTag")
        tag_lbl.setStyleSheet(f"color: {color}; font-size: 11px;")
        title_col.addWidget(name_lbl)
        title_col.addWidget(tag_lbl)
        h_layout.addLayout(title_col)
        h_layout.addStretch(1)

        # Ask AI button
        ai_btn = QPushButton("Ask AI Coach ↗")
        ai_btn.setStyleSheet(
            f"QPushButton {{ background: #131613; color: {color}; border: 1px solid {color}; "
            f"padding: 6px 14px; }} QPushButton:hover {{ background: #1a1e19; }}"
        )
        ai_btn.clicked.connect(lambda: self._ask_ai(profile))
        h_layout.addWidget(ai_btn)

        self._detail_layout.addWidget(header)

        # ── Stats row ─────────────────────────────────────────────────────────
        bot_name = profile["name"]
        # Find matching bot stats (fuzzy)
        bot = None
        for name, b in self._bot_stats.items():
            if name.lower() == bot_name.lower() or profile["id"] in name.lower():
                bot = b
                break
        if not bot:
            # Try partial match
            for name, b in self._bot_stats.items():
                first_word = bot_name.split()[0].lower()
                if first_word in name.lower():
                    bot = b
                    break
        if not bot:
            # BOT_ARCHETYPES fallback — efsane/uzman profillerinin gerçek statları
            try:
                from app.engine.bot_brain import BOT_ARCHETYPES
                p = BOT_ARCHETYPES.get(bot_name)
                if p:
                    bot = {"name": p.name, "vpip": p.vpip, "pfr": p.pfr,
                           "three_bet": p.three_bet, "fold_to_cbet": p.fold_to_cbet,
                           "aggression": p.aggression,
                           "river_bluff": round(p.river_bluff * 100),
                           "call_down": round(p.call_down * 100),
                           "overbet_freq": round(p.overbet_freq * 100),
                           "bluff_river": round(p.bluff_river * 100),
                           "call_3bet": round(p.call_3bet * 100)}
            except Exception:
                bot = None

        if bot:
            stats_lbl = QLabel("STATISTICAL PROFILE")
            stats_lbl.setObjectName("NavGroupLabel")
            self._detail_layout.addWidget(stats_lbl)

            stats_frame = QFrame()
            stats_frame.setObjectName("Card")
            stats_layout = QVBoxLayout(stats_frame)
            stats_layout.setContentsMargins(20, 16, 20, 16)
            stats_layout.setSpacing(10)

            # Row of stat chips
            chip_row = QHBoxLayout()
            chip_row.setSpacing(8)
            chip_row.setAlignment(Qt.AlignLeft)
            chip_pairs = [
                ("VPIP", f"{bot['vpip']}%"),
                ("PFR", f"{bot['pfr']}%"),
                ("3bet", f"{bot['three_bet']}%"),
                ("F2cbet", f"{bot['fold_to_cbet']}%"),
                ("AF", f"{bot['aggression']:.1f}"),
                ("River bluff", f"{bot['river_bluff']}%"),
                ("Call-down", f"{bot['call_down']}%"),
            ]
            for k, v in chip_pairs:
                chip = _stat_chip(k, v, color)
                chip_row.addWidget(chip)
            chip_row.addStretch(1)
            stats_layout.addLayout(chip_row)

            # Stat bars
            bars_grid = QGridLayout()
            bars_grid.setSpacing(6)
            for row_idx, (label, val, hi) in enumerate([
                ("VPIP", bot["vpip"], 65),
                ("PFR", bot["pfr"], 50),
                ("Aggression", bot["aggression"] * 10, 40),
                ("River bluff%", bot["river_bluff"], 60),
                ("Call-down%", bot["call_down"], 90),
            ]):
                lbl = QLabel(label)
                lbl.setObjectName("Muted")
                lbl.setFixedWidth(110)

                bar_outer = QFrame()
                bar_outer.setFixedHeight(8)
                bar_outer.setMinimumWidth(180)
                bar_outer.setStyleSheet("background: #1a1e19; border-radius: 3px;")
                bar_outer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

                fill_pct = min(1.0, val / max(hi, 1))
                bar_fill = QFrame(bar_outer)
                bar_fill.setGeometry(0, 0, max(4, int(fill_pct * 200)), 8)
                bar_fill.setStyleSheet(f"background: {color}; border-radius: 3px;")

                val_lbl = QLabel(f"{val:.0f}")
                val_lbl.setObjectName("Mono")
                val_lbl.setFixedWidth(36)
                val_lbl.setAlignment(Qt.AlignRight)

                bars_grid.addWidget(lbl, row_idx, 0)
                bars_grid.addWidget(bar_outer, row_idx, 1)
                bars_grid.addWidget(val_lbl, row_idx, 2)

            stats_layout.addLayout(bars_grid)

            # Exploit tip from bot profile
            adj = bot.get("adjustment", "")
            if adj:
                adj_lbl = QLabel(f"Bot adjustment hint:  {adj}")
                adj_lbl.setObjectName("Muted")
                adj_lbl.setStyleSheet("font-size: 11px; font-style: italic;")
                adj_lbl.setWordWrap(True)
                stats_layout.addWidget(adj_lbl)

            self._detail_layout.addWidget(stats_frame)

        # ── Description ───────────────────────────────────────────────────────
        desc_lbl = QLabel("PLAYING STYLE")
        desc_lbl.setObjectName("NavGroupLabel")
        self._detail_layout.addWidget(desc_lbl)

        desc_frame = QFrame()
        desc_frame.setObjectName("Card")
        desc_l = QVBoxLayout(desc_frame)
        desc_l.setContentsMargins(20, 16, 20, 16)
        desc_text = QLabel(profile["description"])
        desc_text.setWordWrap(True)
        desc_text.setStyleSheet("font-size: 13px; line-height: 1.6;")
        desc_l.addWidget(desc_text)

        tell_text = QLabel(f"<b>Tell:</b>  {profile['tell']}")
        tell_text.setTextFormat(Qt.RichText)
        tell_text.setWordWrap(True)
        tell_text.setStyleSheet("font-size: 12px; color: #f4c842; margin-top: 8px;")
        desc_l.addWidget(tell_text)
        self._detail_layout.addWidget(desc_frame)

        # ── Exploitation strategy ─────────────────────────────────────────────
        # Wrap in a QWidget so deleteLater() cleans up all children when switching profiles
        row_container = QWidget()
        row = QHBoxLayout(row_container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(16)

        exploit_frame = QFrame()
        exploit_frame.setObjectName("Card")
        exploit_frame.setStyleSheet(f"QFrame#Card {{ border-top: 2px solid {color}; }}")
        exploit_l = QVBoxLayout(exploit_frame)
        exploit_l.setContentsMargins(20, 16, 20, 16)
        exploit_l.setSpacing(8)
        exploit_hdr = QLabel("HOW TO EXPLOIT")
        exploit_hdr.setObjectName("SectionTitle")
        exploit_hdr.setStyleSheet(f"color: {color};")
        exploit_l.addWidget(exploit_hdr)
        for i, tip in enumerate(profile["exploit"]):
            tip_lbl = QLabel(f"{i+1}.  {tip}")
            tip_lbl.setWordWrap(True)
            tip_lbl.setStyleSheet("font-size: 12px; line-height: 1.5;")
            exploit_l.addWidget(tip_lbl)
        row.addWidget(exploit_frame, 1)

        counter_frame = QFrame()
        counter_frame.setObjectName("Card")
        counter_l = QVBoxLayout(counter_frame)
        counter_l.setContentsMargins(20, 16, 20, 16)
        counter_l.setSpacing(8)
        counter_hdr = QLabel("COUNTER-STRATEGY")
        counter_hdr.setObjectName("SectionTitle")
        counter_hdr.setStyleSheet("color: #f4c842;")
        counter_l.addWidget(counter_hdr)
        counter_text = QLabel(profile["counter"])
        counter_text.setWordWrap(True)
        counter_text.setStyleSheet("font-size: 12px; line-height: 1.5;")
        counter_l.addWidget(counter_text)

        mistake_hdr = QLabel("COMMON MISTAKE VS THEM")
        mistake_hdr.setObjectName("TLabel")
        mistake_hdr.setStyleSheet("color: #ff5a5a; margin-top: 10px;")
        counter_l.addWidget(mistake_hdr)
        mistake_text = QLabel(profile["common_mistake"])
        mistake_text.setWordWrap(True)
        mistake_text.setStyleSheet("font-size: 12px; color: #ff8a8a;")
        counter_l.addWidget(mistake_text)

        row.addWidget(counter_frame, 1)
        self._detail_layout.addWidget(row_container)  # widget, not layout — clears correctly

        # ── KAVRAMLAR / TİPOLOJİLER (efsanenin kitabından) ──
        concepts = profile.get("concepts")
        if concepts:
            cf = QFrame()
            cf.setObjectName("Card")
            cf.setStyleSheet(f"QFrame#Card {{ border-left: 3px solid {color}; }}")
            cl = QVBoxLayout(cf)
            cl.setContentsMargins(20, 16, 20, 16)
            cl.setSpacing(8)
            chdr = QLabel(f"📚  {profile.get('concepts_title', 'KAVRAMLAR / TİPOLOJİLER')}")
            chdr.setObjectName("SectionTitle")
            chdr.setStyleSheet(f"color: {color};")
            cl.addWidget(chdr)
            for c in concepts:
                cl_lbl = QLabel(f"•  {c}")
                cl_lbl.setWordWrap(True)
                cl_lbl.setStyleSheet("font-size: 12px; line-height: 1.5;")
                cl.addWidget(cl_lbl)
            self._detail_layout.addWidget(cf)

        self._detail_layout.addStretch(1)

    def _ask_ai(self, profile: dict) -> None:
        """Emit a coach message requesting AI analysis of this archetype."""
        msg = (
            f"Rakip tipi analizi: {profile['name']} ({profile['tag']}).\n"
            f"Özellikler: {profile['description'][:200]}...\n"
            f"Exploit noktaları: {'; '.join(profile['exploit'][:2])}\n\n"
            f"Bu rakip tipiyle karşılaştığımda en kritik 3 uyarlama nedir? "
            f"Özellikle kör steal, river bluff catch ve preflop yeniden yetiştirme konularında somut tavsiye ver."
        )
        self.coach_message.emit(msg)
