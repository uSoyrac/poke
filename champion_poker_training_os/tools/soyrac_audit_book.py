"""KALICI kitap-sayı denetleyicisi — kitaptaki HER sayıyı motora karşı doğrular.
Soru→hipotez→test döngüsünün 'kontrol' ayağı: kitap %100 = sistem mi?

Çalıştır:  PYTHONPATH=. .venv/bin/python tools/soyrac_audit_book.py
Çıkış kodu: 0 = temiz, 1 = gerçek uyumsuzluk (CI guard olarak kullanılabilir).

Üç denetim:
  1) SHCP 'el = sayı' iddiaları → shcp_score
  2) Pozisyon RFI eşikleri → _RFI
  3) tier ↔ strength tutarlılığı → _tier_from
Bilinen yanlış-pozitifler (B4-blocker skoru, equity yüzdeleri, postflop strength, Bridge-HCP)
bağlamla ayıklanır.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.poker.soyrac_advisor import shcp_score, _RFI, _tier_from  # noqa: E402

BOOK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "docs", "soyrac_book", "soyrac_bible.html")

_R = "AKQJT98765432"
VALID = set()
for _i in range(13):
    for _j in range(13):
        VALID.add(_R[_i] + _R[_i] if _i == _j else
                  (_R[_i] + _R[_j] + "s" if _i < _j else _R[_j] + _R[_i] + "o"))

# bağlam-anahtarları: bu kelimeler yakındaysa sayı SHCP DEĞİL (yanlış-pozitif)
_NOT_SHCP = ("b4", "blocker", "blöf", "bluff", "hcp", "briç", "brid", "vs qq", "vs jj",
             "flip", "= 0.", "≈0.", "~0.", "equity", "/57", "/55", "/54", "= 16 +")


def _ctx(text, pos, span=80):
    a, b = max(0, pos - span), min(len(text), pos + span)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text[a:b])).strip()


def audit():
    src = open(BOOK, encoding="utf-8").read()
    plain = re.sub(r"<[^>]+>", " ", src)
    errors = []

    # ---- 1) SHCP el=sayı ----
    for m in re.finditer(r"\b([AKQJT2-9]{2}[so]?)\s*=\s*(?:<b>)?(-?\d+)(?:</b>)?", src):
        hand, val = m.group(1), int(m.group(2))
        if hand not in VALID:
            continue
        if shcp_score(hand) == val:
            continue
        if src[m.end():m.end() + 1] == "+":
            continue           # 'AJs = 10+5+4...' breakdown ilk-terimi → yanlış-pozitif
        c = _ctx(src, m.start())
        if any(w in c.lower() for w in _NOT_SHCP):
            continue           # B4/equity/bridge → yanlış-pozitif
        errors.append(("SHCP", f"{hand}: kitap={val} gerçek={shcp_score(hand)}", c))

    # ---- 2) RFI eşikleri ----
    for m in re.finditer(r"\b(UTG\+1|UTG|BTN|CO|MP|HJ|LJ|SB)\b[^<.]{0,28}?eşi[ğk][^<.0-9]{0,12}?(\d+)", src):
        pos, val = m.group(1), int(m.group(2))
        real = _RFI.get(pos)
        c = _ctx(src, m.start())
        if real is None or real == val:
            continue
        if "vs" in c.lower() or "call" in c.lower() or "3-bet" in c.lower():
            continue           # vs-RFI eşiği (RFI-açış değil) → yanlış-pozitif
        errors.append(("RFI", f"{pos}: kitap eşik {val} _RFI={real}", c))

    # ---- 3) tier ↔ strength ----
    norm = lambda t: "ZAYIF" if t == "ZAYIF-MADE" else t
    pats = [r"(NUT|GÜÇLÜ|ORTA|ZAYIF-MADE|ZAYIF|BLUFF-CATCH|HAVA)[^0-9<]{0,30}?(0\.[0-9]{2,3})",
            r"(0\.[0-9]{2,3})[^0-9<]{0,18}?(NUT|GÜÇLÜ|ORTA|ZAYIF-MADE|ZAYIF|BLUFF-CATCH|HAVA)\b"]
    seen = set()
    for pat in pats:
        for m in re.finditer(pat, plain):
            g = m.groups()
            tier = g[0] if not g[0][0].isdigit() else g[1]
            dec = float(g[1] if not g[0][0].isdigit() else g[0])
            dec_pos = m.start(1) if g[0][0].isdigit() else m.start(2)
            c = _ctx(plain, m.start(), 30)
            _before = plain[max(0, dec_pos - 5):dec_pos]
            if "<" in _before or "lt;" in _before:  # '<0.28' / '&lt;0.28' sınır ifadesi doğru
                continue
            _win = plain[max(0, dec_pos - 35):dec_pos + 8].lower()
            if any(w in _win for w in ("1/3", "pot", "ıslak", "kuru", "boyut", "size", "bas", "bahis")):
                continue       # 0.75 vb. = bet-BOYUTU (strength değil) → yanlış-pozitif
            if norm(tier) == _tier_from(dec, 0):
                continue
            key = (tier, dec, c[:25])
            if key in seen:
                continue
            seen.add(key)
            errors.append(("TIER", f"{tier} ↔ {dec} (motor: {_tier_from(dec, 0)})", c))

    return errors


def main():
    errors = audit()
    if not errors:
        print("✅ KİTAP TEMİZ — tüm SHCP/eşik/tier sayıları motorla uyumlu.")
        return 0
    print(f"❌ {len(errors)} GERÇEK UYUMSUZLUK:")
    for kind, msg, c in errors:
        print(f"  [{kind}] {msg}")
        print(f"        ...{c}...")
    return 1


if __name__ == "__main__":
    sys.exit(main())
