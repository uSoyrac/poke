# Poke — UI Guide

A complete reference for the **Poke** poker training OS design system. This document is self-contained: feed it to Claude Code, paste it into a Figma comment, or use it as the spec source for any reimplementation.

**Source of truth:** `theme.css` (tokens) · `ui.jsx` (components) · `Poke.html` (live prototype)
**Aesthetic:** Brutalist editorial — sharp corners, heavy display type, tabular monospace numbers, generous whitespace, functional ornament only.

---

## 1 — Principles

1. **Sharp, not rounded.** All radii are 0. Borders are 1 px hairlines (`--line`) or 1 px strong (`--line-2`). Reserve 2 px borders for active/focus state.
2. **Numbers as data.** Every numeric value uses JetBrains Mono with tabular-nums. Never display percentages in display fonts.
3. **One primary action per screen.** The page header may have multiple buttons but exactly one is `variant="primary"`.
4. **Numbered everything.** Page headers carry `00 / DASHBOARD`. Cards carry `A1`, `A2`, `B1`. Sections carry small mono numbers. This is editorial typography, not random style.
5. **Density beats decoration.** No drop shadows, no gradients (except subtle table felt), no rounded corners. Visual rhythm comes from grids, lines, and type contrast.
6. **Low cognitive load.** Actions live at predictable positions: page actions top-right, fold/call/raise/all-in always bottom of Play screen.

---

## 2 — Design Tokens

### Color (dark, default)

```css
--bg:        #0a0c0a;   /* page background */
--bg-2:      #0f1210;   /* sidebar, raised areas */
--surface:   #131613;   /* cards, modals */
--surface-2: #181b17;   /* card hover, table headers */
--line:      #23271f;   /* 1-px hairlines */
--line-2:    #33382c;   /* 1-px strong borders */
--ink:       #f4f5ee;   /* primary text */
--ink-2:     #d6d8cf;   /* secondary text */
--muted:     #898d80;   /* tertiary, labels */
--dim:       #5a5e54;   /* off-state */

--accent:    oklch(72% 0.18 145);  /* lime green — brand */
--accent-2:  oklch(82% 0.18 145);  /* accent hover */
--accent-ink:#0a0c0a;              /* text on accent */

--danger:    oklch(64% 0.22 25);   /* raise, error */
--danger-2:  oklch(74% 0.18 25);   /* danger lighter */
--warn:      oklch(80% 0.16 80);   /* amber */
--info:      oklch(72% 0.14 235);  /* blue, fold */
```

### Color (light)

```css
[data-theme="light"] {
  --bg: #f3f3ee;   --bg-2: #ebebe5;   --surface: #fff;   --surface-2: #f7f7f1;
  --line: #d8d8d0; --line-2: #b2b3a8; --ink: #0a0c0a;    --ink-2: #2a2d28;
  --muted: #5a5e54; --dim: #8a8d83;
  --accent: oklch(55% 0.18 145); --accent-2: oklch(45% 0.18 145); --accent-ink: #fff;
}
```

### Type pairing

| Family               | Weight        | Use                                                        |
|----------------------|---------------|------------------------------------------------------------|
| **Space Grotesk**    | 400/500/600/700 | Body, headings, button labels, KPI values                |
| **JetBrains Mono**   | 400/500/700   | Numbers, code, labels (uppercase + tracking), card chips   |
| **Instrument Serif** | 400 italic    | Editorial accents inside headlines (`<em>` tags)           |

Load:
```html
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;700&family=Instrument+Serif:ital@0;1&display=swap">
```

### Type scale

```
H1 (page title)   Space Grotesk 700 · clamp(28px, 4vw, 52px) · -0.045em tracking · 0.96 line-height
H2 (modal title)  Space Grotesk 700 · 22px · -0.03em
H3 (section)      Space Grotesk 600 · 14px · -0.01em
Body              Space Grotesk 500 · 14px · 1.4 line-height
Caption           Space Grotesk 500 · 12-13px · 1.5 line-height
Label             JetBrains Mono 500 · 10px · 0.12em tracking · uppercase
KPI value         Space Grotesk 700 · 40px · -0.04em · tabular-nums
KPI value (lg)    Space Grotesk 700 · 64px · -0.05em
Code/data         JetBrains Mono 500 · 12-13px · tabular-nums
Editorial italic  Instrument Serif 400 italic · matches surrounding size
```

