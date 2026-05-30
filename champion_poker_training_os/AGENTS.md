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
- **Test:** `.venv/bin/python -m pytest tests/ -q --ignore=tests/test_feature_audit.py`
  (79 unit tests + 1 xfail; that file has a module-level `sys.exit(0)` so it
  must be ignored by pytest and run as a script) +
  `.venv/bin/python tests/test_feature_audit.py` (feature checks, run directly) +
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
| **Design source — read FIRST** | `docs/design/` — mirrored copies of `UI_GUIDE.md`, `theme.css`, `poker-table.css`, `poker-table.jsx`, `Poker-Table.html`, `Style-Guide.html`. See `docs/design/README.md` for what each file is for. **Before inventing any new UI, read these — do NOT design a different look.** |
| **Two canonical palettes (don't mix)** | (1) **Poker-table / live play** — felt theme from `dark_flat.qss`: FOLD muted grey (`#898d80`), CALL lime (`#5ad17a`), RAISE/ALL-IN danger red (`#e87474`). Used by `poker_table.py` + play/tournament action buttons. (2) **Study / trainer screens** — bright flat "flashcard" convention defined in `quiz_trainer.py`: `COLOR_RAISE #DC2626` / `COLOR_CALL #10B981` / `COLOR_FOLD #2563EB`, bg `#0F1419`, card `#111827`, line `#1F2937`, ink `#FAFAFA`, good `#10B981`, bad `#DC2626`, muted `#94A3B8`. Used by Range Quiz / MTT Trainer / GTO Chart-style learning screens. **New trainer screens reuse palette (2); new live-table work reuses palette (1).** |
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
| **GTO range data (curated)** | `app/poker/gto_ranges.py` — `get_action(pos, hand, scenario, stack, mode, vs_position)` is the single lookup API. Curated charts cover **RFI** (`RFI_100BB_6MAX`), **push/fold** (`PUSH_FOLD_15BB_BTN`), and **vs-3bet** (`VS_3BET_{BTN,UTG,MP,CO}_100BB`, enabled for those 4 positions, cash, ≥60bb). `_is_curated()` decides curated-vs-heuristic — it's a **domain-by-domain** call, not blanket. **Two lessons learned**: (1) hand-curated WIDE ranges (BB defend / vs-RFI) came out systematically too tight (BB vs UTG 14% vs ~38% target) → defer to heuristic. (2) but for the POLARIZED vs-3bet domain the heuristic was *harmful* (4-bet 100% with TT/AQs, fold bluff-4bet A5s) → curated's textbook shape (value/flat/bluff) is better even if aggregate is a touch tight → vs-3bet uses curated (APPROX tier) |
| **GTO heuristic generator** | `app/poker/gto_generator.py` — `heuristic_get_action()` fallback for ANY (pos × scenario × stack × vs_pos) not curated. Principle-based: position tightness, stack-depth scaling, vs-opener tightness curve, 3-bet pyramid. Produces accurate aggregate % (BB defend 37/41/48/51/57 vs targets 38/42/48/52/58). 100% spot coverage, no empty result. **MTT ante widening (2026-05)**: `build_vs_rfi_range(.., mode)` — in MTT, BB/SB defend with an ante multiplier (BB ×1.24 cap 64%, SB ×1.10 cap 52%) + soft stack floor, so 25bb BB-vs-HJ defends ~61% (was 40%, matching PeakGTO ante spots) |
| **Monte Carlo equity** | `app/poker/mc_equity.py` — `calculate_equity()` + `equity_hand_vs_hand/range`, `equity_range_vs_range`. Pure-Python MC, ~500ms/5K iter. `expand_hand_key("AKs")` → concrete combos. Used by Quiz feedback + Hand History equity track. (Old static lookup `app/poker/equity.py` untouched) |
| **River CFR solver** | `app/poker/river_solver.py` — `RiverSolver(hero_range, villain_range, board, pot, bet_size_frac).solve(iters)` → per-hand BET/CHECK/CALL/FOLD via vanilla CFR + regret-matching. 4 info sets (HERO_FIRST, VILL_VS_BET, VILL_AFTER_CHK, HERO_VS_BET). ~430ms/20×28 combos×300 iter |
| **GTO Chart screen** | `app/ui/screens/range_trainer.py` — `GTORangeChartScreen` (alias `RangeTrainerScreen`). 13×13 grid via `RangeGrid`/`HandCell` (QPainter action splits), position/stack/scenario/mode pickers, right detail panel with `FrequencyBar` |
| **Range Quiz screen (PeakGTO-style)** | `app/ui/screens/quiz_trainer.py` — `QuizTrainerScreen` (`RangeQuizScreen` alias). Random spot generator (4 scenarios, vs_position-aware) + countdown + GTO compare + equity feedback (MC) + per-position stats + spaced-repetition wrong-queue. **Learning loop (2026-05)**: top session bar (HANDS/CORRECT/ERRORS/EV-LOSS/ELO), `QuizStats.record` updates ELO (K=24) + ev_loss_total, `QuizSpot.ev_loss_bb` (🟠 scenario-aware: RFI raise base 2.0, push/fold jam min(stack,15), vs-3bet 4.0), `difficulty_rating()` (1450 base + mixed/vs3bet/short adjustments), colored action-history strip, GTO% revealed on buttons after answer |
| **Solver Sandbox screen** | `app/ui/screens/solver_sandbox.py` — `SolverSandboxScreen`. 13×13 range pickers (hero/villain tabs) + presets + board/pot/bet/iter controls + SOLVE (runs `RiverSolver` in a QThread) → strategy tables |
| **Hand History Archive screen** | `app/ui/screens/hand_history.py` — `HandHistoryScreen`. Date list + paginated hands table + detail panel with per-street equity track + Gemini "analyze this hand" (`analysis_requested` Signal). DB helpers in repository.py: `get_dates_with_hands`, `get_hands_for_date`, `get_overall_archive_stats`, `_ensure_history_index` |
| **In-game GTO assist** | `app/ui/components/gto_range_widget.py` — `GTORangeWidget.update_range(pos, stack, game_type, hero_hand)` shows a colored RAISE/CALL/FOLD badge for hero's exact hand via `gto_ranges.get_action`. Wired in tournament_simulator + play_session. Also hosts **`GTODecisionReveal`** (end-of-hand panel): `show_decisions(log)` renders one row per street showing the GTO-optimal distribution, hero's actual action verdict (✓/≈/✗), and a **`_math_line`** — `📊 Equity %X · break-even %Y (pot · call) · MDF %Z · → call +EV/-EV`. Reset in `_deal_next`, shown in `_on_complete` |
| **MTT range engine** | `app/poker/mtt_ranges.py` — `get_action(mode="MTT")` routes here. `JAM_PCT` table (Nash push/fold, 8-25bb × position, interpolated), `call_vs_jam_pct`, ante-aware depth-shaped `build_mtt_rfi` (20-200bb: deep adds suited connectors, shallow tightens). `mtt_jam_pct(pos, stack)` is the public jam% lookup |
| **MTT Trainer screen** | `app/ui/screens/mtt_trainer.py` — `MTTTrainerScreen`. Mode 1: Push/Fold Drill (random spot + Nash compare + countdown + per-stack stats). Mode 2: Stack Explorer (13×13 range grid; position × 10-200bb × Scenario: Auto/ICM Bubble/ICM FT/Satellite/PKO/Squeeze) |
| **ICM/PKO/Squeeze ranges** | `app/poker/mtt_ranges.py` — `build_icm_push_fold(pos, stack, stage)` (jam tightens under ICM), `build_icm_call_vs_jam(stack, stage, bubble_factor)`, `build_pko_jam/call_vs_jam(.., bounty_ratio)` (widens), `build_squeeze(pos, stack, num_callers)` (polarized). Uses `app/poker/icm.py` (Malmuth-Harville, risk_premium, bubble_factor, bounty_ev). mtt_get_action scenarios: "ICM Push/Fold", "PKO Jam", "Squeeze" |
| **Accuracy provenance** | `app/poker/gto_provenance.py` — `range_provenance(scenario, pos, stack, mode)` → tier (EXACT ✅ / APPROX 🟡 / CONCEPT 🟠 / GAP ❌). GTO Chart shows a badge so the user ALWAYS knows what they're learning. **Honest map**: curated RFI + push/fold Nash + equity + ICM = EXACT; heuristic vs-RFI/vs-3bet/MTT-depth = APPROX; river solver = CONCEPT; full postflop multiway = GAP |
| **Live GTO on buttons** | `app/poker/gto_live_advice.py` — `live_gto_advice(hand, hero_idx, mode)` maps live state → GTO scenario (RFI/vs-RFI/vs-3bet/push-fold via position + betting history + stack) → action frequencies. play_session + tournament `_update_action_buttons` append `42%` to each button (Real Experience Mode'da gizli). **Preflop** = curated/heuristic (EXACT/APPROX). **Postflop** = `_postflop_advice` **board-texture-aware** model (🟠 CONCEPT): MC equity vs action-aware villain range + `postflop_gto` motoru. `_hero_has_initiative` / `_hero_in_position` (dealer_idx'ten) bağlamı belirler. `LiveAdvice.equity` hero equity %. Also writes `AppState.live_gto` (pot_bb/to_call_bb/equity/sizing) for coach + reveal |
| **Postflop GTO beyni** | `app/poker/postflop_gto.py` (Phase D3, saf fonksiyon) — `classify_board(community) → BoardTexture` (paired/monotone/two_tone/connected/wetness/label). `cbet_strategy(eq, tex, in_position, has_initiative) → (bet_freq, size)`: kuru board → yüksek c-bet küçük size (range bet), ıslak → düşük/polarize büyük size, OOP/inisiyatifsiz → daha çok check. `defend_strategy(eq, tex, pot, to_call) → (fold,call,raise)`: MDF + equity + ıslakta semi-bluff raise. Solver-exact değil, GTO-ŞEKLİ doğru |
| **Oturum skor kartı** | `app/poker/session_score.py` (Phase D2) — `SessionScore.add_hand(log)` her elin notlarını biriktirir; `summary()` → GTO doğruluk % (A+B oranı), avg score, EV kaybı, en zayıf street/kategori. play/tournament ekranlar bir SessionScore tutar, reveal panelinin en üstünde "OTURUM N el · GTO doğruluk %X · EV kaybı Ybb · en zayıf: <street>" satırı |
| **AI Coach GTO context** | `main._gto_context_block()` formats `AppState.live_gto` into the Gemini prompt prefix (scenario, hand, freqs, tier). Injected in `chat_with_coach` so the coach evaluates "is my decision GTO-correct?" with real frequencies. `_tournament_context_block()` (ICM) + GTO block + last-hand block stack in order |
| **Fold → space → next hand** | play_session `_space_pressed`/`_space_pressed_mtt`: if hero folded mid-hand, space fast-forwards remaining bot actions (step_action loop) + completes + deals next — no waiting for the bots. **Real Experience Mode'da fold→space önce notlandırılmış reveal'ı gösterir, ikinci space sonraki el** |
| **Real Experience Mode** | `AppState.real_experience` (varsayılan False). Topbar'da `_ExperienceToggle` (REAL/TRAIN) → `TopStatusBar.experience_toggled` → `MainWindow._on_experience_toggled` aktif ekran(lar)ın `apply_experience_mode(real)`'ini çağırır (multi-tab çocukları dahil). AÇIK iken oyun sırasında TÜM GTO ipuçları gizli (`gto_range` paneli setVisible(False), buton %'leri suppress); pot/stack/board normal. El bitince **bloklayan notlandırılmış reveal** (`graded=True`) — turnuvada auto-deal kapanır, SPACE ile ilerlenir. KAPALI = eğitim modu (range bağlamı görünür, cevap `reveal_action=False` ile yine gizli). play_session + tournament_simulator ikisinde de |
| **Karar notlandırma** | `app/poker/decision_grade.py` — saf fonksiyon. `grade_decision(snap) → DecisionGrade(letter A-F, score, ev_loss, note)`: hero en yüksek-frekans GTO aksiyonunu seçti/`≥60` → A; `≥35`→B; `≥15`→C; `<15`→D; EV overlay (`>4bb`→F, `>1.5bb`→cap C); `available=False`→N/A. `grade_hand(decisions) → HandGrade` ortalama. `GTODecisionReveal.show_decisions(log, graded=True)` el skoru başlığı + satır rozetleri gösterir |
| **Karar yakalama (paylaşılan)** | `app/poker/decision_capture.py` — `DecisionRecorder` (reset/capture/attach_hero, street+to_call dedup) + `make_snapshot(hand, hero_idx, gto, bb, sizing)`. tournament_simulator bunu kullanır (play_session'ın kendi inline capture'ı henüz ayrı — gelecekte birleştirilebilir) |
| **Hero-decision persistence + Leak Finder** | `app/db/repository.py` — `record_decision_log(log)` writes each hand's `_decision_log` snapshots to `hero_decisions` (cols added via `_ensure_decision_columns` migration: `category`, `street`, `created_at`). Called in play_session `_on_complete`/`_on_complete_mtt`. `frequency_error = 100 − (GTO% of hero's chosen action)`; `ev_loss` from equity+pot-odds (+EV fold or −EV call). `get_decision_leaks(min_sample=8)` buckets by category (RFI/vs-RFI/vs-3bet/Postflop/Push-Fold) → over-fold / spew / deviation leaks. `get_leak_analysis()` merges played-hands stats (VPIP/WTSD/W$SD) + decision leaks. **`app/ui/screens/leak_finder.py`** `LeakFinderScreen` is now **data-driven**: `reload()` pulls `get_leak_analysis()`, banner shows real-vs-example state, static `EXTENDED_LEAKS` only as fallback when data is thin. `main.navigate()` calls `reload()` on any screen that has it. **Phase D4**: "🔧 Hatalarımdan Drill Üret" → `DrillLibrary.generate_repair_pack(leaks)` gerçek leak'lerden ağırlıklı tamir paketi (Critical=6/High=4/Medium=2 drill — ağır leak → daha çok tekrar = spaced-repetition), Spot Practice Trainer'a yönlendirir. `generate_from_leak(leak, count)` artık parametrik |
| **Multi-street solver** | `app/poker/multistreet_solver.py` — `MultiBetRiverSolver` (EXACT: CHECK/BET_SMALL 33%/BET_BIG 75%, river is single node so multi-size is exactly solvable; big=polarized, small=thin-value verified). `solve_turn` (CONCEPT: turn bet/check with river-equity rollout) |
| **Nested turn+river CFR** | `app/poker/nested_solver.py` — `NestedTurnRiverSolver`: turn bet/check → villain → river DEALT (real chance node, full enumeration + card removal) → river subtree fully solved. EXACT heads-up. Polarized structure verified (KK bet, QQ check, air bluff). Slow (~29s per-combo). Critical bugs fixed: zero-sum payoff (each invests P/2) + vanilla CFR updates BOTH players each iter |
| **Vectorized solver (numpy)** | `app/poker/vector_solver.py` — `VectorRiverSolver`: showdown = matrix product `W @ reach` (W = signed showdown matrix, collision-masked). ~27x faster than per-combo (3000 iter / 140ms). Solver Sandbox's built-in engine uses this (×10 iters, RiverSolver fallback if numpy missing). numpy>=1.24 dep. Same vectorization extends to turn/flop chance nodes |
| **Vectorized turn+river solver (⚠️ experimental)** | `app/poker/vector_turn_solver.py` — `VectorTurnRiverSolver`: turn bet/check → 3 river contexts (A=xx, B=xbc, C=bc) vectorized; ~28x faster. Filters board-colliding combos in `__init__` (phantom-combo bug fixed). **KNOWN BUG (unshipped)**: multi-hand hero range mis-distributes value (KK trips 0% bet vs nested 34%) — could not root-cause. **NOT UI-wired**; `nested_solver` / TexasSolver remain the correct turn engines. Documented via xfail test `test_vector_turn_KNOWN_BUG_multihand_value_distribution` |
| **Bet-sizing analysis (🟠 concept)** | `app/poker/sizing_advice.py` — `SizingAdvice.score(chosen_bb, pot_bb)` → {quality_pct, ev_loss_bb, verdict}; `sizing_advice(hand, hero_idx, mode)` recommends a GTO-standard size (preflop open/3-bet/jam, postflop board-texture fraction). Attached to `AppState.live_gto["sizing"]` in play_session/tournament; `main._gto_context_block()` feeds it to the coach so it can give concrete sizing leaks ("5bb yerine 12bb daha iyi olurdu çünkü…"). Verified: 5bb→quality 54, 12bb→quality 92 |
| **TexasSolver adapter** | `app/poker/texassolver_adapter.py` — arms-length subprocess to the external open-source TexasSolver (AGPL, beats PioSolver). `find_texassolver_binary()` (TEXASSOLVER_PATH env / common paths / PATH). `TexasSolverEngine.solve()` writes console command file → subprocess → parse JSON. **NOT bundled** (AGPL viral → user installs binary themselves; we only invoke = mere aggregation). Solver Sandbox engine toggle: "Built-in CFR 🟠" / "TexasSolver ✅" (when installed). Console command/JSON format may need version-specific tweaks in `_build_input_commands`/`_parse_strategy` |

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

### Bot SPR-aware commitment gate (anti-spew)  — fix 2026-05-29
Postflop bet/raise sizes are chosen as a *pot fraction*. At low SPR a
"normal" half-pot c-bet or river bluff equals the whole stack, so the
engine (`PokerGame._coerce_action`, `amount >= stack → ALL_IN`) turned it
into a full-stack shove — i.e. the bot shoved 7-high / a small underpair
as a "bluff" or "thin value bet" (the reported "76 ile all-in" symptom).
Fix lives in `BotBrain._bet_amount` / `_raise_size` + helper `_commit_ok`:
- `_COMMIT_FRAC = 0.70` — a bet/raise ≥ 70% of remaining stack is treated
  as a stack commitment.
- A committing size is only allowed with genuine value (`strength >= 0.60`
  = overpair / top-pair-good / two-pair+) **or** a real semi-bluff draw
  (`draws >= 0.30` = flush draw / OESD). Otherwise the bet is declined
  (`_bet_amount` returns 0.0 → caller CHECKs) or the raise is downgraded to
  CALL/CHECK. Pot-committed CALLS are unaffected (separate guard above).
- All postflop `_bet_amount` / `_raise_size` call sites pass
  `(player, strength, draws)` so the gate sees the real hand.
- Verified over 4000 hands (8-max, 25bb, Karma Mixed): voluntary trash
  jams 62 → 0; legit value/draw all-ins + pot-odds calls preserved; VPIP
  fidelity unchanged. Regression guard: `tests/test_bot_realism.py`.
- NB: this is decision-quality, NOT a stat target — it shrinks the spewy
  tail without touching archetype VPIP/PFR/AF.

### Eğitim döngüsü: cevabı oyun sırasında SAKLA, el sonu reveal — Phase B (2026-05-29)
User direktifi: "oyunda bana optimal kararı vermesin ama her el sonunda …
fold check call raise x size raise y size etc optimal kararı versin."
- **Canlı bar artık cevabı sızdırmıyor.** `GTORangeWidget.update_range(...,
  reveal_action=False)` → hero rozeti `"<hand>\n? KARARINI VER"` (dashed
  border) gösterir; aksiyon butonları yüzde etiketi taşımaz (`lbl()` sadece
  base string döner). GTO yine de arka planda hesaplanır (koç + reveal için).
- **Yeni `GTODecisionReveal(QFrame)`** (`gto_range_widget.py`): her hero karar
  noktasını `_capture_decision()` (cash) / `_capture_decision_mtt()` ile
  street başına bir kez kaydeder (`_decision_log` + `_captured_keys` dedup,
  `_deal_next`'te sıfırlanır). Hero gerçek aksiyonu `_record_hero_decision*`
  ile snapshot'a iliştirilir. El bitince (`_on_complete*`) panel her street
  için optimal dağılımı (FOLD/CHECK-CALL/RAISE/ALL-IN renkli %), raise size'ı
  (raise% > 0 ise `→ raise size: X bb`), hero'nun gerçek kararını ve verdict'i
  (`✓ uyumlu ≥50% · ≈ kabul edilebilir ≥15% · ✗ sapma`) basar.
- PNG kanıt: `docs/screens/play_reveal.png`.

### AI koç = GTO-matematik eğitmeni — Phase B (2026-05-29)
User direktifi: "Koça soruncada … gto ya göre koçlık etsin. Nasıl düşünmem
gerektiğini söylersin. Bu gto'nun bir math hesabı … sistemimizi bu math
hesabına göre optimize edebiliriz."
- `_gto_pct` (cash) ve tournament_simulator MTT yolu artık `state.live_gto`
  içine `pot_bb` / `to_call_bb` / `street` de yazıyor (MTT'de chip→bb bölünür).
- `MainWindow._gto_context_block()` (main.py) bu spotun **somut sayılarını**
  hesaplayıp prompt'a enjekte ediyor: pot odds = `to_call/(pot+to_call)`,
  break-even equity, risk/ödül oranı, MDF = `pot/(pot+bet)`, alpha. Ardından
  "[KOÇLUK TARZI — NASIL DÜŞÜNMELİ ÖĞRET]" 4-adımlı düşünme direktifi (equity →
  pot-odds eşiği → fold/call/raise + fold/implied equity → mixed ise neden).
  Sistem prompt'u (`coach_prompts.py SYSTEM_PROMPT_TR`) zaten Socratic GTO
  mentoru; bu blok ona **bu el'in gerçek rakamlarını** verir.

### GTO chart matrisi aksiyon-bazlı renk — Phase B (2026-05-29)
User direktifi: "gto chartları düzelt … call raise fold ve optimal decision'a
göre bir chart." `gto_range_widget._HandMatrixWidget.set_action_range(pos,
stack, mode, scenario, vs_position)` her 169 hücre için `get_action()` çağırıp
`_action_cell_bg()` (RAISE `#DC2626` / CALL `#10B981` / FOLD `#2563EB`, mixed =
yatay `qlineargradient`) + `_action_text_color()` uygular. `gto_range_dialog.py`
artık `set_range(hands)` yerine `set_action_range(...)` çağırır, legend de
Raise/Call/Fold/Senin elin. PNG: `docs/screens/gto_dialog_action.png`.

