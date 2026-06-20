"""Full playable tournament runner.

Wraps PokerGame with:
- Blind level schedule (chips, not BB)
- Antes after level 5
- Hand persistence to DB
- Hero leak analysis on session end
- ICM-aware bot mix (more nits late, more LAGs early)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.engine.game_loop import PokerGame, HandResult
from app.engine.hand_state import ActionType, Street


@dataclass
class BlindLevel:
    level: int
    sb: int
    bb: int
    ante: int = 0
    duration_min: int = 10  # purely informational


# ── Big Blind Ante (BBA) — modern online MTT standardı ───────────────────
# Gerçek online turnuvalarda (PokerStars/GGPoker, ~2018 sonrası) ante artık
# "Big Blind Ante": BB oyuncusu masanın tüm ante'sini (≈1× BB) postalar ve
# bu ELE 1 BÜYÜK KÖR kadar ÖLÜ PARA ekler. Antesiz erken seviye YOKTUR.
#
# Bizim motor PER-PLAYER ante modeli (toplam = n·ante). BBA'yı (toplam ≈ 1 BB)
# bu modele çevirmek için per-player ante ≈ BB/n ≈ %12.5 BB (9-max). Böylece
# pot preflop ~1 BB büyür → açış range'leri gerçekçi şekilde genişler.
def _bb_ante(bb: int) -> int:
    """BBA-eşdeğeri per-player ante ≈ %12.5 BB (temiz çipe yuvarlı, min 1)."""
    return max(1, int(bb * 0.125 + 0.5))


def _with_bba(levels: List["BlindLevel"]) -> List["BlindLevel"]:
    """Her seviyenin ante'sini BBA-eşdeğeriyle (≈%12.5 BB) doldur — L1 dahil."""
    for lv in levels:
        lv.ante = _bb_ante(lv.bb)
    return levels


def regular_structure(starting_bb: int = 100) -> List[BlindLevel]:
    """Standard MTT — slow rise. Ante L1'den itibaren (BBA konvansiyonu)."""
    return _with_bba([
        BlindLevel(1, 10, 20, 0, 12),
        BlindLevel(2, 15, 30, 0, 12),
        BlindLevel(3, 25, 50, 0, 12),
        BlindLevel(4, 50, 100, 0, 12),
        BlindLevel(5, 75, 150, 0, 12),
        BlindLevel(6, 100, 200, 0, 12),
        BlindLevel(7, 150, 300, 0, 12),
        BlindLevel(8, 200, 400, 0, 12),
        BlindLevel(9, 300, 600, 0, 10),
        BlindLevel(10, 400, 800, 0, 10),
        BlindLevel(11, 500, 1000, 0, 10),
        BlindLevel(12, 750, 1500, 0, 10),
        BlindLevel(13, 1000, 2000, 0, 10),
        BlindLevel(14, 1500, 3000, 0, 10),
        BlindLevel(15, 2000, 4000, 0, 8),
        BlindLevel(16, 3000, 6000, 0, 8),
        BlindLevel(17, 4000, 8000, 0, 8),
        BlindLevel(18, 5000, 10000, 0, 8),
        BlindLevel(19, 7500, 15000, 0, 8),
        BlindLevel(20, 10000, 20000, 0, 8),
    ])


def turbo_structure() -> List[BlindLevel]:
    """Turbo — faster blind levels. Ante L1'den itibaren (BBA)."""
    return _with_bba([
        BlindLevel(1, 10, 20, 0, 5),
        BlindLevel(2, 25, 50, 0, 5),
        BlindLevel(3, 50, 100, 0, 5),
        BlindLevel(4, 100, 200, 0, 5),
        BlindLevel(5, 150, 300, 0, 5),
        BlindLevel(6, 250, 500, 0, 5),
        BlindLevel(7, 400, 800, 0, 5),
        BlindLevel(8, 600, 1200, 0, 5),
        BlindLevel(9, 1000, 2000, 0, 5),
        BlindLevel(10, 1500, 3000, 0, 5),
        BlindLevel(11, 2500, 5000, 0, 5),
        BlindLevel(12, 4000, 8000, 0, 5),
        BlindLevel(13, 6000, 12000, 0, 4),
        BlindLevel(14, 10000, 20000, 0, 4),
    ])


def hyper_structure() -> List[BlindLevel]:
    """Hyper — ante L1'den itibaren (BBA)."""
    return _with_bba([
        BlindLevel(1, 25, 50, 0, 3),
        BlindLevel(2, 75, 150, 0, 3),
        BlindLevel(3, 150, 300, 0, 3),
        BlindLevel(4, 300, 600, 0, 3),
        BlindLevel(5, 600, 1200, 0, 3),
        BlindLevel(6, 1200, 2400, 0, 3),
        BlindLevel(7, 2500, 5000, 0, 3),
        BlindLevel(8, 5000, 10000, 0, 3),
    ])


