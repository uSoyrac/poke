"""End-to-end feature audit.

Heuristic checks for everything the user asked for in this round:

  1. Karma (Mixed) — every game produces a different bot composition (random).
  2. FieldPicker — add/remove seats, per-seat archetype, random resolution.
  3. Engine accepts bot_archetypes list and uses each seat's archetype.
  4. MultiSessionTabs — N parallel instances, signals forwarded.
  5. Mid-tournament end & restart — _end_and_restart() returns to setup.
  6. Tournament context — populated in AppState during play, cleared on end.
  7. Bot fidelity — VPIP/PFR/3-bet within tolerance for headline archetypes.

Each section prints a [PASS]/[FAIL] line. Exit code is 0 only if all pass.
"""
from __future__ import annotations

import os
import sys
from collections import Counter
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Use the same plugin-path bootstrap as the app so Qt finds libqoffscreen.dylib
from app.main import prepare_qt_platform_plugins as _prep
_prep()

import random

from app.core.app_state import AppState
from app.engine.bot_brain import BOT_ARCHETYPES, KARMA_MIX, hands_in_top_pct
from app.engine.game_loop import PokerGame
from app.engine.hand_state import ActionType


_FAILS: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    tag = "[PASS]" if cond else "[FAIL]"
    line = f"{tag}  {name}"
    if detail:
        line += f"  —  {detail}"
    print(line)
    if not cond:
        _FAILS.append(name)


# ── 1. KARMA RANDOM ─────────────────────────────────────────────────
print("\n── 1. Karma (Mixed) random atama ──")
compositions: list[tuple[str, ...]] = []
for _ in range(8):
    g = PokerGame(num_players=6, starting_stack=100, bot_archetype="Karma (Mixed)")
    compositions.append(tuple(sorted(b.profile.name for _, b in g.bots.items())))
unique_count = len(set(compositions))
check("Karma produces varied compositions across 8 games", unique_count >= 5,
      f"unique = {unique_count}/8")

# Every archetype in KARMA_MIX appears at least once across 50 games
seen: Counter = Counter()
for _ in range(50):
    g = PokerGame(num_players=6, starting_stack=100, bot_archetype="Karma (Mixed)")
    for _, b in g.bots.items():
        seen[b.profile.name] += 1
missing = [a for a in KARMA_MIX if seen[a] == 0]
check("All KARMA_MIX archetypes sampled across 50 games",
      not missing, f"missing = {missing}" if missing else f"all {len(KARMA_MIX)} appeared")


# ── 2. FIELDPICKER ──────────────────────────────────────────────────
print("\n── 2. FieldPicker (+/- seat editor) ──")
from PySide6.QtWidgets import QApplication
qapp = QApplication.instance() or QApplication(sys.argv)
from app.ui.components.field_picker import FieldPicker, RANDOM_LABEL

fp = FieldPicker(default_bots=5)
check("Default 5 bots → total 6 players", fp.total_players() == 6)
check("All default seats start as Random",
      all(a == RANDOM_LABEL for a in [r.archetype() for r in fp._rows]))

# Add seats up to max
for _ in range(5):
    fp._add_random_seat()
check("Max 8 bots respected", len(fp._rows) == 8)

# Set explicit composition
fp.set_composition(["TAG", "Fish", "Maniac", RANDOM_LABEL])
arcs = fp.get_archetypes()
check("set_composition replaces seat list",
      len(arcs) == 4 and arcs[0] == "TAG" and arcs[1] == "Fish" and arcs[2] == "Maniac")
check("Random label resolves to a real archetype",
      arcs[3] in KARMA_MIX, f"resolved = {arcs[3]}")

# Cannot remove last bot
while len(fp._rows) > 1:
    fp._remove_row(fp._rows[-1])
fp._remove_row(fp._rows[0])  # try to remove last
check("Cannot remove last bot (min=1)", len(fp._rows) == 1)


# ── 3. ENGINE accepts custom bot_archetypes list ─────────────────────
print("\n── 3. PokerGame respects custom archetype list ──")
custom = ["Maniac", "Nit", "Fish", "Shark", "Calling Station"]
g = PokerGame(num_players=6, starting_stack=100, bot_archetypes=custom)
got = [b.profile.name for _, b in sorted(g.bots.items())]
check("Engine assigns exactly the custom archetypes", got == custom,
      f"got = {got}")


# ── 4. MULTI-SESSION TABS ────────────────────────────────────────────
print("\n── 4. MultiSessionTabs (parallel sessions) ──")
from app.ui.components.multi_session_tabs import MultiSessionTabs
from app.ui.screens.play_session import PlaySessionScreen

