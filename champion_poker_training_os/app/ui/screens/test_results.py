"""Bot Test Sonuçları (D139) — kapsamlı profil-başarı simülasyonunun kalıcı
görünümü. tools/profile_sim.py'nin ürettiği sonuçları (app/data/profile_sim_
results.json) okur: hangi profiller turnuva (50/100/200bb × 1000/500/200/100) ve
cash'te kazandı + optimal oyuncu stat profili. Gerçek BotBrain oynatma, ölçülmüş.
"""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QScrollArea, QVBoxLayout, QWidget)

from app.core.app_state import AppState
from app.ui.components.metric_card import MetricCard

_DATA = Path(__file__).resolve().parents[2] / "data" / "profile_sim_results.json"


def _load() -> dict:
    try:
        return json.loads(_DATA.read_text())
    except Exception:
        return {}


def _archetype_stats():
    from app.engine.bot_brain import BOT_ARCHETYPES, archetype_skill
    return BOT_ARCHETYPES, archetype_skill


def _analyze(d: dict):
    """JSON → (rows, optimal, meta). rows: per-profil birleşik başarı + stat."""
    BOT, skill_of = _archetype_stats()
    mtt = d.get("mtt", {})
    cash = d.get("cash", {}).get("100bb", {}).get("rows", {})
    itm, wins = {}, {}
    for b in mtt.values():
        for a, r in b.get("rows", {}).items():
            itm.setdefault(a, []).append(r["itm_pct"])
            wins[a] = wins.get(a, 0) + r.get("win", 0)
    rows = []
    for a in itm:
        if a not in BOT:
            continue
        p = BOT[a]
        rows.append({
            "arch": a, "skill": skill_of(a),
            "itm": round(sum(itm[a]) / len(itm[a]), 1),
            "win": wins.get(a, 0),
            "cash": cash.get(a, {}).get("bb_per_100", 0.0),
            "vpip": p.vpip, "pfr": p.pfr, "tb": p.three_bet,
            "af": p.aggression, "fcb": p.fold_to_cbet,
        })
    rows.sort(key=lambda r: -r["itm"])
    # Kazanan kohort = hem MTT hem cash top-8 → optimal stat ortalaması
    top_mtt = {r["arch"] for r in rows[:8]}
    top_cash = {r["arch"] for r in sorted(rows, key=lambda r: -r["cash"])[:8]}
    win_cohort = [r for r in rows if r["arch"] in top_mtt and r["arch"] in top_cash]
    if not win_cohort:
        win_cohort = rows[:5]
    n = len(win_cohort)
    optimal = {
        "vpip": round(sum(r["vpip"] for r in win_cohort) / n),
        "pfr": round(sum(r["pfr"] for r in win_cohort) / n),
        "tb": round(sum(r["tb"] for r in win_cohort) / n),
        "af": round(sum(r["af"] for r in win_cohort) / n, 1),
        "fcb": round(sum(r["fcb"] for r in win_cohort) / n),
        "cohort": [r["arch"] for r in win_cohort],
    }
    return rows, optimal


