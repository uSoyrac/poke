# Champion Poker Training OS

Offline-first PySide6 poker training platform prototype: dark flat UI, solver-style drills, fast bot simulation, tournament/ICM spots, Math Lab, AI coach mock explanations, leak reports, knowledge cards and a study planner.

## Run

```bash
cd champion_poker_training_os
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

If dependencies are already installed, the direct command is:

```bash
cd champion_poker_training_os
python -m app.main
```

## What Works In This MVP

- Dark mode flat PySide6 desktop UI with sidebar navigation.
- Dashboard with metrics, leaks, expensive spots and study plan snapshot.
- GTO Study Library with filters, range grid, solver frequencies, EV table feel and one-click practice/coach actions.
- Spot Practice Trainer with 120 demo spots, action feedback, EV loss, solver frequency, sizing feedback and Turkish coach explanation.
- Hand History Analyzer with 100 seeded hands, replay table, timeline, filters and one-click jumps.
- Fast Play Simulator against rule-based bot archetypes with retry and session skill score.
- Tournament Simulator and ICM/PKO trainer with bubble/final table/PKO spots, risk premium, bubble factor and $EV loss.
- Preflop range grid, postflop concept trainer, river decision trainer and Combat Trainer packs.
- Math Lab with pot odds, alpha, MDF, EV and Bayes drills.
- AI Coach mock engine with RTA safety refusal for live decision prompts.
- Knowledge Base concept cards built as copyright-safe summaries.
- Study Planner and Reports screens with realistic seeded data.
- SQLite schema and seed database bootstrap.
- RTA Guard Strict Mode visible and active; known poker client processes lock strategy modules.

## GTO Engine & Solvers (2026 update)

A full GTO study stack with honest accuracy labelling — every output carries
a tier badge so you always know what you're learning:

- **Preflop GTO charts** — `app/poker/gto_ranges.py` (curated RFI + push/fold,
  ✅ EXACT) + `app/poker/gto_generator.py` (principle-based heuristic for every
  other spot, 🟡 APPROX). 100% spot coverage: RFI / vs-RFI / vs-3bet / push-fold,
  6-max + 8-max, 20–200bb, cash + MTT.
- **GTO Chart screen** (`range_trainer.py`) — GTOWizard-style 13×13 grid with
  position/stack/scenario/mode pickers and an accuracy badge.
- **Range Quiz** (`quiz_trainer.py`) — random-spot drill with countdown, GTO
  compare, per-position stats, spaced repetition and Monte-Carlo equity feedback.
- **MTT Trainer** (`mtt_trainer.py`) — Nash push/fold (8–25bb) drill + Stack
  Explorer (20–200bb) with ICM bubble/FT, satellite, PKO bounty and squeeze
  scenarios. Built on `app/poker/icm.py` (Malmuth-Harville) + `mtt_ranges.py`.
- **Monte-Carlo equity** — `app/poker/mc_equity.py` (pure-Python, validated:
  AA vs KK ≈ 82%). Powers Quiz feedback and Hand History per-street equity.
- **CFR solvers** — `vector_solver.py` (numpy-vectorized river, ~27× faster),
  `nested_solver.py` (turn+river chance-node CFR, heads-up exact),
  `multistreet_solver.py` (multi-bet-size river).
- **Solver Sandbox** (`solver_sandbox.py`) — PioSolver-style range-vs-range
  workbench with an **engine toggle**: a fast built-in vectorized CFR
  (🟠 study-grade) or **TexasSolver** (✅ solver-grade, see below).
- **Live GTO % on action buttons** — Play Session and Tournament show GTO
  frequencies (FOLD/CALL/RAISE/ALLIN %) for the current preflop spot, mapped
  from live state (position, stack, betting history). The AI Coach reads the
  same context to answer "is my decision GTO-correct?".

### Optional: TexasSolver (external, solver-grade postflop)

We do **not** bundle TexasSolver (it is AGPL-3.0). Install it yourself, then
the app calls it arms-length via subprocess (mere aggregation — like calling
`ffmpeg`/`git`):

```bash
# 1. Download/build TexasSolver: github.com/bupticybee/TexasSolver
# 2. Put console_solver where the app can find it (auto-detected):
#    ~/TexasSolver/console_solver   (resources/ folder must sit next to it)
#    or set TEXASSOLVER_PATH=/path/to/console_solver
# 3. Solver Sandbox → Engine → "TexasSolver ✅"
```

Adapter: `app/poker/texassolver_adapter.py` (input command file → subprocess →
JSON parse). Calibrated against TexasSolver v0.2.0 and verified end-to-end.

### Accuracy tiers (gto_provenance.py)

- ✅ **EXACT** — solver-exact / mathematically exact (RFI curated, push/fold
  Nash, equity, ICM, TexasSolver). Memorise with confidence.
- 🟡 **APPROX** — principle-based heuristic; correct shape, approximate
  frequencies (vs-RFI, vs-3bet, MTT-depth). Learn the concept, not exact %.
- 🟠 **CONCEPT** — real but simplified built-in CFR (single bet size).
- ❌ **GAP** — not covered (full multiway postflop). Don't assume.

## Ethics / RTA Boundary

This app is not a HUD, bot, overlay or real-time assistant. It does not read the screen, click buttons, automate clients or answer live-table strategy requests. It is for imported hands, manual offline study spots and simulation only.

## Tests

```bash
cd champion_poker_training_os
pytest
```

## Packaging

```bash
cd champion_poker_training_os
pyinstaller --name "Champion Poker Training OS" --windowed app/main.py
```

## Source Confidence Labels

Strategic outputs show confidence labels such as:

- Exact imported solver
- Pre-solved library
- Mock/demo solver
- Approximate math
- Rule-based heuristic
- AI explanation only

The current MVP mostly uses mock/demo solver and rule-based heuristic data by design.

