"""Soyrac Canlı Koç paneli — kullanıcı OYNARKEN 'nasıl düşün' öğretir.

Tasarım: LXD + Instructional Design + UI/UX workflow spec'i. SAF öğretici;
soyrac_advice/bot kararı/grading'i DEĞİŞTİRMEZ (panel sadece soyrac_explain
çıktısını OKUR). CoachPanel (Gemini) ayrı, dokunulmaz.

3 mod: HINT (karar öncesi öneri+neden) / QUIZ (önce sen, sonra reveal+ders) /
SILENT (sadece el-sonu review). Toggle ⌘K ile aç/kapa (QSettings'te kalıcı).
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QTimer, QSettings
from PySide6.QtGui import QPainter, QColor, QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QComboBox,
    QProgressBar, QSizePolicy,
)

# tone → renk (go=yeşil / caution=amber / stop=kırmızı)
_TONE = {"go": "#3fb950", "caution": "#d4a72c", "stop": "#e0594f", "hidden": "#8a948c"}

_QSS = """
#SoyracPanel { background:#0c1a22; border-left:1px solid #15323f; }
#SoyracHeader { background:#0f2531; border-bottom:1px solid #15323f; }
#SectionTitle { color:#7fd4ff; font-weight:700; font-size:13px; }
#PaneToggle { background:#15323f; color:#7fd4ff; border:none; border-radius:6px; font-size:13px; }
#PaneToggle:hover { background:#1d4456; }
#SoyracMode { background:#10222c; color:#c8d0cc; border:1px solid #1d4456; border-radius:6px; padding:2px 6px; }
#SoyracVerdict { background:#0f1f28; border:1px solid #15323f; border-radius:8px; }
#SoyracScoreBadge { font-family:'JetBrains Mono',monospace; font-size:20px; font-weight:700; color:#e9f3ef; }
#SoyracScenarioChip { color:#7fd4ff; font-size:10px; }
#SoyracDecision { font-size:18px; font-weight:800; }
#SoyracDecision[tone="go"] { color:#3fb950; }
#SoyracDecision[tone="caution"] { color:#d4a72c; }
#SoyracDecision[tone="stop"] { color:#e0594f; }
#SoyracDecision[tone="hidden"] { color:#8a948c; }
#SoyracReason { color:#9aa49c; font-size:11px; }
#SoyracExpander { background:transparent; color:#7fd4ff; border:none; text-align:left; font-size:11px; }
#SoyracExpander:hover { color:#a9e4ff; }
#SoyracChain { background:#0a1820; border:1px solid #142a35; border-radius:6px; }
#SoyracChainLine { color:#c2ccc6; font-size:11px; }
#SoyracSysmap { background:#0a1612; border:1px solid #16302a; border-radius:6px; }
#SysHead { color:#9fe8c4; font-size:11px; font-weight:700; }
#SysLine { color:#9aa49c; font-size:11px; }
#SysCur { color:#e9f3ef; font-size:11px; font-weight:700; background:#16302575;
          border-radius:4px; padding:1px 4px; }
#SoyracFlowNode { background:#10222c; border:1px solid #1d4456; border-radius:6px;
                  color:#9aa49c; font-size:10px; padding:3px 6px; }
