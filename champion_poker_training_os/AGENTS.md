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
- **Test:** `.venv/bin/python -m pytest tests/ -q` (42 tests, all expected
  to pass)
- **Repo:** https://github.com/uSoyrac/poke.git (branch `main`)

---

## 2 · Source-of-truth files

| Concern | File |
|---|---|
| Design tokens, type, animations | `app/ui/theme/dark_flat.qss` (Qt port of `theme.css` from the design bundle) |
| Style Guide reference | `/tmp/style_guide_design/poke/project/UI_GUIDE.md` (gone on reboot — re-fetch from `https://api.anthropic.com/v1/design/h/zXOGR9AImpY9DLg-rtRoDA` if needed) |
| Poker felt / seats / chips | `app/ui/components/poker_table.py` (`LivePokerTable`, `SeatState`, `seats_from_hand`) — **legacy** `PokerTableView` kept here too because trainer screens still import it |
| Card rendering (4-Color Deck) | `app/ui/components/card_view.py` — `SUIT_COLORS` maps each suit to its hex |
| Shortcut registry | `app/ui/components/shortcuts.py` (`SHORTCUTS` list + `ShortcutsDialog`) |
| Sidebar nav | `app/ui/components/sidebar.py` (`EXPANDED_WIDTH=232`, `COLLAPSED_WIDTH=52`) |
| AI coach panel | `app/ui/components/coach_panel.py` (`EXPANDED_WIDTH=360`, `COLLAPSED_WIDTH=40`) |
| Engine (Hold'em rules) | `app/engine/game_loop.py` — `PokerGame.step_action()` is the per-tick API the UI drives |
| Bot brains + archetypes | `app/engine/bot_brain.py` — `BOT_ARCHETYPES` dict, includes "Karma (Mixed)" and "GTO Expert" |
| Tournament wrapper | `app/simulator/tournament_runner.py` — owns blind schedule, owns a `PokerGame` |
| App shell + shortcuts | `app/main.py` — `MainWindow` wires Ctrl+B / Ctrl+J / Ctrl+1..9 / ? |

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

Adding a new shortcut: append one row to `SHORTCUTS` in
`app/ui/components/shortcuts.py` (cheat sheet picks it up automatically),
then bind a `QShortcut` in the relevant screen.

---

## 5 · Recent commits (read for context)

```
7256d87 feat: shortcut library — central registry + ? cheat sheet
46a36ca feat: 4-Color Deck — each suit has its own colour
a2ab383 fix: CALL & ALL-IN buttons — white text + bulletproof solid fill
55526bf fix: CALL button no longer paints with disabled palette while enabled
649ddbe fix: end-to-end UX review — 9 issues from latest screenshot
287556d feat: showdown reveal + collapsible sidebar/coach (Style Guide pass)
e2c84be feat: paced bot actions — see UTG act first, then UTG+1, then SB, then BB
1f6a70a fix: bug-bash sweep — chip positioning, button truncation, collapsible panels
d082f88 feat: tournament felt now displays in BB, like real online poker
edccb2f fix: bet chip positioning + hero card / TO CALL overlap
f2e4373 feat: Unified LivePokerTable + bot/UX overhaul
```

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
.venv/bin/python -m pytest tests/ -q    # 42 tests must pass
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
