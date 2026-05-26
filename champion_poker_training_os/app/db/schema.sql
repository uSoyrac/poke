PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL DEFAULT 'Hero',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS players (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  profile TEXT NOT NULL DEFAULT 'unknown'
);

CREATE TABLE IF NOT EXISTS sessions (
  id INTEGER PRIMARY KEY,
  user_id INTEGER REFERENCES users(id),
  format TEXT NOT NULL,
  started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  hands_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tournaments (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  field_size INTEGER,
  buyin REAL,
  pko_enabled INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS hands (
  id TEXT PRIMARY KEY,
  session_id INTEGER REFERENCES sessions(id),
  format TEXT NOT NULL,
  hero_cards TEXT,
  board TEXT,
  result_bb REAL,
  raw_text TEXT
);

CREATE TABLE IF NOT EXISTS hand_players (
  id INTEGER PRIMARY KEY,
  hand_id TEXT REFERENCES hands(id),
  player_name TEXT NOT NULL,
  position TEXT,
  stack_bb REAL
);

CREATE TABLE IF NOT EXISTS actions (
  id INTEGER PRIMARY KEY,
  hand_id TEXT REFERENCES hands(id),
  street TEXT NOT NULL,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  amount_bb REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS spots (
  id TEXT PRIMARY KEY,
  hand_id TEXT REFERENCES hands(id),
  title TEXT NOT NULL,
  street TEXT NOT NULL,
  position TEXT NOT NULL,
  stack_bb INTEGER,
  pot_bb REAL,
  board_texture TEXT,
  action_line TEXT
);

CREATE TABLE IF NOT EXISTS board_textures (
  id INTEGER PRIMARY KEY,
  board TEXT NOT NULL,
  texture TEXT NOT NULL,
  paired INTEGER DEFAULT 0,
  monotone INTEGER DEFAULT 0,
  connectedness REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS solver_results (
  id INTEGER PRIMARY KEY,
  spot_id TEXT REFERENCES spots(id),
  source_confidence TEXT NOT NULL,
  best_action TEXT NOT NULL,
  action_json TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS hero_decisions (
  id INTEGER PRIMARY KEY,
  spot_id TEXT REFERENCES spots(id),
  hero_action TEXT NOT NULL,
  solver_action TEXT NOT NULL,
  ev_loss REAL NOT NULL,
  frequency_error REAL DEFAULT 0,
  sizing_error TEXT
);

CREATE TABLE IF NOT EXISTS math_results (
  id INTEGER PRIMARY KEY,
  user_id INTEGER REFERENCES users(id),
  kind TEXT NOT NULL,
  prompt TEXT NOT NULL,
  expected REAL NOT NULL,
  answer REAL NOT NULL,
  correct INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS bot_profiles (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  vpip REAL,
  pfr REAL,
  three_bet REAL,
  fold_to_cbet REAL,
  aggression REAL,
  profile_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS simulation_sessions (
  id INTEGER PRIMARY KEY,
  mode TEXT NOT NULL,
  bot_profile TEXT,
  hands_played INTEGER DEFAULT 0,
  skill_score INTEGER DEFAULT 700,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS simulation_hands (
  id INTEGER PRIMARY KEY,
  simulation_session_id INTEGER REFERENCES simulation_sessions(id),
  spot_id TEXT,
  hero_action TEXT,
  bot_action TEXT,
  ev_loss REAL
);

CREATE TABLE IF NOT EXISTS tournament_sims (
  id INTEGER PRIMARY KEY,
  field_size INTEGER,
  speed TEXT,
  pko_enabled INTEGER,
  roi_projection REAL DEFAULT 0,
  finish_position INTEGER
);

CREATE TABLE IF NOT EXISTS tournament_decisions (
  id INTEGER PRIMARY KEY,
  tournament_sim_id INTEGER REFERENCES tournament_sims(id),
  spot_id TEXT,
  chip_ev_loss REAL,
  dollar_ev_loss REAL,
  risk_premium REAL
);

CREATE TABLE IF NOT EXISTS opponent_profiles (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  archetype TEXT NOT NULL,
  stats_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bayes_updates (
  id INTEGER PRIMARY KEY,
  opponent_profile_id INTEGER REFERENCES opponent_profiles(id),
  prior REAL NOT NULL,
  likelihood_type REAL NOT NULL,
  likelihood_not_type REAL NOT NULL,
  posterior REAL NOT NULL,
  note TEXT
);

CREATE TABLE IF NOT EXISTS leaks (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  severity TEXT NOT NULL,
  sample_size INTEGER,
  ev_lost REAL,
  frequency_deviation TEXT,
  fix_strategy TEXT
);

CREATE TABLE IF NOT EXISTS drills (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  source_confidence TEXT NOT NULL DEFAULT 'Mock/demo solver'
);

CREATE TABLE IF NOT EXISTS drill_results (
  id INTEGER PRIMARY KEY,
  drill_id TEXT REFERENCES drills(id),
  answer TEXT,
  correct INTEGER,
  ev_loss REAL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS combat_packs (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  spots INTEGER,
  difficulty TEXT,
  skill_score INTEGER,
  boss_hand TEXT
);

CREATE TABLE IF NOT EXISTS study_plans (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  day TEXT NOT NULL,
  focus TEXT NOT NULL,
  blocks_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS skill_scores (
  id INTEGER PRIMARY KEY,
  category TEXT NOT NULL,
  level INTEGER DEFAULT 1,
  xp INTEGER DEFAULT 0,
  mastery REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS achievements (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  unlocked INTEGER DEFAULT 0,
  unlocked_at TEXT
);

CREATE TABLE IF NOT EXISTS knowledge_cards (
  id INTEGER PRIMARY KEY,
  concept TEXT NOT NULL,
  source TEXT NOT NULL,
  reference TEXT,
  summary TEXT NOT NULL,
  application TEXT
);

CREATE TABLE IF NOT EXISTS ai_coach_logs (
  id INTEGER PRIMARY KEY,
  prompt TEXT NOT NULL,
  response TEXT NOT NULL,
  source_confidence TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS compliance_logs (
  id INTEGER PRIMARY KEY,
  strict_mode INTEGER NOT NULL,
  locked INTEGER NOT NULL,
  detected_processes TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS app_settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tournament_results (
  id INTEGER PRIMARY KEY,
  played_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  name TEXT NOT NULL,
  field_size INTEGER NOT NULL DEFAULT 9,
  buyin REAL NOT NULL DEFAULT 0,
  structure TEXT NOT NULL DEFAULT 'regular',
  finish_position INTEGER,
  prize_won REAL NOT NULL DEFAULT 0,
  hands_played INTEGER NOT NULL DEFAULT 0,
  vpip REAL DEFAULT 0,
  pfr REAL DEFAULT 0,
  bb_per_100 REAL DEFAULT 0,
  profit REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS played_hands (
  id INTEGER PRIMARY KEY,
  hand_id INTEGER NOT NULL,
  hero_cards TEXT,
  community TEXT,
  pot REAL DEFAULT 0,
  hero_invested REAL DEFAULT 0,
  hero_profit REAL DEFAULT 0,
  hero_won INTEGER DEFAULT 0,
  winner_hand_name TEXT,
  streets_seen INTEGER DEFAULT 0,
  session_id INTEGER DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

