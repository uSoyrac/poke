"""D237: gerçek Soyrac-sapma leak'leri (soyrac_hands) Leak Finder'a bağlanır.
-EV leak'ler yüzeye çıkar; +EV touch'lar (loose-call, flat-cheap-flop) HARİÇ.
SAF mantık (_soyrac_leaks_from_rows) sentetik veriyle test edilir (DB-bağımsız)."""
from app.db.repository import _soyrac_leaks_from_rows, get_soyrac_deviation_leaks

_ROWS = [
    {"leak": "Over-defend — çöp/spekülatif savunma (GTO'da bile -EV)", "c": 107, "busts": 35},
    {"leak": "Çok geniş açış (eşik altı raise)", "c": 63, "busts": 30},
    {"leak": "3-bet pot over-call (premium değilken call → para yakar)", "c": 41, "busts": 11},
    {"leak": "Sapma: sen C, Soyrac R", "c": 144, "busts": 22},   # TOUCH (flat-cheap-flop)
    {"leak": "Sapma: sen C, Soyrac F", "c": 63, "busts": 8},      # TOUCH (loose-call)
    {"leak": "Çok sıkı — değer açışı kaçtı", "c": 14, "busts": 0},  # eşikaltı/mapping yok → atla
]


def test_real_leaks_surfaced():
    names = {l["name"] for l in _soyrac_leaks_from_rows(_ROWS)}
    assert any("over-defend" in n.lower() for n in names), names
    assert any("geniş aç" in n.lower() for n in names), names
    assert any("3-bet pot" in n.lower() for n in names), names


def test_touches_excluded():
    """+EV dokunuşlar (sen C Soyrac R/F = flat-cheap / loose-call) leak SAYILMAZ."""
    txt = " ".join(l["name"].lower() for l in _soyrac_leaks_from_rows(_ROWS))
    assert "soyrac r" not in txt and "soyrac f" not in txt and "loose" not in txt


def test_below_min_count_skipped():
    assert _soyrac_leaks_from_rows([{"leak": "Aşırı 4-bet (premium/blocker yok)", "c": 3, "busts": 1}]) == []


def test_severity_by_bust_share():
    hi = _soyrac_leaks_from_rows([{"leak": "Çok geniş açış (eşik altı raise)", "c": 30, "busts": 14}])
    assert hi and hi[0]["severity"] == "High"


def test_each_leak_has_book_fix():
    for l in _soyrac_leaks_from_rows(_ROWS):
        assert "Böl" in l["fix"] or "Bible" in l["fix"], l


def test_db_smoke():
    assert isinstance(get_soyrac_deviation_leaks(), list)
