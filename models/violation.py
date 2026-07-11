# Anti-cheat violation types recognised by the client. Kept as a whitelist so
# a malicious client can't spam arbitrary garbage into the log.
VALID_TYPES = {
    "tab_hidden",       # visibilitychange -> hidden
    "window_blur",      # window lost focus
    "copy_attempt",      # ctrl/cmd+C or copy event
    "cut_attempt",
    "paste_attempt",
    "context_menu",      # right click
    "devtools_shortcut",  # F12 / Ctrl+Shift+I / Ctrl+U etc.
    "devtools_open",      # heuristic size-based detection
    "text_select",        # selection attempted while blocked
}

# Once a team/round accumulates this many logged violations, the quiz auto-submits.
MAX_VIOLATIONS = 3


class Violation:
    @staticmethod
    def log(db, team_id, round_number, v_type, detail=None):
        if v_type not in VALID_TYPES:
            v_type = "other"
        db.execute(
            "INSERT INTO violations (team_id, round_number, type, detail) VALUES (?,?,?,?)",
            (team_id, round_number, v_type, detail),
        )
        db.commit()
        return Violation.count_for(db, team_id, round_number)

    @staticmethod
    def count_for(db, team_id, round_number):
        row = db.execute(
            "SELECT COUNT(*) AS c FROM violations WHERE team_id=? AND round_number=?",
            (team_id, round_number),
        ).fetchone()
        return row["c"] if row else 0

    @staticmethod
    def list_for(db, team_id, round_number):
        return db.execute(
            "SELECT * FROM violations WHERE team_id=? AND round_number=? ORDER BY created_at",
            (team_id, round_number),
        ).fetchall()

    @staticmethod
    def counts_by_team_round(db):
        """Aggregate violation counts grouped by team_id, round_number for reporting."""
        return db.execute(
            """SELECT team_id, round_number, COUNT(*) AS c
               FROM violations GROUP BY team_id, round_number"""
        ).fetchall()

    @staticmethod
    def recent(db, limit=50):
        return db.execute(
            """SELECT v.*, t.name AS team_name
               FROM violations v JOIN teams t ON t.id = v.team_id
               ORDER BY v.created_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()

    @staticmethod
    def clear_all(db):
        db.execute("DELETE FROM violations")
        db.commit()
