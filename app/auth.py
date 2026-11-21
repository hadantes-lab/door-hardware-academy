"""Learner profiles: sign up, sign in, sign out and the profile page.

Identity lives in Flask's signed session cookie as `uid` (the learner_id). A guest
has a uid with no matching user row; signing up attaches a profile to that same uid,
so everything the guest already completed is kept.
"""
from __future__ import annotations

import re
import uuid

from flask import (Blueprint, current_app, flash, g, redirect, render_template, request,
                   session, url_for)

from . import progress

bp = Blueprint("auth", __name__)

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")
MIN_PASSWORD = 8


def _safe_next(target: str | None) -> str:
    """Only follow local redirects, never another site."""
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return url_for("main.home")


def _start_session(learner_id: str) -> None:
    csrf = session.get("csrf")
    session.clear()  # new session on sign-in or sign-out
    session["uid"] = learner_id
    if csrf:
        session["csrf"] = csrf
    session.permanent = True


def _validate_profile(display_name: str, role: str) -> list[str]:
    errors = []
    if not 1 <= len(display_name) <= 40:
        errors.append("Enter a display name of up to 40 characters.")
    if role and role not in progress.ROLES:
        errors.append("Choose a role from the list.")
    return errors


@bp.route("/signup", methods=["GET", "POST"])
def signup():
    if g.user:
        return redirect(url_for("auth.profile"))
    form = {"username": "", "display_name": "", "role": ""}
    errors: list[str] = []
    if request.method == "POST":
        form = {k: request.form.get(k, "").strip() for k in form}
        password = request.form.get("password", "")
        if not USERNAME_RE.match(form["username"]):
            errors.append("Usernames are 3–30 letters, numbers, dots, dashes or underscores.")
        errors += _validate_profile(form["display_name"], form["role"])
        if len(password) < MIN_PASSWORD:
            errors.append(f"Use a password of at least {MIN_PASSWORD} characters.")
        if not errors:
            try:
                # Reuse the guest's learner id so their progress comes with them.
                user = progress.create_user(form["username"], form["display_name"], password,
                                            session["uid"], form["role"])
            except progress.UsernameTaken:
                errors.append("That username is taken. Try another.")
            else:
                _start_session(user.learner_id)
                flash(f"Profile created. Welcome, {user.display_name}! Your progress is saved.")
                return redirect(_safe_next(request.args.get("next")))
    return render_template("signup.html", form=form, errors=errors, roles=progress.ROLES,
                           guest_progress=progress.has_progress(session["uid"])), (400 if errors else 200)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("auth.profile"))
    username = ""
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        user = progress.authenticate(username, request.form.get("password", ""))
        if user is None:
            error = "That username and password don't match. Check both and try again."
        else:
            moved = progress.merge_progress(session["uid"], user.learner_id)
            _start_session(user.learner_id)
            msg = f"Welcome back, {user.display_name}."
            if moved:
                msg += " Lessons you finished as a guest were added to your profile."
            flash(msg)
            return redirect(_safe_next(request.args.get("next")))
    return render_template("login.html", username=username, error=error), (401 if error else 200)


@bp.route("/logout", methods=["POST"])
def logout():
    _start_session(uuid.uuid4().hex)
    flash("Signed out. Sign in any time to pick up where you left off.")
    return redirect(url_for("main.home"))


@bp.route("/profile", methods=["GET", "POST"])
def profile():
    if not g.user:
        return redirect(url_for("auth.login", next=url_for("auth.profile")))
    errors: list[str] = []
    if request.method == "POST":
        action = request.form.get("action")
        if action == "profile":
            display_name = request.form.get("display_name", "").strip()
            role = request.form.get("role", "").strip()
            errors = _validate_profile(display_name, role)
            if not errors:
                progress.update_profile(g.user.learner_id, display_name, role)
                flash("Profile saved.")
                return redirect(url_for("auth.profile"))
        elif action == "password":
            current = request.form.get("current_password", "")
            new = request.form.get("new_password", "")
            if progress.authenticate(g.user.username, current) is None:
                errors.append("Your current password is incorrect.")
            elif len(new) < MIN_PASSWORD:
                errors.append(f"Use a new password of at least {MIN_PASSWORD} characters.")
            else:
                progress.change_password(g.user.learner_id, new)
                flash("Password changed.")
                return redirect(url_for("auth.profile"))

    course = progress.course_progress(g.user.learner_id, current_app.config["SEGMENTS"].values())
    return render_template("profile.html", course=course, roles=progress.ROLES, errors=errors,
                           stats=progress.stats(g.user.learner_id, course)), (400 if errors else 200)
