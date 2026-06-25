"""D323: advisor == KİTAP tutarlılık-testi (kullanıcı: 'advisor %100 kitap olmalı, hatasız her
durumda'). Karar-kritik sabitleri PİNLER: (1) advisor davranışı (_tier_from/type_prior),
(2) kitabın bu sabitleri İÇERMESİ, (3) advisor-kaynağının sizing/gate sabitleri.
Biri saparsa test KIRILIR → bot=advisor=kitap senkronu zorlanır.

NOT: prose-vs-kod tam-denkliği otomatik kanıtlanamaz; bu test KARAR-KRİTİK parametreleri
(7-tier cutoff, sizing, commit-gate, SAYIM prior, value-up) garanti eder — gerçekçi drift'i yakalar."""
import re
from pathlib import Path

from app.poker.opponent_typology import type_prior
from app.poker.soyrac_advisor import _tier_from

_ROOT = Path(__file__).resolve().parent.parent
_BOOK = (_ROOT / "docs/soyrac_book/soyrac_bible.html").read_text(encoding="utf-8")
_SRC = (_ROOT / "app/poker/soyrac_advisor.py").read_text(encoding="utf-8")


def _in_book(num: str) -> bool:
    """Kitapta sayı geçiyor mu (virgüllü ondalık 0,40 dahil)."""
    return num in _BOOK or num.replace(".", ",") in _BOOK


# ── 1) 7-TIER cutoff: advisor davranışı + kitap içeriği ──
_TIER_PINS = [(0.85, "NUT"), (0.62, "GÜÇLÜ"), (0.55, "ORTA"),
              (0.40, "ZAYIF"), (0.28, "BLUFF-CATCH"), (0.20, "HAVA")]


def test_tier_cutoffs_advisor_behavior():
    """_tier_from her cutoff'ta kitabın söylediği tier'ı vermeli (advisor pin)."""
    for s, exp in _TIER_PINS:
        assert _tier_from(s, 0.0) == exp, f"_tier_from({s})={_tier_from(s,0)} ≠ kitap {exp}"
    assert _tier_from(0.50, 0.30) == "DRAW", "draws≥0.30 & str<0.55 → DRAW"


def test_tier_cutoffs_in_book():
    """Kitap her tier cutoff sayısını + tier adını İÇERMELİ."""
    for num in ("0.85", "0.62", "0.55", "0.40", "0.28", "0.30"):
        assert _in_book(num), f"tier cutoff {num} KİTAPTA YOK (advisor↔kitap drift)"
    for tier in ("NUT", "GÜÇLÜ", "ORTA", "ZAYIF", "BLUFF-CATCH", "HAVA", "DRAW"):
        assert tier in _BOOK, f"tier adı {tier} kitapta yok"


# ── 2) SIZING: advisor-kaynağı + kitap ──
def test_sizing_constants_sync():
    """Baz sizing (0.33/0.55/0.75) + value-up (0.45/0.7/0.9) advisor-kaynağında VE kitapta."""
    for num in ("0.33", "0.55", "0.75"):
        assert num in _SRC, f"baz sizing {num} advisor-kaynağında yok (değişti mi?)"
        assert _in_book(num), f"baz sizing {num} kitapta yok"
    # D321 value-up
    for num in ("0.45", "0.7", "0.9"):
        assert num in _SRC, f"value-up {num} advisor-kaynağında yok"
    assert ("0.9" in _BOOK or "~pot" in _BOOK), "value-up (büyük value) kitapta yok"


# ── 3) COMMIT-GATE %70 ──
def test_commit_gate_sync():
    assert "/ stack > 0.70" in _SRC, "commit-gate %70 advisor-kaynağında değişmiş"
    assert "%70" in _BOOK or "0,70" in _BOOK or "0.70" in _BOOK, "commit-gate %70 kitapta yok"


# ── 4) SAYIM prior: advisor davranışı + kitap ──
def test_sayim_prior_sync():
    assert type_prior("elephant") == 1 and type_prior("mouse") == 1 and type_prior("eagle") == 1
    assert type_prior("lion") == 0 and type_prior("jackal") == -1
    # kitap Bölüm 29.2: prior tablosu
    assert re.search(r"Elephant.{0,90}\+1", _BOOK), "SAYIM prior (+1) kitapta (Böl 29.2) yok"
    assert "−1" in _BOOK or "-1" in _BOOK, "Jackal prior (−1) kitapta yok"


# ── 5) value-up CASH-only (turnuvada kapalı) — advisor wiring + kitap uyarısı ──
def test_value_up_cash_only_documented():
    assert "_vup = not tourney" in _SRC, "value-up cash-gate advisor wiring değişmiş"
    assert "CASH" in _BOOK and "TURNUVADA" in _BOOK, "cash-only value uyarısı kitapta yok"
