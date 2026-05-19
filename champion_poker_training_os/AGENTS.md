# AGENTS.md — Champion Poker Training OS

**You are a coding agent.** This doc is the contract: read it once, become
productive immediately, stop re-deriving the same context every session.

Last verified: 2026-05-19 · commit pushed to `origin/claude/friendly-torvalds-0ecc83` · **276/276 tests passing** · UI audit 20/0 issues · 28/28 screens boot clean · Sidebar kbd chips · Dashboard bottom panels Poke · Spot Trainer / Tournament Play / GTO Trainer chrome Poke · Tournament Play 3 visible bugs fixed (top-seat overlap, raw Markdown coach tip, clipped log column).

---

## 30-second orientation

- Offline poker training desktop app — **PySide6 / Qt 6**, Python 3.9+.
- 32 screens (Welcome, Dashboard, Spot Trainer, Tournament Play, GTO Trainer,
  Range Studio, Leak Finder, AI Coach, Style Guide, …).
- UI language: **Turkish** for user-facing strings, English for code/comments.
- Design system: **Poke** — brutalist editorial · 0 radius · lime accent on
  near-black green-tinted dark · Space Grotesk + JetBrains Mono + Instrument
  Serif. See `app/ui/screens/poke_style_guide.py` for the live reference.

---

## Run / test / render

```bash
# Where things live (worktree path may vary, real venv lives outside)
ROOT="/Users/uygar/Documents/New project/poke/champion_poker_training_os"
PY="/Users/uygar/Documents/New project/champion_poker_training_os/.venv/bin/python"
DESKTOP="/Users/uygar/Desktop/Champion Poker Training OS"

# Run the full test suite (must end with "270 / 270 PASS" or higher)
cd "$ROOT" && "$PY" -m pytest tests/ -q

# Boot every screen headless to check for crashes / QSS warnings
QT_QPA_PLATFORM=offscreen "$PY" -c "
import sys; sys.path.insert(0, '.')
from app.main import prepare_qt_platform_plugins; prepare_qt_platform_plugins()
from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)
from app.ui.theme.poke_fonts import load_poke_fonts; load_poke_fonts()
from app.core.app_state import AppState; s = AppState()
import importlib, pkgutil, app.ui.screens as scr
for m in pkgutil.iter_modules(scr.__path__):
    mod = importlib.import_module(f'app.ui.screens.{m.name}')
    for n in dir(mod):
        o = getattr(mod, n)
        if isinstance(o, type) and n.endswith('Screen'):
            try: w = o(s)
            except TypeError: w = o()
            w.show(); app.processEvents()
"
# Expected: 0 'Could not parse' lines, 0 tracebacks.

# UI audit (catches drilldown things like 'START button greyed out')
"$PY" -c "
import os; os.environ['QT_QPA_PLATFORM']='offscreen'
import sys; sys.path.insert(0,'.')
from app.main import prepare_qt_platform_plugins; prepare_qt_platform_plugins()
from PySide6.QtWidgets import QApplication
QApplication.instance() or QApplication([])
from app.agents import UISimulationAgent
r = UISimulationAgent().run_full_audit()
print('passed', len(r.passed), 'issues', len(r.issues))
"
# Expected: 20+ passed, 0 issues.

# Sync to desktop (user runs the app from there)
rsync -a --delete --exclude='.git' --exclude='.venv' --exclude='__pycache__' \
      --exclude='*.pyc' --exclude='.DS_Store' --exclude='.pytest_cache' \
      "$ROOT/" "$DESKTOP/"
```

### Empati testi — PNG-render UI changes (NON-NEGOTIABLE)

Memory says: "kod-doğru ≠ user-anlıyor". After every UI change, render the
affected screen to a PNG and read it back. The user expects this.

```python
import os; os.environ['QT_QPA_PLATFORM']='offscreen'
# (boot boilerplate as above)
w = YourScreen(AppState())
w.resize(1480, 2400); w.show()
app.processEvents(); app.processEvents()
w.grab().save("/tmp/screen.png")
# Then use the Read tool on /tmp/screen.png
```

---

## File map

