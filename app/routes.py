"""Web routes: home, lesson cards, lesson quiz and the cumulative segment quiz."""
from __future__ import annotations

import uuid

from flask import (Blueprint, abort, current_app, flash, redirect, render_template,
                   request, session, url_for)

from . import progress
from .content import Segment
from .quiz import build_segment_quiz, grade, parse_answers

bp = Blueprint("main", __name__)


@bp.before_app_request
def ensure_learner() -> None:
    # One anonymous learner per browser. Swap for real accounts later.
    if "uid" not in session:
        session["uid"] = uuid.uuid4().hex
        session.permanent = True


def _segments() -> dict[str, Segment]:
    return current_app.config["SEGMENTS"]


def _segment_or_404(segment_id: str) -> Segment:
    segment = _segments().get(segment_id)
    if segment is None:
        abort(404)
    return segment


def _lesson_or_redirect(segment: Segment, lesson_id: str):
    """Return (lesson, None) if the learner may open it, else (None, redirect)."""
    lesson = segment.lesson(lesson_id)
    if lesson is None:
        abort(404)
    states = progress.lesson_states(segment, progress.passed_lessons(session["uid"], segment.id))
    state = next(s.state for s in states if s.lesson.id == lesson_id)
    if state == "locked":
        flash("Finish the earlier lessons first to unlock that one.")
        return None, redirect(url_for("main.home"))
    return lesson, None


@bp.route("/")
def home():
    uid = session["uid"]
    segments = [progress.segment_progress(uid, s) for s in _segments().values()]
    # "Today's lesson": the first unfinished step anywhere in the course.
    today = None
    for sp in segments:
        if sp.next_lesson:
            today = ("lesson", sp.segment, sp.next_lesson)
            break
        if sp.quiz_unlocked and not sp.quiz_passed:
            today = ("quiz", sp.segment, None)
            break
    return render_template("home.html", segments=segments, today=today,
                           streak=progress.streak(uid))


@bp.route("/s/<segment_id>/l/<lesson_id>/")
@bp.route("/s/<segment_id>/l/<lesson_id>/<int:card>")
def lesson_card(segment_id: str, lesson_id: str, card: int = 1):
    segment = _segment_or_404(segment_id)
    lesson, redirect_to = _lesson_or_redirect(segment, lesson_id)
    if redirect_to:
        return redirect_to
    if not 1 <= card <= len(lesson.cards):
        abort(404)
    return render_template("card.html", segment=segment, lesson=lesson,
                           card=lesson.cards[card - 1], number=card, total=len(lesson.cards))


@bp.route("/s/<segment_id>/l/<lesson_id>/quiz", methods=["GET", "POST"])
def lesson_quiz(segment_id: str, lesson_id: str):
    segment = _segment_or_404(segment_id)
    lesson, redirect_to = _lesson_or_redirect(segment, lesson_id)
    if redirect_to:
        return redirect_to

    if request.method == "POST":
        result = grade(lesson.quiz, parse_answers(request.form, lesson.quiz), segment.pass_mark)
        progress.record_attempt(session["uid"], segment.id, lesson.id, result.score, result.passed)
        return render_template("result.html", segment=segment, lesson=lesson, result=result,
                               retry_url=url_for("main.lesson_quiz", segment_id=segment.id,
                                                 lesson_id=lesson.id))
    return render_template("quiz.html", segment=segment, lesson=lesson, questions=lesson.quiz,
                           heading=f"Quick check: {lesson.title}")


@bp.route("/s/<segment_id>/quiz", methods=["GET", "POST"])
def segment_quiz(segment_id: str):
    segment = _segment_or_404(segment_id)
    uid = session["uid"]
    sp = progress.segment_progress(uid, segment)
    if not sp.quiz_unlocked:
        flash("Pass every lesson in this segment to unlock the segment quiz.")
        return redirect(url_for("main.home"))

    key = f"segment_quiz:{segment.id}"
    pool = {q.id: q for q in segment.question_pool}

    if request.method == "POST":
        ids = session.get(key)
        if not ids or any(i not in pool for i in ids):
            flash("That quiz expired. Here is a fresh one.")
            return redirect(url_for("main.segment_quiz", segment_id=segment.id))
        questions = [pool[i] for i in ids]
        result = grade(questions, parse_answers(request.form, questions), segment.pass_mark)
        progress.record_attempt(uid, segment.id, None, result.score, result.passed)
        session.pop(key, None)
        return render_template("result.html", segment=segment, lesson=None, result=result,
                               retry_url=url_for("main.segment_quiz", segment_id=segment.id))

    questions = build_segment_quiz(segment)
    session[key] = [q.id for q in questions]
    return render_template("quiz.html", segment=segment, lesson=None, questions=questions,
                           heading=f"Segment quiz: {segment.title}")
