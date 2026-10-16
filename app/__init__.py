"""Door Hardware Academy: bite-sized lessons and quizzes on architectural door hardware."""
from __future__ import annotations

import os
import re
from pathlib import Path

from flask import Flask
from markupsafe import Markup, escape

from . import progress
from .content import load_segments

ROOT = Path(__file__).resolve().parent.parent


def _emphasis(text: str) -> Markup:
    """Render **bold** in lesson text safely: escape first, then add <strong>."""
    escaped = str(escape(text))
    return Markup(re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped))


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_path=str(ROOT / "instance"))
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-change-me"),
        DATABASE=os.environ.get("DATABASE", str(ROOT / "instance" / "progress.db")),
        CONTENT_DIR=os.environ.get("CONTENT_DIR", str(ROOT / "content")),
    )
    if test_config:
        app.config.update(test_config)

    app.config["SEGMENTS"] = load_segments(app.config["CONTENT_DIR"])
    app.jinja_env.filters["emphasis"] = _emphasis
    app.jinja_env.filters["pct"] = lambda v: f"{round(v * 100)}%"
    app.teardown_appcontext(progress.close_db)

    with app.app_context():
        progress.init_db()

    from .routes import bp
    app.register_blueprint(bp)
    return app
