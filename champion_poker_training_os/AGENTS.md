# Agent handoff notes — Champion Poker Training OS

Read this first when picking up the project in a fresh session. It captures
state, conventions, and the recent design decisions a new agent would
otherwise have to reverse-engineer from `git log`.

---

## 1 · What this app is

PySide6 desktop poker-training OS. Brutalist editorial UI (sharp corners,
mono numbers, lime-green accent). Two main play surfaces — **Play Session**
(cash) and **Tournament Simulator** — share one `LivePokerTable` widget.
Around them sit ~15 trainer/analysis screens, an AI coach panel, and a
sidebar nav.

- **Run:** `cd champion_poker_training_os && .venv/bin/python -m app.main`
- **Test:** `.venv/bin/python -m pytest tests/ -q` (42 unit tests) +
  `.venv/bin/python tests/test_feature_audit.py` (27 feature checks) +
  `.venv/bin/python tests/test_bot_archetype_fidelity.py` (bot AI
  realised-vs-target VPIP/PFR/AF report). All three must pass.
- **Render-UI test:** `.venv/bin/python tests/render_ui_screens.py` —
  dumps PNGs to `docs/screens/` so you can eyeball UI changes from the
  user's POV (mandatory per user memory: "UI değişikliği sonrası PNG
  render alıp gerçek user gözünden bak").
- **Repo:** https://github.com/uSoyrac/poke.git (branch `main`)
- **Design source bundle URLs** (only fetch if you need binary assets;
  the relevant text files are mirrored at `docs/design/`):
  - Poker Table — `https://api.anthropic.com/v1/design/h/F_M6HFBVSLnhvl1LEi-r0g?open_file=Poker+Table.html`
  - Style Guide — `https://api.anthropic.com/v1/design/h/zXOGR9AImpY9DLg-rtRoDA?open_file=Style+Guide.html`

---

## 2 · Source-of-truth files

