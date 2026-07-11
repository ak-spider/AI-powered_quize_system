from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, flash
from functools import wraps
from models.question import Question
from models.result import Result
from models.quiz_status import QuizStatus
from models.team import Team
from models.violation import Violation, MAX_VIOLATIONS

quiz_bp = Blueprint("quiz", __name__)


def _db():
    from app import get_db
    return get_db()


def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if not session.get("team_id"):
            return redirect(url_for("auth.login"))
        # Re-check on every request: an admin may disable a team mid-quiz.
        team = Team.get(_db(), session["team_id"])
        if not team or not team["is_active"]:
            session.pop("team_id", None)
            session.pop("team_name", None)
            flash("This team has been disabled by the admin.", "error")
            return redirect(url_for("auth.login"))
        return f(*a, **kw)
    return wrapper


@quiz_bp.route("/waiting")
@login_required
def waiting():
    db = _db()
    status = QuizStatus.maybe_auto_start(db)  # server-clock check every visit
    locked = QuizStatus.is_locked_by_schedule(status)
    if locked:
        return render_template(
            "waiting.html",
            round_number=status["current_round"],
            locked=True,
            start_datetime=status["start_datetime"],
        )
    # Each team's round is decided independently of every other team --
    # a team still finishing round 1 isn't dragged along when round 2
    # opens for teams that are already caught up.
    ts = QuizStatus.team_round_status(db, status, session["team_id"])
    if ts["mode"] == "finished":
        return redirect(url_for("quiz.thank_you"))
    if ts["mode"] == "active":
        return redirect(url_for("quiz.quiz"))
    return render_template("waiting.html", round_number=ts["round_number"], locked=False)


@quiz_bp.route("/quiz", methods=["GET", "POST"])
@login_required
def quiz():
    db = _db()
    status = QuizStatus.maybe_auto_start(db)  # server-clock check every visit
    # Server-side schedule enforcement: even if round_open was flipped on
    # for some other reason, a student's own clock can never bypass this
    # check because "now" is always read from the server (datetime.now()
    # inside QuizStatus, never anything sent by the client).
    if QuizStatus.is_locked_by_schedule(status):
        return redirect(url_for("quiz.waiting"))

    ts = QuizStatus.team_round_status(db, status, session["team_id"])
    if ts["mode"] != "active":
        # Nothing (more) for this team to do right now: either the whole
        # quiz is over for them, or they're caught up and waiting on the
        # admin to open the next round.
        return redirect(url_for("quiz.thank_you" if ts["mode"] == "finished" else "quiz.waiting"))

    round_no = ts["round_number"]
    existing = Result.for_team_round(db, session["team_id"], round_no)
    if existing:
        return render_template("round_finished.html", round_number=round_no, score=existing["score"])

    questions = Question.by_round(db, round_no)

    if request.method == "POST":
        score = 0
        for q in questions:
            ans = (request.form.get(f"q_{q['id']}") or "").upper()
            if ans == q["correct_option"]:
                score += 1
        # Violation count is always recomputed server-side from the logged
        # events, never trusted from the client's hidden field.
        violation_count = Violation.count_for(db, session["team_id"], round_no)
        auto_submitted = request.form.get("auto_submitted") == "1"
        Result.upsert(db, session["team_id"], round_no, score, violation_count, auto_submitted)
        # If every team has now submitted and the admin enabled
        # auto-advance, move to the next round (or finish) automatically.
        QuizStatus.try_auto_advance(db)
        return render_template(
            "round_finished.html",
            round_number=round_no,
            score=score,
            violation_count=violation_count,
            auto_submitted=auto_submitted,
        )

    return render_template(
        "quiz.html",
        questions=questions,
        round_number=round_no,
        duration=status["round_duration"],
        max_violations=MAX_VIOLATIONS,
    )


@quiz_bp.route("/api/violation", methods=["POST"])
@login_required
def log_violation():
    """Anti-cheat event ingestion. The client reports what it observed
    (tab switch, copy attempt, devtools shortcut, etc.); the server is the
    source of truth for the running count and decides when the auto-submit
    threshold has been crossed."""
    db = _db()
    status = QuizStatus.get(db)
    ts = QuizStatus.team_round_status(db, status, session["team_id"])

    if ts["mode"] != "active":
        return jsonify({"ignored": True}), 200
    round_no = ts["round_number"]

    # Already submitted this round (e.g. race with auto-submit) -> nothing to log.
    if Result.for_team_round(db, session["team_id"], round_no):
        return jsonify({"ignored": True}), 200

    payload = request.get_json(silent=True) or {}
    v_type = str(payload.get("type") or "other")[:32]
    detail = str(payload.get("detail") or "")[:200] or None

    count = Violation.log(db, session["team_id"], round_no, v_type, detail)
    return jsonify({
        "count": count,
        "max": MAX_VIOLATIONS,
        "should_auto_submit": count >= MAX_VIOLATIONS,
    })


@quiz_bp.route("/round_finished")
@login_required
def round_finished():
    db = _db()
    # Show the most recently submitted round for THIS team, not whatever
    # round the admin happens to be pointing at globally.
    row = db.execute(
        "SELECT * FROM results WHERE team_id=? ORDER BY submitted_at DESC LIMIT 1",
        (session["team_id"],),
    ).fetchone()
    if not row:
        return redirect(url_for("quiz.waiting"))
    return render_template("round_finished.html", round_number=row["round_number"], score=row["score"])


@quiz_bp.route("/thank_you")
@login_required
def thank_you():
    # Final standings are for the admin only now (see /admin/leaderboard and
    # /admin/winner) -- students just get a plain thank-you message.
    return render_template("thank_you.html")


@quiz_bp.route("/status")
def status():
    db = _db()
    s = QuizStatus.maybe_auto_start(db)  # continuous server-time check
    locked = QuizStatus.is_locked_by_schedule(s)
    resp = {
        "current_round": s["current_round"],
        # round_open never reports true to a student while still locked
        # by schedule, closing off any client-side race to jump the gate.
        "round_open": bool(s["round_open"]) and not locked,
        "finished": bool(s["finished"]),
        "duration": s["round_duration"],
        "schedule_status": QuizStatus.schedule_label(s),
        "can_start": not locked,
        "start_datetime": s["start_datetime"],
    }
    # Per-team fields: what THIS team should be doing right now, which can
    # differ from the global "current_round" once teams progress at their
    # own pace. Pages poll these instead of the global fields.
    team_id = session.get("team_id")
    if team_id and not locked:
        ts = QuizStatus.team_round_status(db, s, team_id)
        resp["your_mode"] = ts["mode"]
        resp["your_round"] = ts.get("round_number")
    return jsonify(resp)
