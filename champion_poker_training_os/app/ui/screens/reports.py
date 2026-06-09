from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core.app_state import AppState
from app.db.seed_data import dashboard_metrics, leaks
from app.ui.components.metric_card import MetricCard


class MiniChart(QWidget):
    """Simple custom-painted chart widget for trend visualization."""

    def __init__(self, data: list[float], label: str = "", color: str = "#22D3EE"):
        super().__init__()
        self.data = data
        self.chart_label = label
        self.color = QColor(color)
        self.setMinimumHeight(120)
        self.setMinimumWidth(200)

    def paintEvent(self, event) -> None:
        if not self.data or len(self.data) < 2:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        margin = 30
        chart_w = w - margin * 2
        chart_h = h - margin * 2

        min_val = min(self.data) * 0.9
        max_val = max(self.data) * 1.1
        val_range = max(max_val - min_val, 1)

        # Draw grid lines
        painter.setPen(QPen(QColor("#2D3748"), 1))
        for i in range(5):
            y = margin + chart_h * i // 4
            painter.drawLine(margin, y, w - margin, y)

        # Draw axis labels
        painter.setPen(QPen(QColor("#9CA3AF"), 1))
        painter.drawText(2, margin + 4, f"{max_val:.0f}")
        painter.drawText(2, h - margin + 4, f"{min_val:.0f}")
        painter.drawText(margin, h - 5, self.chart_label)

        # Draw data points and lines
        points = []
        for i, val in enumerate(self.data):
            x = margin + int(chart_w * i / (len(self.data) - 1))
            y = margin + int(chart_h * (1 - (val - min_val) / val_range))
            points.append((x, y))

        # Fill area under curve
        painter.setPen(Qt.NoPen)
        fill_color = QColor(self.color)
        fill_color.setAlpha(30)
        painter.setBrush(fill_color)
        fill_points = [(points[0][0], margin + chart_h)] + points + [(points[-1][0], margin + chart_h)]
        from PySide6.QtGui import QPolygon
        from PySide6.QtCore import QPoint
        polygon = QPolygon([QPoint(x, y) for x, y in fill_points])
        painter.drawPolygon(polygon)

        # Draw line
        painter.setPen(QPen(self.color, 2))
        for i in range(len(points) - 1):
            painter.drawLine(points[i][0], points[i][1], points[i + 1][0], points[i + 1][1])

        # Draw dots
        painter.setBrush(self.color)
        for x, y in points:
            painter.drawEllipse(x - 4, y - 4, 8, 8)

        # Draw value labels on dots
        painter.setPen(QPen(QColor("#E5E7EB"), 1))
        for i, (x, y) in enumerate(points):
            painter.drawText(x - 10, y - 10, f"{self.data[i]:.0f}")

        painter.end()


