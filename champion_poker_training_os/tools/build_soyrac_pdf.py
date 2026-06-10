"""Soyrac bible montaj: workflow JSON sonucu -> stilize HTML kitap (kapak, TOC,
flowchart SVG'ler, callout kutular, sozluk) -> Chrome headless ile PDF.

Kullanim: .venv/bin/python tools/build_soyrac_pdf.py <workflow_result.json>
"""
from __future__ import annotations
import json, sys, re, subprocess, html
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parents[1] / "docs" / "soyrac_book"
OUT_DIR.mkdir(parents=True, exist_ok=True)
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# ─────────── FLOWCHART SVG'LERI (merkezi, tutarli stil) ───────────
def _box(x, y, w, h, fill, stroke, tcol, title, sub="", rx=6):
    t = f'<text x="{x+w/2}" y="{y+(h/2 if not sub else h/2-6)}" text-anchor="middle" font-size="13" font-weight="500" fill="{tcol}">{title}</text>'
    s = f'<text x="{x+w/2}" y="{y+h/2+12}" text-anchor="middle" font-size="11" fill="{tcol}">{sub}</text>' if sub else ""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="1.2"/>{t}{s}'

def _arrow(x1, y1, x2, y2, label=""):
    lab = f'<text x="{(x1+x2)/2+4}" y="{(y1+y2)/2-3}" font-size="10" fill="#5F5E5A">{label}</text>' if label else ""
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#888780" stroke-width="1.2" marker-end="url(#ar)"/>{lab}'

_DEFS = '<defs><marker id="ar" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#888780"/></marker></defs>'

def fig_system():
    s = [f'<svg viewBox="0 0 720 230" xmlns="http://www.w3.org/2000/svg" class="fig">{_DEFS}']
    s.append(_box(20, 90, 130, 50, "#E6F1FB", "#185FA5", "#0C447C", "Elini puanla", "SHCP (kart + suited)"))
    s.append(_box(200, 90, 130, 50, "#E1F5EE", "#0F6E56", "#04342C", "Pozisyon esigi", "puan >= esik?"))
    s.append(_box(380, 30, 150, 44, "#EAF3DE", "#3B6D11", "#173404", "Preflop karar", "RAISE / CALL / FOLD"))
    s.append(_box(380, 150, 150, 44, "#FAEEDA", "#854F0B", "#412402", "Board oku", "7-kademe el-gucu"))
    s.append(_box(560, 90, 140, 50, "#EEEDFE", "#534AB7", "#26215C", "Postflop karar", "commit-gate + sizing"))
    s.append(_arrow(150, 115, 200, 115))
    s.append(_arrow(330, 110, 380, 60, "el oynanir"))
    s.append(_arrow(330, 120, 380, 165, "flop gelir"))
    s.append(_arrow(530, 172, 560, 130))
    s.append('</svg>')
    return "".join(s)

def fig_preflop():
    s = [f'<svg viewBox="0 0 720 320" xmlns="http://www.w3.org/2000/svg" class="fig">{_DEFS}']
    s.append(_box(280, 10, 160, 40, "#F1EFE8", "#5F5E5A", "#2C2C2A", "Onunde aksiyon?", ""))
    s.append(_box(40, 90, 150, 44, "#E6F1FB", "#185FA5", "#0C447C", "Yok (ilk giren)", "RFI"))
    s.append(_box(285, 90, 150, 44, "#E1F5EE", "#0F6E56", "#04342C", "1 acis var", "vs RFI"))
    s.append(_box(530, 90, 160, 44, "#FBEAF0", "#993556", "#4B1528", "Yukseltildi (3bet)", "vs 3-BET"))
    s.append(_box(20, 175, 190, 50, "#EAF3DE", "#3B6D11", "#173404", "puan >= pozisyon esigi", "UTG15..BTN8 -> RAISE"))
    s.append(_box(270, 175, 180, 64, "#FAEEDA", "#854F0B", "#412402", "cift esik", ">=3bet_t: 3-BET / >=call_t: CALL"))
    s.append(_box(500, 175, 200, 64, "#EEEDFE", "#534AB7", "#26215C", "BLOCKER ekseni (B4)", "B4>=2 -> 4-BET / yoksa CALL/FOLD"))
    s.append(_arrow(330, 50, 115, 90))
    s.append(_arrow(360, 50, 360, 90))
    s.append(_arrow(390, 50, 610, 90))
    s.append(_arrow(115, 134, 115, 175))
    s.append(_arrow(360, 134, 360, 175))
    s.append(_arrow(610, 134, 600, 175))
    s.append(_box(270, 270, 180, 36, "#FCEBEB", "#A32D2D", "#501313", "Stack < 15bb -> PUSH/FOLD", ""))
    s.append(_arrow(360, 239, 360, 270, "kisa stack"))
    s.append('</svg>')
    return "".join(s)

