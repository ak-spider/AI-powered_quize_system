-- Teams (players)
CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- 1 = allowed to log in / play, 0 = disabled by admin (name is kept,
    -- login is refused). Replaces deleting a team as the normal control.
    is_active INTEGER NOT NULL DEFAULT 1
);

-- Questions, grouped by round
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    round_number INTEGER NOT NULL,
    text TEXT NOT NULL,
    option_a TEXT NOT NULL,
    option_b TEXT NOT NULL,
    option_c TEXT NOT NULL,
    option_d TEXT NOT NULL,
    correct_option TEXT NOT NULL CHECK (correct_option IN ('A','B','C','D'))
);

-- Results: one row per team/round
CREATE TABLE IF NOT EXISTS results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER NOT NULL,
    round_number INTEGER NOT NULL,
    score INTEGER NOT NULL DEFAULT 0,
    violation_count INTEGER NOT NULL DEFAULT 0,
    auto_submitted INTEGER NOT NULL DEFAULT 0,
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(team_id, round_number),
    FOREIGN KEY(team_id) REFERENCES teams(id) ON DELETE CASCADE
);

-- Violations: append-only log of anti-cheat events (copy attempts, tab
-- switches, devtools attempts, etc.) captured while a round is in progress.
CREATE TABLE IF NOT EXISTS violations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER NOT NULL,
    round_number INTEGER NOT NULL,
    type TEXT NOT NULL,
    detail TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(team_id) REFERENCES teams(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_violations_team_round ON violations(team_id, round_number);

-- Global quiz status (single row, id=1)
CREATE TABLE IF NOT EXISTS quiz_status (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    current_round INTEGER NOT NULL DEFAULT 1,
    round_open INTEGER NOT NULL DEFAULT 0,
    finished INTEGER NOT NULL DEFAULT 0,
    round_duration INTEGER NOT NULL DEFAULT 60,
    -- Scheduling feature: optional automatic start time for the quiz.
    -- Stored as 'YYYY-MM-DD HH:MM:SS' server-local time. NULL = manual
    -- control only (admin opens Round 1 by hand, as before).
    start_datetime TEXT NULL,
    -- Set to 1 the moment Round 1 has ever been opened (manually or
    -- automatically). Used so the schedule only gates the *initial*
    -- start, not every later round transition.
    quiz_started INTEGER NOT NULL DEFAULT 0,
    -- When 1: once every registered team has submitted the current
    -- round, the next round opens automatically (or the quiz finishes
    -- automatically if there is no next round) -- no admin click needed.
    auto_advance INTEGER NOT NULL DEFAULT 0,
    -- Comma-separated list of every round number ever opened, e.g. "1,2".
    -- Lets each team progress independently: a team still on round 1
    -- keeps access to it even after round 2 opens for teams that are
    -- already done, instead of everyone being forced to the same round.
    opened_rounds TEXT NOT NULL DEFAULT ''
);

-- Admin users
CREATE TABLE IF NOT EXISTS admins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL
);

-- Login Data Validation feature: single-row on/off switch. When enabled,
-- team login is checked against the valid_teams list below; when disabled
-- (default), login behaves exactly as before (any name is accepted).
CREATE TABLE IF NOT EXISTS login_validation_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    validation_enabled INTEGER NOT NULL DEFAULT 0
);

-- Admin-managed list of teams allowed to log in when validation is ON.
-- login_name is what the user types on the login screen; team_name is a
-- friendlier display label (they may be the same). team_members is a free
-- text field and optional.
CREATE TABLE IF NOT EXISTS valid_teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_name TEXT NOT NULL,
    login_name TEXT UNIQUE NOT NULL,
    team_members TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO login_validation_settings (id, validation_enabled) VALUES (1, 0);

INSERT OR IGNORE INTO quiz_status (id, current_round, round_open, finished, round_duration)
VALUES (1, 1, 0, 0, 60);

INSERT OR IGNORE INTO admins (username, password) VALUES ('akash', 'akash2004');

-- Sample questions
INSERT INTO questions (round_number, text, option_a, option_b, option_c, option_d, correct_option) VALUES
(1, 'Capital of France?', 'Berlin', 'Paris', 'Rome', 'Madrid', 'B'),
(1, 'Largest planet in our solar system?', 'Earth', 'Mars', 'Jupiter', 'Saturn', 'C'),
(1, 'Who wrote Hamlet?', 'Dickens', 'Shakespeare', 'Twain', 'Austen', 'B'),
(2, 'Chemical symbol for gold?', 'Go', 'Gd', 'Au', 'Ag', 'C'),
(2, 'Speed of light (approx, m/s)?', '3x10^6', '3x10^8', '3x10^10', '3x10^4', 'B'),
(2, 'H2O is commonly known as?', 'Salt', 'Sugar', 'Water', 'Acid', 'C'),
(3, '12 x 12 = ?', '124', '144', '132', '156', 'B'),
(3, 'Square root of 81?', '7', '8', '9', '10', 'C'),
(3, '15% of 200?', '20', '25', '30', '35', 'C');