| Concern | File |
|---|---|
| Design tokens, type, animations | `app/ui/theme/dark_flat.qss` (Qt port of `theme.css` from the design bundle) |
| **Design source — read FIRST** | `docs/design/` — mirrored copies of `UI_GUIDE.md`, `theme.css`, `poker-table.css`, `poker-table.jsx`, `Poker-Table.html`, `Style-Guide.html`. See `docs/design/README.md` for what each file is for. |
| Poker felt / seats / chips | `app/ui/components/poker_table.py` (`LivePokerTable`, `SeatState`, `seats_from_hand`) — **legacy** `PokerTableView` kept here too because trainer screens still import it |
| Card rendering (4-Color Deck) | `app/ui/components/card_view.py` — `SUIT_COLORS` maps each suit to its hex |
| Shortcut registry | `app/ui/components/shortcuts.py` (`SHORTCUTS` list + `ShortcutsDialog`) |
| Sidebar nav | `app/ui/components/sidebar.py` (`EXPANDED_WIDTH=232`, `COLLAPSED_WIDTH=52`) |
| AI coach panel | `app/ui/components/coach_panel.py` (`EXPANDED_WIDTH=360`, `COLLAPSED_WIDTH=40`) |
| **Multi-tab host** | `app/ui/components/multi_session_tabs.py` — wraps any screen so the user can keep up to 6 parallel sessions/tournaments; forwards `coach_message`/`hand_completed`/`navigate_requested`/`tournament_advice_requested` signals |
| **Per-seat archetype picker** | `app/ui/components/field_picker.py` — `FieldPicker` widget; add/remove seats (1-8 bots), every seat picks a specific archetype or "Random (Karma)" which resamples each game |
| Engine (Hold'em rules) | `app/engine/game_loop.py` — `PokerGame.step_action()` is the per-tick API the UI drives. Accepts `bot_archetypes=List[str]` for explicit per-seat assignment |
| Bot brains + archetypes | `app/engine/bot_brain.py` — `BOT_ARCHETYPES` dict + `hands_in_top_pct()` frequency-aware hand-strength range builder; per-profile open / 3-bet / call ranges precomputed in `BotBrain.__init__` so realised VPIP/PFR land near declared targets |
| Tournament wrapper | `app/simulator/tournament_runner.py` — owns blind schedule, owns a `PokerGame`; `TournamentConfig.bot_mix` is the per-seat archetype list, `paid_places` reports payout-table size |
| Live HUD | `app/core/live_hud.py` — observes bot actions per hand; `merge_with_profile()` blends observed stats with the archetype baseline (weight = min(observed/20, 1)) |
| Tournament context for coach | `app/core/app_state.py` — `tournament_context` dict populated by `TournamentSimulatorScreen._refresh_table` each refresh, consumed by `MainWindow._tournament_context_block()` to prepend ICM/bubble/stack-depth info to every Gemini prompt |
| App shell + shortcuts | `app/main.py` — `MainWindow` wires Ctrl+B / Ctrl+J / Ctrl+1..9 / ? and connects `tournament_advice_requested` → Gemini briefing; `_gemini_for_screen(prompt, screen)` routes Gemini results to any screen's `show_analysis_result()` |
| **MTT Field simulation** | `app/simulator/mtt_field.py` — `MTTField` tracks background field eliminations via phase-adjusted Poisson; `tick(hands)` called each hand; properties: `players_remaining`, `bubble_distance`, `is_itm`, `tables_active`, `prize_summary(n)` |
| **Tournament Analysis screen** | `app/ui/screens/tournament_analysis.py` — two-panel layout; left: scrollable `_TournCard` list from `tournament_results` DB; right: per-tournament hero card + KPI + AI coach QTextEdit OR general aggregate stats view; `analysis_requested` Signal → main.py → Gemini |
| **Tournament history DB** | `app/db/repository.py` — `save_tournament_result(data)` + `get_tournament_history(limit)` read/write `tournament_results` table; schema in `app/db/schema.sql` |
| **GTO range data (curated)** | `app/poker/gto_ranges.py` — `get_action(pos, hand, scenario, stack, mode, vs_position)` is the single lookup API. Curated charts (`RFI_100BB_6MAX`, `PUSH_FOLD_15BB_BTN`) cover RFI + push/fold. `_is_curated()` decides curated-vs-heuristic. **Lesson learned**: hand-curated WIDE ranges (BB defend, vs-3bet) came out systematically too tight (BB vs UTG 14% vs ~38% target) → those defer to the heuristic generator instead |
| **GTO heuristic generator** | `app/poker/gto_generator.py` — `heuristic_get_action()` fallback for ANY (pos × scenario × stack × vs_pos) not curated. Principle-based: position tightness, stack-depth scaling, vs-opener tightness curve, 3-bet pyramid. Produces accurate aggregate % (BB defend 37/41/48/51/57 vs targets 38/42/48/52/58). 100% spot coverage, no empty result |
| **Monte Carlo equity** | `app/poker/mc_equity.py` — `calculate_equity()` + `equity_hand_vs_hand/range`, `equity_range_vs_range`. Pure-Python MC, ~500ms/5K iter. `expand_hand_key("AKs")` → concrete combos. Used by Quiz feedback + Hand History equity track. (Old static lookup `app/poker/equity.py` untouched) |
| **River CFR solver** | `app/poker/river_solver.py` — `RiverSolver(hero_range, villain_range, board, pot, bet_size_frac).solve(iters)` → per-hand BET/CHECK/CALL/FOLD via vanilla CFR + regret-matching. 4 info sets (HERO_FIRST, VILL_VS_BET, VILL_AFTER_CHK, HERO_VS_BET). ~430ms/20×28 combos×300 iter |
| **GTO Chart screen** | `app/ui/screens/range_trainer.py` — `GTORangeChartScreen` (alias `RangeTrainerScreen`). 13×13 grid via `RangeGrid`/`HandCell` (QPainter action splits), position/stack/scenario/mode pickers, right detail panel with `FrequencyBar` |
| **Range Quiz screen** | `app/ui/screens/quiz_trainer.py` — `QuizTrainerScreen`. Random spot generator (4 scenarios, vs_position-aware) + countdown + GTO compare + equity feedback (MC) + per-position stats + spaced-repetition wrong-queue |
| **Solver Sandbox screen** | `app/ui/screens/solver_sandbox.py` — `SolverSandboxScreen`. 13×13 range pickers (hero/villain tabs) + presets + board/pot/bet/iter controls + SOLVE (runs `RiverSolver` in a QThread) → strategy tables |
| **Hand History Archive screen** | `app/ui/screens/hand_history.py` — `HandHistoryScreen`. Date list + paginated hands table + detail panel with per-street equity track + Gemini "analyze this hand" (`analysis_requested` Signal). DB helpers in repository.py: `get_dates_with_hands`, `get_hands_for_date`, `get_overall_archive_stats`, `_ensure_history_index` |
| **In-game GTO assist** | `app/ui/components/gto_range_widget.py` — `GTORangeWidget.update_range(pos, stack, game_type, hero_hand)` shows a colored RAISE/CALL/FOLD badge for hero's exact hand via `gto_ranges.get_action`. Wired in tournament_simulator + play_session |

---

## 3 · Design decisions that took multiple iterations

### Paced bot actions
`PokerGame.step_action()` runs ONE engine step (one bot, or one street
advance) and returns `False` when waiting for hero / hand complete. Both
play screens set `game.paced_bots=True` and use a `QTimer(450ms)` to
drive the loop, so the user watches UTG act, then UTG+1, etc. — the
classic Hold'em action order, visualised. Synchronous mode
(`paced_bots=False`) stays for tests.

### Unified poker table
`LivePokerTable` is the single play widget. Reads `SeatState` objects in
**slot order from hero (CCW on screen, FW in player list)**. Slot 0 is
always the hero seat at the bottom-center. Layouts in `SLOTS[n]` cover
HU through 9-max. `seats_from_hand()` is the bridge between engine
`PlayerSeat` and UI `SeatState`.

### Bet chip positioning
Three-way redundant: `setFixedSize(96,58)` + `setGeometry` + `move()` +
`raise_()`, plus a deferred `QTimer.singleShot(0, _layout_children)` in
`render_state` AND a re-layout in `showEvent`. This stack survives Qt's
latent layout passes that used to dump chips at (0,0).

### Action buttons — never toggle setEnabled
`_update_action_buttons` only calls `hide()/show()`, never
`setEnabled()`. Qt's stylesheet engine sometimes fails to re-evaluate
`:enabled`/`:disabled` inside a tight `setEnabled(False)→setEnabled(True)`
pair, which made CALL render with its disabled palette while
functionally enabled. Visibility alone gates user input now.

### CALL / ALL-IN solid fills
`#ActionCall` and `#ActionAllin` set **both** `background` (shorthand)
AND `background-color` (longhand) to defeat Qt's quirky cascade where
shorthand from a parent rule outranks a longhand override. White text on
both.

### 4-Color Deck
`SUIT_COLORS` in `card_view.py`:
- ♠ Spades → `#f0a04b` (orange — the only colour outside the design's 4 semantic tokens)
- ♥ Hearts → `#e87474` (danger red)
- ♦ Diamonds → `#5a9eef` (blue)
- ♣ Clubs → `#5ad17a` (accent lime)

The rank label and both suit glyphs share the suit's colour so the card
reads as one chromatic unit.

### Collapsible chrome
Sidebar (Ctrl+B) and Coach panel (Ctrl+J) shrink to a thin rail
(52/40 px) showing only the toggle chevron. `PaneToggle` is the QSS
objectName for the chevron — flat with lime accent on hover.

### TO CALL banner
Originally lived inside the felt center widget but overlapped hero hole
cards. Moved out of `_Center` and into each play screen's action deck
(above the buttons). Centered, lime border, mono text.

### Multi-tab parallel sessions
Both Play Session and Tournament Simulator are wrapped in
`MultiSessionTabs` (see `_create_screens` in `app/main.py`). The user
opens up to 6 parallel sessions/tournaments via "+ NEW". Each tab is an
independent screen instance with its own `PokerGame` and `LiveHUD`.
Signals are forwarded transparently — main.py's existing
`coach_message` / `hand_completed` / `tournament_advice_requested`
hooks still work without changes.

### Karma (Mixed) — true random
`PokerGame.__init__` uses `random.sample(KARMA_MIX, num_bots)` when
`bot_archetype == "Karma (Mixed)"`, so every game has a different
field composition. The old implementation cycled through KARMA_MIX in
order — same TAG/LAG/Fish/Station/Reg in seats 1-5 every game. The
fix lives in `app/engine/game_loop.py` around line 95.

### Per-seat archetype picker
`FieldPicker` replaces the old "PLAYERS combo + ARCHETYPE combo" pattern.
The picker is the source of truth for both table size (1-8 bots) and
per-seat archetype. Resolved archetype list goes to
`PokerGame(bot_archetypes=...)` directly. Quick presets (Karma 5-bot,
TAG-heavy, LAG-heavy, Recreational, Tough Regs, Solver Field) populate
the picker via `set_composition()`; user can still tweak afterwards.

### Bot archetype fidelity
Each `BOT_ARCHETYPES` profile declares target VPIP / PFR / 3-bet /
fold-to-cbet / aggression. `BotBrain.__init__` precomputes
per-position open ranges using `hands_in_top_pct(profile.vpip *
_POS_VPIP_MULT[pos])`. Preflop in-range decisions split between
raise/call by `pfr/vpip` ratio (passive profiles limp, aggressive
profiles raise). 3-bet pool is `hands_in_top_pct(three_bet * 1.25)` IP
and `* 0.95` OOP. Postflop marginal-fold rate is `fold_to_cbet * 1.80
- hand_strength*0.35 - call_down*0.15` (the 1.80 multiplier
compensates for strong/medium hands never folding). Run
`tests/test_bot_archetype_fidelity.py` to see the realised vs target
table — 8/15 archetypes hit within ±5pts, the rest are within ±10pts
or sit on natural selection effects (very-tight profiles run higher
AF because their continuing range is stronger).

### Mid-tournament restart
TournamentSimulatorScreen has an "X END & NEW" button in the meta bar
(also Esc shortcut). `_end_and_restart()` stops the bot timer, drops
the in-memory Tournament, clears `state.tournament_context`, and
rebuilds the setup stage so the user can configure a fresh tournament
without leaving the screen. Hands already played stay in the DB.

### Tournament-aware coach
Each tournament refresh writes a rich `tournament_context` dict to
`AppState` (event, structure, level, blinds, hero bb, avg bb, stack
pressure, bubble distance, on-bubble flag, prize pool). When the user
asks the coach anything during a tournament, `MainWindow.chat_with_coach`
and `explain_selected_spot` prepend that context block to the Gemini
prompt so advice is ICM/bubble/structure-aware. On tournament start, a
dedicated `tournament_advice_requested` signal fires a 5-point opening
briefing prompt (early stage strategy, bubble approach, exploits
against the specific bot mix, spots to avoid, end-goal framing).

### Bot pot-commitment guard
Universal guard in `BotBrain.decide()` fires BEFORE preflop/postflop
dispatch. If `invested / (invested + remaining) >= 0.65`, the bot is
forced to CALL or ALL-IN — it never folds when pot-committed. An
additional all-in guard fires when `player.stack / (pot + stack) < 0.35`
and ALL-IN is the only valid action. This prevents the classic "bet 18bb
with 19.5bb, then fold to a raise" bug.

### MTT field simulation + table balancing
`MTTField` runs a background Poisson elimination model:
- Phase rates: early 0.55x, mid 1.0x, bubble 1.45x
- `tick(hands)` called each hand from `_on_hand_complete()`
- Hero table meta bar shows full field PLAYERS count, not just the 9-seat
  table count (when `field_size > 9`)
- `_maybe_refill_table()` in TournamentSimulatorScreen: when hero's table
  drops below 5 players AND the background field still has players, it
  revives bot seats with the average background stack and rolls back
  `is_complete = False` so the tournament continues (table balancing)

### Tournament result report + history
`_build_report()` in TournamentSimulatorScreen generates a full report at
the end of each tournament:
- Hero card: big finish position + prize + grade (S/A+/A/B+/B/C/D based
  on finish percentile)
- KPI strip: VPIP / PFR / BB/100 / Eller (color-coded good/bad)
- Bullet evaluation (auto-generated from stats)
- Past tournament history table (last 10)
- Saves to `tournament_results` DB table on completion

### Tournament Analysis screen
Dedicated "Tournament Analysis" nav item (after Tournament Simulator):
- Left panel: chronological list of `_TournCard` widgets; clicking any
  shows detail on the right; reloads on every `showEvent`
- Right panel — per-tournament: hero card, KPI strip, auto-eval bullets,
  inline AI coach with "ANALİZ AL" button (5-section Turkish prompt)
- Right panel — general: 9-cell stats grid, trend card (last-5 vs earlier),
  "KAPSAMLI ANALİZ AL" button (aggregated prompt)
- `analysis_requested` Signal → `MainWindow._gemini_for_screen()` →
  Gemini async → `show_analysis_result(text)` fills inline QTextEdit AND
  forwards to sidebar coach panel

### × → "REMOVE" / ASCII X
The "×" Unicode glyph (U+00D7) renders as a blank square in JetBrains
Mono on macOS for some weights. We use plain ASCII "X" everywhere the
glyph appears in a small button (tab close, etc.) and the spelled-out
"REMOVE" for FieldPicker rows. Also remember Qt treats `&` in button
text as a mnemonic accelerator — escape with `&&` (see `END && NEW`
in `tournament_simulator.py`).

---

## 4 · Shortcut catalog (verify before adding new ones)

| Keys | Action |
|---|---|
| `Ctrl+B` | Toggle sidebar |
| `Ctrl+J` | Toggle AI Coach panel |
| `?` (Shift+/) | Open shortcut cheat-sheet overlay |
| `Esc` | Close any open dialog |
| `Ctrl+1` … `Ctrl+9` | Jump to the first 9 nav items (Dashboard, Play Session, Tournament, GTO Study, Spot Trainer, Hand History, AI Coach, Leak Finder, Reports) |
| `F` | Fold (Play / Tournament — only fires when button visible) |
| `C` | Call (or Check if no bet) |
| `R` | Raise (or Bet) |
| `A` | All-in |
| `Space` | Deal next hand (Play); skip inter-hand wait (Tournament) |
| `G` | Open GTO range popup (Play / Tournament) |
| `Esc` | End current tournament and return to setup |

Adding a new shortcut: append one row to `SHORTCUTS` in
`app/ui/components/shortcuts.py` (cheat sheet picks it up automatically),
then bind a `QShortcut` in the relevant screen.

---

## 5 · Recent commits (read for context)

```
# GTO + equity + solver session (2026-05-28) — newest first
097123d feat(quiz): multi-scenario drills — vs RFI / vs 3-bet / Push-Fold
501f5aa fix(gto): honest curation — defer wide ranges to heuristic, tune targets
501bce6 feat(gto): heuristic generator → %100 spot coverage (gto_generator.py)
06c25c3 feat: Solver Sandbox — PioSolver-style river CFR UI
baa3e2f feat(history): equity track per street in hand detail
a430e66 feat(quiz): equity feedback after each answer
4c037ea feat(solver): minimal river CFR solver (river_solver.py)
dfe921d feat(bot): hand-strength evaluator — kicker tracking + combo draws + gutshots
5c90fb0 feat(equity): Monte Carlo equity calculator (mc_equity.py)
e5b29dc fix(bot): recalibrate archetype profiles to new evaluator's reality
6b0e090 fix(gto): RFI range %'leri target'a kalibre et
dc4da01 feat: Hand History Archive — day-by-day, 200M-hand scale
bb115f1 feat: Range Quiz trainer — preflop drill mode
31c7d91 feat(gto): in-game hero hand → recommended action badge
2a6ae20 feat: GTO chart system + MTT finish bug fix + bot AI realism
# earlier
fef7755 feat: add Tournament Analysis screen + wire into main.py
c998140 feat(report): comprehensive tournament result screen + history tracking
e43c544 fix(tournament): table balancing + bot pot-commitment
243eae4 feat(tournament): integrate MTTField — real-time large-field simulation
db2dbaa feat: real poker game in Spot Trainer + Drill Library with leak integration
<older> feat: multi-table + per-seat archetype picker + bot AI overhaul
```

### GTO/equity/solver architecture (this session)
- **Coverage strategy**: curated charts (RFI, push/fold — verified accurate)
  + heuristic generator (everything else — principle-based, accurate aggregate %).
  `get_action()` is the single entry point; `_is_curated()` routes.
- **Honest lesson**: hand-curating WIDE ranges from memory produces too-tight
  results. Trust the principled heuristic for BB-defend / vs-3bet; only
  hand-curate tight/polarized spots (RFI, push/fold).
- **Equity (mc_equity) + CFR (river_solver)** are pure-Python, no deps, written
  from public-algorithm knowledge (no AGPL/GPL code reuse — only ideas).
- **New NAV screens**: "Range Quiz", "Solver Sandbox", "Hand History Archive".

---

## 6 · Conventions

- **Language in commits + UI text:** Turkish-friendly. Code, comments, and
  docs in English. The coach panel speaks Turkish to the user
  (`app/ai/coach_engine.py`).
- **Imports:** Qt classes from `PySide6.QtCore`, `PySide6.QtGui`,
  `PySide6.QtWidgets`. Never wildcard.
- **QSS objectNames:** PascalCase (e.g. `ActionCall`, `PaneToggle`,
  `BrandMark`). Reach for an existing objectName before inventing a new one.
- **No rounded corners.** No drop shadows. No gradients except the table
  felt's accent radial glow.
- **bb everywhere on the table.** Internally chips for tournament, but
  `LivePokerTable.set_unit("bb")` divides by `hand.big_blind` for display.
  Meta bars / report screens still show chip totals.
- **Sharp 1px borders.** 2px only for active/focus state.
- **Hide-only, never disable, for action buttons.** See § 3.

---

## 7 · User's typical bug-report shape

The user (`uygar.soyrac@gmail.com`) reports in Turkish, often with a
screenshot. Pattern matching:

- "X karanlık görünmüyor / okunmuyor" → contrast/palette bug, usually
  Qt cascade issue. Reach for shorthand+longhand QSS override.
- "X üst üste / kapatıyor" → layout overlap. Check
  `_layout_children` offsets, raise_() z-order, or the deferred
  relayout in `render_state`.
- "self-QA yap" / "bug bash" → run a heuristic walkthrough, find issues
  through human-eye review, fix them, commit per-issue or as a sweep.
- "design guide göre yap" → fetch the design bundle from the URL in §2,
  check the relevant section, port the styles.
- "şu da olsun" → add the feature, wire shortcut if applicable, add to
  cheat sheet, commit, push.

The user expects an explicit `commit + push to GitHub` at the end of each
substantive change. They follow up with screenshots to verify.

---

## 8 · How to ship work

```bash
.venv/bin/python -m pytest tests/ -q              # 42 unit tests
.venv/bin/python tests/test_feature_audit.py      # 27 feature checks
.venv/bin/python tests/render_ui_screens.py       # PNGs to docs/screens
git add <touched files only>             # never `git add -A`
git commit -m "$(cat <<'EOF'
<imperative subject>

<one-paragraph explanation of WHY>

<bullet list of WHAT changed>

NN tests passing.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push origin main
```

Always include the test-passing count in the message. Always paste the
commit short-SHA back to the user with the run command.

---

## 9 · What's NOT done (good first tasks)

- **Responsive table sizing at narrow widths** — slot positions are %
  but seat tile minWidth=132 is fixed. At < 1100 px effective table
  width the seats start to overlap. Consider scaling tile padding +
  font sizes with widget width.
- **Bot action animations** — `theme.css` defines `.anim-deal`,
  `.anim-fold`, `.anim-pot-pop`, `.anim-muck`, etc. The Qt port doesn't
  use any of them. Adding a CSS-like transition to seat tone changes
  and pot-value flashes would carry information.
- **Bet-chip flight (seat → pot at street end)** — design spec calls
  for an animated chip-fly. Today chips just disappear when the street
  advances. Translate transform animation per Style Guide § 7.
- **Hand-history persistence display** — `app/db/repository.py` saves
  every hand, but no UI surfaces lifetime stats. Reports screen is
  seeded with demo data.
- **Solver integration** — every "solver" output is mock data with a
  source-confidence label. Hooking a real solver is a separate project.

---

## 10 · Untracked siblings (NOT part of this repo)

Outside `champion_poker_training_os/`:

- `../AiToEarn/`, `../poke/`, `../scientific-agent-skills/`,
  `../social_science_analyzer.py` — other projects, ignore them.
- `.claude/` — IDE config / hooks, do not commit.

Filter the staging area accordingly when committing.
