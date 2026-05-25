"""Live HUD — oyun sırasında botların gözlemlenen aksiyonlarını takip eder.

Her el tamamlandığında `update(hand)` çağrılır; her seat için:
  • VPIP, PFR, 3-bet, Fold-to-cbet, Aggression Factor, WTSD
  • Dinamik olarak güncellenir

Kullanım:
    hud = LiveHUD(player_count=6)
    hud.update(hand_result_actions)
    stats = hud.get(seat_idx)  # → dict
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class _SeatStats:
    hands_seen: int = 0
    # Preflop
    vpip_count: int = 0       # VPIP: call/raise preflop (not fold/check BB w/o raise)
    pfr_count: int  = 0       # PFR: raise/3bet preflop
    threebet_opp: int = 0     # 3-bet opportunities (faced an open)
    threebet_did: int = 0     # Actually 3-bet
    # Postflop
    cbet_faced: int = 0
    cbet_folded: int = 0
    aggr_bets: int  = 0       # aggressive actions (bet/raise)
    passive_acts: int = 0     # passive (call)
    # Showdown
    wtsd: int = 0             # went to SD
    wsd:  int = 0             # won at SD

    @property
    def vpip(self) -> float:
        return 100 * self.vpip_count / max(self.hands_seen, 1)

    @property
    def pfr(self) -> float:
        return 100 * self.pfr_count / max(self.hands_seen, 1)

    @property
    def three_bet_pct(self) -> float:
        return 100 * self.threebet_did / max(self.threebet_opp, 1)

    @property
    def fold_to_cbet(self) -> float:
        return 100 * self.cbet_folded / max(self.cbet_faced, 1)

    @property
    def af(self) -> float:
        """Aggression Factor = (bet+raise) / call (postflop)."""
        return self.aggr_bets / max(self.passive_acts, 1)

    @property
    def wtsd_pct(self) -> float:
        return 100 * self.wtsd / max(self.hands_seen, 1)

    @property
    def wsd_pct(self) -> float:
        return 100 * self.wsd / max(self.wtsd, 1)


class LiveHUD:
    """Tüm oyunculara ait dinamik HUD istatistiklerini tutar."""

    def __init__(self, player_count: int = 9):
        self._stats: Dict[int, _SeatStats] = {
            i: _SeatStats() for i in range(player_count)
        }

    def reset(self, player_count: int) -> None:
        self._stats = {i: _SeatStats() for i in range(player_count)}

    def update_from_hand(self, hand) -> None:
        """HandState'i okuyarak tüm oyuncular için HUD'u güncelle."""
        if not hand or not getattr(hand, "is_complete", False):
            return

        from app.engine.hand_state import ActionType, Street

        players = hand.players
        actions = getattr(hand, "actions", [])
        winners = set(getattr(hand, "winners", []) or [])

        for idx, p in enumerate(players):
            if getattr(p, "is_eliminated", False):
                continue
            if idx not in self._stats:
                self._stats[idx] = _SeatStats()
            s = self._stats[idx]
            s.hands_seen += 1

            # VPIP / PFR — preflop voluntary actions
            pf_actions = [a for a in actions
                          if a.player_idx == idx and a.street == Street.PREFLOP]
            did_voluntary = any(
                a.action_type in (ActionType.CALL, ActionType.RAISE,
                                  ActionType.BET, ActionType.ALL_IN)
                for a in pf_actions
            )
            if did_voluntary:
                s.vpip_count += 1

            did_raise_pf = any(
                a.action_type in (ActionType.RAISE, ActionType.BET, ActionType.ALL_IN)
                for a in pf_actions
            )
            if did_raise_pf:
                s.pfr_count += 1

            # 3-bet: if there was a raise before this player and they re-raised
            pre_raises = [
                a for a in actions
                if a.street == Street.PREFLOP
                and a.player_idx != idx
                and a.action_type in (ActionType.RAISE, ActionType.BET)
            ]
            my_pf_raises = [
                a for a in pf_actions
                if a.action_type in (ActionType.RAISE, ActionType.BET, ActionType.ALL_IN)
            ]
            if pre_raises:
                s.threebet_opp += 1
                if len(my_pf_raises) >= 1:
                    s.threebet_did += 1

            # Postflop: aggression + fold-to-cbet
            post_actions = [a for a in actions
                            if a.player_idx == idx and a.street != Street.PREFLOP]
            for pa in post_actions:
                if pa.action_type in (ActionType.BET, ActionType.RAISE, ActionType.ALL_IN):
                    s.aggr_bets += 1
                elif pa.action_type == ActionType.CALL:
                    s.passive_acts += 1

            # Fold to cbet: if someone bet on flop and this player folded
            flop_bets = [a for a in actions
                         if a.street == Street.FLOP and a.player_idx != idx
                         and a.action_type in (ActionType.BET, ActionType.RAISE)]
            if flop_bets:
                my_flop = [a for a in actions
                           if a.street == Street.FLOP and a.player_idx == idx]
                if my_flop:
                    s.cbet_faced += 1
                    if any(a.action_type == ActionType.FOLD for a in my_flop):
                        s.cbet_folded += 1

            # WTSD / WSD
            reached_sd = bool(getattr(hand, "community", None) and
                               len(getattr(hand, "community", [])) == 5 and
                               not getattr(p, "is_folded", True))
            if reached_sd:
                s.wtsd += 1
                if idx in winners:
                    s.wsd += 1

    def get(self, seat_idx: int) -> Optional[dict]:
        """Bir oyuncunun dinamik HUD istatistiklerini döner."""
        s = self._stats.get(seat_idx)
        if not s or s.hands_seen < 1:
            return None
        return {
            "obs_hands":    s.hands_seen,
            "vpip":         round(s.vpip, 1),
            "pfr":          round(s.pfr, 1),
            "three_bet":    round(s.three_bet_pct, 1),
            "fold_to_cbet": round(s.fold_to_cbet, 1),
            "af":           round(s.af, 2),
            "wtsd":         round(s.wtsd_pct, 1),
            "wsd":          round(s.wsd_pct, 1),
        }

    def merge_with_profile(self, seat_idx: int, base_profile: dict) -> dict:
        """Gözlemlenen stats ile bot profilini birleştir.

        Az veri varsa (< 10 el) base_profile'a yakın ağırlık ver.
        Yeterli veri varsa (>= 10 el) gözlemlenen değerleri ön plana çıkar.
        """
        obs = self.get(seat_idx)
        if not obs or obs["obs_hands"] < 3:
            return base_profile   # yeterli veri yok — sadece profile göster

        n = obs["obs_hands"]
        weight = min(n / 20.0, 1.0)   # 0..1, 20 elde tam ağırlık

        def blend(obs_val, base_val):
            return round(obs_val * weight + base_val * (1 - weight), 1)

        merged = dict(base_profile)
        merged.update({
            "vpip":         blend(obs["vpip"],         base_profile.get("vpip", obs["vpip"])),
            "pfr":          blend(obs["pfr"],          base_profile.get("pfr", obs["pfr"])),
            "three_bet":    blend(obs["three_bet"],    base_profile.get("three_bet", obs["three_bet"])),
            "fold_to_cbet": blend(obs["fold_to_cbet"], base_profile.get("fold_to_cbet", obs["fold_to_cbet"])),
            "af":           blend(obs["af"],           base_profile.get("af", base_profile.get("aggression", obs["af"]))),
            "obs_hands":    n,
            "notes":        base_profile.get("notes", ""),
        })
        return merged
