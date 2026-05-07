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

