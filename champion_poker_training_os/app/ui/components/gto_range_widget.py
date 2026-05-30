"""GTO Range Widget — pozisyon, stack derinliği ve oyun tipine göre
optimal aralık bilgisini gösteren kompakt panel.

Kullanım:
    widget = GTORangeWidget()
    widget.update_range(position="CO", stack_bb=45.0, game_type="tournament")

Ayrıca ``_HandMatrixWidget`` — 13×13 el matrisi, her hücre range üyeliğine
göre renklendirilir (yeşil=premium, cyan=range içi, mor=küçük pair, koyu=dışı).
"""
from __future__ import annotations

import re

from PySide6.QtCore import Qt, QObject, QThread, Signal
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)


class _SolveWorker(QObject):
    """TexasSolver EXACT çözümünü arka planda koşturur (UI donmasın)."""
    done = Signal(object)   # dict {action: freq} veya None

    def __init__(self, spot: dict):
        super().__init__()
        self._spot = spot

    def run(self) -> None:
        out = None
        try:
            from app.poker.postflop_solver import solve_spot_exact
            s = self._spot
            out = solve_spot_exact(
                board=s.get("board", ""),
                pot_bb=float(s.get("pot_bb", 0) or 0),
                eff_stack_bb=float(s.get("eff_stack_bb", 100) or 100),
                hero_in_position=bool(s.get("in_position", True)),
                hero_combo=s.get("hero_combo", ""),
                iterations=80,
                pot_type=s.get("pot_type", "SRP"),
            )
        except Exception:
            out = None
        self.done.emit(out)

# ── Renk tokenleri (tema ile uyumlu) ──────────────────────────────
_ACCENT  = "#5ad17a"
_DANGER  = "#e87474"
_WARN    = "#d6c668"
_MUTED   = "#898d80"
_INK     = "#f4f5ee"
_BG2     = "#131613"
_LINE2   = "#33382c"
_INFO    = "#5ad1ce"

# ── GTO Range veri tabanı ─────────────────────────────────────────
# Her pozisyon için: stack aralığına göre (min_bb, range_str, hands_hint, note)
_RANGE_DB: dict[str, list] = {
    # (min_stack_bb, pct, hands, note)
    "UTG": [
        (40,  "13–15%", "AA–22 · AKs–ATs · AKo–AQo · KQs–KJs · JTs · T9s",
               "GTO açılış — sadece güçlü eller"),
        (12,  "11–12%", "44+ · ATs+ · AKo–AQo · KQs",
               "12-40bb: 22-33 ve zayıf AXs çıkar"),
        (0,   "7–8%",   "TT+ · ATs+ · AKo",
               "<12bb push/fold zone — premium only"),
    ],
    "MP": [
        (40,  "17–19%", "UTG + 97s+ · 87s+ · 76s+ · 65s+ · 44-33 · KQo · QJo",
               "Orta pozisyon — suited connectors ekler"),
        (12,  "15–17%", "66+ · AJs+ · AQo+ · KQs · KJs · QJs",
               "Offsuit broadways artar, weak suiteds çıkar"),
        (0,   "10–12%", "88+ · AJs+ · AQo+ · KQs",
               "Push/fold zone"),
    ],
    "CO": [
        (40,  "25–28%", "MP + 54s · 43s · T8s · 98s · AJo · KJo · QJo",
               "CO geniş açılır — BTN'den sonra en iyi pozisyon"),
        (20,  "20–22%", "55+ · ATs+ · AJo+ · KQs · KJs · QJs · JTs",
               "Orta derinlikte sıkılaş"),
        (0,   "14–16%", "77+ · ATs+ · AJo+ · KQs · QJs",
               "Push/fold zone"),
    ],
    "BTN": [
        (40,  "45–50%", "A2s+ · K9s+ · QTs+ · J9s+ · T8s+ · 98s · 87s · 76s · 65s · 22+",
               "BTN: en geniş range — pozisyon çok değerli"),
        (20,  "35–40%", "22+ · A2s+ · KTs+ · QTs+ · J9s+ · T9s · 98s · KJo+ · ATo+",
               "Orta derinlikte biraz daralt"),
        (0,   "22–25%", "55+ · A9s+ · ATo+ · KQs · KJs · QJs · JTs",
               "Push/fold zone"),
    ],
    "SB": [
        (40,  "40–45%", "BTN'e yakın ama OOP — K2s+ · Q6s+ · J7s+ · T8s+ · 22+",
               "OOP dezavantajı var — pozisyon kaybı ciddi"),
        (20,  "28–32%", "33+ · A2s+ · KTs+ · QTs+ · JTs · T9s · KJo+ · AJo+",
               "Orta derinlikte daralt"),
        (0,   "18–22%", "44+ · A7s+ · ATo+ · KQs · QJs",
               "Push/fold zone"),
    ],
    "BB": [
        (40,  "MDF ~52%", "K2s+ · Q4s+ · J7s+ · T8s+ · 97s+ · 86s+ · 75s+ · K9o+ · Q9o+ · J9o+",
               "BB: halihazırda para yatırıldı — geniş defend"),
        (20,  "MDF ~45%", "Suited hands wide · suited broadways · K9o+ · Q9o+ · JTo",
               "Kısa stackte ICM ile daralt"),
        (0,   "MDF ~35%", "22+ · A2s+ · KTs+ · QJs · ATo+ · KQo",
               "Çok kısa stack — sadece yeterli equity"),
    ],
}

# Özel turnuva notları
_TOURNEY_NOTE: dict[str, str] = {
    "UTG":  "Bubble yakınsa sıkılaş. Ante varsa %2-3 genişle.",
    "MP":   "Stack basıncı varsa (20bb altı) push/fold'a geç.",
    "CO":   "Steal frekansı yüksek tut ama ICM baskısına dikkat.",
    "BTN":  "En değerli steal pozisyonu. Short stackleri zorla.",
    "SB":   "OOP. Heads-up steal'de agresif ol, postflop dikkatli.",
    "BB":   "Antes ile defend range genişler. Multiway'de sıkılaş.",
}


