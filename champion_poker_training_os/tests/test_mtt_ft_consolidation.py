"""D247: FT konsolidasyonu — final masaya inerken arka-plan oyuncuları hero masasına
birleşir; aksi halde header sayısı feltteki oyuncudan 1 (veya daha) fazla görünür
(kullanıcı yakaladı: header 6/200 ama feltte 5 oyuncu)."""
from app.simulator.mtt_field import MTTField


def _ft_field():
    f = MTTField(field_size=200, buyin=22.0, structure="regular", hero_table_size=6)
    f._bg = {"weak": 1, "mid": 0, "strong": 0}   # FT'de 1 hayalet bg
    f.update_hero_table(5)                         # hero masasında gerçek 5
    return f


def test_phantom_before_consolidation():
    """Bug durumu: FT'de bg=1 → header(6) feltten(5) fazla."""
    f = _ft_field()
    assert f.is_final_table
    assert f.players_remaining == 6
    assert f._hero_table_remaining == 5            # felt 5 gösterir → fark 1


def test_consolidation_drains_bg_to_zero():
    """FT konsolidasyonu (screen mantığı): bg → hero masası, hayalet kapanır."""
    f = _ft_field()
    need = min(6, f.players_remaining) - 5          # seats=6
    moved = f.move_into_hero_table(need)
    f.update_hero_table(5 + moved)
    assert moved == 1
    assert f.bg_players_remaining == 0
    assert f.players_remaining == f._hero_table_remaining == 6   # header == felt


def test_players_remaining_invariant():
    """Konsolidasyon TOPLAM sayıyı değiştirmez (sadece bg→hero aktarır)."""
    f = _ft_field()
    before = f.players_remaining
    f.move_into_hero_table(1)
    assert f.players_remaining == before           # 6 → 6 (eleme değil, taşıma)
