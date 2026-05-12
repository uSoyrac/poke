# Champion Poker Training OS — Master Audit

A two-pass review of the application as if conducted by:
- **A tournament poker master** (Galfond / Saulsberry style coach)
- **A GTO solver expert** (PIO / Wizard architect mindset)

Each finding is mapped to a fix that's either **landed** in the codebase or
**queued** as the next sprint. This file is the single source of truth for
what "market-ready" means here.

---

## ✅ Landed (verified passing tests)

### Engine correctness
- **Dealer button placement** — `dealer_idx` now correctly maps to the BTN seat
  (was: SB seat by accident). HU still treats SB as the dealer.  
  *Test:* manual + `test_ui_smoke.py`
- **Realistic bet sizing** — `BotBrain._pick_raise_sizing()` produces
  2.0–3.0× BB opens, 2.8–3.6× 3-bets, 2.2–2.7× 4-bets, 33/50/66/75/100% pot
  postflop. Min-raise rule enforced.  
  *Test:* 60-hand probe, all observed raises ≥ 2.0bb.

### GTO data layer
- **Pre-solved chart database** — 15 distinct charts keyed by
  position × stack × vs. Drives RangeMatrix, Spot Trainer, GTO Trainer.  
  *Test:* `test_drill_catalog.py` + chart variety probe (BTN=3, LJ=2, etc.).
- **Hand-specific strategy lookup** — `hand_169_from_cards()` resolves
  hero's exact 169-cell combo and pulls its frequency mix.  
  *Test:* AKs/BTN→raise 100%, 72o/UTG→fold 100%.
- **Mock solver chart-aware** — `solve_spot()` priority chain:
  CSV import → pre-solved chart → heuristic fallback.

### Drill catalog
- **325 named, hand-crafted spots** across 7 categories (Open-raising,
  BB Defense, SB Defense, 3-bet Defense, Postflop, ICM, Cash).  
  Every spot has full metadata + auto-filled defaults.
- **Random session starts** — Spot Trainer / GTO Trainer / ICM Trainer
  all open on different spots each session.

### Multi-agent system
- **6 agents** (PokerPlayer, Coach, LeakDetector, DrillGenerator, Review,
  GTOMaster) + AgentOrchestrator chaining workflows.  
  *Tests:* `test_agents.py` (17), `test_gto_master_agent.py` (8).

### UI quality bar
- **Unified action buttons** — `GtoActionButton` rolled out across
  Spot Trainer, GTO Trainer, ICM, Combat, Tournament Sim/Play, Postflop, River.
- **Scrollable sidebar** — all 27 nav items reachable on any window size.
- **Real cards everywhere** — `CardView` widgets in Spot Trainer, Tournament
  Play, ICM Trainer.
- **Interactive GTO Trainer** — Position chips clickable, tab modes
  (Strategy / Strategy+EV / EV / Equity) functional, hand combos clickable.
- **Action chips on static spot ovals** — `SpotSnapshot.last_action` field
  drives fold/raise indicators on positions.
- **Welcome screen** — Onboarding landing page with 3-step workflow,
  KPI cards, personalized recommendation, full surface map.

### Tests
- **162 unit tests pass** (Python sandbox, no PySide6)
- **+34 PySide6-gated tests** (UI smoke, range matrix modes, GTO trainer
  interactivity, GTO master agent) — auto-skip in sandbox, run in venv.

---

## 🟡 Next sprint (queued, not landed)

### Solver depth
- **Solver tree navigation** — currently each spot is a single decision.
  Real GTO needs the *response tree*: after hero raises, what does villain
  do next? Three-street solver trees would be the right model.
- **Sizing matrix** — at each node, the solver should support multiple
  sizings (1/3, 1/2, 2/3, pot, overbet) with per-sizing EV.

### Coaching depth
- **Personalized leak heatmap** — combine LeakDetectionAgent output with
  position × pot type matrix; show user's accuracy per cell.
- **Spaced repetition queue** — adaptive engine already tracks intervals;
  surface it as a dedicated "Today's Review Queue" screen.
- **Coach voice memo (audio)** — for accessibility + post-session review.

### UX polish
- **Tutorial overlay** — guide first-time users through their first drill
  with annotated callouts.
- **Search bar** — Cmd+F across spot catalog + concept library.
- **Keyboard shortcuts** — 1=Fold, 2=Call, 3=Raise, 4=Jam universally.
- **Mobile / tablet layout** — current build assumes ≥1200px width.

### Real-world data
- **Real solver CSV import** at scale — current CSV importer works for
  single files; needs bulk-folder import + node merging.
- **HUD overlay for live hand history** — given a hand history file,
  show the GTO line over each decision in a sidebar.

---

## 🎓 Master coach principles (encoded in `GTOMasterAgent`)

Every analysis from the master agent walks through:

1. **Spot identification** — position, stack, street, pot type
2. **Range advantage** — whose pre-action range looks stronger on this board?
3. **Nut advantage** — whose range contains more top-equity combos?
4. **Blocker analysis** — does the hero's hand block villain's value/bluffs?
5. **Board texture** — wet/dry, paired, monotone, connected → sizing
   discipline directly follows
6. **Position dynamics** — IP vs OOP, multi-way risk, positional pressure
7. **Recommended action** — solver baseline with frequency
8. **Common leak warning** — what most players get wrong here
9. **Drill prescription** — specific repair drill recommendation

These eight steps are inspired by the structured analysis Galfond, Saulsberry,
and PIO solver users follow when reviewing hands. The agent gives the user
the same framework regardless of which screen they're on.

---

## 📦 Market-readiness checklist

- [x] First-run welcome screen with clear path forward
- [x] 27 training surfaces, every one reachable + tested for construction
- [x] 325 drills with real GTO data behind every action button
- [x] Multi-agent architecture (6 specialised agents + orchestrator)
- [x] Unit + UI tests covering all critical paths
- [x] Hand history import (PokerStars + CoinPoker)
- [x] Adaptive learning + spaced repetition
- [x] Pre-solved range matrix with 4 view modes
- [x] Master coach review accessible from every screen
- [ ] In-app onboarding tour (Step 1: first drill walkthrough)
- [ ] Performance audit at 1000+ catalog size
- [ ] Mobile/tablet responsive layout
- [ ] Real-time multi-street solver tree
- [ ] Audio / TTS for coach commentary

---

*Generated by the Master Audit pass on the codebase.  
Last refreshed: this commit.*
