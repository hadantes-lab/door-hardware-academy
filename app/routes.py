"""Web routes: home, lesson cards, lesson quiz and the cumulative unit (segment) quiz."""
from __future__ import annotations

from flask import (Blueprint, abort, current_app, flash, redirect, render_template,
                   request, session, url_for)

from . import progress
from .content import Segment
from .quiz import build_segment_quiz, grade, parse_answers

bp = Blueprint("main", __name__)


def _segments() -> dict[str, Segment]:
    return current_app.config["SEGMENTS"]


def _course() -> list[progress.SegmentProgress]:
    return progress.course_progress(session["uid"], _segments().values())


def _unit_or_404(segment_id: str) -> progress.SegmentProgress:
    unit = next((sp for sp in _course() if sp.segment.id == segment_id), None)
    if unit is None:
        abort(404)
    return unit


def _locked_unit_redirect(unit: progress.SegmentProgress):
    flash(f"Pass the Unit {unit.number - 1} quiz to unlock Unit {unit.number}.")
    return redirect(url_for("main.home"))


def _lesson_or_redirect(unit: progress.SegmentProgress, lesson_id: str):
    """Return (lesson, None) if the learner may open it, else (None, redirect)."""
    state = next((s for s in unit.lessons if s.lesson.id == lesson_id), None)
    if state is None:
        abort(404)
    if not unit.unlocked:
        return None, _locked_unit_redirect(unit)
    if state.state == "locked":
        flash("Finish the earlier lessons first to unlock that one.")
        return None, redirect(url_for("main.home"))
    return state.lesson, None


@bp.route("/")
def home():
    uid = session["uid"]
    course = _course()
    # "Today's lesson": the first unfinished step anywhere in the course.
    today = None
    for sp in course:
        if sp.next_lesson:
            today = ("lesson", sp, sp.next_lesson)
            break
        if sp.quiz_unlocked and not sp.quiz_passed:
            today = ("quiz", sp, None)
            break
    return render_template("home.html", course=course, today=today,
                           streak=progress.streak(uid),
                           guest_progress=progress.has_progress(uid))


@bp.route("/s/<segment_id>/l/<lesson_id>/")
@bp.route("/s/<segment_id>/l/<lesson_id>/<int:card>")
def lesson_card(segment_id: str, lesson_id: str, card: int = 1):
    unit = _unit_or_404(segment_id)
    lesson, redirect_to = _lesson_or_redirect(unit, lesson_id)
    if redirect_to:
        return redirect_to
    if not 1 <= card <= len(lesson.cards):
        abort(404)
    return render_template("card.html", unit=unit, segment=unit.segment, lesson=lesson,
                           card=lesson.cards[card - 1], number=card, total=len(lesson.cards))


@bp.route("/s/<segment_id>/l/<lesson_id>/quiz", methods=["GET", "POST"])
def lesson_quiz(segment_id: str, lesson_id: str):
    unit = _unit_or_404(segment_id)
    segment = unit.segment
    lesson, redirect_to = _lesson_or_redirect(unit, lesson_id)
    if redirect_to:
        return redirect_to

    if request.method == "POST":
        result = grade(lesson.quiz, parse_answers(request.form, lesson.quiz), segment.pass_mark)
        progress.record_attempt(session["uid"], segment.id, lesson.id, result.score, result.passed)
        return render_template("result.html", unit=unit, segment=segment, lesson=lesson,
                               result=result,
                               retry_url=url_for("main.lesson_quiz", segment_id=segment.id,
                                                 lesson_id=lesson.id))
    return render_template("quiz.html", unit=unit, segment=segment, lesson=lesson,
                           questions=lesson.quiz, heading=f"Quick check: {lesson.title}")


@bp.route("/s/<segment_id>/quiz", methods=["GET", "POST"])
def segment_quiz(segment_id: str):
    unit = _unit_or_404(segment_id)
    segment = unit.segment
    uid = session["uid"]
    if not unit.unlocked:
        return _locked_unit_redirect(unit)
    if not unit.quiz_unlocked:
        flash("Pass every lesson in this unit to unlock the unit quiz.")
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
        return render_template("result.html", unit=unit, segment=segment, lesson=None,
                               result=result,
                               retry_url=url_for("main.segment_quiz", segment_id=segment.id))

    questions = build_segment_quiz(segment)
    session[key] = [q.id for q in questions]
    return render_template("quiz.html", unit=unit, segment=segment, lesson=None,
                           questions=questions,
                           heading=f"Unit {unit.number} quiz: {segment.title}")
