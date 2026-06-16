"""D242: MTT playbook — kanonik evre tespiti TEK KAYNAK + stage stratejisi.

Çözülen bug: stage 3 yerde farklı eşiklerle (icm 0.6 vs 0.85, avg-stack) → tutarsız.
mtt_stage gerçek-yer (kalan-vs-ödeme) > icm > derinlik önceliğiyle TEK tanım verir."""
from app.poker.mtt_playbook import mtt_stage, stage_plan


def test_final_table_by_remaining():
    """9 veya az kalan → final table (gerçek-yer, en güvenilir)."""
    assert mtt_stage(players_remaining=9, paid_places=50)["stage"] == "final table"
    assert mtt_stage(players_remaining=6, paid_places=50)["stage"] == "final table"


def test_bubble_by_remaining_band():
    """Paranın hemen üstü bant → bubble (ICM eşiğine değil gerçek-yere bak)."""
    # paid=15 → bubble_top = ceil(15*1.15)+1 = 18; rem 16-18 bubble
    assert mtt_stage(players_remaining=16, paid_places=15)["stage"] == "bubble"
    assert mtt_stage(players_remaining=18, paid_places=15)["stage"] == "bubble"
    # rem=40 (paranın çok üstü) → bubble DEĞİL
    assert mtt_stage(players_remaining=40, paid_places=15, avg_stack_bb=30)["stage"] != "bubble"


def test_itm_post_money_pre_ft():
    """Parada ama FT-öncesi → itm."""
    assert mtt_stage(players_remaining=12, paid_places=15)["stage"] == "itm"


def test_ground_truth_beats_icm_threshold():
    """ÇELİŞKİ ÇÖZÜMÜ: gerçek-yer varken icm eşiği KULLANILMAZ (eski bug kaynağı).
    icm=0.95 (eski kod 'bubble' derdi) ama 40 kişi var, para 15 → bubble DEĞİL."""
    out = mtt_stage(players_remaining=40, paid_places=15, icm_pressure=0.95, avg_stack_bb=30)
    assert out["stage"] != "bubble"
    assert out["source"] == "depth"


def test_icm_fallback_when_no_seat_data():
    """Gerçek-yer yoksa icm-baskısı yön verir (rem=0)."""
    assert mtt_stage(icm_pressure=0.9)["stage"] == "bubble"
    assert mtt_stage(icm_pressure=0.5)["stage"] == "itm"


def test_depth_buckets_early_mid_late():
    """Para-öncesi → derinlik bucket'ı (early≥45, mid≥22, late<22)."""
    assert mtt_stage(avg_stack_bb=80)["stage"] == "early"
    assert mtt_stage(avg_stack_bb=30)["stage"] == "mid"
    assert mtt_stage(avg_stack_bb=12)["stage"] == "late"


def test_stage_plan_each_stage_has_priorities():
    """Her evre stratejik öncelik döndürür (playbook içeriği)."""
    for stg in ("early", "mid", "late", "bubble", "itm", "final table"):
        p = stage_plan(stg)
        assert p["priorities"] and p["headline"]
        assert p["stage"] == stg


def test_mtt_exploit_phase_uses_canonical_depth():
    """mtt_exploit._phase artık mtt_stage'den derinlik bucket'ı alır (tek kaynak)."""
    from app.poker.mtt_exploit import _phase
    assert _phase("", 80, 80) == "early"
    assert _phase("", 12, 12) == "late"
    assert _phase("bubble", 30, 30) == "bubble"   # açık stage öncelikli