class TestResultsScreen(QWidget):
    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        scroll.setWidget(body)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)
        L = QVBoxLayout(body)
        L.setContentsMargins(20, 18, 20, 22)
        L.setSpacing(14)

        d = _load()
        if not d.get("mtt"):
            t = QLabel("Test sonucu bulunamadı.\n\n`tools/profile_sim.py` çalıştırılınca "
                       "(eşit profil, 50/100/200bb, 1000/500/200/100 alan + cash) sonuçlar "
                       "app/data/profile_sim_results.json'a yazılır ve burada görünür.")
            t.setWordWrap(True)
            t.setObjectName("Muted")
            L.addWidget(t)
            L.addStretch(1)
            return

        rows, opt = _analyze(d)
        meta = d.get("meta", {})

        title = QLabel("🏆 Bot Test Sonuçları — Optimal Oyuncu Profili")
        title.setObjectName("Title")
        L.addWidget(title)
        sub = QLabel(
            f"Gerçek BotBrain oynatma · {len(d.get('mtt', {}))} turnuva konfigürasyonu "
            f"(50/100/200bb × 1000/500/200/100 kişi) + cash 6-max · eşit 27-profil alan · "
            f"~{meta.get('elapsed', 0):.0f}s. Sonuç VARSAYILMADI, ÖLÇÜLDÜ.")
        sub.setObjectName("Muted")
        sub.setWordWrap(True)
        L.addWidget(sub)

        # ── OPTİMAL PROFİL kartları ──
        opt_title = QLabel("🧬 Kazananın Oyun Profili (hem turnuva HEM cash zirvesinin ortalaması)")
        opt_title.setObjectName("SectionTitle")
        L.addWidget(opt_title)
        cards = QGridLayout()
        cards.setSpacing(10)
        for i, (lbl, val, det) in enumerate([
            ("VPIP", f"{opt['vpip']}%", "sıkı-orta · asla %30+"),
            ("PFR", f"{opt['pfr']}%", "limpleme — raise et"),
            ("3-BET", f"{opt['tb']}%", "seçici ama aktif"),
            ("AF", f"{opt['af']}", "agresif ama kontrollü"),
            ("FOLD-TO-CBET", f"{opt['fcb']}%", "disiplin · yenildiğinde fold"),
        ]):
            cards.addWidget(MetricCard(lbl, val, det), 0, i)
        L.addLayout(cards)
        coh = QLabel("Kazanan kohort: " + " · ".join(opt["cohort"]))
        coh.setObjectName("Muted")
        coh.setWordWrap(True)
        L.addWidget(coh)

        # ── SIRALAMA tablosu ──
        rank_title = QLabel("📊 Tüm Profiller — Başarı + Stat (MTT ort. ITM% · cash bb/100)")
        rank_title.setObjectName("SectionTitle")
        L.addWidget(rank_title)
        panel = QFrame()
        panel.setObjectName("DataPanel")
        pv = QVBoxLayout(panel)
        pv.setSpacing(1)
        pv.addLayout(self._row(
            ["PROFİL", "SKILL", "ITM%", "WIN", "CASH", "VPIP", "PFR", "3B", "AF", "FCB"],
            header=True))
        for r in rows:
            cash_s = f"{r['cash']:+.1f}" if r["cash"] else "—"
            accent = ("Green" if r["skill"] == "strong"
                      else "Amber" if r["skill"] == "mid" else "Red")
            pv.addLayout(self._row(
                [r["arch"], r["skill"], f"{r['itm']:.1f}", str(r["win"]), cash_s,
                 f"{r['vpip']:.0f}", f"{r['pfr']:.0f}", f"{r['tb']:.0f}",
                 f"{r['af']:.1f}", f"{r['fcb']:.0f}"], accent=accent))
        L.addWidget(panel)

        note = QLabel(
            "📌 Bağlam: SIĞ (≤50bb)/büyük alan → push/fold uzmanları (Short Stack Jam, "
            "ICM Expert) ladder eder; DERİN (200bb)+cash → Solver/GTO postflop zekâsı "
            "biriktirir (en çok 1.lik + en yüksek bb/100). Kaybeden formülü: loose "
            "(VPIP30+) VEYA pasif (AF<1.6) VEYA disiplinsiz (FCB<30).")
        note.setObjectName("Muted")
        note.setWordWrap(True)
        L.addWidget(note)
        L.addStretch(1)

    def _row(self, cells, header=False, accent="Mono"):
        h = QHBoxLayout()
        h.setContentsMargins(8, 5, 8, 5)
        widths = [150, 56, 48, 40, 56, 44, 44, 36, 40, 44]
        for i, c in enumerate(cells):
            lbl = QLabel(str(c))
            if i < len(widths):
                lbl.setMinimumWidth(0)
                lbl.setFixedWidth(widths[i])
            if header:
                lbl.setObjectName("TLabel")
            elif i == 0:
                lbl.setObjectName("Muted")
            elif i == 1:
                lbl.setObjectName(accent)
            else:
                lbl.setStyleSheet("font-family:'JetBrains Mono',monospace; font-size:11px;")
            h.addWidget(lbl)
        h.addStretch(1)
        return h
