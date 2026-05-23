// poker-table.jsx — Reusable poker table component for Poke
// Brutalist editorial system · sharp corners · mono numbers · lime accent
// Works at any seat count (2/3/6/8/9) and any street (preflop→showdown)

const { useMemo: ptUseMemo } = React;

/* ───────────────────────────────────────────────────────────────
   SEAT GEOMETRY — % positions inside the 100×100 felt box.
   Hero is always anchored to the bottom of the table (y > 80).
   ─────────────────────────────────────────────────────────────── */
const LAYOUTS = {
  hu: [
    { pos: "BTN/SB", x: 50, y: 92 },
    { pos: "BB",     x: 50, y: 8  },
  ],
  three: [
    { pos: "BTN", x: 50, y: 92 },
    { pos: "SB",  x: 8,  y: 35 },
    { pos: "BB",  x: 92, y: 35 },
  ],
  six: [
    { pos: "UTG", x: 22, y: 10 },
    { pos: "HJ",  x: 78, y: 10 },
    { pos: "CO",  x: 95, y: 52 },
    { pos: "BTN", x: 75, y: 92 },
    { pos: "SB",  x: 25, y: 92 },
    { pos: "BB",  x: 5,  y: 52 },
  ],
  eight: [
    { pos: "UTG",   x: 50, y: 6  },
    { pos: "UTG+1", x: 75, y: 10 },
    { pos: "LJ",    x: 92, y: 30 },
    { pos: "HJ",    x: 92, y: 70 },
    { pos: "CO",    x: 75, y: 90 },
    { pos: "BTN",   x: 50, y: 94 },
    { pos: "SB",    x: 25, y: 90 },
    { pos: "BB",    x: 8,  y: 70 },
  ],
  nine: [
    { pos: "UTG",   x: 38, y: 6  },
    { pos: "UTG+1", x: 62, y: 6  },
    { pos: "MP",    x: 82, y: 14 },
    { pos: "LJ",    x: 95, y: 38 },
    { pos: "HJ",    x: 95, y: 70 },
    { pos: "CO",    x: 78, y: 92 },
    { pos: "BTN",   x: 50, y: 96 },
    { pos: "SB",    x: 22, y: 92 },
    { pos: "BB",    x: 5,  y: 70 },
  ],
};

/* ───────────────────────────────────────────────────────────────
   SUIT LOOKUPS — match existing PCard contract from ui.jsx
   ─────────────────────────────────────────────────────────────── */
const SUITS = { s: "♠", h: "♥", d: "♦", c: "♣" };
const isRed = (suit) => suit === "h" || suit === "d";

function MiniCard({ card, size = "md" }) {
  if (card === "back") {
    return <div className={`pc pc--back pc--${size}`}/>;
  }
  const r = card[0];
  const s = card[1];
  return (
    <div className={`pc pc--${size} ${isRed(s) ? "pc--red" : ""}`}>
      <span>{r}</span>
      <span className="pc__suit">{SUITS[s]}</span>
    </div>
  );
}

/* ───────────────────────────────────────────────────────────────
   CHIP STACK — small visual bet indicator
   ─────────────────────────────────────────────────────────────── */
function Chips({ size = 4 }) {
  return (
    <span className="chip-stack">
      {Array.from({ length: Math.min(size, 5) }).map((_, i) => <i key={i}/>)}
    </span>
  );
}

/* ───────────────────────────────────────────────────────────────
   SEAT — single player position. Modifiers: hero / villain / out / acting
   props.state  = { stack, action, bet, hero, villain, folded, mucked,
                    hole, name, timebank, isActing }
   ─────────────────────────────────────────────────────────────── */
