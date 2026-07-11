from datetime import datetime

# Format used to store start_datetime in SQLite (server-local time, no
# timezone). Matches the value produced by an HTML <input type="datetime-local">.
DATETIME_FMT = "%Y-%m-%dT%H:%M"


class QuizStatus:
    @staticmethod
    def get(db):
        return db.execute("SELECT * FROM quiz_status WHERE id=1").fetchone()

    @staticmethod
    def update(db, **kwargs):
        if not kwargs:
            return
        cols = ", ".join(f"{k}=?" for k in kwargs)
        db.execute(f"UPDATE quiz_status SET {cols} WHERE id=1", tuple(kwargs.values()))
        db.commit()

    # ---------------------------------------------------------------
    # Scheduling helpers
    # ---------------------------------------------------------------
    @staticmethod
    def parse_start(value):
        """Parse a stored/submitted start_datetime string into a datetime,
        or None if unset/invalid."""
        if not value:
            return None
        try:
            return datetime.strptime(value, DATETIME_FMT)
        except ValueError:
            try:
                # Also accept 'YYYY-MM-DD HH:MM:SS' in case it was stored
                # via a different path.
                return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return None

    @staticmethod
    def set_schedule(db, start_datetime_str):
        """Admin sets (or clears, if falsy) the automatic start time.
        Does not touch round_open/quiz_started directly."""
        start = QuizStatus.parse_start(start_datetime_str)
        QuizStatus.update(
            db,
            start_datetime=start.strftime(DATETIME_FMT) if start else None,
        )

    @staticmethod
    def clear_schedule(db):
        QuizStatus.update(db, start_datetime=None)

    @staticmethod
    def schedule_label(row, now=None):
        """Returns 'Not Scheduled', 'Upcoming', or 'Live' for the
        scheduling widget. Purely informational -- does not gate access."""
        if not row["start_datetime"]:
            return "Not Scheduled"
        if row["quiz_started"]:
            return "Live"
        start = QuizStatus.parse_start(row["start_datetime"])
        if start is None:
            return "Not Scheduled"
        now = now or datetime.now()
        return "Live" if now >= start else "Upcoming"

    @staticmethod
    def is_locked_by_schedule(row, now=None):
        """The single source of truth for student-facing access control.
        True => quiz has NOT started yet and access must be blocked,
        regardless of what round_open says. Always evaluated against the
        SERVER clock, so a student's local clock cannot bypass it."""
        if row["quiz_started"]:
            return False
        if not row["start_datetime"]:
            return False
        start = QuizStatus.parse_start(row["start_datetime"])
        if start is None:
            return False
        now = now or datetime.now()
        return now < start

    @staticmethod
    def maybe_auto_start(db):
        """Call on every student-facing request. If a start time is set,
        hasn't fired yet, and the server clock has reached/passed it,
        automatically open Round 1 -- no admin action required."""
        row = QuizStatus.get(db)
        if row["finished"] or row["quiz_started"] or not row["start_datetime"]:
            return row
        start = QuizStatus.parse_start(row["start_datetime"])
        if start is not None and datetime.now() >= start:
            QuizStatus.update(db, round_open=1, quiz_started=1)
            row = QuizStatus.get(db)
        return row

    @staticmethod
    def set_auto_advance(db, enabled):
        QuizStatus.update(db, auto_advance=1 if enabled else 0)

    @staticmethod
    def try_auto_advance(db):
        """Call right after a team submits a round. If auto-advance is on
        and every registered team has now submitted the current round,
        move on with no admin click required:
          - if the next round has questions, open it automatically
          - otherwise there IS no round 2 (or round N+1) to show, so the
            quiz finishes automatically instead of waiting forever
        Safe to call unconditionally -- it's a no-op unless the toggle is
        on and the round is actually fully submitted."""
        from models.question import Question  # local import avoids a cycle

        row = QuizStatus.get(db)
        if not row["auto_advance"] or row["finished"] or not row["round_open"]:
            return row

        from models.result import Result  # local import avoids a cycle
        if not Result.all_teams_submitted(db, row["current_round"]):
            return row

        next_round = row["current_round"] + 1
        if Question.by_round(db, next_round):
            QuizStatus.next_round(db)   # advances current_round, closes round_open
            QuizStatus.open_round(db)   # opens the new round automatically
        else:
            QuizStatus.finish(db)       # no round 2 (or beyond) -- end the quiz
        return QuizStatus.get(db)

    # ---------------------------------------------------------------
    # Per-team independent round progression
    # ---------------------------------------------------------------
    @staticmethod
    def get_opened_rounds(row):
        """Every round number that has ever been opened, as a sorted list
        of ints, e.g. [1, 2]. A round in this list stays available to any
        team that hasn't submitted it yet, regardless of how far other
        teams have progressed."""
        raw = (row["opened_rounds"] or "").strip()
        if not raw:
            return []
        out = []
        for part in raw.split(","):
            part = part.strip()
            if part.isdigit():
                out.append(int(part))
        return sorted(set(out))

    @staticmethod
    def team_round_status(db, row, team_id):
        """What THIS team should see right now, independent of every other
        team's progress. Returns a dict with 'mode':
          - 'finished': quiz ended globally, or this team has completed
            the last configured round -> show the thank-you page.
          - 'active': this team has a round to play right now ->
            'round_number' tells which one.
          - 'waiting': nothing to do right now (round paused, quiz not
            started, or this team is caught up and waiting on the admin
            to open the next round) -> 'round_number' is the best guess
            for display purposes only.
        """
        from models.result import Result
        from models.question import Question

        if row["finished"]:
            return {"mode": "finished"}

        opened = QuizStatus.get_opened_rounds(row)

        if not row["round_open"]:
            return {"mode": "waiting", "round_number": row["current_round"]}

        for r in opened:
            if not Result.for_team_round(db, team_id, r):
                return {"mode": "active", "round_number": r}

        # Team has submitted every round opened so far. If the highest
        # opened round is also the last round with questions configured,
        # there is nothing left for this team to ever do.
        all_rounds = Question.rounds(db)
        if opened and all_rounds and max(opened) >= max(all_rounds):
            return {"mode": "finished"}

        next_round = (max(opened) + 1) if opened else row["current_round"]
        return {"mode": "waiting", "round_number": next_round}

    # ---------------------------------------------------------------
    @staticmethod
    def open_round(db):
        # Opening a round manually also marks the quiz as started, so a
        # later schedule change can't retroactively lock out a round the
        # admin already opened by hand. The round being opened is added
        # to opened_rounds so it stays reachable for stragglers even
        # after later rounds are opened on top of it.
        row = QuizStatus.get(db)
        opened = QuizStatus.get_opened_rounds(row)
        if row["current_round"] not in opened:
            opened.append(row["current_round"])
        QuizStatus.update(
            db,
            round_open=1,
            quiz_started=1,
            opened_rounds=",".join(str(r) for r in sorted(opened)),
        )

    @staticmethod
    def close_round(db):
        # Global pause: stops every round (opened or not) from being
        # playable until re-opened. Does not forget which rounds were
        # opened -- opened_rounds is untouched.
        QuizStatus.update(db, round_open=0)

    @staticmethod
    def next_round(db):
        s = QuizStatus.get(db)
        QuizStatus.update(db, current_round=s["current_round"] + 1, round_open=0)

    @staticmethod
    def finish(db):
        QuizStatus.update(db, finished=1, round_open=0)

    @staticmethod
    def reset(db):
        QuizStatus.update(
            db,
            current_round=1,
            round_open=0,
            finished=0,
            quiz_started=0,
            opened_rounds="",
        )

    @staticmethod
    def set_duration(db, seconds):
        QuizStatus.update(db, round_duration=int(seconds))
