from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


SKILL_CATEGORIES = [
    {"id": "preflop", "name": "Preflop Foundation", "icon": "🃏", "description": "RFI ranges, 3bet/4bet, squeeze, blind defense"},
    {"id": "blind_defense", "name": "Blind Defense", "icon": "🛡️", "description": "BB vs BTN, SB strategy, defend frequency"},
    {"id": "three_bet", "name": "3Bet Pots", "icon": "⚡", "description": "3bet construction, 4bet/5bet, cold call, squeeze"},
    {"id": "flop", "name": "Flop Strategy", "icon": "🎯", "description": "Cbet, check-raise, board texture, range advantage"},
    {"id": "turn", "name": "Turn Strategy", "icon": "🔄", "description": "Double barrel, probe, delayed cbet, turn sizing"},
    {"id": "river", "name": "River Strategy", "icon": "🏁", "description": "Bluff-catch, thin value, blockers, MDF"},
    {"id": "icm", "name": "ICM", "icon": "💰", "description": "Bubble, final table, risk premium, chipEV vs $EV"},
    {"id": "pko", "name": "PKO", "icon": "🎯", "description": "Bounty EV, adjusted ranges, PKO dynamics"},
    {"id": "math", "name": "Math Reflex", "icon": "🧮", "description": "Pot odds, Alpha, MDF, EV, Bayes, combos"},
    {"id": "exploit", "name": "Exploit Adjustments", "icon": "🔍", "description": "Player profiling, tendency exploit, pool adjust"},
    {"id": "mental", "name": "Mental Discipline", "icon": "🧠", "description": "Tilt control, session discipline, study habits"},
    {"id": "tournament", "name": "Tournament Pressure", "icon": "🏆", "description": "Stack management, aggression, survival"},
]

ACHIEVEMENTS = [
    {"id": "drills_100", "name": "Century Driller", "description": "Complete 100 drills", "icon": "💯", "condition": "drills >= 100", "xp": 200},
    {"id": "drills_500", "name": "Drill Sergeant", "description": "Complete 500 drills", "icon": "🎖️", "condition": "drills >= 500", "xp": 500},
    {"id": "drills_1000", "name": "Drill Master", "description": "Complete 1000 drills", "icon": "⭐", "condition": "drills >= 1000", "xp": 1000},
    {"id": "streak_7", "name": "Week Warrior", "description": "7-day training streak", "icon": "🔥", "condition": "streak >= 7", "xp": 300},
    {"id": "streak_30", "name": "Monthly Machine", "description": "30-day training streak", "icon": "🌟", "condition": "streak >= 30", "xp": 800},
    {"id": "icm_zero", "name": "ICM Clean", "description": "Zero ICM punts in a week", "icon": "🛡️", "condition": "icm_punts_week == 0", "xp": 400},
    {"id": "river_master", "name": "River Blocker Master", "description": "River accuracy >80% over 50 decisions", "icon": "🏁", "condition": "river_accuracy >= 80", "xp": 350},
    {"id": "bb_repair", "name": "BB Defend Repaired", "description": "BB defend leak fixed (deviation <5%)", "icon": "🛡️", "condition": "bb_deviation < 5", "xp": 300},
    {"id": "math_90", "name": "Math Genius", "description": "Math reflex score 90+", "icon": "🧮", "condition": "math_reflex >= 90", "xp": 400},
    {"id": "final_table_boss", "name": "Final Table Boss", "description": "Complete final table combat pack with 80%+ accuracy", "icon": "🏆", "condition": "ft_pack_accuracy >= 80", "xp": 500},
    {"id": "hands_10k", "name": "Volume King", "description": "Analyze 10,000 hands", "icon": "📊", "condition": "hands_analyzed >= 10000", "xp": 600},
    {"id": "combat_all", "name": "Combat Veteran", "description": "Complete all combat packs", "icon": "⚔️", "condition": "all_packs_complete", "xp": 1000},
    {"id": "preflop_85", "name": "Preflop Solid", "description": "Preflop accuracy >85%", "icon": "🃏", "condition": "preflop_accuracy >= 85", "xp": 300},
    {"id": "ev_loss_20", "name": "EV Optimizer", "description": "EV loss <20bb/100 decisions", "icon": "📉", "condition": "ev_loss_100 < 20", "xp": 400},
    {"id": "study_plan", "name": "Plan Follower", "description": "Complete a full study plan", "icon": "📋", "condition": "plan_complete", "xp": 500},
]


@dataclass
class SkillNode:
    """A single skill in the skill tree."""
    id: str
    name: str
    icon: str
    description: str
    level: int = 1
    xp: int = 0
    mastery: float = 0.0

    @property
    def xp_for_next_level(self) -> int:
        """XP required to reach the next level."""
        return self.level * 150 + 50

    @property
    def level_progress(self) -> float:
        """Progress toward next level as a percentage."""
        needed = self.xp_for_next_level
        return min(100.0, (self.xp / needed) * 100) if needed > 0 else 100.0

    def add_xp(self, amount: int) -> bool:
        """Add XP and return True if leveled up."""
        self.xp += amount
        leveled = False
        while self.xp >= self.xp_for_next_level and self.level < 10:
            self.xp -= self.xp_for_next_level
            self.level += 1
            self.mastery = min(100.0, self.level * 10.0)
            leveled = True
        return leveled

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "icon": self.icon,
            "description": self.description, "level": self.level,
            "xp": self.xp, "mastery": self.mastery,
            "xp_next": self.xp_for_next_level, "progress": self.level_progress,
        }


