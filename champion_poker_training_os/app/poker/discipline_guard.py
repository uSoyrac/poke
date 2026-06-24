"""D309: Disiplin-Kalkanı — override-tespiti (kullanıcı tanı: 'çok hızlı değer kaybı').
Gerçek MTT verisi (T73-76, %89 uyum): kayıplar advisor'ı OVER-ACTION yönünde override etmekten
(advisor FOLD derken CALL/RAISE; CHECK derken BET/RAISE). Sistem advisor'ı izleyince +%101 ROI;
boşluk = execution. Bu modül o anı yakalar → ekran 'sert onay' diyaloğu gösterir (kullanıcı seçti).

Saf mantık (Qt'siz, test-edilebilir). KURAL: kullanıcı advisor'dan DAHA AGRESİF/daha-loose ise
(over-action = leak yönü) → uyar. Under-action (advisor'dan daha pasif/sıkı) müdahale edilmez."""
from __future__ import annotations

# Agresyon merdiveni: fold < check < call < aggr(bet/raise/jam/all-in/3bet/4bet)
_RANK = {"fold": 0, "check": 1, "call": 2, "aggr": 3}


def _norm(a) -> str:
    a = (a or "").upper()
    if "FOLD" in a:
        return "fold"
    if "CALL" in a:                                   # 'CALL' içinde 'ALL' geçer → önce
        return "call"
    if any(k in a for k in ("RAISE", "3-BET", "4-BET", "JAM", "ALL", "BET", "AÇ")):
        return "aggr"
    if "CHECK" in a:
        return "check"
    return "other"


def override_warning(user_action, advisor_action) -> "tuple[bool, str | None]":
    """Kullanıcı advisor'dan daha agresifse (over-action override) → (True, advisor_display).
    Aksi (uyumlu / under-action / advisor belirsiz) → (False, None)."""
    if not advisor_action:
        return False, None
    u = _norm(user_action)
    a = _norm(advisor_action)
    if u == "other" or a == "other":
        return False, None
    if _RANK[u] > _RANK[a]:                            # kullanıcı advisor'ı agresyonda AŞIYOR
        disp = {"fold": "FOLD", "check": "CHECK", "call": "CALL", "aggr": ""}[a]
        return True, disp
    return False, None


def override_message(user_action, advisor_disp) -> str:
    """Onay diyaloğu metni."""
    ua = (user_action or "").upper()
    act = ("CALL" if "CALL" in ua else "RAISE" if "RAISE" in ua
           else "JAM" if ("JAM" in ua or "ALL" in ua) else "BET" if "BET" in ua else ua)
    return (f"⛔ SOYRAC: {advisor_disp}\n\n"
            f"Bu eli {act} etmek = override (advisor {advisor_disp} diyor). Gerçek MTT verinde "
            f"hızlı değer-kaybının ana sebebi tam bu: kazanan tavsiyeyi geçmek.\n\n"
            f"Yine de {act} etmek istiyor musun?")
