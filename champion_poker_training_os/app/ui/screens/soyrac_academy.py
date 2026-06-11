"""Soyrac Sistem Eğitimi — müfredat-tabanlı öğren→alıştır→ustalaş ekranı.

Tasarım: LXD+ID+UX workflow. Canlı Koç'tan farkı: oyun-DIŞI, kendi-hızında,
yapılandırılmış. GRADER = soyrac_curriculum/soyrac_explain (mock YOK). İlerleme
QSettings'te kalıcı. soyrac_advice/bot DEĞİŞMEZ.
"""
from __future__ import annotations

import random

from PySide6.QtCore import Qt, Signal, QSettings, QByteArray
from PySide6.QtGui import QPixmap, QPainter
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QScrollArea, QStackedWidget, QSizePolicy,
)

from app.poker.soyrac_curriculum import (
    MODULES, module_list, make_drill, grade_drill, compute_badge, belt, _norm_action)

_QSS = """
#AcademyRoot { background:#0c1410; }
#AcademyTitle { color:#7fd4ff; font-size:20px; font-weight:800; }
#AcademyBelt { color:#d4a72c; font-size:13px; font-weight:700; }
#ModRail { background:#0f1b16; border:1px solid #1c3329; border-radius:10px; }
#ModBtn { background:#10221b; color:#c8d0cc; border:1px solid #1c3329; border-radius:8px;
          text-align:left; padding:8px 10px; font-size:12px; }
#ModBtn:hover { background:#16302575; border:1px solid #2f7d5c; }
#ModBtn[active="true"] { background:#163025; border:1px solid #3fb97a; color:#e9f3ef; }
#ModBtn[locked="true"] { color:#5a6b62; }
#Card { background:#0f1b16; border:1px solid #1c3329; border-radius:10px; }
#LessonTitle { color:#e9f3ef; font-size:17px; font-weight:800; }
#Analogy { color:#d4a72c; font-size:12px; font-style:italic; }
#Bullet { color:#c2ccc6; font-size:12px; }
#WorkedHead { color:#7fd4ff; font-size:12px; font-weight:700; }
#ChainLine { color:#a9b7af; font-size:11px; }
#PrimaryBtn { background:#1d6e4a; color:#eafff4; border:none; border-radius:8px;
              padding:9px 16px; font-size:13px; font-weight:700; }
#PrimaryBtn:hover { background:#258a5c; }
#DrillHand { font-family:'JetBrains Mono',monospace; font-size:26px; font-weight:800; color:#e9f3ef; }
#DrillCtx { color:#7fd4ff; font-size:12px; }
#AnsBtn { background:#13261e; color:#dfe7e2; border:1px solid #2a4a3a; border-radius:8px;
          padding:12px; font-size:14px; font-weight:700; }
#AnsBtn:hover { background:#1b3a2c; border:1px solid #3fb97a; }
#FbCorrect { color:#3fb950; font-size:14px; font-weight:800; }
#FbWrong { color:#e0594f; font-size:14px; font-weight:800; }
#FbWhy { color:#c2ccc6; font-size:12px; }
#FbChain { color:#9aa49c; font-size:11px; }
#ProgHead { color:#7fd4ff; font-size:12px; font-weight:700; }
#ProgRow { color:#c2ccc6; font-size:11px; }
#MetricBig { color:#e9f3ef; font-size:15px; font-weight:800; }
"""


def _fig_pixmap(fig_key, w=300):
    """FIGS SVG'sini pixmap'e çevir (QtSvg.QSvgRenderer); yoksa None."""
    try:
        from tools.build_soyrac_pdf import FIGS
        from PySide6.QtSvg import QSvgRenderer
        fn = FIGS.get(fig_key)
        if not fn:
            return None
        svg = fn()
        r = QSvgRenderer(QByteArray(svg.encode("utf-8")))
        sz = r.defaultSize()
        vw, vh = sz.width(), sz.height()
        if vw <= 0:                       # viewBox-only SVG → boyutu viewBox'tan al
            import re
            mb = re.search(r'viewBox="[\d.]+ [\d.]+ ([\d.]+) ([\d.]+)"', svg)
            if mb:
                vw, vh = float(mb.group(1)), float(mb.group(2))
        if vw <= 0:
            return None
        h = max(1, int(w * vh / vw))
        pm = QPixmap(w, h); pm.fill(Qt.transparent)
        p = QPainter(pm); r.render(p); p.end()
        return pm
    except Exception:
        return None