function Seat({ pos, x, y, state }) {
  if (!state) {
    // empty seat placeholder
    return (
      <div className="pt-seat pt-seat--empty" style={{ left:`${x}%`, top:`${y}%` }}>
        <div className="t-label">{pos}</div>
        <div className="t-mono pt-seat__empty">EMPTY</div>
      </div>
    );
  }

  const {
    stack, action, bet, hero, villain, folded, mucked, isActing,
    hole, name = pos, timebank,
  } = state;

  const tone =
    hero ? "hero" :
    villain ? "villain" :
    folded ? "out" :
    "default";

  const cls = [
    "pt-seat",
    `pt-seat--${tone}`,
    isActing ? "pt-seat--acting anim-pulse" : "",
    folded ? "pt-seat--folded" : "",
    mucked ? "anim-muck" : "",
  ].filter(Boolean).join(" ");

  return (
    <div className={cls} style={{ left:`${x}%`, top:`${y}%` }}>
      {(hero || villain) && (
        <div className="pt-seat__tag t-label">
          {hero ? "HERO" : "VILLAIN"}
        </div>
      )}
      <div className="pt-seat__card">
        <div className="pt-seat__row">
          <span className="t-label pt-seat__pos">{pos}</span>
          <span className="t-mono pt-seat__stk">{stack.toFixed(2)}</span>
        </div>
        {name !== pos && <div className="pt-seat__name t-mono">{name}</div>}
        {timebank != null && (
          <div className="pt-seat__timebank">
            <i style={{ width: `${timebank}%` }}/>
          </div>
        )}
      </div>

      {action && !folded && (
        <div className={`pt-seat__act t-label pt-seat__act--${actionTone(action)}`}>
          {action}{bet ? ` · ${bet.toFixed(1)}` : ""}
        </div>
      )}
      {folded && action === "FOLD" && !mucked && (
        <div className="pt-seat__act t-label pt-seat__act--fold">FOLD</div>
      )}
    </div>
  );
}

function actionTone(a) {
  if (!a) return "neutral";
  if (a === "FOLD") return "fold";
  if (a === "CHECK") return "check";
  if (a === "CALL" || a === "OPEN" || a === "LIMP") return "call";
  if (a === "ALL-IN" || a === "JAM") return "jam";
  return "raise"; // RAISE / 3-BET / 4-BET / 5-BET / BET
}

/* ───────────────────────────────────────────────────────────────
   DEALER BUTTON — small disk placed next to BTN seat
   ─────────────────────────────────────────────────────────────── */
function DealerButton({ x, y }) {
  return (
    <div className="pt-button" style={{ left:`${x}%`, top:`${y}%` }}>
      <span className="t-mono">D</span>
    </div>
  );
}

/* ───────────────────────────────────────────────────────────────
   BET CHIP — chips sitting at a seat (between seat and center)
   ─────────────────────────────────────────────────────────────── */
function BetChip({ x, y, amount, tone = "neutral" }) {
  return (
    <div className={`pt-bet pt-bet--${tone}`} style={{ left:`${x}%`, top:`${y}%` }}>
      <Chips size={Math.min(5, Math.ceil(amount / 3))}/>
      <span className="t-mono pt-bet__val">{amount.toFixed(1)} bb</span>
    </div>
  );
}

/* ───────────────────────────────────────────────────────────────
   CENTER — board cards + pot + street tag
   ─────────────────────────────────────────────────────────────── */
function TableCenter({ pot, board, street = "PREFLOP", note, big = false }) {
  return (
    <div className="pt-center">
      <span className={`tag tag--g`}><span className="dot"/>{street}</span>
      {board && board.length > 0 && (
        <div className="pt-board">
          {board.map((c, i) => <MiniCard key={i} card={c}/>)}
          {street === "FLOP" && [0,1].map(i => <div key={`p${i}`} className="pt-board__placeholder"/>)}
          {street === "TURN" && <div className="pt-board__placeholder"/>}
        </div>
      )}
      <div className="t-label pt-center__lbl">POT</div>
      <div className={`pt-pot ${big ? "pt-pot--xl" : ""}`}>
        {pot.toFixed(2)}
        <small>bb</small>
      </div>
      {note && <div className="t-label pt-center__sub">{note}</div>}
    </div>
  );
}

/* ───────────────────────────────────────────────────────────────
   HERO HOLE CARDS — large pair offset toward center from hero seat
   ─────────────────────────────────────────────────────────────── */
function HeroCards({ x, y, cards, size = "lg" }) {
  // Pull cards 28% toward center so they don't overlap the seat tile.
  const dx = (50 - x) * 0.28;
  const dy = (50 - y) * 0.28;
  return (
    <div className="pt-hole" style={{ left:`${x + dx}%`, top:`${y + dy}%` }}>
      <MiniCard card={cards[0]} size={size}/>
      <MiniCard card={cards[1]} size={size}/>
    </div>
  );
}

/* villain showdown cards (smaller, face-up) */
function VillainCards({ x, y, cards }) {
  const dx = (50 - x) * 0.28;
  const dy = (50 - y) * 0.28;
  return (
    <div className="pt-hole pt-hole--small" style={{ left:`${x + dx}%`, top:`${y + dy}%` }}>
      <MiniCard card={cards[0]}/>
      <MiniCard card={cards[1]}/>
    </div>
  );
}