```
app/
  main.py                       # entry point + NAV_ITEMS + screen factories
  core/                         # app_state, config, logging, rta_guard
  db/                           # repository, mistakes_queue, tournament_archive
  ai/coach_engine.py            # teacher_review() · explain_spot() · coach_chat()
  poker/                        # ranges, alpha_mdf, pot_odds, blockers
  solver/                       # mock_solver, preflop_charts, csv_importer
  engine/                       # game_loop (PokerGame), bot_brain, evaluator, hand_state
  simulator/                    # mtt_engine, field_simulator, fast_play_engine
  training/                     # mastery_model, position_breakdown
  agents/                       # ui_simulator (audit)
  data/                         # poker_glossary, pro_profiles
  leaks/                        # classification, signatures
  ui/
    theme/
      poke_tokens.py            # ← Poke design system tokens (use these!)
      poke_fonts.py             # ← load_poke_fonts() at app startup
      fonts/                    # bundled TTFs (Space Grotesk · JetBrains Mono · Instrument Serif)
      dark_flat.qss             # legacy QSS — slowly being replaced
      theme_manager.py          # apply_dark_theme(app)
    components/
      poke/                     # ← Poke primitives — PokeBtn, PokeCard, PokeStat, PokeTag, PokeSeg, PokePageHeader
      oval_table.py             # table widget with story-mode preflop chips
      range_matrix.py           # 13×13 grid (drag-select)
      card_view.py              # 4-color deck (♠ black · ♥ red · ♦ blue · ♣ green)
      coach_panel.py            # right-side coach output
      sidebar.py                # SidebarNav (LEGACY style, candidate for Poke port)
      topbar.py                 # TopStatusBar (LEGACY)
      help_overlay.py           # `?` shortcut overlay
    screens/                    # 32 screens, one file each
      welcome.py                # ✅ Poke-migrated
      dashboard.py              # ⚠️ top half Poke, bottom panels legacy
      poke_style_guide.py       # ✅ Style Guide (live reference)
      spot_trainer.py           # ❌ legacy — high priority migration target
      tournament_play.py        # ❌ legacy
      …                         # 26 more, all legacy

poke/                           # design handoff bundle (READ ONLY — reference)
  README.md
  project/
    Style Guide.html            # the canonical spec
    HANDOFF.md                  # PySide6 mapping guide
    theme.css                   # source of truth for tokens

tests/                          # 270 tests
```

---

## Conventions (the rules — break them and tests will catch you)

### Code

- **Poker hand notation** is "AKs" / "AKo" / "AA" — two ranks then optional `s/o`.
  Cards (with suit) are "Ah" / "Ks" / "Td9c2s" — alternating rank+suit.
  Don't parse cards with `hand[::2]` — that returns "As" for "AKs" (rank+suit).
- **BB-first sizing** everywhere — labels show "2.5bb open" not "33% pot".
  Pot% only in parens for postflop context.
- **Per-option breakdown** in coach feedback. Users see frequency % + EV + sizing
  for EVERY option, not just GTO best. See `app.ai.coach_engine.teacher_review`.
- **No emoji in user-facing strings** unless asked. Decoration only confuses.
- **Turkish for user strings, English for code/comments.**

### Qt / QSS

- **0px radius everywhere.** Brutalist. No `border-radius` in Poke components.
- Qt QSS does **NOT** support these — they'll print "Could not parse stylesheet":
  - `cursor` → use `setCursor(Qt.PointingHandCursor)` instead
  - `line-height`
  - `letter-spacing` → use `QFont.setLetterSpacing()` instead
  - `text-transform` → call `.upper()` on the string instead
  - `box-shadow`, `transform`, `transition` — none supported
- **Don't concat f-string opener with plain-string continuation that ends in `}}`.**
  This is the most painful bug we've hit:
  ```python
  # WRONG — produces `QPushButton{...}}` (double close) → Qt rejects everything
  btn.setStyleSheet(
      f"QPushButton{{background:{c};"
      "padding:4px;}}"                  # ← plain string, `}}` stays literal
  )
  # RIGHT — either both f-strings or close properly
  btn.setStyleSheet(
      f"QPushButton{{background:{c};padding:4px;}}"
  )
  ```
- **`paintEvent` exceptions crash the process on macOS** (Qt C++ event dispatch
  has no Python exception handler). Always wrap risky math/parsing in
  `try/except` — never let a `ValueError` escape `paintEvent`.

### Engine

- Dealer button rotates automatically inside `_finish_hand`. Don't double-rotate.
- `_finish_hand` handles 0 / 1 / many active players — don't assume ≥ 2 for showdown.
- Bot preflop opens: 2.0–3.0×BB. 3-bets: 2.5–4× the open. (See `bot_brain.py`)

