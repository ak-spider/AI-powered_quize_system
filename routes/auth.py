from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import sqlite3
from models.team import Team
from models.login_validation import LoginValidationSettings, ValidTeam

auth_bp = Blueprint("auth", __name__)


def _db():
    from app import get_db
    return get_db()


@auth_bp.route("/", methods=["GET"])
def index():
    if session.get("team_id"):
        return redirect(url_for("quiz.waiting"))
    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        name = request.form.get("team_name", "").strip()
        if not name:
            flash("Team name is required.", "error")
            return render_template("login.html")
        db = _db()

        # Admin Controlled Login Data Validation for Teams: when enabled,
        # the entered name must exactly match a team the admin listed in
        # the Admin Panel before the normal login flow continues. When
        # disabled (default), this is a no-op and behavior is unchanged.
        if LoginValidationSettings.is_enabled(db) and ValidTeam.find_by_login(db, name) is None:
            flash("Invalid Team/Login Name. Please enter a valid team.", "error")
            return render_template("login.html")

        team = Team.get_by_name(db, name)
        if team is None:
            # auto-register on first login
            try:
                tid = Team.create(db, name)
                team = Team.get(db, tid)
            except sqlite3.IntegrityError:
                flash("Could not create team.", "error")
                return render_template("login.html")
        elif not team["is_active"]:
            flash("This team name has been disabled by the admin.", "error")
            return render_template("login.html")
        session["team_id"] = team["id"]
        session["team_name"] = team["name"]
        return redirect(url_for("quiz.waiting"))
    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    session.pop("team_id", None)
    session.pop("team_name", None)
    return redirect(url_for("auth.login"))