/* face-down opponent cards */
function OpponentCards({ x, y }) {
  const dx = (50 - x) * 0.26;
  const dy = (50 - y) * 0.26;
  return (
    <div className="pt-hole pt-hole--small" style={{ left:`${x + dx}%`, top:`${y + dy}%` }}>
      <MiniCard card="back" size="xs"/>
      <MiniCard card="back" size="xs"/>
    </div>
  );
}

/* ───────────────────────────────────────────────────────────────
   POKER TABLE — the full composition.
   props:
     layout      = "hu" | "three" | "six" | "eight" | "nine"
     seats       = { POS: { stack, action, bet, hero, villain, folded, mucked, hole } }
     pot         = number (bb)
     board       = ["As","Kh","2c", ...] | null
     street      = "PREFLOP" | "FLOP" | "TURN" | "RIVER" | "SHOWDOWN"
     heroCards   = ["As","Ks"]
     dealerPos   = "BTN" | etc — defaults to "BTN"
     showOpponentBacks = bool (default true) — show face-down cards at non-folded seats
     note        = optional small text under pot ("BLINDS 0.5/1 · ANTE 12.5%")
     bigPot      = bool — preflop scenarios get the huge 64px pot, postflop 40px
   ─────────────────────────────────────────────────────────────── */
function PokerTable(props) {
  const {
    layout = "eight",
    seats = {},
    pot = 0,
    board = null,
    street = "PREFLOP",
    heroCards,
    dealerPos = "BTN",
    showOpponentBacks = true,
    note,
    bigPot = false,
    variant = "stadium", // stadium | hex | rect
    grid = true,
  } = props;

  const positions = LAYOUTS[layout];
  const posMap = ptUseMemo(
    () => Object.fromEntries(positions.map(p => [p.pos, p])),
    [layout]
  );

  // Compute hero / villain seats for hole-card placement
  const heroPos = Object.entries(seats).find(([_, s]) => s.hero)?.[0];
  const villainPos = Object.entries(seats).find(([_, s]) => s.villain)?.[0];
  const heroP = heroPos && posMap[heroPos];
  const villainP = villainPos && posMap[villainPos];

  // Dealer button placement: 14% toward center from BTN seat
  const btnP = posMap[dealerPos] || posMap.BTN;
  const btnX = btnP ? btnP.x + (50 - btnP.x) * 0.18 : 50;
  const btnY = btnP ? btnP.y + (50 - btnP.y) * 0.18 : 50;

  return (
    <div className={`pt pt--${variant} ${grid ? "pt--grid" : ""}`}>
      {/* Stadium felt outline */}
      <div className={`pt-felt pt-felt--${variant}`}/>

      {/* Optional inner felt glow */}
      <div className="pt-felt__glow"/>

      {/* Center: pot + board + street */}
      <TableCenter pot={pot} board={board} street={street} note={note} big={bigPot}/>

      {/* Dealer button */}
      {btnP && <DealerButton x={btnX} y={btnY}/>}

      {/* Seats */}
      {positions.map(p => (
        <Seat key={p.pos} pos={p.pos} x={p.x} y={p.y} state={seats[p.pos]}/>
      ))}

      {/* Bet chips for non-folded seats with an active bet */}
      {Object.entries(seats).map(([pos, s]) => {
        if (!s || !s.bet || s.folded) return null;
        const p = posMap[pos];
        if (!p) return null;
        const cx = p.x + (50 - p.x) * 0.48;
        const cy = p.y + (50 - p.y) * 0.48;
        const tone = s.hero ? "hero" : s.villain ? "villain" : "neutral";
        return <BetChip key={`bet-${pos}`} x={cx} y={cy} amount={s.bet} tone={tone}/>;
      })}

      {/* Opponent face-down cards */}
      {showOpponentBacks && positions.map(p => {
        const s = seats[p.pos];
        if (!s || s.hero || s.folded || s.mucked) return null;
        // skip villain at showdown when villain.hole is given (handled below)
        if (s.villain && s.hole) return null;
        return <OpponentCards key={`bk-${p.pos}`} x={p.x} y={p.y}/>;
      })}

      {/* Villain face-up at showdown */}
      {villainP && seats[villainPos]?.hole && (
        <VillainCards x={villainP.x} y={villainP.y} cards={seats[villainPos].hole}/>
      )}

      {/* Hero hole cards */}
      {heroP && heroCards && (
        <HeroCards x={heroP.x} y={heroP.y} cards={heroCards}/>
      )}
    </div>
  );
}

window.PokerTable = PokerTable;
window.MiniCard = MiniCard;
window.Chips = Chips;
window.LAYOUTS = LAYOUTS;
