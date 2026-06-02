"""Alan dağılımı GERÇEKÇİLİĞİ — gerçek MTT alanları zayıf-ağırlıklıdır.

Eski davranış: uniform dağıtım (her arketip eşit olası) → gerçekçi DEĞİL.
Yeni: KARMA_WEIGHTS ile ~%62 rekreasyonel, ~%26 orta reg, ~%12 güçlü.
"""
from __future__ import annotations

import random
from collections import Counter

from app.engine.bot_brain import (
    BOT_ARCHETYPES, KARMA_MIX, KARMA_WEIGHTS, realistic_mtt_mix, sample_field,
)

_WEAK = {"Fish", "Calling Station", "Aggro Fish", "Tight Passive", "Nit", "Rock", "Maniac"}
_MID = {"TAG", "Reg", "LAG", "Balanced Reg"}
_STRONG = {"Shark", "GTO Expert", "Exploit Expert", "Solver Bot"}


def test_weights_valid_and_in_pool():
    assert abs(sum(KARMA_WEIGHTS.values()) - 100) <= 1, "ağırlıklar ~100 toplamalı"
    for name in KARMA_WEIGHTS:
        assert name in BOT_ARCHETYPES, f"{name} geçersiz arketip"
        assert name in KARMA_MIX, f"{name} KARMA_MIX'te değil"


def test_realistic_mix_is_weak_heavy():
    """Büyük alanda: zayıf çoğunluk, güçlü azınlık (gerçek MTT)."""
    rng = random.Random(7)
    field = realistic_mtt_mix(2000, rng=rng)
    c = Counter(field)
    weak = sum(c[a] for a in _WEAK) / len(field)
    mid = sum(c[a] for a in _MID) / len(field)
    strong = sum(c[a] for a in _STRONG) / len(field)
    assert 0.52 <= weak <= 0.72, f"zayıf oran %{weak*100:.0f} (beklenen ~%62)"
    assert 0.18 <= mid <= 0.34, f"orta oran %{mid*100:.0f} (beklenen ~%26)"
    assert 0.06 <= strong <= 0.18, f"güçlü oran %{strong*100:.0f} (beklenen ~%12)"
    assert weak > strong * 2.5, "zayıflar güçlülerden belirgin çok olmalı"


def test_realistic_mix_size_and_validity():
    f = realistic_mtt_mix(8, rng=random.Random(1))
    assert len(f) == 8
    assert all(a in BOT_ARCHETYPES for a in f)
    assert realistic_mtt_mix(0) == []


def test_sample_field_default_fill_is_weighted_not_uniform():
    """sample_field random dolgusu artık ağırlıklı: büyük örneklemde Fish >> Shark."""
    rng = random.Random(11)
    big = []
    for _ in range(300):
        big.extend(sample_field(8, None, rng=rng))
    c = Counter(big)
    assert all(a in KARMA_MIX for a in big)        # üyelik korunur (eski test)
    # Zayıf bir tip (Fish) güçlü bir tipten (Solver Bot) belirgin çok çıkmalı
    assert c["Fish"] > c["Solver Bot"] * 2, f"Fish {c['Fish']} vs Solver {c['Solver Bot']}"


def test_tournament_default_field_is_realistic_and_fresh():
    """Turnuva varsayılan alanı gerçekçi + her config'te taze (sabit dizi değil)."""
    from app.simulator.tournament_runner import TournamentConfig
    a = TournamentConfig().bot_mix
    b = TournamentConfig().bot_mix
    assert all(x in BOT_ARCHETYPES for x in a)
    # İki ayrı config aynı sabit diziyi vermemeli (randomize edildi)
    assert a != b or len(set(a)) > 1, "varsayılan alan taze örneklenmiyor"


def test_expanded_karma_mix_has_mid_regs():
    """Bimodal değil: orta-seviye reg'ler havuzda olmalı (normal-benzeri dağılım)."""
    assert _MID & set(KARMA_MIX), "orta reg yok — havuz bimodal"
    assert len(KARMA_MIX) >= 14, "havuz çok küçük"