# Senaryo (RFI dışı) için panel metni: (üst satır, ipucu)
_SCENARIO_INFO: dict[str, tuple[str, str]] = {
    "vs RFI":   ("vs Açış — defans", "Call / 3-bet / fold (açana & pozisyona göre)"),
    "vs 3-bet": ("vs 3-bet — 4-bet kararı",
                 "Premium 4-bet · TT–AQ call · A5s–A3s blöf 4-bet"),
    "vs 4-bet": ("vs 4-bet", "QQ+/AK devam · gerisi fold"),
    "Push/Fold": ("Push/Fold — Nash", "Jam veya fold (stack ≤ ~16bb)"),
    "Postflop": ("Postflop", "Board + equity → el sonu reveal'da kesin GTO"),
}


def _scenario_key(scen: str) -> str:
    """live_gto_advice senaryo metnini kaba anahtara indir."""
    s = (scen or "").lower()
    if "4-bet" in s and "vs" in s:
        return "vs 4-bet"
    if "3-bet" in s:
        return "vs 3-bet"
    if "vs rfi" in s or "vs açış" in s:
        return "vs RFI"
    if "push" in s:
        return "Push/Fold"
    if "postflop" in s:
        return "Postflop"
    if s.startswith("rfi") or "açış" in s:
        return "RFI"
    return ""


def _range_info(pos: str, stack_bb: float) -> tuple[str, str, str, str]:
    """(pct, hands, note, tourney_note) döner."""
    entries = _RANGE_DB.get(pos.upper(), _RANGE_DB.get("CO", []))
    for min_bb, pct, hands, note in entries:
        if stack_bb >= min_bb:
            return pct, hands, note, _TOURNEY_NOTE.get(pos.upper(), "")
    # Fallback
    if entries:
        _, pct, hands, note = entries[-1]
        return pct, hands, note, _TOURNEY_NOTE.get(pos.upper(), "")
    return "—", "—", "", ""


