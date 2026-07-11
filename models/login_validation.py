"""Admin Controlled Login Data Validation for Teams.

Two pieces of state:

- LoginValidationSettings: a single-row on/off switch. When OFF (the
  default), team login behaves exactly as it always has -- any name is
  accepted and existing functionality is untouched. When ON, the name
  entered at login must exactly match a record the admin created below.

- ValidTeam: the admin-managed allow-list itself (team name, login name,
  optional team members). login_name is what a user is expected to type
  on the login screen and is unique; team_name is a friendlier display
  label and doesn't have to be unique.

Kept in its own module so the feature is easy to enable/disable/extend
without touching the existing Team/auth logic beyond a single guard.
"""


class LoginValidationSettings:
    @staticmethod
    def get(db):
        row = db.execute(
            "SELECT * FROM login_validation_settings WHERE id=1"
        ).fetchone()
        if row is None:
            # Defensive fallback in case a very old DB missed the migration
            # for some reason -- keeps the feature OFF (safe default) and
            # existing behavior intact instead of erroring out.
            db.execute(
                "INSERT OR IGNORE INTO login_validation_settings (id, validation_enabled) VALUES (1, 0)"
            )
            db.commit()
            row = db.execute(
                "SELECT * FROM login_validation_settings WHERE id=1"
            ).fetchone()
        return row

    @staticmethod
    def is_enabled(db):
        row = LoginValidationSettings.get(db)
        return bool(row["validation_enabled"]) if row else False

    @staticmethod
    def set_enabled(db, enabled):
        db.execute(
            "UPDATE login_validation_settings SET validation_enabled=? WHERE id=1",
            (1 if enabled else 0,),
        )
        db.commit()


class ValidTeam:
    @staticmethod
    def all(db):
        return db.execute(
            "SELECT * FROM valid_teams ORDER BY team_name COLLATE NOCASE"
        ).fetchall()

    @staticmethod
    def get(db, valid_team_id):
        return db.execute(
            "SELECT * FROM valid_teams WHERE id=?", (valid_team_id,)
        ).fetchone()

    @staticmethod
    def find_by_login(db, login_name):
        """Exact match (case-insensitive, whitespace-trimmed) lookup used
        during the actual login check. Only compares against login_name --
        the value entered at login must match the Login Name the admin
        set, not the (separate, display-only) Team Name field."""
        name = (login_name or "").strip()
        if not name:
            return None
        return db.execute(
            "SELECT * FROM valid_teams WHERE login_name=? COLLATE NOCASE",
            (name,),
        ).fetchone()

    @staticmethod
    def create(db, team_name, login_name, team_members=""):
        cur = db.execute(
            "INSERT INTO valid_teams (team_name, login_name, team_members) VALUES (?,?,?)",
            (team_name.strip(), login_name.strip(), (team_members or "").strip()),
        )
        db.commit()
        return cur.lastrowid

    @staticmethod
    def update(db, valid_team_id, team_name, login_name, team_members=""):
        db.execute(
            "UPDATE valid_teams SET team_name=?, login_name=?, team_members=? WHERE id=?",
            (team_name.strip(), login_name.strip(), (team_members or "").strip(), valid_team_id),
        )
        db.commit()

    @staticmethod
    def delete(db, valid_team_id):
        db.execute("DELETE FROM valid_teams WHERE id=?", (valid_team_id,))
        db.commit()
