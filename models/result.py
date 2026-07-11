class Result:
    @staticmethod
    def upsert(db, team_id, round_number, score, violation_count=0, auto_submitted=False):
        db.execute(
            """INSERT INTO results (team_id, round_number, score, violation_count, auto_submitted)
               VALUES (?,?,?,?,?)
               ON CONFLICT(team_id, round_number) DO UPDATE SET
                    score=excluded.score,
                    violation_count=excluded.violation_count,
                    auto_submitted=excluded.auto_submitted,
                    submitted_at=CURRENT_TIMESTAMP""",
            (team_id, round_number, score, violation_count, 1 if auto_submitted else 0),
        )
        db.commit()

    @staticmethod
    def for_team_round(db, team_id, round_number):
        return db.execute(
            "SELECT * FROM results WHERE team_id=? AND round_number=?",
            (team_id, round_number),
        ).fetchone()

    @staticmethod
    def leaderboard(db):
        """Team ranking algorithm.

        Ranking rules (in priority order):
          1. Highest total score across all rounds wins.
          2. Fewer anti-cheat violations wins a tie on score (an honest team
             should not be outranked by one that scored the same only after
             attempting to cheat).
          3. Whoever finished all their submissions earliest wins a further tie.
        Ties that remain identical on all three factors share the same rank,
        using standard competition ranking (1, 2, 2, 4 - the next distinct
        rank skips the number of tied entries, same convention as sports
        leaderboards).
        """
        rows = db.execute(
            """SELECT t.id, t.name,
                      COALESCE(SUM(r.score), 0) AS total,
                      COUNT(r.id) AS rounds_played,
                      COALESCE(SUM(r.violation_count), 0) AS violations,
                      MAX(r.submitted_at) AS last_submitted_at
               FROM teams t LEFT JOIN results r ON r.team_id = t.id
               GROUP BY t.id, t.name"""
        ).fetchall()

        data = [dict(r) for r in rows]

        def sort_key(row):
            # None (no submissions yet) sorts after any real timestamp.
            last = row["last_submitted_at"] or "9999-12-31 23:59:59"
            return (-row["total"], row["violations"], last, row["name"])

        data.sort(key=sort_key)

        rank = 0
        prev_tie_key = None
        for i, row in enumerate(data, start=1):
            tie_key = (row["total"], row["violations"], row["last_submitted_at"])
            if tie_key != prev_tie_key:
                rank = i
            row["rank"] = rank
            prev_tie_key = tie_key

        return data

    @staticmethod
    def round_results(db, round_number):
        return db.execute(
            """SELECT t.name, r.score, r.violation_count, r.auto_submitted
               FROM results r JOIN teams t ON t.id=r.team_id
               WHERE r.round_number=?
               ORDER BY r.score DESC, r.violation_count ASC, t.name""",
            (round_number,),
        ).fetchall()

    @staticmethod
    def submitted_count(db, round_number):
        row = db.execute(
            "SELECT COUNT(*) AS n FROM results WHERE round_number=?",
            (round_number,),
        ).fetchone()
        return row["n"]

    @staticmethod
    def all_teams_submitted(db, round_number):
        """True once every currently ENABLED team has a result row for
        this round. Disabled teams don't block auto-advance (nothing to
        wait for from a team that isn't allowed to play), matching how
        the leaderboard already treats no-shows."""
        total_teams = db.execute(
            "SELECT COUNT(*) AS n FROM teams WHERE is_active=1"
        ).fetchone()["n"]
        if total_teams == 0:
            return False
        submitted = db.execute(
            """SELECT COUNT(*) AS n FROM results r
               JOIN teams t ON t.id = r.team_id
               WHERE r.round_number=? AND t.is_active=1""",
            (round_number,),
        ).fetchone()["n"]
        return submitted >= total_teams

    @staticmethod
    def reset_all(db):
        db.execute("DELETE FROM results")
        db.execute("DELETE FROM violations")
        db.commit()