### Kart + buton boyutlarını küçült — Phase B (2026-05-29)
User: "kartların boyu çok büyük … küçültüp diğer alanlara yer açabiliriz."
- Hero hole kartları `lg` (60×84) → `md` (44×60); board kartları `md` → `sm`
  (32×44) (`poker_table.py`).
- `LivePokerTable.minimumHeight` 380 → 330; play/MTT tablo holder 440 → 380.
- Aksiyon butonları minH 44 → 38, minW 68 → 64 (cash + MTT).
- PNG empati testi yapıldı (`docs/screens/05_play_session_live.png`): masa
  daha kompakt, alt bölge nefes alıyor.

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
# Phase B — el-sonu GTO reveal + math koçu + chart/kart UI (2026-05-29) — newest first
#   el sonu optimal karar paneli (cevap oyunda gizli), koça somut pot-odds/MDF,
#   aksiyon-bazlı chart matrisi (gto_range_dialog), kart/buton küçültme.
# Bot realism + PeakGTO trainer + sizing (2026-05-29) — newest first
253db58 fix(bot): SPR-aware commitment gate — botlar trash ile all-in atmıyor
b9b7abf feat(trainer): preflop Range Quiz'i PeakGTO seviyesine çıkar + BB-defans leak fix
ba45ef5 feat(solver): vectorized turn+river CFR (deneysel) + phantom-combo bug fix
70001b7 feat(sizing): bet-sizing leak analizi — GTO-standart boyut + quality/EV scoring
# Live GTO + coach + UX (2026-05-28) — newest first
763ff13 feat(coach): AI Coach'a canlı GTO context — "kararım doğru mu?"
9afb930 feat(play): fold sonrası space → anında sonraki el
fbff768 feat(live): GTO % on action buttons (play + tournament)
2f8cbe2 fix(solver): TexasSolver adapter — gerçek v0.2.0 formatına kalibre
# Solver speed + external engine (2026-05-28)
7c31298 perf(solver): Solver Sandbox built-in engine → vectorized (numpy)
7c5d841 feat(solver): vectorized river CFR (numpy) — ~27x hız
a87b0fb feat(solver): TexasSolver integration — arms-length subprocess (EXACT)
dabd388 feat(solver): nested turn+river CFR — chance nodes, EXACT heads-up
# Full GTO completeness (2026-05-28)
4ccc45b feat(solver): multi-bet-size river (EXACT) + turn rollout (CONCEPT)
b0a1052 feat(mtt): ICM/PKO/Squeeze scenarios wired into Stack Explorer
56bddd7 feat(mtt): ICM + squeeze + bounty range engines
1178cea feat(gto): accuracy provenance system — "yanlış öğrenme" koruması
# MTT system (2026-05-28)
4ceba63 docs: AGENTS.md — MTT engine + trainer
<mtt>   feat(mtt): MTT Trainer screen — push/fold drill + stack explorer
1d872f1 feat(mtt): stack-depth-aware MTT range engine (Nash + ante)
# GTO + equity + solver session (2026-05-28)
40e9a42 docs: AGENTS.md — GTO/equity/solver session
501f5aa fix(gto): honest curation — defer wide ranges to heuristic
501bce6 feat(gto): heuristic generator → %100 spot coverage
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