@dataclass
class Achievement:
    """A single achievement."""
    id: str
    name: str
    description: str
    icon: str
    condition: str
    xp: int
    unlocked: bool = False
    unlocked_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "description": self.description,
            "icon": self.icon, "xp": self.xp, "unlocked": self.unlocked,
            "unlocked_at": self.unlocked_at,
        }


@dataclass
class SkillTree:
    """Manages the player's skill tree and achievements."""
    nodes: Dict[str, SkillNode] = field(default_factory=dict)
    achievements: Dict[str, Achievement] = field(default_factory=dict)
    total_xp: int = 0

    def __post_init__(self):
        if not self.nodes:
            for cat in SKILL_CATEGORIES:
                self.nodes[cat["id"]] = SkillNode(
                    id=cat["id"], name=cat["name"],
                    icon=cat["icon"], description=cat["description"],
                )
        if not self.achievements:
            for ach in ACHIEVEMENTS:
                self.achievements[ach["id"]] = Achievement(
                    id=ach["id"], name=ach["name"], description=ach["description"],
                    icon=ach["icon"], condition=ach["condition"], xp=ach["xp"],
                )

    @property
    def overall_level(self) -> int:
        """Average level across all skill nodes."""
        if not self.nodes:
            return 1
        return max(1, sum(n.level for n in self.nodes.values()) // len(self.nodes))

    @property
    def overall_mastery(self) -> float:
        """Average mastery across all skill nodes."""
        if not self.nodes:
            return 0.0
        return round(sum(n.mastery for n in self.nodes.values()) / len(self.nodes), 1)

    @property
    def unlocked_count(self) -> int:
        return sum(1 for a in self.achievements.values() if a.unlocked)

    def grant_xp(self, category: str, amount: int) -> dict:
        """Grant XP to a skill category. Returns info about level-ups."""
        result = {"category": category, "xp_granted": amount, "leveled_up": False, "new_level": 0}
        if category in self.nodes:
            node = self.nodes[category]
            leveled = node.add_xp(amount)
            self.total_xp += amount
            result["leveled_up"] = leveled
            result["new_level"] = node.level
        return result

    def unlock_achievement(self, achievement_id: str) -> Optional[Achievement]:
        """Unlock an achievement if not already unlocked."""
        if achievement_id in self.achievements:
            ach = self.achievements[achievement_id]
            if not ach.unlocked:
                ach.unlocked = True
                import datetime
                ach.unlocked_at = datetime.datetime.now().isoformat()
                return ach
        return None

    def check_achievements(self, stats: dict) -> List[Achievement]:
        """Check all achievements against current stats and unlock any earned."""
        newly_unlocked = []
        checks = {
            "drills_100": stats.get("drills", 0) >= 100,
            "drills_500": stats.get("drills", 0) >= 500,
            "drills_1000": stats.get("drills", 0) >= 1000,
            "streak_7": stats.get("streak", 0) >= 7,
            "streak_30": stats.get("streak", 0) >= 30,
            "icm_zero": stats.get("icm_punts_week", 99) == 0,
            "river_master": stats.get("river_accuracy", 0) >= 80,
            "bb_repair": stats.get("bb_deviation", 99) < 5,
            "math_90": stats.get("math_reflex", 0) >= 90,
            "final_table_boss": stats.get("ft_pack_accuracy", 0) >= 80,
            "hands_10k": stats.get("hands_analyzed", 0) >= 10000,
            "combat_all": stats.get("all_packs_complete", False),
            "preflop_85": stats.get("preflop_accuracy", 0) >= 85,
            "ev_loss_20": stats.get("ev_loss_100", 999) < 20,
            "study_plan": stats.get("plan_complete", False),
        }
        for ach_id, earned in checks.items():
            if earned and ach_id in self.achievements and not self.achievements[ach_id].unlocked:
                ach = self.unlock_achievement(ach_id)
                if ach:
                    newly_unlocked.append(ach)
        return newly_unlocked

    def get_summary(self) -> dict:
        return {
            "overall_level": self.overall_level,
            "overall_mastery": self.overall_mastery,
            "total_xp": self.total_xp,
            "categories": [n.to_dict() for n in self.nodes.values()],
            "achievements_unlocked": self.unlocked_count,
            "achievements_total": len(self.achievements),
        }


# Pre-built demo skill tree with some progress
def demo_skill_tree() -> SkillTree:
    """Create a demo skill tree with some XP already earned."""
    tree = SkillTree()
    demo_xp = {
        "preflop": 280, "blind_defense": 150, "three_bet": 120,
        "flop": 220, "turn": 180, "river": 160,
        "icm": 200, "pko": 90, "math": 250,
        "exploit": 100, "mental": 70, "tournament": 170,
    }
    for cat, xp in demo_xp.items():
        tree.grant_xp(cat, xp)

    # Unlock some demo achievements
    demo_stats = {
        "drills": 142, "streak": 6, "preflop_accuracy": 84,
        "math_reflex": 81, "river_accuracy": 68,
    }
    tree.check_achievements(demo_stats)
    return tree
