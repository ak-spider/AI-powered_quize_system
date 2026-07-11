from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from functools import wraps
import sqlite3
from models.question import Question
from models.result import Result
from models.quiz_status import QuizStatus
from models.team import Team
from models.violation import Violation
from models.login_validation import LoginValidationSettings, ValidTeam

admin_bp = Blueprint("admin", __name__)


def _db():
    from app import get_db
    return get_db()


def admin_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if not session.get("is_admin"):
            return redirect(url_for("admin.login"))
        return f(*a, **kw)
    return wrapper


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form.get("username", "").strip()
        p = request.form.get("password", "").strip()
        row = _db().execute("SELECT * FROM admins WHERE username=? AND password=?", (u, p)).fetchone()
        if row:
            session["is_admin"] = True
            session["admin_user"] = u
            return redirect(url_for("admin.dashboard"))
        flash("Invalid admin credentials.", "error")
    return render_template("admin/login.html")


@admin_bp.route("/logout")
def logout():
    session.pop("is_admin", None)
    session.pop("admin_user", None)
    return redirect(url_for("admin.login"))


@admin_bp.route("/", methods=["GET", "POST"])
@admin_required
def dashboard():
    db = _db()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "toggle_active":
            team_id = int(request.form["team_id"])
            active = request.form.get("active") == "1"
            Team.set_active(db, team_id, active)
            flash("Team enabled." if active else "Team disabled.", "success")
        elif action == "delete_team":
            team_id = int(request.form["team_id"])
            Team.delete(db, team_id)
            flash("Team deleted.", "success")
        return redirect(url_for("admin.dashboard"))
    return render_template(
        "admin/dashboard.html",
        teams=Team.all(db),
        questions_count=len(Question.all(db)),
        rounds=Question.rounds(db),
    )


@admin_bp.route("/login-validation", methods=["GET", "POST"])
@admin_required
def login_validation():
    db = _db()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "toggle":
            enabled = request.form.get("enabled") == "1"
            LoginValidationSettings.set_enabled(db, enabled)
            flash("Login Data Validation enabled." if enabled else "Login Data Validation disabled.", "success")
        elif action == "create":
            team_name = request.form.get("team_name", "").strip()
            login_name = request.form.get("login_name", "").strip()
            team_members = request.form.get("team_members", "").strip()
            if not team_name or not login_name:
                flash("Team Name and Login Name are required.", "error")
            else:
                try:
                    ValidTeam.create(db, team_name, login_name, team_members)
                    flash("Team added.", "success")
                except sqlite3.IntegrityError:
                    flash("A team with that Login Name already exists.", "error")
        elif action == "update":
            valid_team_id = int(request.form["id"])
            team_name = request.form.get("team_name", "").strip()
            login_name = request.form.get("login_name", "").strip()
            team_members = request.form.get("team_members", "").strip()
            if not team_name or not login_name:
                flash("Team Name and Login Name are required.", "error")
            else:
                try:
                    ValidTeam.update(db, valid_team_id, team_name, login_name, team_members)
                    flash("Team updated.", "success")
                except sqlite3.IntegrityError:
                    flash("A team with that Login Name already exists.", "error")
        elif action == "delete":
            ValidTeam.delete(db, int(request.form["id"]))
            flash("Team removed.", "success")
        return redirect(url_for("admin.login_validation"))

    edit_id = request.args.get("edit", type=int)
    edit_team = ValidTeam.get(db, edit_id) if edit_id else None
    return render_template(
        "admin/login_validation.html",
        settings=LoginValidationSettings.get(db),
        valid_teams=ValidTeam.all(db),
        edit_team=edit_team,
    )


@admin_bp.route("/round", methods=["GET", "POST"])
@admin_required
def round_control():
    db = _db()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "open":
            QuizStatus.open_round(db)
        elif action == "close":
            QuizStatus.close_round(db)
        elif action == "next":
            QuizStatus.next_round(db)
        elif action == "finish":
            QuizStatus.finish(db)
        elif action == "reset":
            QuizStatus.reset(db)
            Result.reset_all(db)
        elif action == "duration":
            try:
                QuizStatus.set_duration(db, int(request.form.get("duration", 60)))
            except ValueError:
                flash("Invalid duration.", "error")
        elif action == "set_schedule":
            value = request.form.get("start_datetime", "").strip()
            if value and QuizStatus.parse_start(value) is None:
                flash("Invalid start date/time.", "error")
            else:
                QuizStatus.set_schedule(db, value)
                flash("Quiz start time scheduled." if value else "Schedule cleared.", "success")
        elif action == "clear_schedule":
            QuizStatus.clear_schedule(db)
            flash("Schedule cleared.", "success")
        elif action == "toggle_auto_advance":
            QuizStatus.set_auto_advance(db, request.form.get("enabled") == "1")
            flash(
                "Auto-advance enabled." if request.form.get("enabled") == "1" else "Auto-advance disabled.",
                "success",
            )
        return redirect(url_for("admin.round_control"))

    status = QuizStatus.get(db)
    return render_template(
        "admin/round_control.html",
        rounds=Question.rounds(db),
        schedule_status=QuizStatus.schedule_label(status),
        submitted_count=Result.submitted_count(db, status["current_round"]),
        team_count=Team.active_count(db),
        opened_rounds=QuizStatus.get_opened_rounds(status),
    )


@admin_bp.route("/questions", methods=["GET", "POST"])
@admin_required
def questions():
    db = _db()
    if request.method == "POST":
        action = request.form.get("action", "create")
        if action == "delete":
            Question.delete(db, int(request.form["id"]))
        else:
            Question.create(
                db,
                int(request.form["round_number"]),
                request.form["text"].strip(),
                request.form["option_a"].strip(),
                request.form["option_b"].strip(),
                request.form["option_c"].strip(),
                request.form["option_d"].strip(),
                request.form["correct_option"].strip().upper(),
            )
        return redirect(url_for("admin.questions"))
    return render_template("admin/questions.html", questions=Question.all(db))


@admin_bp.route("/leaderboard")
@admin_required
def leaderboard():
    return render_template("admin/leaderboard.html", leaderboard=Result.leaderboard(_db()))


@admin_bp.route("/results")
@admin_required
def results():
    db = _db()
    data = {}
    for r in Question.rounds(db):
        data[r] = Result.round_results(db, r)
    return render_template("admin/results.html", data=data)


@admin_bp.route("/winner")
@admin_required
def winner():
    board = Result.leaderboard(_db())
    winner = board[0] if board else None
    return render_template("admin/winner.html", winner=winner, leaderboard=board)

@admin_bp.route("/violations")
@admin_required
def violations():
    return render_template("admin/violations.html", rows=Violation.recent(_db(), limit=200))


@admin_bp.route("/history", methods=["GET","POST"])
@admin_required
def history():
    db=_db()
    if request.method=="POST":
        act=request.form.get("action")
        if act=="clear":
            db.execute("DELETE FROM results")
        elif request.form.get("id"):
            db.execute("DELETE FROM results WHERE id=?",(request.form.get("id"),))
        db.commit()
        return redirect(url_for("admin.history"))
    rows=db.execute("SELECT * FROM results ORDER BY id DESC").fetchall()
    return render_template("admin/history.html", rows=rows)