### Tests

- Add a regression test for every bug fix. Pattern:
  ```python
  def test_<thing>_does_not_<break>():
      # reproduce conditions
      assert <invariant>
  ```
- Tests live in `tests/test_*.py`. Run before every commit.

---

## Known landmines (we hit these — don't fall in again)

1. **`range_viewer._hand_strength("AKs")`** segfault — see "Poker hand notation"
   above. Already fixed but the pattern repeats; audit any new hand parser.

2. **`min()` of empty `evaluations`** in `evaluator.determine_winners` — happens
   when the hero folds last and every villain has also folded. Fixed by
   `_run_betting_round_step` recheck + walkover handling in `_finish_hand`.

3. **Drill Builder START gray** — `__init__` called `_on_selection_changed(set())`
   which disabled the button after `table.select_all(True)` already populated it.
   Fixed; pattern: when wiring signals at init, prefer real state over `set()`.

4. **UI simulator imports `_BigCard` and `_StatCard`** from welcome.py — keep
   these public symbols on any welcome.py refactor. Same for any class
   `findChildren(...)` looks for.

5. **The PySide6 venv lives outside the worktree** at
   `/Users/uygar/Documents/New project/champion_poker_training_os/.venv/`.
   The worktree at `…/poke/champion_poker_training_os/` has no venv. Always use
   the absolute path to the venv Python.

6. **Path-with-spaces breaks `QT_QPA_PLATFORM_PLUGIN_PATH`.** Use
   `app.main.prepare_qt_platform_plugins()` which copies plugins to
   `/tmp/champion_poker_training_os_qt_platforms/` — already handles this.

7. **macOS .DS_Store files** keep appearing. `rsync --exclude='.DS_Store'` and
   keep them out of git.

---

## Workflow

```bash
# 1. Pull latest
cd "$ROOT" && git pull

# 2. Verify clean baseline before changing anything
"$PY" -m pytest tests/ -q   # → 270 passed
# Render any screen you'll touch BEFORE — so you have a "before" picture

# 3. Make changes (one logical unit per commit)

# 4. Verify
"$PY" -m pytest tests/ -q
# PNG-render the affected screens, read them back, sanity-check

# 5. Commit (Turkish title OK, English body, always with Co-Authored-By)
git add <files>; git commit -m "$(cat <<'EOF'
<area>: <what changed>

<why · what was the root cause · how does the fix work>

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"

# 6. Sync to desktop (the user runs the app from there)
rsync -a --delete --exclude='.git' --exclude='.venv' --exclude='__pycache__' \
      --exclude='*.pyc' --exclude='.DS_Store' --exclude='.pytest_cache' \
      "$ROOT/" "$DESKTOP/"

# 7. Push to GitHub (so next session can pull fresh)
git push origin claude/friendly-torvalds-0ecc83
```

---

## Design system reference (Poke)

**Tokens** — `from app.ui.theme import poke_tokens as t`

```python
t.BG          # #0a0c0a    App background
t.BG_2        # #0f1210    Sidebar, raised
t.SURFACE     # #131613    Cards, modals
t.SURFACE_2   # #181b17    Hover, headers
t.LINE        # #23271f    Hairline border
t.LINE_2      # #33382c    Strong / interactive border
t.INK         # #f4f5ee    Primary text
t.INK_2       # #d6d8cf    Secondary text
t.MUTED       # #898d80    Labels
t.DIM         # #5a5e54    Off labels
t.ACCENT      # #5db75b    Brand lime
t.ACCENT_INK  # #0a0c0a    Text on accent
t.DANGER      # #cc3a2b    Bet / raise / error
t.WARN        # #d6a23b    Caution
t.INFO        # #5288d6    Fold / neutral
```

**Components** — `from app.ui.components.poke import …`

```python
PokeBtn(label, variant="primary"|"default"|"danger"|"ghost",
        size="sm"|"md"|"lg", kbd="↵", block=True/False)
PokeCard(title, num="A1", sub="4 SPOTS", action=PokeBtn(...))
  card.add_to_body(widget)
PokeStat(label, value, unit="bb/100", delta="1.4", delta_sign="+", sub="...")
PokeTag(text, tone="g"|"r"|"y"|"b"|"neutral", dot=True/False)
PokeSeg(["7d","30d","All"], value="30d")  # .changed signal
PokePageHeader(num="01 / Dashboard", title="Sharpen your <em>edge</em>.",
                sub="...", actions=PokeBtn(...))
```