## 9 · Yapılacaklar — Roadmap (sıradaki ajan buradan devam etsin)

Phase B (2026-05-29) tamamlandı: el-sonu GTO reveal, GTO-math koçu, aksiyon-
bazlı chart matrisi, küçültülmüş kart/butonlar.

Phase C (2026-05-29) tamamlandı:
- ✅ **Reveal paneline equity + pot-matematiği** — her street için MC equity +
  break-even (pot odds) + MDF + "call +EV/-EV" satırı (`gto_range_widget.py`
  `_math_line`, `gto_live_advice` `equity` alanı).
- ✅ **Postflop villain range aksiyon-duyarlı** — villain bet boyutuna göre
  devam-range'i daralıyor (`_villain_continuing_range(n, bet_frac)`).
- ✅ **vs-3bet (4-bet) curated chart'ları etkinleştirildi** — BTN/UTG/MP/CO,
  cash, ≥60bb. Heuristik bu polarize domende ZARARLIYDI (TT/AQs ile %100 4-bet,
  A5s bluff-4bet'i fold). Curated ders-kitabı şekli (value/flat/bluff) →
  APPROX tier (`_is_curated`). BB-defend hâlâ heuristik (geniş domain).
- ✅ **Hero kararları persist + Leak Finder gerçek veriye bağlandı** —
  `record_decision_log` her el sonu `hero_decisions`'a yazıyor; `get_decision_leaks`
  kategori bazlı over-fold/spew/sapma tespiti; `get_leak_analysis` iki kaynağı
  birleştiriyor; `LeakFinderScreen` artık data-driven (örnek katalog sadece
  veri yokken fallback).

Aşağıdakiler **henüz açık** — kabaca öncelik sırasıyla.

### 9a · GTO derinliği (en yüksek değer)
- **Postflop GTO solver-exact değil.** Canlı reveal postflop'ta equity-temelli
  CONCEPT (🟠) model kullanıyor (`_postflop_advice`); yön doğru ama solver-exact
  değil. TexasSolver / nested CFR'yi canlı reveal'a bağlamak gerçek frekans verir.
- **Multiway + sizing tree zayıf.** `sizing_advice` tek bir önerilen boyut
  veriyor; GTO'da spot başına 2-3 boyut karışımı olur. Sizing matrisi
  (small/big/overbet frekansları) ileride.
- **vs-RFI (BB defend) curated yok.** Bu geniş domain hâlâ heuristik (curated
  elle yazıldığında sistematik çok-sıkı çıkıyor). Solver-verified geniş range
  tabloları gerekir.

### 9b · UI / UX
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

### 9c · Veri / kalıcılık
- **Hand-history persistence display** — `app/db/repository.py` saves
  every hand, but no UI surfaces lifetime stats. Reports screen is
  seeded with demo data.
- ✅ **Leak Finder gerçek veriye bağlandı** (Phase C) — `hero_decisions`
  persist + `get_decision_leaks` + data-driven `LeakFinderScreen`. Sıradaki:
  stats-temelli leak'lere de EV-tahmini eklemek (şu an sadece karar-bazlı
  leak'ler EV gösteriyor).

### 9d · Solver
- **Solver integration** — built-in CFR çalışıyor ama "EXACT" çıktılar
  TexasSolver subprocess'ine bağlı (AGPL, repo dışında `~/TexasSolver/`).
  Canlı postflop reveal'i bu motora bağlamak ayrı bir proje.

> NOT (lisans): TexasSolver AGPL — binary'yi repoya KOYMA, sadece subprocess
> ile arms-length çağır. Gemini API key `.env`'de, git-ignored — ASLA commit etme.

---

## 10 · Untracked siblings (NOT part of this repo)

Outside `champion_poker_training_os/`:

- `../AiToEarn/`, `../poke/`, `../scientific-agent-skills/`,
  `../social_science_analyzer.py` — other projects, ignore them.
- `.claude/` — IDE config / hooks, do not commit.

Filter the staging area accordingly when committing.