Helper classes in `theme.css`:
```css
.t-display { font-family: 'Space Grotesk'; font-weight: 700; letter-spacing: -0.04em; }
.t-mono    { font-family: 'JetBrains Mono'; font-variant-numeric: tabular-nums; }
.t-serif   { font-family: 'Instrument Serif'; font-style: italic; }
.t-label   { font-family: 'JetBrains Mono'; font-size: 10px; font-weight: 500;
             text-transform: uppercase; letter-spacing: 0.12em; color: var(--muted); }
```

### Spacing

Scale (px): `4 · 6 · 8 · 10 · 12 · 14 · 16 · 18 · 20 · 24 · 28 · 32 · 40 · 48 · 64`

Conventions:
- Card padding: 14 px header / 18 px body.
- Page padding: 28 px top, 28 px sides, 60 px bottom.
- Gaps between cards in a row: 20 px.
- Gaps between sections: 24 px.

### Radii & borders

- `border-radius: 0` everywhere. No exceptions.
- `1px solid var(--line)` — default container border.
- `1px solid var(--line-2)` — interactive elements, cards.
- `2px solid var(--accent)` — focus, active panel, primary CTA.

### Motion

```css
/* timing functions */
--ease-snap:    cubic-bezier(.3, .7, .3, 1);     /* default */
--ease-pop:     cubic-bezier(.2, .8, .2, 1);     /* counters, scale */
--ease-overshoot:cubic-bezier(.3, .7, .3, 1.4);  /* labels appearing */

/* durations */
120ms   tap feedback, color transitions
240ms   fold-out, fade
320ms   label-pop, seat-act
520ms   pot-pop, muck-fly
720ms   chip-fly (seat → pot)
```

Animation class names (defined in `theme.css`):
`.anim-deal` `.anim-pulse` `.anim-pot-pop` `.anim-fold` `.anim-seat-act` `.anim-label` `.anim-muck` `.anim-count`

---

## 3 — App layout

```
┌──────────┬──────────────────────────────────────────────────────┐
│          │ TOP BAR  56px  ─ breadcrumb / scenario / theme        │
│          ├──────────────────────────────────────────────────────┤
│ SIDEBAR  │                                                       │
│  232px   │                                                       │
│          │             MAIN SCROLL AREA                          │
│  brand   │             (Page screens or full-bleed)              │
│  groups  │                                                       │
│  user    │                                                       │
│          ├──────────────────────────────────────────────────────┤
│          │ STATUS BAR  28px  ─ connected · cache · shortcuts     │
└──────────┴──────────────────────────────────────────────────────┘
```

CSS grid:
```css
.app {
  display: grid;
  grid-template-columns: 232px 1fr;
  grid-template-rows: 56px 1fr 28px;
  grid-template-areas: "nav top" "nav main" "nav bot";
  height: 100vh;
}
```

### Page header pattern

Every Page-screen begins with:

```html
<div class="page__hd">
  <div>
    <div class="page__num">00 / DASHBOARD</div>
    <h1 class="page__title">Good evening,<br><em>Erkin</em> — focus on <em>3-bet defense</em>.</h1>
    <div class="page__sub">Your queue has 12 spots due. EV-loss trending down…</div>
  </div>
  <div class="page__act">
    <button class="btn">Import</button>
    <button class="btn btn--primary">Start training</button>
  </div>
</div>
```

The `<em>` inside `page__title` automatically switches to Instrument Serif italic — never use it for emphasis, only for editorial rhythm in the headline.

---

## 4 — Components

### Btn

```jsx
<Btn variant="primary" icon="play" kbd="↵">Start training</Btn>
<Btn variant="ghost" icon="upload">Import</Btn>
<Btn variant="danger" lg>Reset</Btn>
<Btn block icon="save">Save range</Btn>
```

Props: `variant` (default | primary | danger | ghost) · `icon` (icon name) · `kbd` (small keyboard hint) · `block` (full-width) · `lg` (larger padding) · `disabled`.

Visual: 1px border, 9×14 padding, 13px Space Grotesk 600, -0.01em tracking. Primary = solid accent. Ghost = no fill. Danger = solid danger. No hover lift, no shadow — just a slight border-color shift.

### Card

```jsx
<Card num="A1" title="Today's training block" sub="4 SPOTS · ~25 MIN" action={<Btn variant="ghost">Re-roll</Btn>}>
  …body content…
</Card>
```

Header pattern: `num · title · sub · action`. Body has 18 px padding by default; pass `padding={false}` to remove (for tables, lists).

### Tag

```jsx
<Tag tone="g" dot>ACTIVE</Tag>
<Tag tone="r">LEARN</Tag>
<Tag tone="y">MEDIUM</Tag>
<Tag tone="b">FOLD</Tag>
<Tag>NEUTRAL</Tag>
```