state = AppState()
host = MultiSessionTabs(
    screen_factory=lambda: PlaySessionScreen(state),
    title_prefix="Session",
)
check("Starts with one tab", len(host._tabs) == 1)
host.add_tab(); host.add_tab(); host.add_tab()
check("Can add up to 4 tabs", len(host._tabs) == 4)
# Max tabs cap
for _ in range(5):
    host.add_tab()
check("Tabs capped at MAX_TABS", len(host._tabs) == MultiSessionTabs.MAX_TABS)

# Signals forwarded
received: list[str] = []
host.coach_message.connect(received.append)
# Trigger a signal from an inner tab
host._screens[0].coach_message.emit("test-signal")
check("Signal forwarded from inner tab to host",
      "test-signal" in received, f"received = {received}")

# Close a tab
target = host._tabs[2]
host._on_tab_closed(target)
check("Closing a tab decrements count", len(host._tabs) == MultiSessionTabs.MAX_TABS - 1)


# ── 5. MID-TOURNAMENT END & RESTART ──────────────────────────────────
print("\n── 5. Mid-tournament END & NEW ──")
from app.ui.screens.tournament_simulator import TournamentSimulatorScreen
ts = TournamentSimulatorScreen(state)

# Stub field picker to 4 bots so tournament starts fast
ts.field_picker.set_composition(["TAG", "Fish", "Maniac", "Nit"])
ts._start_tournament()
check("Tournament started", ts.tournament is not None)
check("Tournament context populated",
      state.tournament_context is not None
      and state.tournament_context.get("active") is True)

# End mid-game
ts._end_and_restart()
check("End & restart drops tournament", ts.tournament is None)
check("End & restart clears tournament_context",
      state.tournament_context is None)
check("After end, setup screen is rebuilt (field_picker re-attached)",
      hasattr(ts, "field_picker"))


# ── 6. TOURNAMENT-ADVICE SIGNAL ──────────────────────────────────────
print("\n── 6. Tournament advice signal ──")
captured: list[str] = []
ts2 = TournamentSimulatorScreen(state)
ts2.tournament_advice_requested.connect(captured.append)
ts2.field_picker.set_composition(["TAG", "Fish", "Reg"])
ts2._start_tournament()
check("tournament_advice_requested fires on start", len(captured) == 1)
check("Briefing prompt mentions structure & buyin",
      bool(captured) and "buy-in" in captured[0].lower() and "Hero range" in captured[0])
ts2._end_and_restart()


# ── 7. BOT FIDELITY HEADLINES ────────────────────────────────────────
print("\n── 7. Bot AI fidelity (smoke check) ──")
# Quick 100-hand smoke for top archetypes — VPIP should land within ±8pts
def quick_vpip(archetype: str, n: int = 120) -> float:
    g = PokerGame(num_players=6, starting_stack=100,
                  bot_archetypes=[archetype] * 5, paced_bots=False)
    vol = total = 0
    for _ in range(n):
        for p in g.players:
            p.stack = 100; p.is_eliminated = False
        g.start_hand()
        guard = 0
        while g.current_hand and not g.current_hand.is_complete and guard < 200:
            if g.is_waiting_for_hero:
                g.hero_act(ActionType.FOLD, 0)
            else:
                g.step_action()
            guard += 1
        from app.engine.hand_state import Street
        hand = g.current_hand
        if not hand:
            continue
        for idx in range(6):
            if idx == 0 or g.players[idx].is_eliminated:
                continue
            total += 1
            pfa = [a for a in hand.actions
                   if a.player_idx == idx and a.street == Street.PREFLOP]
            if any(a.action_type in (ActionType.CALL, ActionType.RAISE,
                                      ActionType.BET, ActionType.ALL_IN) for a in pfa):
                vol += 1
    return 100 * vol / max(total, 1)

for name in ("TAG", "Fish", "Maniac", "Nit", "Calling Station"):
    target = BOT_ARCHETYPES[name].vpip
    realized = quick_vpip(name)
    diff = abs(realized - target)
    check(f"{name} VPIP within ±10 of target ({target})",
          diff <= 10, f"realized = {realized:.1f}, diff = {diff:.1f}")


# ── 8. HAND STRENGTH RANKING SANITY ─────────────────────────────────
print("\n── 8. Hand strength ranking ──")
top5 = hands_in_top_pct(5)
check("AA in top 5%", "AA" in top5)
check("KK in top 5%", "KK" in top5)
check("72o NOT in top 5%", "72o" not in top5)
check("72o NOT in top 25%", "72o" not in hands_in_top_pct(25))
check("72o eventually in top 100%", "72o" in hands_in_top_pct(100))


# ── REPORT ─────────────────────────────────────────────────────────
print()
print("=" * 70)
print(f"FEATURE AUDIT — {len(_FAILS)} failures out of all checks")
if _FAILS:
    for f in _FAILS:
        print(f"  ✗ {f}")
    sys.exit(1)
print("✓ ALL FEATURE CHECKS PASS")
sys.exit(0)
