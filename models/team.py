class Team:
    @staticmethod
    def get_by_name(db, name):
        return db.execute("SELECT * FROM teams WHERE name=?", (name,)).fetchone()

    @staticmethod
    def get(db, team_id):
        return db.execute("SELECT * FROM teams WHERE id=?", (team_id,)).fetchone()

    @staticmethod
    def create(db, name, password=""):
        cur = db.execute("INSERT INTO teams (name, password) VALUES (?,?)", (name, password))
        db.commit()
        return cur.lastrowid

    @staticmethod
    def all(db):
        return db.execute("SELECT * FROM teams ORDER BY name").fetchall()

    @staticmethod
    def active_count(db):
        return db.execute(
            "SELECT COUNT(*) AS n FROM teams WHERE is_active=1"
        ).fetchone()["n"]

    @staticmethod
    def delete(db, team_id):
        db.execute("DELETE FROM teams WHERE id=?", (team_id,))
        db.commit()

    @staticmethod
    def set_active(db, team_id, active):
        """Enable or disable a team's login without deleting its history.
        Disabled teams keep their name, results, and violations, but
        cannot log in (or continue playing if already logged in) until
        re-enabled."""
        db.execute(
            "UPDATE teams SET is_active=? WHERE id=?",
            (1 if active else 0, team_id),
        )
        db.commit()