Tones map directly to semantic colors. Dot prop adds a 5px dot indicator. Always uppercase, mono, 10px.

### Stat / KPI

```jsx
<Stat label="WINRATE" value="7.2" unit="bb/100" delta="1.4" deltaSign="+" sub="vs last 7d"/>
<Stat label="EV-LOSS" value="0.17" unit="bb/h" delta="0.05" deltaSign="−" mono/>
```

Visual: 18×20 padding, 40px Space Grotesk value, 10px JetBrains Mono label. Delta+ in accent, delta− in danger-2. Use `mono` to switch value to JetBrains Mono.

### Seg (segmented control)

```jsx
<Seg options={["Tournament","Cash Games"]} value={lib} onChange={setLib}/>
<Seg options={[{value:"strategy",label:"STRATEGY"},{value:"ev",label:"+EV"}]} value={view} onChange={setView}/>
```

Visual: row of buttons, single 1px border, 7×14 padding each, mono 11px uppercase, accent fill when active.

### Bar

```jsx
<Bar value={78} max={100} tone="g" h={6}/>
```

Tones: `g | r | y | b`. Height defaults to 6 px. No animation by default.

### Spark

```jsx
<Spark data={[3.1, 2.4, 4.2, 3.8, 5.1, 6.2]} w={120} h={36}/>
<Spark data={[5,4,3,2,1]} down/>  /* danger color */
```

A polyline + filled polygon below. Use for inline trend indicators in stats and tables.

### PCard (poker card)

```jsx
<PCard card="As"/>          {/* Ace of spades */}
<PCard card="Kh" size="lg"/>{/* large */}
<PCard card="Qd" size="xs"/>{/* tiny, for inline use */}
<PCard back/>               {/* card back, accent diagonal stripes */}
```

Notation: `<rank><suit>` where rank ∈ `23456789TJQKA` and suit ∈ `shdc` (spade/heart/diamond/club). Red suits get `--danger`. Sizes: xs 22×30 · md 38×52 · lg 64×88.

### Split (resizable panes)

```jsx
<Split direction="horizontal" sizes={[280, "fill", 320]} mins={[180, 400, 240]} storageKey="coach">
  <Pane1/> <Pane2/> <Pane3/>
</Split>

{/* For inline page sections — height is auto */}
<Split fill={false} sizes={["fill", 380]} mins={[400, 300]} storageKey="studio">
  <LeftCol/> <RightCol/>
</Split>
```

Props: `direction` · `sizes` (px values; one can be `"fill"`) · `mins` · `storageKey` (persists drag in localStorage) · `fill` (default true; set false for page-style auto-height).

Visual: 4–20 px draggable handle, turns accent green on hover. Supports horizontal & vertical.

### RangeGrid

```jsx
<RangeGrid ranges={{ "AKs": { raise: 0.7, call: 0.3, fold: 0 } }} onClick={onCellClick}/>
```

13×13 button grid. Each cell shows hand label (`AA`, `AKs`, `AKo`). Each can have a layered horizontal bar — `raise` (red) + `call` (blue) + `fold` (gray). Drag-to-select supported when wired with `onPointerDown/Enter`.

### Modal

```jsx
<Modal num="02 / SETUP" title="Trainer Scenario" sub="DEFINE A REPEATABLE BLOCK"
  onClose={...} footer={<><Btn>Close</Btn><Btn variant="primary">Start</Btn></>} wide>
  …content…
</Modal>
```

Centered overlay, 1 px solid border, no radius. ESC and backdrop-click close. `wide` switches to 1280 px width.

### Page wrapper

```jsx
<Page num="04 / STUDIO" title="Range Studio<br>— <em>build, compare,</em> export." sub="…" actions={<Btn>Save</Btn>}>
  …screen content…
</Page>
```

Renders the page header pattern with proper number, title, sub, and right-aligned action group. The title HTML is `dangerouslySetInnerHTML` so you can include `<em>` and `<br>`.

---

## 5 — Icons

Stroke-based, 24×24 viewBox, 1.6 px stroke. Minimal set — never invent new icons; pick from this list or use a placeholder.

```
home · play · target · grid · leak · brain · chart · book · crown · sparkles · bolt · history · cards · coach · settings · moon · sun · search · arrowR · arrowL · plus · x · check · chip · flame · flag · save · filter · chev · eye · spade · diamond · heart · club · upload · refresh · note
```

Add a new icon by extending the `paths` object in `Icon` (`ui.jsx`). Always stroke, never fill (except for chips and pot icons).

---

## 6 — Patterns

### KPI strip (top of dashboard / reports)

5 columns of `Stat` widgets, no gap (1 px line between via card borders).