class SoyracAcademyScreen(QWidget):
    coach_message = Signal(str)

    def __init__(self, state=None):
        super().__init__()
        self.state = state
        self.setObjectName("AcademyRoot")
        self.setStyleSheet(_QSS)
        self._st = QSettings("Champion", "PokerOS")
        self._cur = "M0"
        self._drill = None
        self._answered = False
        self._mod_btns = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14); root.setSpacing(12)

        # HEADER
        head = QHBoxLayout()
        t = QLabel("🎓 Soyrac Sistem Eğitimi"); t.setObjectName("AcademyTitle")
        head.addWidget(t)
        head.addStretch(1)
        self.belt_lbl = QLabel(""); self.belt_lbl.setObjectName("AcademyBelt")
        head.addWidget(self.belt_lbl)
        root.addLayout(head)

        body = QHBoxLayout(); body.setSpacing(12)

        # SOL: müfredat rail
        rail = QFrame(); rail.setObjectName("ModRail"); rail.setFixedWidth(232)
        rv = QVBoxLayout(rail); rv.setContentsMargins(10, 12, 10, 12); rv.setSpacing(6)
        rv.addWidget(self._h("MÜFREDAT"))
        for m in module_list():
            b = QPushButton(); b.setObjectName("ModBtn"); b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=m["key"]: self._select(k))
            rv.addWidget(b); self._mod_btns[m["key"]] = b
        rv.addStretch(1)
        body.addWidget(rail)

        # ORTA: sahne (öğren / alıştır)
        self.stage = QStackedWidget()
        self.stage.addWidget(self._build_learn())   # idx 0
        self.stage.addWidget(self._build_drill())   # idx 1
        body.addWidget(self.stage, 1)

        # SAĞ: ilerleme
        prog = QFrame(); prog.setObjectName("Card"); prog.setFixedWidth(232)
        self.prog_v = QVBoxLayout(prog); self.prog_v.setContentsMargins(12, 12, 12, 12)
        self.prog_v.setSpacing(6)
        self.prog_v.addWidget(self._h("USTALIK"))
        self._prog_rows = []
        body.addWidget(prog)

        root.addLayout(body, 1)
        self._refresh_rail()
        self._select("M0")

    # ── yardımcı başlık ──
    def _h(self, txt):
        l = QLabel(txt); l.setObjectName("ProgHead"); return l

    # ── ÖĞREN görünümü ──
    def _build_learn(self):
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(10)
        card = QFrame(); card.setObjectName("Card")
        cv = QVBoxLayout(card); cv.setContentsMargins(16, 14, 16, 16); cv.setSpacing(8)
        self.learn_title = QLabel(""); self.learn_title.setObjectName("LessonTitle")
        self.learn_title.setWordWrap(True); cv.addWidget(self.learn_title)
        self.learn_analogy = QLabel(""); self.learn_analogy.setObjectName("Analogy")
        self.learn_analogy.setWordWrap(True); cv.addWidget(self.learn_analogy)
        self.learn_fig = QLabel(); self.learn_fig.setAlignment(Qt.AlignCenter)
        cv.addWidget(self.learn_fig)
        self.learn_bullets = QVBoxLayout(); self.learn_bullets.setSpacing(4)
        cv.addLayout(self.learn_bullets)
        # worked example
        cv.addWidget(self._wsep())
        self.worked_head = QLabel("💡 Örnek (canlı motordan)"); self.worked_head.setObjectName("WorkedHead")
        cv.addWidget(self.worked_head)
        self.worked_chain = QVBoxLayout(); self.worked_chain.setSpacing(3)
        cv.addLayout(self.worked_chain)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(card)
        v.addWidget(scroll, 1)
        self.start_drill_btn = QPushButton("Hazırım → Alıştır 🎯"); self.start_drill_btn.setObjectName("PrimaryBtn")
        self.start_drill_btn.setCursor(Qt.PointingHandCursor)
        self.start_drill_btn.clicked.connect(lambda: self._start_drill())
        v.addWidget(self.start_drill_btn, 0, Qt.AlignRight)
        return w

    def _wsep(self):
        s = QFrame(); s.setFrameShape(QFrame.HLine)
        s.setStyleSheet("color:#1c3329; background:#1c3329; max-height:1px;"); return s

    # ── ALIŞTIR görünümü ──
    def _build_drill(self):
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(10)
        card = QFrame(); card.setObjectName("Card")
        cv = QVBoxLayout(card); cv.setContentsMargins(16, 16, 16, 16); cv.setSpacing(10)
        top = QHBoxLayout()
        self.drill_mod = QLabel(""); self.drill_mod.setObjectName("DrillCtx"); top.addWidget(self.drill_mod)
        top.addStretch(1)
        self.drill_score = QLabel(""); self.drill_score.setObjectName("DrillCtx"); top.addWidget(self.drill_score)
        cv.addLayout(top)
        self.drill_hand = QLabel("—"); self.drill_hand.setObjectName("DrillHand")
        self.drill_hand.setAlignment(Qt.AlignCenter); cv.addWidget(self.drill_hand)
        self.drill_ctx = QLabel(""); self.drill_ctx.setObjectName("DrillCtx")
        self.drill_ctx.setAlignment(Qt.AlignCenter); self.drill_ctx.setWordWrap(True); cv.addWidget(self.drill_ctx)
        ans = QHBoxLayout(); ans.setSpacing(8)
        self.ans_btns = {}
        for key, txt in [("FOLD", "FOLD"), ("CALL", "CALL / CHECK"), ("RAISE", "RAISE / BET")]:
            b = QPushButton(txt); b.setObjectName("AnsBtn"); b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self._answer(k))
            ans.addWidget(b, 1); self.ans_btns[key] = b
        cv.addLayout(ans)
        # feedback
        self.fb = QFrame(); self.fb.setObjectName("Card")
        fbv = QVBoxLayout(self.fb); fbv.setContentsMargins(12, 10, 12, 10); fbv.setSpacing(5)
        self.fb_verdict = QLabel(""); self.fb_verdict.setObjectName("FbCorrect")
        self.fb_verdict.setWordWrap(True); fbv.addWidget(self.fb_verdict)
        self.fb_why = QLabel(""); self.fb_why.setObjectName("FbWhy"); self.fb_why.setWordWrap(True); fbv.addWidget(self.fb_why)
        self.fb_chain = QVBoxLayout(); self.fb_chain.setSpacing(2); fbv.addLayout(self.fb_chain)
        self.next_btn = QPushButton("Sonraki →"); self.next_btn.setObjectName("PrimaryBtn")
        self.next_btn.setCursor(Qt.PointingHandCursor); self.next_btn.clicked.connect(lambda: self._start_drill())
        fbv.addWidget(self.next_btn, 0, Qt.AlignRight)
        cv.addWidget(self.fb)
        cv.addStretch(1)
        v.addWidget(card, 1)
        back = QPushButton("← Derse dön"); back.setObjectName("ModBtn"); back.setCursor(Qt.PointingHandCursor)
        back.clicked.connect(lambda: self.stage.setCurrentIndex(0))
        v.addWidget(back, 0, Qt.AlignLeft)
        return w

    # ── modül seç → öğren ──
    def _select(self, mk):
        self._cur = mk
        m = MODULES[mk]
        for k, b in self._mod_btns.items():
            b.setProperty("active", "true" if k == mk else "false")
            b.style().unpolish(b); b.style().polish(b)
        self.learn_title.setText(m["title"])
        self.learn_analogy.setText("🔗 " + m["analogy"])
        pm = _fig_pixmap(m["fig_key"], 300)
        if pm:
            self.learn_fig.setPixmap(pm); self.learn_fig.show()
        else:
            self.learn_fig.hide()
        self._clear(self.learn_bullets)
        for bl in m["learn_bullets"]:
            l = QLabel("• " + bl); l.setObjectName("Bullet"); l.setWordWrap(True)
            self.learn_bullets.addWidget(l)
        # worked example (gerçek motordan)
        self._clear(self.worked_chain)
        if m["scenario"]:
            d = make_drill(mk, difficulty=1, rng=random.Random(hash(mk) & 0xffff))
            if d:
                head = f"{d.hand_key} · {d.scenario}"
                if d.vs_position:
                    head += f" · {d.vs_position} açtı"
                hl = QLabel(f"Örnek el: {head} → {d.correct}"); hl.setObjectName("ChainLine")
                hl.setWordWrap(True); self.worked_chain.addWidget(hl)
                for s in d.explain.get("chain_steps", []):
                    cl = QLabel("  " + s); cl.setObjectName("ChainLine"); cl.setWordWrap(True)
                    self.worked_chain.addWidget(cl)
            self.start_drill_btn.show()
            self.worked_head.show()
        else:
            self.start_drill_btn.hide()
            self.worked_head.hide()
        self.stage.setCurrentIndex(0)

    # ── drill başlat ──
    def _start_drill(self):
        m = MODULES[self._cur]
        if not m["scenario"]:
            return
        diff = self._st.value(f"academy/{self._cur}/best_streak", 0, int)
        difficulty = 1 if diff < 4 else (2 if diff < 8 else 3)
        self._drill = make_drill(self._cur, difficulty=difficulty)
        self._answered = False
        d = self._drill
        self.drill_mod.setText(f"{m['title']} · zorluk {difficulty}")
        self.drill_hand.setText(d.hand_key)
        ctx = f"{d.scenario}"
        if d.position:
            ctx += f" · {d.position}"
        if d.vs_position:
            ctx += f" · {d.vs_position} açtı"
        if d.board:
            ctx += " · board: " + " ".join(c.display for c in d.board)
        if d.tourney:
            ctx += f" · TURNUVA {d.stack_bb:.0f}bb"
        self.drill_ctx.setText(ctx)
        att, cor = self._stat()
        self.drill_score.setText(f"{cor}/{att} doğru")
        self.fb.setVisible(False)
        for b in self.ans_btns.values():
            b.setEnabled(True)
        self.stage.setCurrentIndex(1)

    # ── cevap ──
    def _answer(self, action):
        if self._answered or not self._drill:
            return
        self._answered = True
        res = grade_drill(self._drill, action)
        for b in self.ans_btns.values():
            b.setEnabled(False)
        # ilerleme persist
        pre = f"academy/{self._cur}"
        att = self._st.value(pre + "/attempts", 0, int) + 1
        cor = self._st.value(pre + "/correct", 0, int) + (1 if res.is_correct else 0)
        streak = (self._st.value(pre + "/streak", 0, int) + 1) if res.is_correct else 0
        best = max(self._st.value(pre + "/best_streak", 0, int), streak)
        self._st.setValue(pre + "/attempts", att); self._st.setValue(pre + "/correct", cor)
        self._st.setValue(pre + "/streak", streak); self._st.setValue(pre + "/best_streak", best)
        acc = cor / max(att, 1)
        badge = compute_badge(acc, best, MODULES[self._cur])
        if badge:
            self._st.setValue(pre + "/badge", badge)
        # feedback göster
        self.fb.setVisible(True)
        if res.is_correct:
            self.fb_verdict.setObjectName("FbCorrect")
            self.fb_verdict.setText(f"✅ Doğru! Soyrac da {res.correct_action} derdi.")
        else:
            self.fb_verdict.setObjectName("FbWrong")
            txt = f"❌ Sen {res.user_action} · Soyrac {res.correct_action}"
            if res.leak_category:
                txt += f"\n📌 {res.leak_category}"
            self.fb_verdict.setText(txt)
        self.fb_verdict.style().unpolish(self.fb_verdict); self.fb_verdict.style().polish(self.fb_verdict)
        self.fb_why.setText(res.why)
        self._clear(self.fb_chain)
        for s in res.chain_steps:
            cl = QLabel("• " + s); cl.setObjectName("FbChain"); cl.setWordWrap(True)
            self.fb_chain.addWidget(cl)
        self.drill_score.setText(f"{cor}/{att} doğru · streak {streak}")
        if res.leak_category:
            self.coach_message.emit(f"📌 Soyrac dersi: {res.leak_category}")
        self._refresh_rail()

    # ── rail + ilerleme tazele ──
    def _refresh_rail(self):
        badges = []
        for m in module_list():
            mk = m["key"]
            pre = f"academy/{mk}"
            att = self._st.value(pre + "/attempts", 0, int)
            cor = self._st.value(pre + "/correct", 0, int)
            badge = self._st.value(pre + "/badge", "")
            badges.append(badge)
            acc = int(100 * cor / att) if att else 0
            b = self._mod_btns[mk]
            tag = f"  %{acc}" if att else ""
            b.setText(f"{badge or '○'} {mk} · {m['title']}{tag}")
        self.belt_lbl.setText(belt(badges))
        # sağ panel
        self._clear_widgets(self._prog_rows)
        self._prog_rows = []
        for m in module_list():
            mk = m["key"]; pre = f"academy/{mk}"
            att = self._st.value(pre + "/attempts", 0, int)
            cor = self._st.value(pre + "/correct", 0, int)
            badge = self._st.value(pre + "/badge", "")
            acc = int(100 * cor / att) if att else 0
            row = QLabel(f"{badge or '○'} {mk}  %{acc}" + (f" ({att})" if att else ""))
            row.setObjectName("ProgRow")
            self.prog_v.addWidget(row); self._prog_rows.append(row)

    def _stat(self):
        pre = f"academy/{self._cur}"
        return self._st.value(pre + "/attempts", 0, int), self._st.value(pre + "/correct", 0, int)

    def _clear(self, layout):
        while layout.count():
            it = layout.takeAt(0)
            if it.widget():
                it.widget().setParent(None)

    def _clear_widgets(self, rows):
        for w in rows:
            w.setParent(None)
