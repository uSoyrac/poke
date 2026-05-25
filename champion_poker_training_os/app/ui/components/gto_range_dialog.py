"""GTO Range Dialog — mevcut el durumuna göre GTO range ve tavsiyeler.

Oyun sırasında 'GTO' butonuna tıklanınca açılır.
Setup ekranında da 'Range Önizle' butonu ile çalışır.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from app.ui.components.gto_range_widget import (
    _range_info, _RANGE_DB, _HandMatrixWidget, parse_range_str,
)

_ACCENT = "#5ad17a"
_DANGER = "#e87474"
_WARN   = "#d6c668"
_MUTED  = "#898d80"
_INK    = "#f4f5ee"
_INK2   = "#d6d8cf"
_BG     = "#0a0c0a"
_BG2    = "#131613"
_LINE   = "#23271f"
_LINE2  = "#33382c"
_INFO   = "#5ad1ce"


def _card(parent=None) -> QFrame:
    f = QFrame(parent)
    f.setObjectName("GTOCard")
    f.setStyleSheet(
        "QFrame#GTOCard { background:#131613; border:1px solid #33382c; }"
    )
    return f


_SUIT_MAP = {"♠": "s", "♥": "h", "♦": "d", "♣": "c"}
_RANK_NORM = {"T": "T", "J": "J", "Q": "Q", "K": "K", "A": "A",
              "10": "T", "2": "2", "3": "3", "4": "4", "5": "5",
              "6": "6", "7": "7", "8": "8", "9": "9"}

def _try_highlight_hero(matrix, hero_cards_str: str) -> None:
    """Parse hero hole-card string (e.g. '9♣J♥' or '9c Jh') and highlight on matrix."""
    import re
    # Match rank + suit pairs (Unicode suits or letter suits)
    pats = re.findall(r"([AKQJT2-9]{1,2})[♠♥♦♣shdc]", hero_cards_str)
    if len(pats) < 2:
        return
    r1, r2 = pats[0].upper(), pats[1].upper()
    r1 = "T" if r1 == "10" else r1
    r2 = "T" if r2 == "10" else r2
    from app.ui.components.gto_range_widget import _MATRIX_RIDX
    i1, i2 = _MATRIX_RIDX.get(r1, -1), _MATRIX_RIDX.get(r2, -1)
    if i1 < 0 or i2 < 0 or i1 == i2:
        return
    # Determine suited/offsuit — we don't know from abbreviation alone,
    # highlight both cells so the user can see either option
    from app.ui.components.gto_range_widget import _matrix_cell_hand
    # Higher rank first (lower index = higher rank in our RANKS array)
    hi, lo = (i1, i2) if i1 < i2 else (i2, i1)
    suited   = _matrix_cell_hand(hi, lo)   # e.g. "JTs"
    offsuit  = _matrix_cell_hand(lo, hi)   # e.g. "JTo"
    matrix.highlight_hero(suited, offsuit)


class GTORangeDialog(QDialog):
    """Popup: mevcut el durumuna göre GTO range bilgisi."""

    def __init__(
        self,
        parent=None,
        position: str = "",
        stack_bb: float = 100.0,
        players_active: int = 6,
        game_type: str = "cash",      # "cash" | "tournament"
        hero_cards: str = "",          # örn "5♥9♦"
        street: str = "preflop",
        pot_bb: float = 0.0,
        big_blind_bb: float = 1.0,
        level: str = "",
    ):
        super().__init__(parent)
        self.setWindowTitle("GTO Range Analizi")
        # Wide enough to show the 13×13 matrix (13*44 + 12*2 gap + 40 padding = ~640)
        self.setMinimumWidth(660)
        self.setMaximumWidth(920)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setStyleSheet(f"""
            QDialog {{ background:{_BG}; color:{_INK}; }}
            QLabel  {{ background:transparent; }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── HEADER ──────────────────────────────────────────────────
        header = QFrame()
        header.setStyleSheet(f"background:{_BG2}; border-bottom:2px solid {_ACCENT};")
        h_l = QHBoxLayout(header)
        h_l.setContentsMargins(20, 14, 20, 14)

        title_col = QVBoxLayout()
        t1 = QLabel("GTO RANGE ANALİZİ")
        t1.setStyleSheet(
            f"font-family:'JetBrains Mono',monospace; font-size:11px; "
            f"letter-spacing:2.5px; color:{_ACCENT}; font-weight:700;"
        )
        ctx_parts = []
        if position:    ctx_parts.append(position.upper())
        if stack_bb:    ctx_parts.append(f"{stack_bb:.0f}bb")
        if players_active: ctx_parts.append(f"{players_active}P")
        if level:       ctx_parts.append(level)
        t2 = QLabel("  ·  ".join(ctx_parts) if ctx_parts else "Genel Analiz")
        t2.setStyleSheet(
            f"font-family:'JetBrains Mono',monospace; font-size:13px; "
            f"font-weight:700; color:{_INK};"
        )
        title_col.addWidget(t1)
        title_col.addWidget(t2)
        h_l.addLayout(title_col, 1)

        if hero_cards:
            card_lbl = QLabel(hero_cards)
            card_lbl.setStyleSheet(
                f"font-family:'JetBrains Mono',monospace; font-size:18px; "
                f"font-weight:700; color:{_WARN}; padding:4px 10px; "
                f"background:#1f1a0d; border:1px solid #5a4f28;"
            )
            h_l.addWidget(card_lbl)

        close_btn = QPushButton("✕")
        close_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{_MUTED}; "
            f"font-size:16px; border:none; padding:4px 8px; }}"
            f"QPushButton:hover {{ color:{_INK}; }}"
        )
        close_btn.clicked.connect(self.close)
        h_l.addWidget(close_btn)
        root.addWidget(header)

        # ── SCROLL BODY ──────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"background:{_BG};")
        body = QWidget()
        body.setStyleSheet(f"background:{_BG};")
        b_l = QVBoxLayout(body)
        b_l.setContentsMargins(20, 18, 20, 20)
        b_l.setSpacing(14)

        # ── DURUM ANALİZİ ────────────────────────────────────────────
        if position:
            pct, hands, note, tourney_note = _range_info(position, stack_bb)

            # Stack depth uyarı rengi
            if stack_bb < 15:
                stack_color = _DANGER
                stack_tag   = "⚠ PUSH/FOLD ZONE"
                stack_note  = "Bu stack derinliğinde sadece All-in veya Fold kararları geçerli. Nash equilibrium chart kullan."
            elif stack_bb < 25:
                stack_color = _WARN
                stack_tag   = "⚡ SHORT STACK"
                stack_note  = "3-bet/fold artık işe yaramaz. Raise/call veya shove stratejisine geç."
            elif stack_bb < 50:
                stack_color = _INK2
                stack_tag   = "ORTA STACK"
                stack_note  = "SPR düşüyor. Commit eşiğini her el hesapla."
            else:
                stack_color = _ACCENT
                stack_tag   = "DEEP STACK"
                stack_note  = "Full postflop oyunu mümkün. Pozisyon ve range avantajını kullan."

            # Ana range card
            rcard = _card()
            r_l = QVBoxLayout(rcard)
            r_l.setContentsMargins(16, 14, 16, 14)
            r_l.setSpacing(8)

            row1 = QHBoxLayout()
            pos_lbl = QLabel(position.upper())
            pos_lbl.setStyleSheet(
                f"font-family:'JetBrains Mono',monospace; font-size:22px; "
                f"font-weight:700; color:{_INFO}; letter-spacing:2px;"
            )
            pct_lbl = QLabel(f"Açılış: {pct}")
            pct_lbl.setStyleSheet(
                f"font-family:'JetBrains Mono',monospace; font-size:18px; "
                f"font-weight:700; color:{stack_color};"
            )
            stag_lbl = QLabel(stack_tag)
            stag_lbl.setStyleSheet(
                f"font-family:'JetBrains Mono',monospace; font-size:10px; "
                f"font-weight:700; letter-spacing:1.5px; color:{_BG}; "
                f"background:{stack_color}; padding:2px 7px;"
            )
            row1.addWidget(pos_lbl)
            row1.addStretch(1)
            row1.addWidget(pct_lbl)
            row1.addSpacing(12)
            row1.addWidget(stag_lbl)
            r_l.addLayout(row1)

            hands_lbl = QLabel(hands)
            hands_lbl.setStyleSheet(
                f"font-family:'JetBrains Mono',monospace; font-size:11px; "
                f"color:{_INK2}; line-height:1.5;"
            )
            hands_lbl.setWordWrap(True)
            r_l.addWidget(hands_lbl)

            note_lbl = QLabel(note)
            note_lbl.setStyleSheet(
                f"font-family:'JetBrains Mono',monospace; font-size:10px; "
                f"color:{_MUTED}; font-style:italic;"
            )
            note_lbl.setWordWrap(True)
            r_l.addWidget(note_lbl)

            if stack_note:
                sn_lbl = QLabel(f"→ {stack_note}")
                sn_lbl.setStyleSheet(
                    f"font-family:'JetBrains Mono',monospace; font-size:10px; "
                    f"color:{stack_color};"
                )
                sn_lbl.setWordWrap(True)
                r_l.addWidget(sn_lbl)

            b_l.addWidget(rcard)

            # ── 13×13 HAND MATRIX ────────────────────────────────────
            # Section label + colour legend
            mat_hdr = QHBoxLayout()
            mat_title = QLabel("RANGE MATRİSİ")
            mat_title.setStyleSheet(
                f"font-family:'JetBrains Mono',monospace; font-size:9px; "
                f"letter-spacing:2px; color:{_MUTED}; font-weight:700; "
                f"padding-top:4px; border-top:1px solid {_LINE2};"
            )
            mat_hdr.addWidget(mat_title)
            mat_hdr.addStretch(1)
            # Legend chips
            for col, label in [(_ACCENT, "Premium"), ("#5ad1ce", "Range içi"), ("#7c3aed", "Küçük pair"), (_BG2, "Dışı")]:
                chip = QLabel(label)
                chip.setStyleSheet(
                    f"font-family:'JetBrains Mono',monospace; font-size:8px; "
                    f"background:{col}; color:{'#0a0c0a' if col != _BG2 else _MUTED}; "
                    f"padding:2px 7px; border:1px solid #23271f; margin-left:4px;"
                )
                mat_hdr.addWidget(chip)
            b_l.addLayout(mat_hdr)

            matrix = _HandMatrixWidget()
            matrix.set_range(hands)
            # Highlight hero's hand if we can parse it (e.g. "9♣J♥" → "J9o")
            if hero_cards:
                _try_highlight_hero(matrix, hero_cards)
            b_l.addWidget(matrix)

            # Turnuva notu
            if game_type == "tournament" and tourney_note:
                tcard = _card()
                t_l = QVBoxLayout(tcard)
                t_l.setContentsMargins(14, 10, 14, 10)
                tlbl = QLabel("TURNUVA ICM NOTU")
                tlbl.setStyleSheet(
                    f"font-family:'JetBrains Mono',monospace; font-size:9px; "
                    f"letter-spacing:2px; color:{_WARN}; font-weight:700;"
                )
                tnote_lbl = QLabel(tourney_note)
                tnote_lbl.setStyleSheet(
                    f"font-family:'JetBrains Mono',monospace; font-size:11px; "
                    f"color:{_INK2};"
                )
                tnote_lbl.setWordWrap(True)
                t_l.addWidget(tlbl)
                t_l.addWidget(tnote_lbl)
                b_l.addWidget(tcard)

        # ── TÜM POZİSYONLAR ÖZET TABLOSU ────────────────────────────
        sep_lbl = QLabel("TÜM POZİSYONLAR — MEVCUT STACK")
        sep_lbl.setStyleSheet(
            f"font-family:'JetBrains Mono',monospace; font-size:9px; "
            f"letter-spacing:2px; color:{_MUTED}; font-weight:700; "
            f"padding-top:6px; border-top:1px solid {_LINE2};"
        )
        b_l.addWidget(sep_lbl)

        tbl = _card()
        tbl_l = QVBoxLayout(tbl)
        tbl_l.setContentsMargins(14, 10, 14, 10)
        tbl_l.setSpacing(4)

        for pos in ["UTG", "MP", "CO", "BTN", "SB", "BB"]:
            pct_t, hands_t, _, _ = _range_info(pos, stack_bb)
            row = QHBoxLayout()
            row.setSpacing(0)
            is_cur = pos == (position or "").upper()
            pos_c = _INFO if is_cur else _MUTED
            p_l = QLabel(pos)
            p_l.setFixedWidth(52)
            p_l.setStyleSheet(
                f"font-family:'JetBrains Mono',monospace; font-size:11px; "
                f"font-weight:{'700' if is_cur else '400'}; color:{pos_c};"
            )
            pct_l = QLabel(pct_t)
            pct_l.setFixedWidth(80)
            pct_l.setStyleSheet(
                f"font-family:'JetBrains Mono',monospace; font-size:11px; "
                f"font-weight:{'700' if is_cur else '400'}; color:{_ACCENT if is_cur else _INK2};"
            )
            h_l2 = QLabel(hands_t[:60] + ("…" if len(hands_t) > 60 else ""))
            h_l2.setStyleSheet(
                f"font-family:'JetBrains Mono',monospace; font-size:10px; color:{_MUTED};"
            )
            row.addWidget(p_l)
            row.addWidget(pct_l)
            row.addWidget(h_l2, 1)
            tbl_l.addLayout(row)

        b_l.addWidget(tbl)

        # ── SETUP modunda: range filtresi seçim iptali / açıklaması ─
        if game_type == "setup":
            self._add_setup_info(b_l, position, stack_bb)

        b_l.addStretch(1)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

    def _add_setup_info(self, layout, pos, stack_bb):
        infocard = _card()
        i_l = QVBoxLayout(infocard)
        i_l.setContentsMargins(14, 10, 14, 10)
        i_l.setSpacing(6)
        t = QLabel("RANGE FİLTRESİ NEDEN ÖNEMLİ?")
        t.setStyleSheet(
            f"font-family:'JetBrains Mono',monospace; font-size:9px; "
            f"letter-spacing:2px; color:{_INFO}; font-weight:700;"
        )
        d = QLabel(
            "Range filtresi seçersen o session boyunca sana sadece o range'den eller gelir. "
            "Bu sayede belirli ellerin nasıl oynanacağını tekrar tekrar drill yapabilirsin.\n\n"
            "• Premium Only: Karar ağırlıklı — nadir ama kritik eller\n"
            "• TAG Range: EP açılış kasları güçlendir\n"
            "• Speculative: Implied odds ve draw oyunlarını geliştir\n"
            "• Tüm Eller: GTO dağılım — gerçek oyun simülasyonu"
        )
        d.setStyleSheet(
            f"font-family:'JetBrains Mono',monospace; font-size:11px; "
            f"color:{_INK2}; line-height:1.6;"
        )
        d.setWordWrap(True)
        i_l.addWidget(t)
        i_l.addWidget(d)
        layout.addWidget(infocard)


def show_gto_dialog(
    parent=None,
    position: str = "",
    stack_bb: float = 100.0,
    players_active: int = 6,
    game_type: str = "cash",
    hero_cards: str = "",
    street: str = "preflop",
    pot_bb: float = 0.0,
    big_blind_bb: float = 1.0,
    level: str = "",
) -> None:
    """Convenience wrapper — oluştur, göster, işi bitince temizle."""
    dlg = GTORangeDialog(
        parent=parent,
        position=position,
        stack_bb=stack_bb,
        players_active=players_active,
        game_type=game_type,
        hero_cards=hero_cards,
        street=street,
        pot_bb=pot_bb,
        big_blind_bb=big_blind_bb,
        level=level,
    )
    dlg.exec()