#SoyracFlowNode[active="true"] { background:#15323f; color:#e9f3ef; border:1px solid #2f7d9c; }
#SoyracFlowArrow { color:#5a6b64; font-size:12px; }
#SoyracReview { background:#0f1f28; border:1px solid #15323f; border-radius:8px; }
#SoyracReviewTitle { color:#7fd4ff; font-weight:700; font-size:11px; }
#SoyracReviewLine { color:#c2ccc6; font-size:11px; }
#SoyracReviewWarn { color:#e0d070; font-size:11px; }
#SoyracLeakLink { background:transparent; color:#d4a72c; border:none; text-align:left; font-size:11px; }
#SoyracLeakLink:hover { color:#f0c860; }
#SoyracFlash { border-radius:8px; }
#SoyracFlash[flash="go"] { background:rgba(63,185,80,0.18); }
#SoyracFlash[flash="stop"] { background:rgba(224,89,79,0.18); }
"""


class _ThreshBar(QProgressBar):
    """SHCP skorunu 0..40 ölçekte gösterir; eşik(ler)i dikey çizgiyle işaretler."""
    def __init__(self):
        super().__init__()
        self.setObjectName("SoyracThreshBar")
        self.setRange(0, 40)
        self.setTextVisible(True)
        self.setFixedHeight(18)
        self._marks = []          # [(value, color)]
        self._tone = "go"

    def set_state(self, score, marks, tone):
        self._marks = marks or []
        self._tone = tone
        self.setValue(max(0, min(40, score or 0)))
        self.setStyleSheet(
            "#SoyracThreshBar{background:#0a1820;border:1px solid #1d4456;border-radius:4px;"
            "text-align:center;color:#c8d0cc;font-size:9px;}"
            f"#SoyracThreshBar::chunk{{background:{_TONE.get(tone,'#3fb950')};border-radius:3px;}}")

    def paintEvent(self, ev):
        super().paintEvent(ev)
        if not self._marks:
            return
        p = QPainter(self)
        w, h = self.width(), self.height()
        for val, col in self._marks:
            x = int(w * max(0, min(40, val)) / 40)
            p.setPen(QColor(col))
            p.drawLine(x, 1, x, h - 1)
        p.end()


class SoyracCoachPanel(QFrame):
    """Canlı koç paneli. Ekran şu sinyalleri bağlar: study_leak (Leak Finder'a)."""
    study_leak = Signal(str)

    EXPANDED_WIDTH = 340
    COLLAPSED_WIDTH = 44
    MODES = ["hint", "quiz", "silent"]

    def __init__(self):
        super().__init__()
        self.setObjectName("SoyracPanel")
        self.setStyleSheet(_QSS)
        self.setFixedWidth(self.EXPANDED_WIDTH)
        self._collapsed = False
        self._last_explain = None
        self._review_rows = []
        self._st = QSettings("Champion", "PokerOS")
        self._mode = self._st.value("soyrac/coach_mode", "hint")
        if self._mode not in self.MODES:
            self._mode = "hint"
        self._chain_open = self._st.value("soyrac/chain_expanded", "false") == "true"

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # [A] HEADER
        self.header = QFrame(); self.header.setObjectName("SoyracHeader")
        hb = QHBoxLayout(self.header); hb.setContentsMargins(8, 6, 8, 6); hb.setSpacing(6)
        self.toggle_btn = QPushButton("◀"); self.toggle_btn.setObjectName("PaneToggle")
        self.toggle_btn.setFixedSize(26, 26); self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.setToolTip("Koçu daralt/aç (⌘K)")
        self.toggle_btn.clicked.connect(self.toggle_collapsed)
        hb.addWidget(self.toggle_btn)
        self.title = QLabel("🧮 SOYRAC KOÇ"); self.title.setObjectName("SectionTitle")
        hb.addWidget(self.title, 1)
        self.mode_combo = QComboBox(); self.mode_combo.setObjectName("SoyracMode")
        self.mode_combo.addItems(["💡 Canlı İpucu", "🎯 Quiz", "🔇 Sessiz"])
        self.mode_combo.setCurrentIndex(self.MODES.index(self._mode))
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        hb.addWidget(self.mode_combo)
        root.addWidget(self.header)

        body = QVBoxLayout(); body.setContentsMargins(10, 10, 10, 10); body.setSpacing(8)

        # [B] VERDICT (flash sarmalı)
        self.flash = QFrame(); self.flash.setObjectName("SoyracFlash")
        fl = QVBoxLayout(self.flash); fl.setContentsMargins(2, 2, 2, 2); fl.setSpacing(0)
        self.verdict = QFrame(); self.verdict.setObjectName("SoyracVerdict")
        vb = QVBoxLayout(self.verdict); vb.setContentsMargins(10, 8, 10, 8); vb.setSpacing(5)
        row1 = QHBoxLayout(); row1.setSpacing(8)
        self.score_badge = QLabel("SHCP —"); self.score_badge.setObjectName("SoyracScoreBadge")
        row1.addWidget(self.score_badge)
        self.scenario_chip = QLabel(""); self.scenario_chip.setObjectName("SoyracScenarioChip")
        self.scenario_chip.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row1.addWidget(self.scenario_chip, 1)
        vb.addLayout(row1)
        self.thresh_bar = _ThreshBar(); vb.addWidget(self.thresh_bar)
        # True-count tarzı eşik kırılımı (D194): 'baz 15 · ICM +1 · sığ +2 → efektif 18'
        self.count_lbl = QLabel(""); self.count_lbl.setObjectName("SoyracCount")
        self.count_lbl.setWordWrap(True)
        self.count_lbl.setStyleSheet("color:#7fd4ff; font-size:11px; padding:1px 0 3px 0;")
        self.count_lbl.setVisible(False); vb.addWidget(self.count_lbl)
        self.decision_lbl = QLabel("—"); self.decision_lbl.setObjectName("SoyracDecision")
        vb.addWidget(self.decision_lbl)
        self.reason_lbl = QLabel(""); self.reason_lbl.setObjectName("SoyracReason")
        self.reason_lbl.setWordWrap(True); vb.addWidget(self.reason_lbl)
        fl.addWidget(self.verdict)
        body.addWidget(self.flash)

        # [C] EXPANDER + CHAIN
        self.expander = QPushButton("▾ Nasıl düşünmeliyim?"); self.expander.setObjectName("SoyracExpander")
        self.expander.setCursor(Qt.PointingHandCursor); self.expander.clicked.connect(self._toggle_chain)
        body.addWidget(self.expander)
        self.chain = QFrame(); self.chain.setObjectName("SoyracChain")
        self.chain_v = QVBoxLayout(self.chain); self.chain_v.setContentsMargins(8, 6, 8, 6)
        self.chain_v.setSpacing(3)
        body.addWidget(self.chain)

        # [C2] SİSTEM HARİTASI — tüm sistemi öğret + şu an hangi dalda olduğunu göster
        self.sys_btn = QPushButton("📚 Sistem nasıl çalışır?")
        self.sys_btn.setObjectName("SoyracExpander"); self.sys_btn.setCursor(Qt.PointingHandCursor)
        self.sys_btn.clicked.connect(self._toggle_sysmap)
        body.addWidget(self.sys_btn)
        self.sysmap = QFrame(); self.sysmap.setObjectName("SoyracSysmap")
        self.sysmap_v = QVBoxLayout(self.sysmap); self.sysmap_v.setContentsMargins(8, 6, 8, 6)
        self.sysmap_v.setSpacing(3)
        body.addWidget(self.sysmap)

        # [D] FLOW (postflop)
        self.flow = QFrame(); self.flow.setObjectName("SoyracFlow")
        self.flow_h = QHBoxLayout(self.flow); self.flow_h.setContentsMargins(2, 2, 2, 2)
        self.flow_h.setSpacing(4)
        body.addWidget(self.flow)

        body.addStretch(1)

        # [E] REVIEW (el-sonu)
        self.review = QFrame(); self.review.setObjectName("SoyracReview")
        self.review_v = QVBoxLayout(self.review); self.review_v.setContentsMargins(10, 8, 10, 8)
        self.review_v.setSpacing(4)
        self.review_title = QLabel("EL ÖZETİ · SOYRAC GÖZÜYLE"); self.review_title.setObjectName("SoyracReviewTitle")
        self.review_v.addWidget(self.review_title)
        body.addWidget(self.review)

        self.body_w = QFrame(); self.body_w.setLayout(body)
        self.body_w.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        root.addWidget(self.body_w, 1)

        QShortcut(QKeySequence("Ctrl+K"), self, activated=self.toggle_collapsed)
        QShortcut(QKeySequence("Meta+K"), self, activated=self.toggle_collapsed)

        self._apply_chain_visibility()
        self._sysmap_open = False
        self.chain.setVisible(False)
        self.sysmap.setVisible(False)
        self.flow.setVisible(False)
        self.review.setVisible(False)
        # İlk açılış nötr durumu (boş "SHCP —" + beyaz çubuk göstermesin)
        self.thresh_bar.setVisible(False)
        self.score_badge.setText("🧮 Hazır")
        self.decision_lbl.setText("El bekleniyor…")
        self._set_tone(self.decision_lbl, "hidden")
        self._sync_mode_ui()

    # ════ MOD ════
    def _on_mode_changed(self, idx):
        self._mode = self.MODES[idx] if 0 <= idx < 3 else "hint"
        self._st.setValue("soyrac/coach_mode", self._mode)
        self._sync_mode_ui()
        if self._last_explain:
            self.on_decision_point(self._last_explain)

    def _sync_mode_ui(self):
        silent = self._mode == "silent"
        self.flash.setVisible(not silent)
        self.expander.setVisible(not silent)
        self.sys_btn.setVisible(not silent)
        if silent:
            self.chain.setVisible(False)
            self.sysmap.setVisible(False)

    # ════ TETİK 1: karar anı ════
    def on_decision_point(self, explain: dict):
        """soyrac_explain çıktısını render et (HINT: tam / QUIZ: maskeli / SILENT: gizli)."""
        self._last_explain = explain
        self.review.setVisible(False)
        self._clear_flash()
        if not explain or self._mode == "silent":
            return
        # review'dan dönüşte üst verdict'i geri göster
        self.flash.setVisible(True)
        self.expander.setVisible(True)
        self.sys_btn.setVisible(True)
        if self._sysmap_open:
            self._render_sysmap(explain); self.sysmap.setVisible(True)
        score = explain.get("score")
        self.score_badge.setText(f"SHCP {score}" if score is not None else explain.get("tier", "—"))
        self.scenario_chip.setText(explain.get("scenario_label", ""))
        # eşik çubuğu
        marks = []
        thr = explain.get("threshold")
        if thr is not None:
            marks.append((thr, "#7fd4ff"))
        if explain.get("call_t") is not None:
            marks.append((explain["call_t"], "#d4a72c"))
        if explain.get("raise_t") is not None:
            marks.append((explain["raise_t"], "#3fb950"))
        tone = explain.get("tone", "go")
        self.thresh_bar.setVisible(score is not None)
        if score is not None:
            self.thresh_bar.set_state(score, marks, tone)
            self.thresh_bar.setFormat(f"%v / 40")

        quiz = self._mode == "quiz"
        # True-count eşik kırılımı — RFI'de + quiz değilse (cevabı sızdırmasın)
        cl = explain.get("count_line", "")
        bd = explain.get("threshold_breakdown") or {}
        show_count = bool(cl) and not quiz and any(
            bd.get(k) for k in ("icm_adj", "deep_adj", "tourney_adj", "table_adj"))
        self.count_lbl.setVisible(show_count)
        if show_count:
            self.count_lbl.setText("🎲 " + cl)

        if quiz:
            self.decision_lbl.setText("?  (sen ne yapardın?)")
            self._set_tone(self.decision_lbl, "hidden")
            self.reason_lbl.setText("Karar ver — sonra Soyrac'ın cevabını göstereceğim.")
            self.chain.setVisible(False)
        else:
            self.decision_lbl.setText(explain.get("action", "—"))
            self._set_tone(self.decision_lbl, tone)
            self.reason_lbl.setText(explain.get("why", ""))
            if self._chain_open:
                self._render_chain(explain)
                self.chain.setVisible(True)
        self._render_flow(explain if not quiz else None)

    # ════ TETİK 2: hero aksiyon verdi ════
    def on_hero_acted(self, hero_action: str, snap=None):
        """Aksiyon sonrası: HINT'te flash, QUIZ'de reveal+ders, leak kaydı."""
        from app.poker.soyrac_advisor import soyrac_leak_category
        exp = self._last_explain
        if not exp or self._mode == "silent":
            return
        leak = soyrac_leak_category(exp, hero_action)
        if self._mode == "quiz":                       # REVEAL
            self.decision_lbl.setText(exp.get("action", "—"))
            self._set_tone(self.decision_lbl, exp.get("tone", "go"))
            if leak:
                self.reason_lbl.setText(f"⚠ {leak}")
                self._render_chain(exp); self.chain.setVisible(True)
                self.study_leak.emit(leak)
            else:
                self.reason_lbl.setText("✅ Soyrac ile aynı! " + exp.get("why", ""))
            self._render_flow(exp)
        else:                                          # HINT flash
            self._flash("stop" if leak else "go")
            if leak:
                self.study_leak.emit(leak)
        if leak and snap is not None:
            self._record_leak(leak)

    # ════ TETİK 3: el bitti ════
    def on_hand_complete(self, decisions=None, summary=None):
        """El-sonu mini-review: Sen ↔ Soyrac + ders."""
        # eski satırları temizle
        for w in self._review_rows:
            w.setParent(None)
        self._review_rows = []
        rows = decisions or []
        if not rows:
            self.review.setVisible(False)
            return
        aligned = 0
        worst = None
        for d in rows:
            street = d.get("street", "")
            you = d.get("hero", "—")
            soy = d.get("soyrac", "—")
            grade = d.get("grade", "")
            ok = d.get("aligned", you == soy)
            aligned += 1 if ok else 0
            mark = "✓" if ok else "✗"
            lbl = QLabel(f"{street}: Sen {you} {mark} Soyrac {soy}" + (f" · {grade}" if grade else ""))
            lbl.setObjectName("SoyracReviewLine"); lbl.setWordWrap(True)
            self.review_v.addWidget(lbl); self._review_rows.append(lbl)
            if not ok and d.get("lesson") and worst is None:
                worst = d["lesson"]
        summ = QLabel(f"{aligned}/{len(rows)} kararın Soyrac çizgisinde.")
        summ.setObjectName("SoyracReviewLine"); self.review_v.addWidget(summ)
        self._review_rows.append(summ)
        if worst:
            warn = QLabel(f"⚠ {worst}"); warn.setObjectName("SoyracReviewWarn"); warn.setWordWrap(True)
            self.review_v.addWidget(warn); self._review_rows.append(warn)
            link = QPushButton("Bu leak'i çalış →"); link.setObjectName("SoyracLeakLink")
            link.setCursor(Qt.PointingHandCursor)
            link.clicked.connect(lambda: self.study_leak.emit(worst))
            self.review_v.addWidget(link); self._review_rows.append(link)
        # review odakta: üstteki karar-anı verdict'ini gizle (boş kart görünmesin)
        self.flash.setVisible(False)
        self.expander.setVisible(False)
        self.sys_btn.setVisible(False)
        self.sysmap.setVisible(False)
        self.chain.setVisible(False)
        self.flow.setVisible(False)
        self.review.setVisible(True)

    # ════ yardımcılar ════
    def _render_chain(self, explain):
        while self.chain_v.count():
            it = self.chain_v.takeAt(0)
            if it.widget():
                it.widget().setParent(None)
        for step in explain.get("chain_steps", []):
            lbl = QLabel(f"• {step}"); lbl.setObjectName("SoyracChainLine"); lbl.setWordWrap(True)
            self.chain_v.addWidget(lbl)

    def _render_flow(self, explain):
        while self.flow_h.count():
            it = self.flow_h.takeAt(0)
            if it.widget():
                it.widget().setParent(None)
        nodes = (explain or {}).get("flow_nodes") if explain else None
        if not nodes:
            self.flow.setVisible(False)
            return
        for i, (label, value, active) in enumerate(nodes):
            node = QLabel(f"{label}: {value}"); node.setObjectName("SoyracFlowNode")
            node.setProperty("active", "true" if active else "false")
            self.flow_h.addWidget(node)
            if i < len(nodes) - 1:
                arr = QLabel("→"); arr.setObjectName("SoyracFlowArrow")
                self.flow_h.addWidget(arr)
        self.flow.setVisible(True)

    def _toggle_chain(self):
        self._chain_open = not self.chain.isVisible()
        if self._chain_open and self._last_explain:
            self._render_chain(self._last_explain)
        self.chain.setVisible(self._chain_open)
        self._st.setValue("soyrac/chain_expanded", "true" if self._chain_open else "false")

    def _toggle_sysmap(self):
        self._sysmap_open = not self.sysmap.isVisible()
        if self._sysmap_open:
            self._render_sysmap(self._last_explain)
        self.sysmap.setVisible(self._sysmap_open)
        self.sys_btn.setText("▴ Sistemi gizle" if self._sysmap_open else "📚 Sistem nasıl çalışır?")

    def _render_sysmap(self, explain):
        while self.sysmap_v.count():
            it = self.sysmap_v.takeAt(0)
            if it.widget():
                it.widget().setParent(None)
        scn = str((explain or {}).get("scenario", "")).lower()
        phase = (explain or {}).get("phase", "preflop")

        def head(t):
            l = QLabel(t); l.setObjectName("SysHead"); l.setWordWrap(True); self.sysmap_v.addWidget(l)

        def line(t, cur=False):
            l = QLabel(t); l.setObjectName("SysCur" if cur else "SysLine"); l.setWordWrap(True)
            self.sysmap_v.addWidget(l)

        head("💡 ÇEKİRDEK İLKE")
        line("Elin gücü TEK eksen (SHCP puanı). Pozisyon/board/ICM puana EKLENMEZ — sadece karar EŞİĞİNİ kaydırır.")
        if phase == "preflop":
            head("AKIŞ: El → SHCP puan → senaryo → eşik → karar")
            branches = [
                ("rfi", "RFI", "önünde açış yok → SEN aç (puan ≥ pozisyon eşiği)"),
                ("vs rfi", "vs-RFI", "biri açtı → çift eşik: 3bet / call / fold"),
                ("3-bet", "vs-3bet", "3-bet var → blocker ekseni (premium/A5s 4-bet, gerisi fold)"),
                ("push", "Push/Fold", "<15bb → equity ekseni: puan ≥16 JAM"),
            ]
            if "push" in scn:
                _cur = "push"
            elif "3-bet" in scn or "3bet" in scn:
                _cur = "3-bet"
            elif "vs" in scn and "rfi" in scn:
                _cur = "vs rfi"
            elif "rfi" in scn:
                _cur = "rfi"
            else:
                _cur = ""
            head("SENARYO DALLARI (şu an ◀)")
            for kk, name, desc in branches:
                cur = (kk == _cur)
                line(f"{'▶' if cur else '•'} {name}: {desc}" + ("  ◀ ŞU AN" if cur else ""), cur)
        else:
            head("POSTFLOP AKIŞ: Board oku → 7-kademe → 3 altın kural → karar")
            line("7-kademe: NUT · GÜÇLÜ · ORTA · ZAYIF · BLUFF-CATCH · DRAW · HAVA")
            line("3 altın kural: commit-gate (%70) · flop range-cbet (kuru) · pot-odds")
            tier = (explain or {}).get("tier")
            if tier:
                line(f"▶ Şu an: {tier} kademesi", True)
        head("FORMAT")
        line("Cash = loose-aggressive (balığı ez) · Turnuva = erken sıkı + geç steal + ICM")

    def _apply_chain_visibility(self):
        self.expander.setText("▴ Düşünceyi gizle" if self._chain_open else "▾ Nasıl düşünmeliyim?")

    def _set_tone(self, widget, tone):
        widget.setProperty("tone", tone)
        widget.style().unpolish(widget); widget.style().polish(widget)

    def _flash(self, kind):
        self.flash.setProperty("flash", kind)
        self.flash.style().unpolish(self.flash); self.flash.style().polish(self.flash)
        QTimer.singleShot(600, self._clear_flash)

    def _clear_flash(self):
        self.flash.setProperty("flash", "")
        self.flash.style().unpolish(self.flash); self.flash.style().polish(self.flash)

    def _record_leak(self, leak):
        try:
            from app.poker.leak_ledger import record_leak
            record_leak(leak)
        except Exception:
            pass

    def toggle_collapsed(self):
        self._collapsed = not self._collapsed
        self.body_w.setVisible(not self._collapsed)
        self.title.setVisible(not self._collapsed)
        self.mode_combo.setVisible(not self._collapsed)
        self.setFixedWidth(self.COLLAPSED_WIDTH if self._collapsed else self.EXPANDED_WIDTH)
        self.toggle_btn.setText("▶" if self._collapsed else "◀")