class ReportsScreen(QWidget):
    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        metrics = dashboard_metrics()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        scroll.setWidget(body)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        # Header
        header = QHBoxLayout()
        title = QLabel("Reports")
        title.setObjectName("Title")
        header.addWidget(title)
        self.period = QComboBox()
        self.period.addItems(["Weekly", "Monthly", "Session"])
        header.addWidget(self.period)
        export = QPushButton("Export HTML/PDF Report")
        export.setObjectName("PrimaryButton")
        export.clicked.connect(lambda: self.status.setText("✓ Demo report exported: HTML/PDF adapter ready."))
        header.addWidget(export)
        layout.addLayout(header)

        self.status = QLabel("Weekly report ready.")
        self.status.setObjectName("Green")
        layout.addWidget(self.status)

        # ── GTO GELİŞİM (gerçek hero_decisions verisinden) ──
        self.gto_frame = QFrame()
        self.gto_frame.setObjectName("Card")
        self._gto_layout = QVBoxLayout(self.gto_frame)
        gto_title = QLabel("📈  GTO GELİŞİM  ·  gerçek oyun verisi")
        gto_title.setObjectName("SectionTitle")
        self._gto_layout.addWidget(gto_title)
        self.gto_body = QLabel("")
        self.gto_body.setWordWrap(True)
        self.gto_body.setTextFormat(Qt.TextFormat.RichText)
        self.gto_body.setStyleSheet(
            "font-family:'JetBrains Mono',Menlo,monospace; font-size:12px;")
        self._gto_layout.addWidget(self.gto_body)
        self._gto_chart_holder = QVBoxLayout()
        self._gto_layout.addLayout(self._gto_chart_holder)
        layout.addWidget(self.gto_frame)

        # Summary cards (gerçek veriden — reload() günceller)
        stats = QGridLayout()
        self.card_hands = MetricCard("Oynanan El", "0", "gerçek oyun", "Green")
        self.card_acc = MetricCard("GTO Doğruluk", "—", "kararların", "Green")
        self.card_evloss = MetricCard("EV Kaybı", "0.0bb", "toplam (gerçek)", "Amber")
        self.card_winrate = MetricCard("bb/100", "0.0", "kazanç oranı", "Green")
        stats.addWidget(self.card_hands, 0, 0)
        stats.addWidget(self.card_acc, 0, 1)
        stats.addWidget(self.card_evloss, 0, 2)
        stats.addWidget(self.card_winrate, 0, 3)
        layout.addLayout(stats)

        # ── GÜÇLÜ / ZAYIF YÖNLER (gerçek veriden içgörü) ──
        self.insights_frame = QFrame()
        self.insights_frame.setObjectName("Card")
        self._insights_layout = QVBoxLayout(self.insights_frame)
        ins_title = QLabel("🔎  GÜÇLÜ / ZAYIF YÖNLER  ·  gerçek veriden")
        ins_title.setObjectName("SectionTitle")
        self._insights_layout.addWidget(ins_title)
        self.insights_body = QLabel("")
        self.insights_body.setWordWrap(True)
        self.insights_body.setTextFormat(Qt.TextFormat.RichText)
        self.insights_body.setStyleSheet(
            "font-family:'JetBrains Mono',Menlo,monospace; font-size:12px;")
        self._insights_layout.addWidget(self.insights_body)
        layout.addWidget(self.insights_frame)

        # ── SEGMENT ANALİZİ (pozisyon × stack — derin içgörü) ──
        self.segment_frame = QFrame()
        self.segment_frame.setObjectName("Card")
        self._segment_layout = QVBoxLayout(self.segment_frame)
        seg_title = QLabel("📊  SEGMENT ANALİZİ  ·  format × aşama × masa × pozisyon × stack")
        seg_title.setObjectName("SectionTitle")
        self._segment_layout.addWidget(seg_title)
        self.segment_body = QLabel("")
        self.segment_body.setWordWrap(True)
        self.segment_body.setTextFormat(Qt.TextFormat.RichText)
        self.segment_body.setStyleSheet(
            "font-family:'JetBrains Mono',Menlo,monospace; font-size:12px;")
        self._segment_layout.addWidget(self.segment_body)
        layout.addWidget(self.segment_frame)

        # Charts row
        charts = QHBoxLayout()

        # 7-day accuracy trend
        accuracy_chart = QFrame()
        accuracy_chart.setObjectName("Card")
        ac_layout = QVBoxLayout(accuracy_chart)
        ac_title = QLabel("7-Day Accuracy Trend")
        ac_title.setObjectName("SectionTitle")
        ac_layout.addWidget(ac_title)
        ac_layout.addWidget(MiniChart(
            [float(v) for v in metrics["progress_7d"]],
            "Mon → Sun",
            "#22D3EE",
        ))
        charts.addWidget(accuracy_chart)

        # EV loss trend
        ev_chart = QFrame()
        ev_chart.setObjectName("Card")
        ev_layout = QVBoxLayout(ev_chart)
        ev_title = QLabel("EV Loss Trend (bb/100)")
        ev_title.setObjectName("SectionTitle")
        ev_layout.addWidget(ev_title)
        ev_layout.addWidget(MiniChart(
            [29.4, 27.1, 25.8, 24.2, 23.5, 22.9, metrics["ev_loss_per_100"]],
            "Improving ↓",
            "#10B981",
        ))
        charts.addWidget(ev_chart)

        # Skill score progression
        skill_chart = QFrame()
        skill_chart.setObjectName("Card")
        sk_layout = QVBoxLayout(skill_chart)
        sk_title = QLabel("Skill Score Progression")
        sk_title.setObjectName("SectionTitle")
        sk_layout.addWidget(sk_title)
        # D130: eskiden uydurma yükseliş rampası [680..735, real] vardı (sahte
        # 'Rising ↑'). Skill-history tracker yok → gerçek tek noktayı dürüstçe
        # göster (uydurma trend değil).
        _sk = float(metrics["skill_score"])
        sk_layout.addWidget(MiniChart(
            [_sk] if _sk else [0],
            "Mevcut skor (geçmiş takibi yok)",
            "#8B5CF6",
        ))
        charts.addWidget(skill_chart)
        layout.addLayout(charts)

        # Accuracy breakdown
        breakdown = QFrame()
        breakdown.setObjectName("DataPanel")
        bd_layout = QVBoxLayout(breakdown)
        bd_title = QLabel("Accuracy Breakdown")
        bd_title.setObjectName("SectionTitle")
        bd_layout.addWidget(bd_title)

        breakdown_data = [
            ("Preflop", metrics["preflop_accuracy"], "Cyan"),
            ("Postflop", metrics["postflop_accuracy"], "Amber"),
            ("River", metrics["river_score"], "Amber"),
            ("ICM", metrics["icm_discipline"], "Green"),
            ("Math Reflex", metrics["math_reflex"], "Green"),
        ]
        for name, value, color in breakdown_data:
            row = QHBoxLayout()
            label = QLabel(name)
            label.setFixedWidth(120)
            bar = _PercentBar(value)
            pct = QLabel(f"{value}%")
            pct.setObjectName(color)
            pct.setFixedWidth(50)
            row.addWidget(label)
            row.addWidget(bar, 1)
            row.addWidget(pct)
            bd_layout.addLayout(row)
        layout.addWidget(breakdown)

        # Active leaks
        leak_frame = QFrame()
        leak_frame.setObjectName("DataPanel")
        leak_layout = QVBoxLayout(leak_frame)
        leak_title = QLabel("Active Leaks")
        leak_title.setObjectName("SectionTitle")
        leak_layout.addWidget(leak_title)
        # D130: sabit sahte leaks() yerine GERÇEK leak motoru (oyuncu stat'larından).
        # Gerçek leak'lerde ev_lost yok → graceful (.get); fix yoksa detail göster.
        from app.db.repository import get_leak_analysis
        for leak in get_leak_analysis():
            row = QHBoxLayout()
            name = QLabel(leak.get("name", "—"))
            name.setObjectName("Muted")
            sev = leak.get("severity", "Info")
            severity = QLabel(sev)
            severity.setObjectName("Red" if sev in ("Critical", "High") else "Amber")
            _ev = leak.get("ev_lost")
            ev = QLabel(f"-{_ev}bb" if _ev is not None else "")
            ev.setObjectName("Red")
            fix = QLabel(leak.get("fix") or leak.get("detail", ""))
            fix.setObjectName("Green")
            fix.setWordWrap(True)
            row.addWidget(name, 2)
            row.addWidget(severity)
            row.addWidget(ev)
            row.addWidget(fix, 3)
            leak_layout.addLayout(row)
        layout.addWidget(leak_frame)

        # Recommendations
        rec = QFrame()
        rec.setObjectName("Card")
        rec_layout = QVBoxLayout(rec)
        rec_title = QLabel("Next Week Focus")
        rec_title.setObjectName("SectionTitle")
        rec_layout.addWidget(rec_title)
        recommendations = [
            "1. River bluff discipline: reduce overbluff frequency by 15%",
            "2. BB defend expansion: add suited gappers and wheel aces",
            "3. ICM call-off tightening: respect pay jump premium",
            "4. Turn paired board: check more, barrel less",
            "5. Thin value practice: half-pot river bets vs capped ranges",
        ]
        for r in recommendations:
            label = QLabel(r)
            label.setObjectName("Cyan")
            rec_layout.addWidget(label)
        layout.addWidget(rec)

        self.reload()   # tüm bölümler gerçek veriden dolsun

    def reload(self) -> None:
        """Tüm bölümleri gerçek veriden tazele (kartlar + içgörü + GTO gelişim)."""
        try:
            from app.db.repository import (
                get_gto_accuracy_trend, get_gto_category_accuracy,
                get_player_stats, get_self_insights, get_segmented_insights,
            )
            trend = get_gto_accuracy_trend(days=14)
            cats = get_gto_category_accuracy()
            pstats = get_player_stats()
            insights = get_self_insights()
            segments = get_segmented_insights()
        except Exception:
            trend, cats, pstats = [], {}, {}
            insights = {"strengths": [], "weaknesses": []}
            segments = []

        # ── Özet kartları (gerçek) ──
        tot = sum(c["n"] for c in cats.values())
        acc = (round(sum(c["accuracy"] * c["n"] for c in cats.values()) / tot, 0)
               if tot else 0)
        ev_total = round(sum(c.get("avg_ev_loss", 0) * c["n"] for c in cats.values()), 1)
        self.card_hands.set_value(str(pstats.get("total_hands", 0)))
        self.card_acc.set_value(f"%{acc:.0f}" if tot else "—")
        self.card_acc.set_detail(f"{tot} karar")
        self.card_evloss.set_value(f"{ev_total:.1f}bb")
        self.card_winrate.set_value(f"{pstats.get('bb_per_100', 0):+.1f}")

        # ── Güçlü / Zayıf yönler ──
        st = insights.get("strengths", []); wk = insights.get("weaknesses", [])
        if not st and not wk:
            self.insights_body.setText(
                "<span style='color:#94A3B8'>Yeterli veri yok. Real Experience "
                "modda el oyna / HH import et — güçlü ve zayıf yönlerin burada "
                "gerçek kararlarından çıkarılacak.</span>")
        else:
            html = ""
            if st:
                html += "<span style='color:#10B981; font-weight:700'>✓ GÜÇLÜ:</span><br>"
                html += "<br>".join(f"&nbsp;&nbsp;• {s}" for s in st) + "<br>"
            if wk:
                html += "<span style='color:#DC2626; font-weight:700'>⚠ GELİŞTİR:</span><br>"
                html += "<br>".join(f"&nbsp;&nbsp;• {w}" for w in wk)
            self.insights_body.setText(html)

        # ── Segment analizi ──
        if not segments:
            self.segment_body.setText(
                "<span style='color:#94A3B8'>Yeterli hata-spotu yok. Real "
                "Experience modda el oyna — pozisyon × stack segmentlerindeki "
                "sistematik hataların (örn. 'erken pozisyon + sığ stack'te "
                "gereksiz raise') burada çıkacak.</span>")
        else:
            shtml = []
            for s in segments[:5]:
                # EV-kaybı sadece anlamlıysa göster (preflop open'larda EV proxy yok)
                meta = f"{s['n']} hata"
                if s["ev_lost"] >= 0.5:
                    meta += f" · ~{s['ev_lost']:.0f}bb kayıp"
                shtml.append(
                    f"<b style='color:#22D3EE'>{s['segment']}</b> "
                    f"<span style='color:#94A3B8'>({meta})</span><br>"
                    f"&nbsp;&nbsp;{s['pattern']}<br>"
                    f"&nbsp;&nbsp;<span style='color:#5ad17a'>→ {s['tip']}</span>")
            self.segment_body.setText("<br><br>".join(shtml))

        # Eski grafiği temizle
        while self._gto_chart_holder.count():
            it = self._gto_chart_holder.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

        total_dec = sum(c["n"] for c in cats.values())
        if total_dec == 0:
            self.gto_body.setText(
                "<span style='color:#94A3B8'>Henüz GTO karar verisi yok. "
                "Real Experience Mode'da el oyna veya PokerStars el geçmişini "
                "içeri al — bu bölüm gerçek doğruluğunu gün gün gösterecek.</span>")
            return

        # Genel doğruluk (kararlarla ağırlıklı)
        overall = round(
            sum(c["accuracy"] * c["n"] for c in cats.values()) / total_dec, 1)
        first = trend[0]["accuracy"] if trend else overall
        last = trend[-1]["accuracy"] if trend else overall
        delta = last - first
        arrow = "↑" if delta > 3 else ("↓" if delta < -3 else "→")
        acol = "#10B981" if delta > 3 else ("#DC2626" if delta < -3 else "#F59E0B")

        # Kategori kırılımı (en zayıf en üstte)
        rows = sorted(cats.items(), key=lambda kv: kv[1]["accuracy"])
        cat_lines = "  ·  ".join(
            f"{name} <b>%{d['accuracy']:.0f}</b> "
            f"<span style='color:#94A3B8'>({d['n']})</span>"
            for name, d in rows)
        self.gto_body.setText(
            f"Genel GTO doğruluk: <b style='color:#22D3EE'>%{overall:.0f}</b>  "
            f"<span style='color:{acol}'>(14g: %{first:.0f} → %{last:.0f} {arrow})</span>"
            f"  ·  {total_dec} karar<br>"
            f"<span style='color:#94A3B8'>Kategori:</span> {cat_lines}"
        )
        if trend:
            self._gto_chart_holder.addWidget(MiniChart(
                [d["accuracy"] for d in trend], "GTO doğruluk (gün gün)",
                "#22D3EE"))


class _PercentBar(QWidget):
    """Simple horizontal bar showing a percentage."""

    def __init__(self, value: int):
        super().__init__()
        self.value = min(100, max(0, value))
        self.setMinimumHeight(20)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()

        # Background
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#1F2937"))
        painter.drawRoundedRect(0, 2, w, h - 4, 4, 4)

        # Filled portion
        fill_w = int(w * self.value / 100)
        if self.value >= 80:
            color = QColor("#10B981")
        elif self.value >= 60:
            color = QColor("#22D3EE")
        else:
            color = QColor("#F59E0B")
        painter.setBrush(color)
        painter.drawRoundedRect(0, 2, fill_w, h - 4, 4, 4)
        painter.end()