class GTORangeWidget(QFrame):
    """Kompakt GTO range paneli — action deck'in üstüne entegre edilir."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("GTORangePanel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            f"QFrame#GTORangePanel {{"
            f"  background: {_BG2};"
            f"  border: 1px solid {_LINE2};"
            f"  border-left: 3px solid {_INFO};"
            f"}}"
        )

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 6, 12, 6)
        root.setSpacing(12)

        # Sol: pozisyon + yüzde
        left = QVBoxLayout()
        left.setSpacing(1)
        self._pos_lbl = QLabel("—")
        self._pos_lbl.setStyleSheet(
            f"font-family:'JetBrains Mono',monospace; font-size:11px; "
            f"letter-spacing:2px; color:{_INFO}; background:transparent; font-weight:700;"
        )
        self._pct_lbl = QLabel("—")
        self._pct_lbl.setStyleSheet(
            f"font-family:'JetBrains Mono',monospace; font-size:13px; "
            f"font-weight:700; color:{_INK}; background:transparent;"
        )
        left.addWidget(self._pos_lbl)
        left.addWidget(self._pct_lbl)
        root.addLayout(left)

        # Orta: eller ve not
        mid = QVBoxLayout()
        mid.setSpacing(1)
        self._hands_lbl = QLabel("—")
        self._hands_lbl.setStyleSheet(
            f"font-family:'JetBrains Mono',monospace; font-size:10px; "
            f"color:{_MUTED}; background:transparent;"
        )
        self._hands_lbl.setWordWrap(True)
        self._note_lbl = QLabel("")
        self._note_lbl.setStyleSheet(
            f"font-family:'JetBrains Mono',monospace; font-size:9px; "
            f"color:{_WARN}; background:transparent;"
        )
        self._note_lbl.setWordWrap(True)
        mid.addWidget(self._hands_lbl)
        mid.addWidget(self._note_lbl)
        root.addLayout(mid, 1)

        # Sağ: stack bilgisi
        self._stack_lbl = QLabel("")
        self._stack_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._stack_lbl.setStyleSheet(
            f"font-family:'JetBrains Mono',monospace; font-size:10px; "
            f"color:{_MUTED}; background:transparent;"
        )
        root.addWidget(self._stack_lbl)

        # En sağ: hero hand → tavsiye edilen aksiyon badge'i
        # Örnek: "K7s\nRAISE 55%" (renk: kırmızı raise, yeşil call, mavi fold)
        self._hero_badge = QLabel("")
        self._hero_badge.setAlignment(Qt.AlignCenter)
        self._hero_badge.setMinimumWidth(110)
        self._hero_badge.setStyleSheet(
            f"font-family:'JetBrains Mono',monospace; font-size:11px; "
            f"font-weight:700; color:{_MUTED}; background:transparent; "
            f"padding: 2px 8px; border-radius:4px;"
        )
        self._hero_badge.hide()   # only shown when hero hand is known
        root.addWidget(self._hero_badge)

    def update_range(
        self,
        position: str,
        stack_bb: float,
        game_type: str = "cash",       # "cash" veya "tournament"
        hero_hand: str | None = None,  # canonical key, örn "AKs", "QJo", "77"
        reveal_action: bool = True,    # False → spesifik tavsiyeyi gizle (train modu)
        advice=None,                   # LiveAdvice — gerçek senaryo (RFI/vs-3bet…)
    ) -> None:
        """Pozisyon ve stack'e göre GTO range bilgisini güncelle.

        ``advice`` (LiveAdvice) verilirse panel GERÇEK senaryoyu yansıtır
        (RFI / vs RFI / vs 3-bet / Push-Fold / Postflop) — sadece statik açılış
        range'i değil. Böylece 3-bet/4-bet ve farklı pot/senaryolar net olur.

        ``reveal_action=False`` ise spesifik aksiyon cevabı gizlenir (eğitim
        modu); senaryo + bağlam yine de doğru gösterilir.
        """
        if not position:
            return

        pct, hands, note, tourney_note = _range_info(position, stack_bb)
        pos_text = f"GTO · {position.upper()}"
        pct_text = f"Açılış: {pct}"
        hands_text = hands
        display_note = tourney_note if game_type == "tournament" and tourney_note else note

        # ── Senaryo-duyarlı görünüm (gerçek GTO) ──
        scen = (getattr(advice, "scenario", "") or "") if advice else ""
        if advice is not None and getattr(advice, "available", False) and scen:
            key = _scenario_key(scen)
            if key == "RFI":
                pass    # açılış range'i doğru — statik metni koru
            else:
                line, hint = _SCENARIO_INFO.get(
                    key, ("Karar spotu", "El sonu reveal'da kesin GTO"))
                pos_text = f"GTO · {scen}"
                pct_text = line
                hands_text = hint
                display_note = getattr(advice, "tier_label", "") or ""

        self._pos_lbl.setText(pos_text)
        self._pct_lbl.setText(pct_text)
        self._hands_lbl.setText(hands_text)
        self._note_lbl.setText(display_note)
        self._note_lbl.setVisible(bool(display_note))

        self._stack_lbl.setText(f"{stack_bb:.0f}bb")
        self._update_hero_badge(position, stack_bb, hero_hand,
                                reveal=reveal_action, advice=advice)

        # Renk uyarısı: çok kısa stack
        if stack_bb < 15:
            self._pct_lbl.setStyleSheet(
                f"font-family:'JetBrains Mono',monospace; font-size:13px; "
                f"font-weight:700; color:{_DANGER}; background:transparent;"
            )
            self._note_lbl.setText("⚠ Push/fold zone — Nash chart kullan")
            self._note_lbl.setVisible(True)
        elif stack_bb < 30:
            self._pct_lbl.setStyleSheet(
                f"font-family:'JetBrains Mono',monospace; font-size:13px; "
                f"font-weight:700; color:{_WARN}; background:transparent;"
            )
        else:
            self._pct_lbl.setStyleSheet(
                f"font-family:'JetBrains Mono',monospace; font-size:13px; "
                f"font-weight:700; color:{_INK}; background:transparent;"
            )

    def _update_hero_badge(
        self,
        position: str,
        stack_bb: float,
        hero_hand: str | None,
        reveal: bool = True,
        advice=None,
    ) -> None:
        """Hero'nun spesifik eli için GTO tavsiyesini badge olarak göster."""
        if not hero_hand:
            self._hero_badge.hide()
            return
        # Eğitim modu: cevabı şimdi gösterme — önce sen karar ver
        if not reveal:
            self._hero_badge.setText(f"{hero_hand}\n? KARARINI VER")
            self._hero_badge.setStyleSheet(
                f"font-family:'JetBrains Mono',monospace; font-size:11px; "
                f"font-weight:700; color:{_MUTED}; background:transparent; "
                f"padding: 2px 10px; border-radius:4px; "
                f"border: 1px dashed {_LINE2};"
            )
            self._hero_badge.show()
            return

        # GERÇEK senaryo frekansları (advice varsa) — yoksa RFI fallback
        if advice is not None and getattr(advice, "available", False):
            r = float(getattr(advice, "raise_", 0))
            c = float(getattr(advice, "call", 0))
            f = float(getattr(advice, "fold", 0))
            allin = float(getattr(advice, "allin", 0))
            if allin > max(r, c, f):       # push/fold → JAM
                r, c = allin, 0.0
        else:
            try:
                from app.poker.gto_ranges import get_action
            except Exception:
                self._hero_badge.hide()
                return
            depth = 100 if stack_bb >= 60 else (40 if stack_bb >= 30 else 20)
            pos = position.upper()
            if pos in ("LJ", "UTG+1"):
                pos = "MP"
            if pos == "HJ":
                pos = "CO"
            action = get_action(pos, hero_hand, scenario="RFI",
                                stack_depth=depth, mode="cash")
            r = action.get("raise", 0)
            c = action.get("call", 0)
            f = action.get("fold", 0)

        # En yüksek frekanslı aksiyonu primary olarak göster
        if r >= c and r >= f:
            primary, primary_color = "RAISE", _DANGER
            primary_pct = r
        elif c >= f:
            primary, primary_color = "CALL", _ACCENT
            primary_pct = c
        else:
            primary, primary_color = "FOLD", _INFO
            primary_pct = f

        # Mixed strategy uyarısı
        sub = ""
        if 0 < r < 100 and 0 < f < 100:
            sub = f"  (mixed)"

        text = f"{hero_hand}\n{primary} {primary_pct}%{sub}"
        self._hero_badge.setText(text)
        self._hero_badge.setStyleSheet(
            f"font-family:'JetBrains Mono',monospace; font-size:11px; "
            f"font-weight:700; color:{primary_color}; background:transparent; "
            f"padding: 2px 10px; border-radius:4px; "
            f"border: 2px solid {primary_color};"
        )
        self._hero_badge.show()


# ══════════════════════════════════════════════════════════════════════════
#  El-sonu GTO reveal — oyun sırasında gizli, el bitince optimal kararı açar
# ══════════════════════════════════════════════════════════════════════════