```jsx
<div className="grid" style={{gridTemplateColumns:'repeat(5,1fr)'}}>
  <Stat label="WINRATE" value="7.2" unit="bb/100" delta="1.4" deltaSign="+"/>
  ...
</div>
```

### Leak list row

```jsx
<button style={{display:'grid', gridTemplateColumns:'auto 40px 1fr auto auto', gap:14, padding:'14px 18px'}}>
  <span className="t-mono" style={{color:'var(--dim)'}}>#1</span>
  <Tag tone="r">4B</Tag>
  <div><div>BTN vs HJ 4-bet jam</div><div className="t-label">PREFLOP · 124 HANDS · 8% FREQ</div></div>
  <Spark data={trend} down/>
  <span className="t-mono" style={{color:'var(--danger-2)', fontSize:15}}>−0.84</span>
</button>
```

### Poker table seat

```jsx
<div className="seat is-hero">
  <div className="seat__pos">HJ</div>
  <div className="seat__stk">37.70</div>
</div>
```

Modifiers: `.is-hero` (accent border) · `.is-villain` (danger border) · `.is-action` (pulse) · `.is-out` (opacity 0.34).

### Action deck (Play screen footer)

4 buttons in a row at the bottom, full-width sticky footer with raise sizer.

| Action | Color | Key | When |
|--------|-------|-----|------|
| FOLD     | `--info`   bg-tint | F | Always |
| CALL · X | `--accent` solid    | C | When facing a bet |
| RAISE · X| `--danger` bg-tint  | R | Always (open if no bet) |
| ALL-IN X | `--danger` solid    | A | Always |

Buttons are 16 px Space Grotesk 700, 14 px label, 11 px mono `kbd` chip.

### Resizable two-column page section

Wrap any side-by-side area with `<Split fill={false}>` and let users drag the divider:

```jsx
<Split fill={false} sizes={[320, "fill"]} mins={[240, 480]} storageKey="my-section">
  <Card>Left</Card>
  <Card>Right</Card>
</Split>
```

---

## 7 — Animations

| Class            | Purpose                                  | Duration | Easing       |
|------------------|------------------------------------------|----------|--------------|
| `.anim-deal`     | Card dealing in from above               | 480 ms   | overshoot    |
| `.anim-pulse`    | Hero seat ring at action time            | 1500 ms  | ease-in-out  |
| `.anim-pot-pop`  | Pot count flash when chips arrive        | 520 ms   | pop          |
| `.anim-fold`     | Seat dim + small Y shift                 | 280 ms   | ease-out     |
| `.anim-seat-act` | Quick scale-up of acting seat            | 380 ms   | snap         |
| `.anim-label`    | Action label pop-in                      | 320 ms   | overshoot    |
| `.anim-muck`     | Villain cards fly off when folding       | 520 ms   | ease-in      |
| `.anim-count`    | Number counter slide-up                  | 280 ms   | ease-out     |

Bet-chip flight (seat → pot) is JS-driven; toggle `is-moving` class on a `.bet-blob` element and let CSS `transition: all 700ms cubic-bezier(.3,.7,.3,1)` animate `left/top`.

---

## 8 — Accessibility & keyboard

| Key   | Action                                |
|-------|---------------------------------------|
| 1-0   | Top-level navigation                  |
| W     | Welcome / onboarding                  |
| ,     | Settings                              |
| ?     | Open AI Coach                         |
| F     | Fold (Play screen)                    |
| C     | Call                                  |
| R     | Raise                                 |
| A     | All-in                                |
| SPACE / ↵ | Next hand (after decision)         |
| ESC   | Close modal                           |

Color contrast: All foreground text passes WCAG AA on its assigned surface. Active accent on dark surface: 6.4:1. Muted on bg: 4.7:1.

Motion preferences: respect `prefers-reduced-motion` by disabling `.anim-*` classes globally. (Optional: add `@media (prefers-reduced-motion: reduce) { .anim-* { animation: none !important; } }`.)

---

## 9 — Tweaks panel contract

Floating panel in the bottom-right when the host toggles edit mode. Defaults live in `app.jsx`:

```js
const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "accentHue": 145,
  "density": "regular",
  "tableStyle": "stadium",
  "fontScale": 100,
  "showGrid": true,
  "dark": true
}/*EDITMODE-END*/;
```

When the user changes a value, the host writes back to this block. Changes apply live via `useEffect` setting CSS custom properties.

---

## 10 — Asset & screen map