def fig_postflop():
    s = [f'<svg viewBox="0 0 720 340" xmlns="http://www.w3.org/2000/svg" class="fig">{_DEFS}']
    s.append(_box(280, 8, 160, 38, "#F1EFE8", "#5F5E5A", "#2C2C2A", "Board + el-gucu oku", ""))
    s.append(_box(280, 70, 160, 38, "#E6F1FB", "#185FA5", "#0C447C", "Bahis karsisinda miyim?", ""))
    s.append(_box(30, 140, 200, 56, "#E1F5EE", "#0F6E56", "#04342C", "HAYIR (bana check)", "agresorsem+kuru board -> RANGE-CBET; islak -> polarize"))
    s.append(_box(490, 140, 200, 56, "#FAEEDA", "#854F0B", "#412402", "EVET (bahis var)", "equity >= pot-odds? -> CALL; NUT/GUCLU -> RAISE; yoksa FOLD"))
    s.append(_box(255, 230, 210, 50, "#FCEBEB", "#A32D2D", "#501313", "COMMIT-GATE", "yigin %70+ riskse: sadece GUCLU+/cekme ile devam"))
    s.append(_box(255, 300, 210, 32, "#EEEDFE", "#534AB7", "#26215C", "Sonraki sokak: bir kademe asagi say", ""))
    s.append(_arrow(360, 46, 360, 70))
    s.append(_arrow(330, 108, 130, 140))
    s.append(_arrow(390, 108, 590, 140))
    s.append(_arrow(160, 196, 320, 230))
    s.append(_arrow(560, 196, 400, 230))
    s.append(_arrow(360, 280, 360, 300))
    s.append('</svg>')
    return "".join(s)

def fig_icm():
    s = [f'<svg viewBox="0 0 720 200" xmlns="http://www.w3.org/2000/svg" class="fig">{_DEFS}']
    s.append(_box(20, 80, 150, 50, "#E6F1FB", "#185FA5", "#0C447C", "Chip-EV karari", "cash gibi"))
    s.append(_box(220, 80, 160, 50, "#FAEEDA", "#854F0B", "#412402", "Elenme pahali mi?", "bubble / final table"))
    s.append(_box(440, 30, 250, 44, "#FCEBEB", "#A32D2D", "#501313", "EVET -> esik +1 (SIKIS)", "marjinal calloff/jam fold"))
    s.append(_box(440, 120, 250, 44, "#E1F5EE", "#0F6E56", "#04342C", "HAYIR -> chip-EV ayni", "normal oyna"))
    s.append(_arrow(170, 105, 220, 105))
    s.append(_arrow(380, 95, 440, 60, "risk premium"))
    s.append(_arrow(380, 115, 440, 140))
    s.append('</svg>')
    return "".join(s)

FIGS = {"system": fig_system, "preflop": fig_preflop, "preflop_decision": fig_preflop,
        "postflop": fig_postflop, "postflop_decision": fig_postflop, "icm": fig_icm}

def _strip_fence(h):
    h = re.sub(r"^```[a-z]*\n?", "", h.strip())
    h = re.sub(r"\n?```$", "", h.strip())
    return h