class GTODecisionReveal(QFrame):
    """El bittikten sonra GTO-optimal kararı/kararları gösteren panel.

    Oyun sırasında gizli kalır (``hide_panel()``); el tamamlanınca
    ``show_decisions([...])`` ile her hero karar noktasının optimal aksiyon
    dağılımını (FOLD/CALL/RAISE/ALL-IN % + size) ve senin gerçek kararını
    yan yana gösterir — "kod-doğru ≠ user-anlıyor": önce karar ver, sonra gör.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("GTOReveal")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            f"QFrame#GTOReveal {{ background:{_BG2}; "
            f"border:1px solid {_LINE2}; border-left:3px solid {_WARN}; }}"
        )
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(12, 8, 12, 8)
        self._root.setSpacing(4)

        self._title = QLabel("EL SONU · GTO OPTİMAL KARAR")
        self._title.setStyleSheet(
            f"font-family:'JetBrains Mono',monospace; font-size:10px; "
            f"letter-spacing:2px; font-weight:700; color:{_WARN}; "
            f"background:transparent;"
        )
        self._root.addWidget(self._title)

        self._rows = QVBoxLayout()
        self._rows.setSpacing(3)
        self._root.addLayout(self._rows)

        # ── On-demand EXACT solver (TexasSolver, arka planda) ──
        self._exact_btn = QPushButton("🎯  EXACT solver ile kesinleştir")
        self._exact_btn.setStyleSheet(
            f"QPushButton {{ background:#0f2318; color:{_INFO}; "
            f"border:1px solid {_INFO}; border-radius:5px; "
            f"font-family:'JetBrains Mono',monospace; font-size:10px; "
            f"font-weight:700; padding:4px 10px; }} "
            f"QPushButton:hover {{ background:#132a20; }} "
            f"QPushButton:disabled {{ color:{_MUTED}; border-color:{_LINE2}; }}")
        self._exact_btn.clicked.connect(self._run_exact_solve)
        self._exact_btn.hide()
        self._root.addWidget(self._exact_btn)
        self._exact_result = QLabel("")
        self._exact_result.setTextFormat(Qt.RichText)
        self._exact_result.setWordWrap(True)
        self._exact_result.setStyleSheet(
            f"font-family:'JetBrains Mono',monospace; font-size:10px; "
            f"color:{_INK}; background:transparent;")
        self._exact_result.hide()
        self._root.addWidget(self._exact_result)
        self._solve_thread = None
        self._solve_worker = None
        self._solvable_spot = None

        self.hide()

    def hide_panel(self) -> None:
        self.hide()

    def _clear_rows(self) -> None:
        while self._rows.count():
            it = self._rows.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
            elif it.layout():
                _lay = it.layout()
                while _lay.count():
                    sub = _lay.takeAt(0)
                    if sub.widget():
                        sub.widget().deleteLater()

    def show_decisions(self, decisions: list, graded: bool = False,
                       session_summary: dict | None = None) -> None:
        """``decisions``: her biri bir hero karar noktası (dict).

        Beklenen anahtarlar (eksikler tolere edilir):
          street, scenario, tier, fold, call, raise, allin,
          sizing_label, sizing_bb, hero_action, hero_amount,
          available (bool), note (str)

        ``graded=True`` (Real Experience Mode): üstte el skoru başlığı + her
        karar satırında harf notu (A-F) + "SPACE → sonraki el" ipucu gösterilir.
        ``session_summary``: verilirse en üstte oturum karnesi satırı (oturum
        boyu GTO doğruluk %, EV kaybı, en zayıf street).
        """
        self._clear_rows()
        self._graded = graded
        self._setup_exact_button(decisions)
        if graded:
            self._title.setText("EL SONU · KARAR KARNESİ  ·  GTO OPTİMAL")
        else:
            self._title.setText("EL SONU · GTO OPTİMAL KARAR")

        # ── Oturum karnesi satırı (en üstte) ──
        if session_summary and session_summary.get("n_decisions", 0) > 0:
            acc = session_summary.get("accuracy", 0)
            acc_color = (_ACCENT if acc >= 70 else
                         _WARN if acc >= 50 else _DANGER)
            ev = session_summary.get("ev_lost", 0)
            weak = session_summary.get("weakest")
            weak_s = f"  ·  en zayıf: <span style='color:{_DANGER}'>{weak}</span>" if weak else ""
            sess = QLabel(
                f"<span style='color:{_MUTED}'>OTURUM "
                f"{session_summary.get('n_hands', 0)} el</span>  ·  "
                f"<span style='color:{acc_color}; font-weight:700'>GTO doğruluk "
                f"%{acc:.0f}</span>  ·  "
                f"<span style='color:{_MUTED}'>EV kaybı {ev:.1f}bb</span>{weak_s}"
            )
            sess.setTextFormat(Qt.RichText)
            sess.setStyleSheet(
                f"font-family:'JetBrains Mono',monospace; font-size:11px; "
                f"background:transparent; padding-bottom:2px;"
            )
            self._rows.addWidget(sess)

        if not decisions:
            lbl = QLabel("Bu elde hero karar noktası yok (fold edildi / blind).")
            lbl.setStyleSheet(
                f"font-family:'JetBrains Mono',monospace; font-size:10px; "
                f"color:{_MUTED}; background:transparent;"
            )
            self._rows.addWidget(lbl)
            self.show()
            return

        # ── El skoru başlığı (graded) ──
        if graded:
            try:
                from app.poker.decision_grade import grade_hand
                hg = grade_hand(decisions)
            except Exception:
                hg = None
            if hg and hg.score is not None:
                color = self._grade_color(hg.letter)
                ev_s = (f"  ·  EV kaybı ~{hg.ev_loss_total:.1f}bb"
                        if hg.ev_loss_total else "")
                hdr = QLabel(
                    f"<span style='color:{color}; font-weight:700'>EL NOTU: "
                    f"{hg.letter}  (%{hg.score:.0f})</span>"
                    f"<span style='color:{_MUTED}'>  ·  {hg.n_decisions} karar"
                    f"{ev_s}</span>"
                )
                hdr.setTextFormat(Qt.RichText)
                hdr.setStyleSheet(
                    f"font-family:'JetBrains Mono',monospace; font-size:13px; "
                    f"background:transparent;"
                )
                self._rows.addWidget(hdr)

        for d in decisions:
            self._rows.addLayout(self._build_row(d))

        # Hero bu eli oynadıysa SPACE ipucu (panel artık otomatik kapanmıyor)
        if any(d.get("hero_action") for d in decisions):
            hint = QLabel("▸ SPACE ile onayla → sonraki el")
            hint.setStyleSheet(
                f"font-family:'JetBrains Mono',monospace; font-size:10px; "
                f"letter-spacing:1px; color:{_INFO}; background:transparent; "
                f"font-weight:700; padding-top:3px;"
            )
            self._rows.addWidget(hint)
        self.show()

    @staticmethod
    def _grade_color(letter: str) -> str:
        return {
            "A": _ACCENT, "B": _ACCENT, "C": _WARN, "D": _DANGER, "F": _DANGER,
        }.get(letter, _MUTED)

    # ── On-demand EXACT solver (TexasSolver, arka planda) ───────────────
    def _setup_exact_button(self, decisions: list) -> None:
        """Çözülebilir bir postflop spot varsa EXACT butonunu göster."""
        self._exact_result.hide()
        self._exact_result.setText("")
        spot = None
        for d in (decisions or []):
            if not d.get("available"):
                continue
            board = d.get("board") or ""
            ncards = len([x for x in board.split() if x])
            if ncards >= 3 and d.get("hero_combo"):
                spot = d                      # son uygun postflop spot
        self._solvable_spot = spot
        can = spot is not None
        if can:
            try:
                from app.poker.postflop_solver import solver_available
                can = solver_available()
            except Exception:
                can = False
        self._exact_btn.setVisible(bool(can))
        if can:
            self._exact_btn.setEnabled(True)
            self._exact_btn.setText("🎯  EXACT solver ile kesinleştir")

    def _run_exact_solve(self) -> None:
        if not self._solvable_spot:
            return
        # Önceki thread bitmediyse yok say
        if self._solve_thread is not None and self._solve_thread.isRunning():
            return
        self._exact_btn.setEnabled(False)
        self._exact_btn.setText("🎯  Çözülüyor… (~5–15s, TexasSolver)")
        self._exact_result.hide()
        self._solve_thread = QThread(self)
        self._solve_worker = _SolveWorker(self._solvable_spot)
        self._solve_worker.moveToThread(self._solve_thread)
        self._solve_thread.started.connect(self._solve_worker.run)
        self._solve_worker.done.connect(self._on_exact_done)
        self._solve_worker.done.connect(self._solve_thread.quit)
        self._solve_thread.start()

    def _on_exact_done(self, out) -> None:
        self._exact_btn.setEnabled(True)
        self._exact_btn.setText("🎯  EXACT solver ile kesinleştir")
        if not out:
            self._exact_result.setText(
                f"<span style='color:{_MUTED}'>Solver şu an çözemedi "
                f"(binary/board/zaman aşımı). CONCEPT öneri geçerli.</span>")
            self._exact_result.show()
            return
        parts = []
        for a, f in sorted(out.items(), key=lambda kv: -kv[1]):
            au = a.upper()
            color = (_DANGER if au.startswith(("BET", "RAISE", "ALL"))
                     else _ACCENT if au in ("CHECK", "CALL") else _INFO)
            parts.append(f"<span style='color:{color}'>{a} %{f:.0f}</span>")
        spot = self._solvable_spot or {}
        self._exact_result.setText(
            f"✅ <b style='color:{_ACCENT}'>EXACT</b> "
            f"<span style='color:{_MUTED}'>(TexasSolver · {spot.get('board','')}"
            f" · {'IP' if spot.get('in_position') else 'OOP'}):</span>  "
            + "   ·   ".join(parts))
        self._exact_result.show()

    @staticmethod
    def _verdict(d: dict) -> tuple[str, str]:
        """(işaret, renk) — hero kararı optimal frekansla uyumlu mu?"""
        action_to_key = {
            "FOLD": "fold", "CHECK": "call", "CALL": "call",
            "BET": "raise", "RAISE": "raise", "ALL_IN": "allin", "ALLIN": "allin",
        }
        ha = (d.get("hero_action") or "").upper().replace("-", "_")
        key = action_to_key.get(ha)
        if not d.get("available") or key is None:
            return "", _MUTED
        pct = float(d.get(key, 0) or 0)
        if pct >= 50:
            return "✓ GTO ile uyumlu", _ACCENT
        if pct >= 15:
            return "≈ kabul edilebilir (mixed)", _WARN
        return "✗ GTO'dan sapma", _DANGER

    @staticmethod
    def _math_line(d: dict) -> str:
        """Bu karar noktasının somut GTO-matematiği (RichText).

        equity %  ·  pot odds (break-even) %  ·  MDF %  →  +EV/-EV yorumu.
        Veri yoksa "" döner (satır gizlenir).
        """
        pot = float(d.get("pot_bb", 0) or 0)
        to_call = float(d.get("to_call_bb", 0) or 0)
        eq = float(d.get("equity", 0) or 0)
        parts: list[str] = []

        if eq > 0:
            parts.append(f"<span style='color:{_ACCENT}'>Equity %{eq:.0f}</span>")

        if to_call > 0.01 and pot > 0:
            pot_odds = 100.0 * to_call / (pot + to_call)   # break-even equity
            mdf = 100.0 * pot / (pot + to_call)            # min defense freq
            parts.append(
                f"<span style='color:{_WARN}'>break-even %{pot_odds:.0f}</span> "
                f"(pot {pot:.1f}bb · call {to_call:.1f}bb)"
            )
            parts.append(f"MDF %{mdf:.0f}")
            # Equity biliniyorsa +EV/-EV call yorumu
            if eq > 0:
                if eq >= pot_odds:
                    parts.append(
                        f"<span style='color:{_ACCENT}'>→ call +EV "
                        f"(equity &gt; break-even)</span>"
                    )
                else:
                    parts.append(
                        f"<span style='color:{_DANGER}'>→ call -EV "
                        f"(equity &lt; break-even)</span>"
                    )

        if not parts:
            return ""
        return "📊  " + "  ·  ".join(parts)

    def _build_row(self, d: dict):
        col = QVBoxLayout()
        col.setSpacing(1)

        street = (d.get("street") or "").upper()
        scen = d.get("scenario") or ""
        tier = d.get("tier") or ""
        head = QLabel(f"{street}  ·  {scen}" + (f"  ·  {tier}" if tier else ""))
        head.setStyleSheet(
            f"font-family:'JetBrains Mono',monospace; font-size:9px; "
            f"letter-spacing:1px; color:{_INFO}; background:transparent; font-weight:700;"
        )
        col.addWidget(head)

        # ── Matematik satırı (equity · pot-odds · MDF) — her zaman göster ──
        math_line = self._math_line(d)
        if math_line:
            ml = QLabel(math_line)
            ml.setTextFormat(Qt.RichText)
            ml.setStyleSheet(
                f"font-family:'JetBrains Mono',monospace; font-size:10px; "
                f"color:{_MUTED}; background:transparent;"
            )
            ml.setWordWrap(True)
            col.addWidget(ml)

        if not d.get("available"):
            note = d.get("note") or "Postflop GTO için solver gerekli (Solver Sandbox)."
            nl = QLabel(f"  {note}")
            nl.setStyleSheet(
                f"font-family:'JetBrains Mono',monospace; font-size:10px; "
                f"color:{_MUTED}; background:transparent;"
            )
            nl.setWordWrap(True)
            col.addWidget(nl)
            return col

        # Optimal aksiyon dağılımı
        parts = []
        for label, key, color in [
            ("FOLD", "fold", _INFO), ("CHECK/CALL", "call", _ACCENT),
            ("RAISE", "raise", _DANGER), ("ALL-IN", "allin", _DANGER),
        ]:
            pct = float(d.get(key, 0) or 0)
            if pct > 0:
                parts.append(f"<span style='color:{color}'>{label} {pct:.0f}%</span>")
        dist = "   ·   ".join(parts) if parts else "—"

        # Size sadece raise/bet öneriliyorsa anlamlı (fold/call için gizle)
        sizing = ""
        if d.get("sizing_bb") and float(d.get("raise", 0) or 0) > 0:
            sizing = f"   →   raise size: {d['sizing_bb']:.1f}bb"
            if d.get("sizing_label"):
                sizing += f" ({d['sizing_label']})"

        opt = QLabel(f"Optimal:  {dist}{sizing}")
        opt.setTextFormat(Qt.RichText)
        opt.setStyleSheet(
            f"font-family:'JetBrains Mono',monospace; font-size:11px; "
            f"font-weight:700; color:{_INK}; background:transparent;"
        )
        opt.setWordWrap(True)
        col.addWidget(opt)

        # Hero'nun gerçek kararı + verdict (+ graded: harf notu)
        ha = d.get("hero_action")
        if ha:
            amt = d.get("hero_amount")
            amt_s = f" {amt:.1f}bb" if isinstance(amt, (int, float)) and amt else ""
            mark, mcolor = self._verdict(d)
            grade_s = ""
            if getattr(self, "_graded", False):
                try:
                    from app.poker.decision_grade import grade_decision
                    g = grade_decision(d)
                    if g.score is not None:
                        gcolor = self._grade_color(g.letter)
                        grade_s = (f"   <span style='color:{gcolor}; "
                                   f"font-weight:700'>[{g.letter}]</span>")
                except Exception:
                    grade_s = ""
            you = QLabel(f"Senin kararın:  {ha}{amt_s}    {mark}{grade_s}")
            you.setTextFormat(Qt.RichText)
            you.setStyleSheet(
                f"font-family:'JetBrains Mono',monospace; font-size:10px; "
                f"font-weight:700; color:{mcolor}; background:transparent;"
            )
            col.addWidget(you)

            # ── Boyut karşılaştırması: "sen 5bb → GTO ~12bb dene" ──
            rec = d.get("sizing_bb")
            if (ha.upper() in ("RAISE", "BET")
                    and isinstance(rec, (int, float)) and rec
                    and isinstance(amt, (int, float)) and amt):
                ratio = amt / rec
                if ratio < 0.7:
                    sv, scol = (f"⚠ KÜÇÜK — GTO ~{rec:.1f}bb (daha büyük raise "
                                f"value/fold-equity kazandırır)"), _WARN
                elif ratio > 1.45:
                    sv, scol = (f"⚠ BÜYÜK — GTO ~{rec:.1f}bb (overbet sadece "
                                f"polarize range'le)"), _WARN
                else:
                    sv, scol = f"✓ boyut GTO'ya yakın (~{rec:.1f}bb)", _ACCENT
                szl = QLabel(f"      boyut: sen {amt:.1f}bb  →  {sv}")
                szl.setWordWrap(True)
                szl.setStyleSheet(
                    f"font-family:'JetBrains Mono',monospace; font-size:10px; "
                    f"color:{scol}; background:transparent;")
                col.addWidget(szl)
        return col


# ══════════════════════════════════════════════════════════════════════════
#  Hand Matrix — 13×13 colour-coded range grid
# ══════════════════════════════════════════════════════════════════════════

_MATRIX_RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']
_MATRIX_RIDX  = {r: i for i, r in enumerate(_MATRIX_RANKS)}

# Cell colour buckets
_MC_PREMIUM = "#5ad17a"   # lime-green  — AA/KK/QQ/JJ + AKs/AKo
_MC_VALUE   = "#5ad1ce"   # cyan        — other in-range hands
_MC_PAIR_SM = "#7c3aed"   # indigo      — pairs 77 and below when in range
_MC_OUT     = "#0f1210"   # near-black  — out of range
_MC_OUT_TXT = "#23271f"   # border-only text
_MC_IN_TXT  = "#0a0c0a"   # ink on coloured cells
_MC_SM_TXT  = "#e0d0ff"   # light text on purple cells


def _matrix_cell_hand(i: int, j: int) -> str:
    """Canonical hand string for matrix cell (row i, col j)."""
    r = _MATRIX_RANKS
    if i == j:
        return r[i] + r[j]              # pair  e.g. "AA"
    elif i < j:
        return r[i] + r[j] + "s"       # suited e.g. "AKs"
    else:
        return r[j] + r[i] + "o"       # offsuit e.g. "AKo"


def _matrix_cell_colors(hand: str, in_range: bool) -> tuple[str, str]:
    """Return (bg, fg) for a matrix cell."""
    if not in_range:
        return _MC_OUT, _MC_OUT_TXT
    # Premium
    if hand in ("AA", "KK", "QQ", "JJ", "AKs", "AKo"):
        return _MC_PREMIUM, _MC_IN_TXT
    # Small pairs (77 and below → index ≥ 6)
    if len(hand) == 2 and hand[0] == hand[1]:
        if _MATRIX_RIDX.get(hand[0], 0) >= 6:
            return _MC_PAIR_SM, _MC_SM_TXT
    return _MC_VALUE, _MC_IN_TXT


# ── Action-frequency coloring (GTOWizard / range_trainer ile tutarlı) ──
# RAISE=kırmızı, CALL=yeşil, FOLD=mavi. Mixed → yatay gradient split.
_AC_RAISE = "#DC2626"
_AC_CALL  = "#10B981"
_AC_FOLD  = "#2563EB"
_AC_FOLD_DIM = "#16203a"   # tam-fold hücreler için kısık mavi (grid'i boğmasın)


def _action_cell_bg(action: dict) -> str:
    """Build a horizontal RAISE|CALL|FOLD gradient from an action-freq dict.

    Pure action → solid color. Mixed → linear-gradient with hard stops, so
    the cell visually splits the same way the live range_trainer chart does.
    """
    r = max(0.0, float(action.get("raise", 0)))
    c = max(0.0, float(action.get("call", 0)))
    f = max(0.0, float(action.get("fold", 0)))
    total = r + c + f
    if total <= 0:
        return _AC_FOLD_DIM
    r, c, f = r / total, c / total, f / total

    # Pure-action fast paths
    if f >= 0.999:
        return _AC_FOLD_DIM          # whole-grid fold cells stay subtle
    if r >= 0.999:
        return _AC_RAISE
    if c >= 0.999:
        return _AC_CALL

    # Mixed → hard-stop horizontal gradient: raise | call | fold
    stops: list[tuple[float, str]] = []
    pos = 0.0
    for frac, color in ((r, _AC_RAISE), (c, _AC_CALL), (f, _AC_FOLD)):
        if frac <= 0:
            continue
        stops.append((pos, color))
        pos += frac
        stops.append((min(pos, 1.0), color))
    parts = ", ".join(f"stop:{p:.3f} {col}" for p, col in stops)
    return f"qlineargradient(x1:0, y1:0, x2:1, y2:0, {parts})"


def _action_text_color(action: dict) -> str:
    """Readable ink for an action cell — light on saturated, muted on dim fold."""
    f = float(action.get("fold", 0))
    r = float(action.get("raise", 0))
    c = float(action.get("call", 0))
    if f >= 99.9 and r <= 0 and c <= 0:
        return "#6b7da3"   # muted on dim-fold
    return "#ffffff"


def parse_range_str(s: str) -> set[str]:
    """Parse a GTO range string into a set of canonical hand tokens.

    Supported notations:
        AKs, AKo, AA          – single hand
        JJ+, A2s+, K9o+      – plus (hand and better)
        AKs–ATs, AA–22       – dash range
    Non-hand text (Turkish notes, percentages) is silently ignored.
    """
    result: set[str] = set()
    # Normalise dash variants
    s = s.replace("–", "-").replace("–", "-")
    # Split on middle-dot separator; fall back to comma/space
    tokens = re.split(r"[·,]", s)

    # Regex for a valid hand token: 2 rank chars + optional s/o
    _H = r"[AKQJT98765432]{2}[so]?"

    for raw in tokens:
        raw = raw.strip()
        # Dash range first (must precede single-hand match)
        m = re.search(rf"({_H})\s*-\s*({_H})", raw)
        if m:
            _matrix_expand_dash(m.group(1), m.group(2), result)
            continue
        # Plus or single
        m = re.search(_H, raw)
        if m:
            hand = m.group(0)
            if "+" in raw[m.end():m.end() + 1] or raw.endswith("+"):
                _matrix_expand_plus(hand, result)
            else:
                result.add(hand)
    return result


def _matrix_expand_dash(start: str, end: str, out: set) -> None:
    r, ri = _MATRIX_RANKS, _MATRIX_RIDX
    if not start or not end:
        return
    suf = start[2] if len(start) == 3 else ""
    # Pair range e.g. "AA-22"
    if start[0] == start[1] and end[0] == end[1]:
        lo = min(ri.get(start[0], 0), ri.get(end[0], 12))
        hi = max(ri.get(start[0], 0), ri.get(end[0], 12))
        for i in range(lo, hi + 1):
            out.add(r[i] + r[i])
    # Same first card e.g. "AKs-ATs"
    elif start[0] == end[0] and len(start) == 3 and len(end) == 3:
        first_i = ri.get(start[0], 0)
        lo = min(ri.get(start[1], 0), ri.get(end[1], 12))
        hi = max(ri.get(start[1], 0), ri.get(end[1], 12))
        for i in range(lo, hi + 1):
            if i != first_i:
                out.add(start[0] + r[i] + suf)


def _matrix_expand_plus(hand: str, out: set) -> None:
    r, ri = _MATRIX_RANKS, _MATRIX_RIDX
    if len(hand) == 2 and hand[0] == hand[1]:
        # Pair+: "JJ+" → JJ, QQ, KK, AA
        top = ri.get(hand[0], 12)
        for i in range(0, top + 1):
            out.add(r[i] + r[i])
    elif len(hand) == 3:
        first, second, suf = hand[0], hand[1], hand[2]
        fi = ri.get(first, 0)
        si = ri.get(second, 12)
        # "K9s+" → KQs, KJs, KTs, K9s  (from si downward to fi+1)
        for i in range(fi + 1, si + 1):
            out.add(first + r[i] + suf)


class _HandMatrixWidget(QWidget):
    """13×13 colour-coded hand-range matrix.

    Upper triangle = suited, diagonal = pairs, lower triangle = offsuit.
    Call ``set_range(hands_str)`` to colour cells that are in the open range.
    """

    CELL_W = 44   # px per cell
    CELL_H = 34

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._in_range: set[str] = set()
        self._cells: list[list[QLabel]] = []
        # Per-cell base (bg, fg, weight) cache so highlight_hero can re-apply
        # the gold border without losing action/category coloring.
        self._base: list[list[tuple[str, str, str]]] = []
        self._build()

    def _build(self) -> None:
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(2)

        for i in range(13):
            row: list[QLabel] = []
            base_row: list[tuple[str, str, str]] = []
            for j in range(13):
                hand = _matrix_cell_hand(i, j)
                lbl = QLabel(hand)
                lbl.setAlignment(Qt.AlignCenter)
                lbl.setFixedSize(self.CELL_W, self.CELL_H)
                bg, fg = _matrix_cell_colors(hand, False)
                lbl.setStyleSheet(self._compose(bg, fg, "400"))
                grid.addWidget(lbl, i, j)
                row.append(lbl)
                base_row.append((bg, fg, "400"))
            self._cells.append(row)
            self._base.append(base_row)

    @staticmethod
    def _compose(bg: str, fg: str, weight: str,
                 border: str = "1px solid #1a1e18") -> str:
        return (
            f"background:{bg}; color:{fg}; "
            f"font-family:'JetBrains Mono','Menlo',monospace; "
            f"font-size:8px; font-weight:{weight}; "
            f"border:{border};"
        )

    def _apply(self, i: int, j: int, bg: str, fg: str, weight: str) -> None:
        self._base[i][j] = (bg, fg, weight)
        self._cells[i][j].setStyleSheet(self._compose(bg, fg, weight))

    def set_range(self, hands_str: str) -> None:
        """Colour cells by category membership (legacy / fallback path)."""
        self._in_range = parse_range_str(hands_str)
        for i in range(13):
            for j in range(13):
                hand = _matrix_cell_hand(i, j)
                in_r = hand in self._in_range
                bg, fg = _matrix_cell_colors(hand, in_r)
                self._apply(i, j, bg, fg, "700" if in_r else "400")

    def set_action_range(
        self,
        position: str,
        stack_bb: float,
        mode: str = "cash",
        scenario: str = "RFI",
        vs_position: str | None = None,
    ) -> None:
        """Colour every cell by its GTO action frequency (RAISE/CALL/FOLD).

        Mirrors the range_trainer chart: red=raise, green=call, blue=fold,
        mixed strategies show a horizontal split. This is the math-driven
        view — each cell is the optimal action for that hand at this spot.
        """
        try:
            from app.poker.gto_ranges import get_action
        except Exception:
            # Fall back to the textual range if the engine is unavailable
            return

        pos = position.upper()
        if pos in ("LJ", "UTG+1"):
            pos = "MP"
        if pos == "HJ":
            pos = "CO"
        depth = 100 if stack_bb >= 60 else (40 if stack_bb >= 30 else 20)
        eng_mode = "MTT" if mode == "tournament" else "cash"

        self._in_range = set()
        for i in range(13):
            for j in range(13):
                hand = _matrix_cell_hand(i, j)
                try:
                    action = get_action(pos, hand, scenario=scenario,
                                        stack_depth=depth, mode=eng_mode,
                                        vs_position=vs_position)
                except Exception:
                    action = {"raise": 0, "call": 0, "fold": 100}
                bg = _action_cell_bg(action)
                fg = _action_text_color(action)
                # Treat any non-fold action as "in range" for hero weighting
                in_r = (action.get("raise", 0) + action.get("call", 0)) > 0
                if in_r:
                    self._in_range.add(hand)
                self._apply(i, j, bg, fg, "700" if in_r else "400")

    def highlight_hero(self, *hero_hands: str) -> None:
        """Add a gold border to the hero's specific hand cell(s).

        Pass one or two hands (suited + offsuit) to highlight both.
        Works for both category and action coloring (reads the base cache).
        """
        highlighted = set(hero_hands)
        for i in range(13):
            for j in range(13):
                hand = _matrix_cell_hand(i, j)
                bg, fg, weight = self._base[i][j]
                border = ("2px solid #d6c668" if hand in highlighted
                          else "1px solid #1a1e18")
                self._cells[i][j].setStyleSheet(self._compose(bg, fg, weight, border))