# Default payout structures (% of prize pool)
# 9-max → top 3 paid  (realistic MTT payout)
# 6-max → top 2 paid  (typical SNG / 6-handed)
PAYOUT_STRUCTURES = {
    "9-max": [
        (1, 0.50), (2, 0.30), (3, 0.20),
    ],
    "6-max": [
        (1, 0.65), (2, 0.35),
    ],
    "Heads-Up": [(1, 1.0)],
}


@dataclass
class TournamentConfig:
    name: str = "$22 Bounty Hunter"
    field_size: int = 9
    starting_chips: int = 2000
    structure: str = "regular"  # regular | turbo | hyper
    buyin: float = 22.0
    payout_key: str = "9-max"
    hands_per_level: int = 12  # How many hands before blinds go up
    # Varsayılan alan GERÇEKÇİ MTT dağılımı (zayıf-ağırlıklı) + her turnuvada
    # TAZE örneklenir (aynı diziyi tekrar etmez). Kullanıcı tournament_simulator'da
    # özel bir mix seçerse o aynen kullanılır.
    bot_mix: List[str] = field(
        default_factory=lambda: __import__(
            "app.engine.bot_brain", fromlist=["realistic_mtt_mix"]
        ).realistic_mtt_mix(12))
    hero_range_filter: str = ""   # "" = all hands; "Premium" / "TAG Range" / etc.

    @property
    def total_chips(self) -> int:
        return self.starting_chips * self.field_size

    @property
    def prize_pool(self) -> float:
        return self.buyin * self.field_size

    @property
    def paid_places(self) -> int:
        return len(PAYOUT_STRUCTURES.get(self.payout_key, []))


@dataclass
class TournamentState:
    config: TournamentConfig
    level_idx: int = 0
    hands_this_level: int = 0
    hands_total: int = 0
    players_left: int = 0
    is_complete: bool = False
    finish_position: Optional[int] = None
    prize_won: float = 0.0
    levels: List[BlindLevel] = field(default_factory=list)
    eliminated_order: List[int] = field(default_factory=list)  # Player indices in order they busted

    @property
    def current_level(self) -> BlindLevel:
        if not self.levels:
            return BlindLevel(1, 10, 20)
        return self.levels[min(self.level_idx, len(self.levels) - 1)]

    @property
    def hands_until_next_level(self) -> int:
        return max(0, self.config.hands_per_level - self.hands_this_level)