def _insert_figs(chapter_html, chap_n):
    # figref placeholder'lari -> gercek SVG
    def repl(m):
        key = (m.group(1) or "").lower()
        for k, fn in FIGS.items():
            if k in key:
                return f'<figure class="figwrap">{fn()}<figcaption>Sekil — {html.escape(key)}</figcaption></figure>'
        return ""
    out = re.sub(r'<div class="figref"[^>]*data-fig="([^"]*)"[^>]*>.*?</div>', repl, chapter_html, flags=re.S)
    # bolum basina ana flowchart (1=system, 6=preflop, 11=postflop, 12=icm)
    lead = {1: "system", 6: "preflop", 11: "postflop", 12: "icm"}.get(chap_n)
    if lead and 'figwrap' not in out[:1500]:
        out = re.sub(r'(</h2>)', r'\1\n<figure class="figwrap">' + FIGS[lead]() + f'<figcaption>Sekil — {lead}</figcaption></figure>', out, count=1)
    return out

CSS = """
@page { size: A4; margin: 18mm 16mm 18mm 16mm; }
* { box-sizing: border-box; }
body { font-family: -apple-system, 'Helvetica Neue', Arial, sans-serif; color: #1a1a18; line-height: 1.62; font-size: 11.2pt; margin: 0; }
h1 { font-size: 30pt; font-weight: 600; margin: 0 0 6px; letter-spacing: -0.5px; }
h2 { font-size: 19pt; font-weight: 600; color: #0C447C; margin: 0 0 14px; padding-bottom: 8px; border-bottom: 2px solid #185FA5; page-break-after: avoid; }
h3 { font-size: 14pt; font-weight: 600; color: #173404; margin: 20px 0 8px; page-break-after: avoid; }
h4 { font-size: 12pt; font-weight: 600; color: #2C2C2A; margin: 14px 0 6px; }
p { margin: 0 0 10px; }
ul, ol { margin: 0 0 10px; padding-left: 22px; }
li { margin: 0 0 5px; }
.chapter { page-break-before: always; }
table.tbl { width: 100%; border-collapse: collapse; margin: 12px 0 16px; font-size: 10pt; page-break-inside: avoid; }
table.tbl th { background: #E6F1FB; color: #0C447C; text-align: left; padding: 7px 9px; border: 0.5px solid #B5D4F4; font-weight: 600; }
table.tbl td { padding: 6px 9px; border: 0.5px solid #D3D1C7; vertical-align: top; }
table.tbl tr:nth-child(even) td { background: #FAFAF7; }
.note, .why, .example, .gto, .icm, .keyrule { padding: 9px 13px; margin: 11px 0; border-radius: 7px; border-left: 4px solid; font-size: 10.4pt; page-break-inside: avoid; }
.note { background: #F1EFE8; border-color: #888780; }
.why { background: #EAF3DE; border-color: #3B6D11; }
.example { background: #FAEEDA; border-color: #BA7517; }
.gto { background: #E6F1FB; border-color: #185FA5; }
.icm { background: #EEEDFE; border-color: #534AB7; }
.keyrule { background: #FBEAF0; border-color: #D4537E; font-weight: 500; }
.term { background: #F1EFE8; padding: 1px 5px; border-radius: 4px; }
.term b { color: #0C447C; }
figure.figwrap { margin: 16px 0; text-align: center; page-break-inside: avoid; }
figure.figwrap svg.fig { width: 100%; max-width: 620px; height: auto; border: 0.5px solid #D3D1C7; border-radius: 8px; padding: 8px; background: #fff; }
figure.figwrap figcaption { font-size: 9.5pt; color: #5F5E5A; margin-top: 5px; font-style: italic; }
.cover { page-break-after: always; text-align: center; padding-top: 60mm; }
.cover .sub { font-size: 14pt; color: #5F5E5A; margin-top: 10px; }
.cover .meta { margin-top: 40mm; font-size: 10pt; color: #888780; }
.cover .badges span { display: inline-block; background: #E6F1FB; color: #0C447C; font-size: 10pt; padding: 5px 14px; border-radius: 7px; margin: 4px; }
.toc { page-break-after: always; }
.toc h2 { border: none; }
.toc ol { list-style: none; padding: 0; counter-reset: c; }
.toc li { counter-increment: c; padding: 7px 0; border-bottom: 0.5px solid #E5E3DC; font-size: 11pt; }
.toc li::before { content: counter(c) ". "; color: #185FA5; font-weight: 600; }
.gloss dt { font-weight: 600; color: #0C447C; margin-top: 9px; }
.gloss dd { margin: 2px 0 0; padding-left: 0; color: #2C2C2A; }
"""

