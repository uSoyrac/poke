"""AI Koç ↔ Strateji Playbook bağı.

Playbook ilkeleri hem koçun LLM sistem prompt'una gömülü (online) hem de
offline coach_chat 'strateji' cevabında yer alır. Ekran ile koç TEK kaynaktan
(app.poker.playbook) beslenir → tutarlılık garantili.
"""
from __future__ import annotations

from app.poker.playbook import (
    CASH_PLAYBOOK, MTT_PLAYBOOK, playbook_reference_text,
)


def test_reference_text_covers_both_formats():
    ref = playbook_reference_text()
    assert "CASH GAME PLAYBOOK" in ref
    assert "MTT PLAYBOOK" in ref
    # Her bölümün başlığı referansta görünür (koç ismen atıf yapabilsin)
    for sec in CASH_PLAYBOOK + MTT_PLAYBOOK:
        assert sec["title"] in ref, f"{sec['title']} referansta yok"
    # 'Neden' gerekçeleri de gömülü (anlayış aktarımı)
    assert "Neden:" in ref


def test_reference_text_is_compact():
    """Token tasarrufu: bölüm başına ilk N ilke (hepsi değil)."""
    full_rules = sum(len(s["rules"]) for s in CASH_PLAYBOOK + MTT_PLAYBOOK)
    ref_rules = playbook_reference_text(max_rules=2).count("   - ")
    assert ref_rules < full_rules, "referans tüm ilkeleri almamalı (kompakt)"
    assert ref_rules >= len(CASH_PLAYBOOK + MTT_PLAYBOOK), "her bölümden en az 1 ilke"


def test_system_prompt_embeds_playbook():
    from app.ai.coach_prompts import SYSTEM_PROMPT_WITH_PLAYBOOK, SYSTEM_PROMPT_TR
    assert len(SYSTEM_PROMPT_WITH_PLAYBOOK) > len(SYSTEM_PROMPT_TR)
    assert "STRATEJİ PLAYBOOK" in SYSTEM_PROMPT_WITH_PLAYBOOK
    assert "CASH GAME PLAYBOOK" in SYSTEM_PROMPT_WITH_PLAYBOOK
    assert "MTT PLAYBOOK" in SYSTEM_PROMPT_WITH_PLAYBOOK


def test_gemini_client_uses_playbook_prompt():
    """gemini_client, playbook gömülü sistem prompt'unu kullanmalı."""
    import app.ai.gemini_client as gc
    from app.ai.coach_prompts import SYSTEM_PROMPT_WITH_PLAYBOOK
    assert gc.SYSTEM_PROMPT_TR is SYSTEM_PROMPT_WITH_PLAYBOOK


def test_offline_coach_strategy_query_returns_playbook():
    from app.ai.coach_engine import coach_chat
    out = coach_chat("uzun vade cash game stratejisi nedir")
    assert "CASH GAME" in out
    assert "Strategy Playbook" in out


def test_offline_coach_mtt_strategy_query():
    from app.ai.coach_engine import coach_chat
    out = coach_chat("turnuva (mtt) uzun dönem strateji")
    assert "MTT" in out
    # MTT playbook'un ilk bölümü stack derinliği
    assert "Stack" in out or "stack" in out


# ── Growth & Edge Lab ↔ Koç bağı ─────────────────────────────────────
def test_system_prompt_embeds_growth_concepts():
    from app.ai.coach_prompts import SYSTEM_PROMPT_WITH_PLAYBOOK
    for kw in ("KELLY", "RISK OF RUIN", "ERGODICITY", "ÜSTEL BÜYÜME"):
        assert kw in SYSTEM_PROMPT_WITH_PLAYBOOK, f"'{kw}' sistem prompt'ta yok"


def test_system_prompt_embeds_elite_thinking_protocol():
    """advanced-poker-coach skill'inin 6-adım refleksi + ilkeleri app koçuna gömülü."""
    from app.ai.coach_prompts import SYSTEM_PROMPT_WITH_PLAYBOOK as P
    for kw in ("ELİT DÜŞÜNME PROTOKOLÜ", "RANGE → BOARD", "ADVANTAGE",
               "INDIFFERENCE", "DEVIATE", "Karar ≠ sonuç", "MDF çıpası"):
        assert kw in P, f"'{kw}' düşünme protokolünde yok"


def test_offline_coach_bankroll_positive_winrate():
    from app.ai.coach_engine import coach_chat
    stats = {"total_hands": 5000, "bb_per_100": 6.0}
    out = coach_chat("bankroll iflas riski ne olmalı", session_stats=stats)
    assert "Bankroll" in out
    assert "buy-in" in out.lower()
    assert "Kelly" in out or "kelly" in out.lower()


def test_offline_coach_bankroll_negative_winrate_warns_edge():
    from app.ai.coach_engine import coach_chat
    stats = {"total_hands": 5000, "bb_per_100": -3.0}
    out = coach_chat("kelly ve bankroll", session_stats=stats)
    assert "EDGE YOK" in out or "edge" in out.lower()


def test_offline_coach_bankroll_no_data():
    from app.ai.coach_engine import coach_chat
    out = coach_chat("bankroll", session_stats=None)
    assert "Growth & Edge Lab" in out