| File                       | What it owns                                    |
|----------------------------|-------------------------------------------------|
| `theme.css`                | All tokens, animations, base styles, media queries |
| `ui.jsx`                   | All shared components + `useMediaQuery`         |
| `app.jsx`                  | App shell, router, sidebar, top bar, tweaks    |
| `tweaks-panel.jsx`         | Tweaks shell + form controls                    |
| `screens/dashboard.jsx`    | 00 / Dashboard — KPIs, today's block, heatmap   |
| `screens/play.jsx`         | 01 / Live Table — drill loop, AI coach panel    |
| `screens/trainer.jsx`      | 02 / GTO Trainer — range strategy + scenario modal |
| `screens/tournament.jsx`   | 03 / Tournament — final table, ICM tree         |
| `screens/studio.jsx`       | 04 / Studio — range builder, compare, equity    |
| `screens/leaks.jsx`        | 05 / Leak Finder — heatmap, leak queue, detail  |
| `screens/analyzer.jsx`     | 06 / Hand Analyzer — replay, streets, EV delta  |
| `screens/library.jsx`      | 07 / Knowledge — books, concepts, spots         |
| `screens/coach.jsx`        | 08 / AI Coach — chat + inspector                |
| `screens/reports.jsx`      | 09 / Reports — cash curve, skills, radar        |
| `screens/welcome.jsx`      | Welcome — 5-step onboarding                     |
| `screens/settings.jsx`     | Settings — 9-tab preferences + RTA Guard        |

---

## 11 — Adapting to Figma

To recreate in Figma:

1. **Frame setup.** Use 1480 × 1000 frames for desktop screens. Background: `#0a0c0a` (dark) or `#f3f3ee` (light).
2. **Local styles.** Define all colors as Figma color styles using the names in §2 (`bg`, `surface`, `accent`, etc.).
3. **Text styles.** Create 6 text styles per the type scale: `H1 / H2 / H3 / Body / Caption / Label / KPI Value`.
4. **Components.** Build these as Figma components in this order: `Btn` → `Tag` → `Card` → `Stat` → `Seg` → `PCard` → `Seat` → `RangeGrid` → `Page Header`.
5. **Variants.** `Btn`: variant (default/primary/danger/ghost) × size (md/lg) × state (default/hover/disabled). `Tag`: tone (default/g/r/y/b) × dot (true/false).
6. **Grids.** Set a Figma grid: 28 px outer padding, 20 px gap, 12 columns. Most screens fit this.
7. **Auto-layout.** Cards: vertical auto-layout, 0 px gap (use hairline borders instead), 14/18 px padding for header/body.
8. **Effects.** Don't use Figma shadows or blurs. The aesthetic is flat.

A screenshot of `Style Guide.html` (in this project) gives you a one-page visual stickersheet — drop it into Figma as a reference and trace the components.

---

## 12 — Voice & copy

- Numbered prefixes: `00 / DASHBOARD`, `A1`, `B2`. Always uppercase, monospace, 0.14em tracking.
- Section headers in JetBrains Mono uppercase: `LEAK QUEUE`, `RANKED BY EV-LOSS · BB/100`.
- Display copy can use editorial italic (`<em>` → Instrument Serif): "*Plug your leaks. Sharpen your edge.*"
- Avoid filler words. "EV-LOSS" not "Expected Value Loss". "MDF" not "Minimum Defense Frequency" (except first use in tutorials).
- Action verbs in CTAs: "Start training" not "Click here to begin training".

---

## 13 — Don't

- ❌ Don't use border-radius anywhere.
- ❌ Don't use drop shadows.
- ❌ Don't use emoji except when it's part of the brand voice (e.g., the 🔥 streak indicator).
- ❌ Don't use Inter, Roboto, or system fonts as a fallback for headings.
- ❌ Don't introduce new accent colors. Use the 4 semantic colors (accent, danger, warn, info) and that's it.
- ❌ Don't use gradients except the subtle radial on the poker table felt.
- ❌ Don't animate things that don't carry information.

---

## 14 — Do

- ✅ Use tabular-nums everywhere a number could change.
- ✅ Use the page header pattern (num + h1 + sub + actions) on every page.
- ✅ Use `<em>` italics sparingly in headlines for editorial rhythm.
- ✅ Number your sections and cards (A1, A2, B1).
- ✅ Give every section a `t-label` heading in JetBrains Mono uppercase.
- ✅ Wrap side-by-side content in `<Split>` so users can resize.
- ✅ Test at 1180 px (auto-collapses) and 920 px (further collapses).

---

For an interactive walkthrough, open `Poke.html`. For PySide6 implementation specifics, see `HANDOFF.md`. For one-page visual reference, open `Style Guide.html`.