**Typography**

```python
from app.ui.theme import poke_fonts
poke_fonts.display(size=52)        # Space Grotesk 700, page titles
poke_fonts.body(size=13)           # Space Grotesk 500
poke_fonts.mono(size=11)           # JetBrains Mono, tabular nums
poke_fonts.label()                 # Mono 10px, uppercase labels
poke_fonts.serif_italic(size=36)   # Instrument Serif italic
```

Or inline QSS:
```python
lbl.setStyleSheet(f"font-family: 'Space Grotesk'; font-weight: 700; "
                   f"font-size: 24px; color: {t.INK}; background: transparent;")
```

**Rules**

- Sharp corners. Always. No exceptions.
- 1-px hairline borders. 2-px reserved for accent focus/active.
- Numbers always tabular — they line up vertically when stacked.
- Editorial italic (`<em>`) for emphasis inside headlines only.
- Mono uppercase for section labels — `▸  PROGRESS`.

See `app/ui/screens/poke_style_guide.py` for the live in-app reference.

---

## Migration roadmap (Poke)

| Screen | Status | Priority |
|---|---|---|
| Style Guide                      | ✅ Done            | (reference) |
| Welcome                          | ✅ Done            | done |
| Dashboard (top half)             | ✅ Done            | done |
| **SidebarNav**                   | ✅ Done            | done — kbd chips ⌃1..⌃9 on right |
| **TopStatusBar**                 | ✅ Done            | done — touches every screen |
| Dashboard (bottom panels)        | ✅ Done            | done — leak/skill/adaptive rows are Poke |
| Spot Trainer (chrome)            | ✅ Done            | done — 0 radius + lime accent + Poke tokens |
| Tournament Play (chrome + bugs)  | ✅ Done            | done — top-seat fix, Markdown coach, wider log, Poke tokens |
| GTO Trainer (Range Studio)       | ✅ Done            | done — 0 radius + Poke tokens (range matrix still uses semantic colors) |
| MTT Setup Dialog                 | ✅ Done            | done — 0 radius |
| AI Coach                         | ⚠️ Partial        | medium — colour swap; layout still legacy |
| Other 20 screens                 | ❌ Legacy         | low (background) |

Each migration is one commit. Workflow per screen:

1. Read the existing screen (note public symbols, signals, data sources)
2. Render BEFORE PNG → `/tmp/before_<name>.png`
3. Rewrite with Poke primitives; preserve all public API + behaviour
4. Render AFTER PNG → `/tmp/after_<name>.png`
5. Tests still green; UI audit still green
6. Commit + sync + push

---

## When to start a fresh chat

Heuristic: this current chat is fine for **2–3 more focused turns**. After that,
context bloat starts costing more than a fresh-chat onboarding would.

**Fresh-chat starter prompt** (paste into a new chat):

> Read AGENTS.md in `/Users/uygar/Documents/New project/poke/champion_poker_training_os/`.
> Then check `git log --oneline -10` to see what's already done. We're on commit
> `<latest-hash>` (`git rev-parse --short HEAD`). I want to: <your task>.

That gets a new agent productive in ~5K tokens instead of 50K.

---

## What's broken / known issues

- **20 screens** still legacy-styled — same dark cyan theme as before
  (Range Studio, Math Lab, Combat, Reports, Hands, Heads-Up, ICM, River,
  Postflop, Knowledge Base, Study Planner, Settings, Skills Report, etc.).
- AI Coach: colour constants point at Poke tokens but the layout (chat panel,
  quick-access pills) is still the legacy cyan composition — a layout pass
  is still needed.
- **`This plugin does not support propagateSizeHints()`** appears in headless
  boot. Harmless — Qt offscreen plugin limitation.

None of these are crashes. The app works end-to-end; only visual consistency
is partial.

---

## One last thing

Before any UI commit, run **both** of these and verify outputs:

```bash
"$PY" -m pytest tests/ -q                                # → 270 passed
QT_QPA_PLATFORM=offscreen "$PY" -c "<all-screen boot>" 2>&1 | grep 'Could not parse' | wc -l   # → 0
```

If either fails, fix it before committing. The cost of a follow-up "fix the
thing I just broke" commit is higher than 2 minutes of verification.

---

*This file is the contract. Update it when you learn something new — the next
agent (you, in a fresh chat) will thank you.*
