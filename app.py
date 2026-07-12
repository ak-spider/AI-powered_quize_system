import os
import sqlite3
from flask import Flask, g

from routes.auth import auth_bp
from routes.quiz import quiz_bp
from routes.admin import admin_bp

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database", "quiz.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "database", "quiz.sql")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()


def migrate_db():
    """Bring an existing quiz.db up to date with newer schema additions
    (violation tracking) without touching already-collected data."""
    if not os.path.exists(DB_PATH):
        return
    conn = sqlite3.connect(DB_PATH)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(results)")}
    if "violation_count" not in cols:
        conn.execute("ALTER TABLE results ADD COLUMN violation_count INTEGER NOT NULL DEFAULT 0")
    if "auto_submitted" not in cols:
        conn.execute("ALTER TABLE results ADD COLUMN auto_submitted INTEGER NOT NULL DEFAULT 0")

    # Quiz scheduling feature.
    qs_cols = {row[1] for row in conn.execute("PRAGMA table_info(quiz_status)")}
    if "start_datetime" not in qs_cols:
        conn.execute("ALTER TABLE quiz_status ADD COLUMN start_datetime TEXT NULL")
    if "quiz_started" not in qs_cols:
        conn.execute("ALTER TABLE quiz_status ADD COLUMN quiz_started INTEGER NOT NULL DEFAULT 0")
    if "auto_advance" not in qs_cols:
        conn.execute("ALTER TABLE quiz_status ADD COLUMN auto_advance INTEGER NOT NULL DEFAULT 0")

    # Independent per-team round progression: tracks every round number
    # that has ever been opened (comma-separated), so a team that is still
    # finishing round 1 keeps access to it even after the admin opens
    # round 2 for teams that are already done.
    if "opened_rounds" not in qs_cols:
        conn.execute("ALTER TABLE quiz_status ADD COLUMN opened_rounds TEXT NOT NULL DEFAULT ''")

    # Team enable/disable (replaces destructive delete as the primary
    # admin control over which team names may log in).
    t_cols = {row[1] for row in conn.execute("PRAGMA table_info(teams)")}
    if "is_active" not in t_cols:
        conn.execute("ALTER TABLE teams ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")

    conn.execute("""CREATE TABLE IF NOT EXISTS violations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team_id INTEGER NOT NULL,
        round_number INTEGER NOT NULL,
        type TEXT NOT NULL,
        detail TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(team_id) REFERENCES teams(id) ON DELETE CASCADE
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_violations_team_round ON violations(team_id, round_number)")

    # Login Data Validation feature (admin-controlled team allow-list).
    conn.execute("""CREATE TABLE IF NOT EXISTS login_validation_settings (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        validation_enabled INTEGER NOT NULL DEFAULT 0
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS valid_teams (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team_name TEXT NOT NULL,
        login_name TEXT UNIQUE NOT NULL,
        team_members TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.execute(
        "INSERT OR IGNORE INTO login_validation_settings (id, validation_enabled) VALUES (1, 0)"
    )
    conn.commit()
    conn.close()


def create_app():
    app = Flask(__name__)
    app.secret_key = "change-me-in-production"
    app.config["DB_PATH"] = DB_PATH

    if not os.path.exists(DB_PATH):
        init_db()
    else:
        migrate_db()

    app.teardown_appcontext(close_db)

    app.register_blueprint(auth_bp)
    app.register_blueprint(quiz_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")

    @app.context_processor
    def inject_globals():
        from models.quiz_status import QuizStatus
        return {"quiz_status": QuizStatus.get(get_db())}

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug_mode, host="0.0.0.0", port=port)