class Tournament:
    """Single-table tournament runner. Hero + bots play until 1 left or hero busts."""

    def __init__(self, config: TournamentConfig):
        self.config = config
        if config.structure == "turbo":
            levels = turbo_structure()
        elif config.structure == "hyper":
            levels = hyper_structure()
        else:
            levels = regular_structure()

        self.state = TournamentState(
            config=config,
            levels=levels,
            players_left=config.field_size,
        )

        # Build the game
        level = self.state.current_level
        # Distribute archetypes
        bot_archs = (config.bot_mix * ((config.field_size // len(config.bot_mix)) + 1))[:config.field_size - 1]
        bot_names = [f"villain_{i}" for i in range(1, config.field_size)]
        self.game = PokerGame(
            num_players=config.field_size,
            starting_stack=float(config.starting_chips),
            small_blind=float(level.sb),
            big_blind=float(level.bb),
            ante=float(level.ante),
            hero_seat=0,
            bot_archetypes=bot_archs,
            player_names=bot_names,
            hero_range_filter=config.hero_range_filter,
        )
        self.hand_log: List[HandResult] = []

    # ── RESUME (D295): hand-boundary snapshot/restore (donma/çökme/kapanmada kayıp YOK) ──
    def to_dict(self) -> dict:
        """El-arası temiz state → resume için serileştir (mid-hand fragile kısım hariç)."""
        cfg = self.config
        hrf = cfg.hero_range_filter
        if isinstance(hrf, (set, frozenset)):
            hrf = sorted(str(x) for x in hrf)
        return {
            "config": {
                "name": cfg.name, "field_size": cfg.field_size,
                "starting_chips": cfg.starting_chips, "structure": cfg.structure,
                "buyin": cfg.buyin, "payout_key": cfg.payout_key,
                "hands_per_level": cfg.hands_per_level, "bot_mix": list(cfg.bot_mix),
                "hero_range_filter": hrf,
            },
            "state": {
                "level_idx": self.state.level_idx, "hands_this_level": self.state.hands_this_level,
                "hands_total": self.state.hands_total, "players_left": self.state.players_left,
                "is_complete": self.state.is_complete, "finish_position": self.state.finish_position,
                "prize_won": self.state.prize_won, "eliminated_order": list(self.state.eliminated_order),
            },
            "dealer_idx": self.game.dealer_idx,
            "seats": [{"stack": float(p.stack), "position": p.position,
                       "is_eliminated": bool(p.is_eliminated), "name": p.name,
                       "archetype": (self.game.bots[i].profile.name
                                     if i in self.game.bots and getattr(self.game.bots[i], "profile", None)
                                     else None)}
                      for i, p in enumerate(self.game.players)],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Tournament":
        """Snapshot'tan turnuvayı yeniden kur (stack'ler/blind-level/seat'ler aynı)."""
        c = d["config"]
        hrf = c.get("hero_range_filter", "")
        if isinstance(hrf, list):
            hrf = set(hrf) if hrf else ""
        config = TournamentConfig(
            name=c["name"], field_size=c["field_size"], starting_chips=c["starting_chips"],
            structure=c["structure"], buyin=c["buyin"], payout_key=c["payout_key"],
            hands_per_level=c["hands_per_level"], bot_mix=list(c["bot_mix"]),
            hero_range_filter=hrf,
        )
        t = cls(config)
        s = d["state"]
        t.state.level_idx = int(s["level_idx"]); t.state.hands_this_level = int(s["hands_this_level"])
        t.state.hands_total = int(s["hands_total"]); t.state.players_left = int(s["players_left"])
        t.state.is_complete = bool(s.get("is_complete", False))
        t.state.finish_position = s.get("finish_position")
        t.state.prize_won = float(s.get("prize_won", 0.0))
        t.state.eliminated_order = list(s.get("eliminated_order", []))
        t.game.dealer_idx = int(d.get("dealer_idx", 0))
        lvl = t.state.current_level
        t.game.set_blinds(float(lvl.sb), float(lvl.bb), float(lvl.ante))
        # Seat stack/eliminated geri yükle; refilled-seat arketipini de geri ver (sadık bot)
        from app.engine.bot_brain import BOT_ARCHETYPES, BotBrain
        for i, sd in enumerate(d.get("seats", [])):
            if i >= len(t.game.players):
                break
            p = t.game.players[i]
            p.stack = float(sd["stack"]); p.is_eliminated = bool(sd.get("is_eliminated", False))
            if sd.get("position"):
                p.position = sd["position"]
            arch = sd.get("archetype")
            if arch and i in t.game.bots and arch in BOT_ARCHETYPES:
                try:
                    t.game.bots[i] = BotBrain(BOT_ARCHETYPES[arch])
                except Exception:
                    pass
        return t

    # ── PUBLIC API ─────────────────────────────────────────────────

    @property
    def is_complete(self) -> bool:
        return self.state.is_complete

    @property
    def hero_chips(self) -> float:
        return self.game.players[self.game.hero_seat].stack

    @property
    def hero_busted(self) -> bool:
        hero = self.game.players[self.game.hero_seat]
        return hero.is_eliminated or hero.stack <= 0

    @property
    def players_remaining(self) -> int:
        return sum(1 for p in self.game.players if not p.is_eliminated)

    def start_hand(self):
        if self.state.is_complete:
            return None
        # Bump blind level if needed
        if self.state.hands_this_level >= self.config.hands_per_level:
            self.state.level_idx = min(self.state.level_idx + 1, len(self.state.levels) - 1)
            self.state.hands_this_level = 0

        # Her el başında mevcut level'in blind+ante'sini SENKRONLA — eskiden
        # set_blinds yalnızca level atlayınca çağrılıyordu; level_idx başka
        # yoldan değişirse (late-reg, restore) ante kesilmeden kalıyordu.
        lvl = self.state.current_level
        self.game.set_blinds(float(lvl.sb), float(lvl.bb), float(lvl.ante))

        # Track who is in
        pre_alive = {i for i, p in enumerate(self.game.players) if not p.is_eliminated}
        hand = self.game.start_hand()
        return hand

    def hero_act(self, action_type: ActionType, amount: float = 0.0):
        if self.state.is_complete:
            return None
        hand = self.game.hero_act(action_type, amount)
        self._post_hand_maybe()
        return hand

    def advance_after_hand_complete(self):
        """Call once a hand finishes to record stats & advance the tournament state."""
        self._post_hand_maybe()

    def _post_hand_maybe(self):
        if not self.game.current_hand or not self.game.current_hand.is_complete:
            return
        # Already recorded this hand?
        if self.game.hand_history and (not self.hand_log or self.hand_log[-1].hand_id != self.game.hand_history[-1].hand_id):
            result = self.game.hand_history[-1]
            self.hand_log.append(result)
            self.state.hands_total += 1
            self.state.hands_this_level += 1

            # Detect new eliminations
            for i, p in enumerate(self.game.players):
                if p.stack <= 0 and not p.is_eliminated:
                    p.is_eliminated = True
                if p.is_eliminated and i not in self.state.eliminated_order:
                    self.state.eliminated_order.append(i)

            self.state.players_left = self.players_remaining

            # Hero busted?
            if self.hero_busted:
                # Hero's finishing position = current players_remaining + 1
                finish = self.state.players_left + 1 if self.state.players_left < self.config.field_size else self.config.field_size
                # Actually finish = number of players still in when hero busted + 1
                finish = self.state.players_left + 1
                self.state.finish_position = finish
                self.state.prize_won = self._prize_for(finish)
                self.state.is_complete = True
                return

            # Single survivor → tournament over (hero won)
            if self.state.players_left <= 1:
                self.state.finish_position = 1
                self.state.prize_won = self._prize_for(1)
                self.state.is_complete = True

    def rebalance_hero_table(self, target_size: int, avg_stack: float) -> int:
        """Masa dengeleme — kırılan masalardan hero'nun masasına oyuncu taşı.

        Elenen bot koltuklarını taze oyuncularla (field bot_mix'ten) doldurur,
        her birine ~avg_stack chip verir. Gerçek MTT'de masalar kısalınca
        kırılıp oyuncular dağıtılır; bu, hero'nun masasını final masaya kadar
        dolu tutar (her seferinde yeni rakipler). Döner: yeni oturan sayısı.

        NOT: sadece eller arasında çağrılmalı (el ortasında değil).
        """
        import random as _random
        from app.engine.bot_brain import BotBrain, BOT_ARCHETYPES, KARMA_MIX

        active = [p for p in self.game.players if not p.is_eliminated]
        target_size = min(int(target_size), len(self.game.players))
        if len(active) >= target_size:
            return 0
        need = target_size - len(active)
        mix = [a for a in (self.config.bot_mix or KARMA_MIX)
               if a in BOT_ARCHETYPES] or list(KARMA_MIX)
        _names = ["seat_in", "moved", "redraw", "balanced", "incoming",
                  "newtable", "transfer", "fresh"]
        seated = 0
        for i, p in enumerate(self.game.players):
            if seated >= need:
                break
            if p.is_eliminated:
                arch = _random.choice(mix)
                prof = BOT_ARCHETYPES.get(arch, BOT_ARCHETYPES["Balanced Reg"])
                p.is_eliminated = False
                p.stack = max(1.0, float(avg_stack))
                p.name = f"{_random.choice(_names)}{i}"
                p.is_all_in = False
                p.is_folded = False
                p.current_bet = 0.0
                self.game.bots[i] = BotBrain(prof)
                if i in self.state.eliminated_order:
                    self.state.eliminated_order.remove(i)
                seated += 1
        if seated:
            self.state.players_left = self.players_remaining
        return seated

    def _prize_for(self, position: int) -> float:
        payouts = PAYOUT_STRUCTURES.get(self.config.payout_key, [])
        for pos, pct in payouts:
            if pos == position:
                return round(self.config.prize_pool * pct, 2)
        return 0.0

    # ── ANALYSIS ───────────────────────────────────────────────────

    def leak_report(self) -> dict:
        """Compute hero leaks from the hand log."""
        if not self.hand_log:
            return {
                "summary": "No hands played yet.",
                "stats": {},
                "leaks": [],
            }

        stats = self.game.get_session_stats()
        hero_idx = self.game.hero_seat
        total = len(self.hand_log)

        # Position breakdown
        position_stats: Dict[str, dict] = {}
        for h in self.hand_log:
            pos = h.hero_position or "?"
            ps = position_stats.setdefault(pos, {"hands": 0, "profit": 0.0, "vpip": 0, "pfr": 0})
            ps["hands"] += 1
            ps["profit"] += h.hero_profit
            voluntarily_in = any(
                a.player_idx == hero_idx and a.street == Street.PREFLOP
                and a.action_type in (ActionType.CALL, ActionType.BET, ActionType.RAISE, ActionType.ALL_IN)
                for a in h.actions
            )
            raised_pf = any(
                a.player_idx == hero_idx and a.street == Street.PREFLOP
                and a.action_type in (ActionType.BET, ActionType.RAISE, ActionType.ALL_IN)
                for a in h.actions
            )
            if voluntarily_in:
                ps["vpip"] += 1
            if raised_pf:
                ps["pfr"] += 1

        # Compute % stats per position
        for pos, ps in position_stats.items():
            n = max(ps["hands"], 1)
            ps["vpip_pct"] = round(100 * ps["vpip"] / n, 1)
            ps["pfr_pct"] = round(100 * ps["pfr"] / n, 1)
            ps["bb_per_100"] = round(100 * ps["profit"] / (n * self.game.big_blind), 1) if self.game.big_blind else 0

        # Leaks
        leaks: List[dict] = []
        vpip = stats.get("vpip", 0)
        pfr = stats.get("pfr", 0)
        wtsd = stats.get("wtsd", 0)

        if vpip > 38:
            leaks.append({
                "name": "Too loose preflop",
                "severity": "HIGH",
                "detail": f"VPIP {vpip}% — target 20-28% in tournaments. You're playing trash hands voluntarily.",
                "fix": "Use the position-aware open ranges (UTG: top 14%, BTN: top 40%).",
                "ev_loss": round((vpip - 28) * 0.15, 2),
            })
        elif vpip < 14 and total > 15:
            leaks.append({
                "name": "Too tight preflop",
                "severity": "MEDIUM",
                "detail": f"VPIP {vpip}% — you're missing steal spots from BTN/CO and blind defense.",
                "fix": "Widen ranges in late position and defend BB vs late position opens.",
                "ev_loss": round((22 - vpip) * 0.10, 2),
            })

        gap = vpip - pfr
        if gap > 10 and total > 15:
            leaks.append({
                "name": "Passive preflop (calling station)",
                "severity": "HIGH",
                "detail": f"VPIP-PFR gap = {gap:.1f}% — too many limps/calls, too few raises.",
                "fix": "Open-raise (don't limp) when first in. 3-bet polarized vs late-position opens.",
                "ev_loss": round(gap * 0.12, 2),
            })

        if wtsd > 35 and total > 10:
            leaks.append({
                "name": "Going to showdown too often",
                "severity": "MEDIUM",
                "detail": f"WTSD {wtsd}% — calling too thin on turn/river.",
                "fix": "Use MDF + blocker logic. Fold marginal bluff-catchers vs polarized lines.",
                "ev_loss": round((wtsd - 28) * 0.15, 2),
            })

        # Position-specific
        for pos in ("UTG", "UTG+1"):
            ps = position_stats.get(pos)
            if ps and ps["hands"] >= 3 and ps["vpip_pct"] > 30:
                leaks.append({
                    "name": f"Too loose from {pos}",
                    "severity": "MEDIUM",
                    "detail": f"{pos} VPIP {ps['vpip_pct']}% over {ps['hands']} hands.",
                    "fix": f"From {pos} only play top ~14% (TT+, AQ+, KQs, suited connectors selectively).",
                    "ev_loss": round((ps['vpip_pct'] - 14) * 0.1, 2),
                })

        # Big losing positions
        for pos, ps in position_stats.items():
            if ps["hands"] >= 5 and ps["bb_per_100"] < -50:
                leaks.append({
                    "name": f"Losing badly from {pos}",
                    "severity": "HIGH",
                    "detail": f"{pos}: {ps['bb_per_100']}bb/100 over {ps['hands']} hands.",
                    "fix": f"Review {pos} ranges and post-flop play from this position.",
                    "ev_loss": abs(ps['bb_per_100']) / 100,
                })

        if not leaks:
            leaks.append({
                "name": "No major leaks detected",
                "severity": "INFO",
                "detail": f"Stats look healthy over {total} hands.",
                "fix": "Keep training. Push the edge into wider profitable spots.",
                "ev_loss": 0,
            })

        # Sort by severity then ev_loss
        sev_order = {"HIGH": 0, "MEDIUM": 1, "INFO": 2}
        leaks.sort(key=lambda l: (sev_order.get(l["severity"], 99), -l.get("ev_loss", 0)))

        return {
            "summary": (
                f"Hero played {total} hands · Finish: "
                f"{self.state.finish_position or 'live'} of {self.config.field_size} · "
                f"Prize: ${self.state.prize_won:.0f} / ${self.config.prize_pool:.0f}"
            ),
            "stats": stats,
            "position_stats": position_stats,
            "leaks": leaks,
            "biggest_pot": stats.get("biggest_pot", 0),
            "structure": self.config.structure,
        }
