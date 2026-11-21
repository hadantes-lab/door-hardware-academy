"""Door Hardware Academy: bite-sized lessons and quizzes on architectural door hardware."""
from __future__ import annotations

import hmac
import os
import re
import secrets
import uuid
from datetime import timedelta
from pathlib import Path

from flask import Flask, abort, g, request, session
from markupsafe import Markup, escape

from . import progress
from .content import load_segments

ROOT = Path(__file__).resolve().parent.parent


def _emphasis(text: str) -> Markup:
    """Render **bold** in lesson text safely: escape first, then add <strong>."""
    escaped = str(escape(text))
    return Markup(re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped))


def _csrf_token() -> str:
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_path=str(ROOT / "instance"))
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-change-me"),
        DATABASE=os.environ.get("DATABASE", str(ROOT / "instance" / "progress.db")),
        CONTENT_DIR=os.environ.get("CONTENT_DIR", str(ROOT / "content")),
        PERMANENT_SESSION_LIFETIME=timedelta(days=180),
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "") == "1",
    )
    if test_config:
        app.config.update(test_config)

    app.config["SEGMENTS"] = load_segments(app.config["CONTENT_DIR"])
    app.jinja_env.filters["emphasis"] = _emphasis
    app.jinja_env.filters["pct"] = lambda v: f"{round(v * 100)}%"
    app.jinja_env.globals["csrf_token"] = _csrf_token
    app.teardown_appcontext(progress.close_db)

    with app.app_context():
        progress.init_db()

    @app.before_request
    def load_learner() -> None:
        # Every visitor gets a learner id; signed-in visitors also have a profile row.
        if "uid" not in session:
            session["uid"] = uuid.uuid4().hex
            session.permanent = True
        g.user = progress.user_by_learner(session["uid"])

    @app.before_request
    def check_csrf() -> None:
        if request.method == "POST" and not app.config.get("CSRF_DISABLED"):
            sent = request.form.get("csrf_token", "")
            if not sent or not hmac.compare_digest(sent, session.get("csrf", "")):
                abort(400, "Your session expired. Go back, refresh the page and try again.")

    from .auth import bp as auth_bp
    from .routes import bp as main_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    return app