def build(result_path):
    data = json.loads(Path(result_path).read_text())
    if "result" in data and isinstance(data["result"], dict):
        data = data["result"]
    chapters = data["chapters"]
    review = data.get("review", {})

    parts = []
    # KAPAK
    parts.append('<div class="cover"><h1>SOYRAC</h1><div class="sub">Insan-Hesaplanabilir Poker Karar Sistemi<br>Felsefe · Mantik · GTO &amp; ICM Karsiliklari · Ornekler</div>'
                 '<div class="badges" style="margin-top:30mm"><span>Preflop GTO uyumu %91</span><span>Postflop %93</span><span>ICM %91</span><span>Cash +46…+80 bb/100</span></div>'
                 '<div class="meta">Bridge HCP ve Blackjack Hi-Lo felsefesiyle · ampirik dogrulanmis · ogretici el kitabi</div></div>')
    # ICINDEKILER
    toc = '<div class="toc"><h2>Icindekiler</h2><ol>'
    for c in chapters:
        toc += f'<li>{html.escape(c["t"])}</li>'
    toc += '<li>Sozluk (Glossary)</li></ol></div>'
    parts.append(toc)

    # BOLUMLER
    glossary = {}
    for c in chapters:
        d = c.get("data") or {}
        ch = _strip_fence(d.get("chapter_html", "") or f"<h2>Bolum {c['n']}. {c['t']}</h2><p>(uretilemedi)</p>")
        ch = _insert_figs(ch, c["n"])
        parts.append(f'<div class="chapter">{ch}</div>')
        for g in (d.get("glossary") or []):
            t = (g.get("term") or "").strip()
            if t and t not in glossary:
                glossary[t] = (g.get("tr") or "").strip()

    # EDITOR KAPATICI NOTLAR
    cn = (review or {}).get("closing_notes_html", "")
    if cn:
        parts.append(f'<div class="chapter"><h2>Editor Notlari</h2>{_strip_fence(cn)}</div>')

    # SOZLUK
    gl = '<div class="chapter gloss"><h2>Sozluk (Glossary)</h2><dl>'
    for t in sorted(glossary, key=str.lower):
        gl += f'<dt>{html.escape(t)}</dt><dd>{html.escape(glossary[t])}</dd>'
    gl += '</dl></div>'
    parts.append(gl)

    full = f'<!DOCTYPE html><html lang="tr"><head><meta charset="utf-8"><style>{CSS}</style></head><body>{"".join(parts)}</body></html>'
    html_path = OUT_DIR / "soyrac_bible.html"
    html_path.write_text(full, encoding="utf-8")
    pdf_path = OUT_DIR / "Soyrac_Sistemi_Bible.pdf"
    subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf_path}", str(html_path)], check=True,
                   capture_output=True, timeout=120)
    n_words = sum(len(re.sub(r"<[^>]+>", " ", (c.get("data") or {}).get("chapter_html", "")).split()) for c in chapters)
    print(f"HTML: {html_path}")
    print(f"PDF:  {pdf_path}  ({pdf_path.stat().st_size//1024} KB)")
    print(f"Bolum: {len(chapters)} · Sozluk terim: {len(glossary)} · ~kelime: {n_words}")

if __name__ == "__main__":
    build(sys.argv[1])
