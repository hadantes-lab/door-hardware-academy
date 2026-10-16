"""Learner progress stored in SQLite: quiz attempts, unlocks and daily streaks."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from flask import current_app, g

from .content import Lesson, Segment

SCHEMA = """
CREATE TABLE IF NOT EXISTS attempts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT    NOT NULL,
    segment_id  TEXT    NOT NULL,
    lesson_id   TEXT,               -- NULL for the cumulative segment quiz
    score       REAL    NOT NULL,
    passed      INTEGER NOT NULL,
    taken_on    TEXT    NOT NULL,   -- ISO date, used for streaks
    created_at  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS attempts_user ON attempts (user_id, segment_id);
"""


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        path = current_app.config["DATABASE"]
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(path)
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(_exc=None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    get_db().executescript(SCHEMA)


def record_attempt(user_id: str, segment_id: str, lesson_id: str | None,
                   score: float, passed: bool, today: date | None = None) -> None:
    today = today or date.today()
    db = get_db()
    db.execute(
        "INSERT INTO attempts (user_id, segment_id, lesson_id, score, passed, taken_on, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, segment_id, lesson_id, score, int(passed), today.isoformat(),
         datetime.now(timezone.utc).isoformat()),
    )
    db.commit()


def passed_lessons(user_id: str, segment_id: str) -> set[str]:
    rows = get_db().execute(
        "SELECT DISTINCT lesson_id FROM attempts"
        " WHERE user_id = ? AND segment_id = ? AND lesson_id IS NOT NULL AND passed = 1",
        (user_id, segment_id),
    ).fetchall()
    return {r["lesson_id"] for r in rows}


def best_segment_score(user_id: str, segment_id: str) -> float | None:
    row = get_db().execute(
        "SELECT MAX(score) AS best FROM attempts"
        " WHERE user_id = ? AND segment_id = ? AND lesson_id IS NULL",
        (user_id, segment_id),
    ).fetchone()
    return row["best"]


def segment_passed(user_id: str, segment_id: str) -> bool:
    row = get_db().execute(
        "SELECT 1 FROM attempts WHERE user_id = ? AND segment_id = ? AND lesson_id IS NULL AND passed = 1",
        (user_id, segment_id),
    ).fetchone()
    return row is not None


def streak(user_id: str, today: date | None = None) -> int:
    """Consecutive days with at least one passed quiz, ending today (or yesterday,
    so a streak is not lost before the learner has had a chance to practise today)."""
    today = today or date.today()
    rows = get_db().execute(
        "SELECT DISTINCT taken_on FROM attempts WHERE user_id = ? AND passed = 1",
        (user_id,),
    ).fetchall()
    days = {date.fromisoformat(r["taken_on"]) for r in rows}
    cursor = today if today in days else today - timedelta(days=1)
    count = 0
    while cursor in days:
        count += 1
        cursor -= timedelta(days=1)
    return count


@dataclass(frozen=True)
class LessonState:
    lesson: Lesson
    state: str  # "done", "next" or "locked"


@dataclass(frozen=True)
class SegmentProgress:
    segment: Segment
    lessons: tuple[LessonState, ...]
    quiz_unlocked: bool
    quiz_passed: bool
    best_quiz_score: float | None

    @property
    def done_count(self) -> int:
        return sum(s.state == "done" for s in self.lessons)

    @property
    def next_lesson(self) -> Lesson | None:
        return next((s.lesson for s in self.lessons if s.state == "next"), None)


def lesson_states(segment: Segment, passed: set[str]) -> tuple[LessonState, ...]:
    """Lessons unlock in order: each one opens once the previous one is passed."""
    states = []
    previous_done = True
    for lesson in segment.lessons:
        if lesson.id in passed:
            state = "done"
        elif previous_done:
            state = "next"
        else:
            state = "locked"
        states.append(LessonState(lesson, state))
        previous_done = state == "done"
    return tuple(states)


def segment_progress(user_id: str, segment: Segment) -> SegmentProgress:
    states = lesson_states(segment, passed_lessons(user_id, segment.id))
    return SegmentProgress(
        segment=segment,
        lessons=states,
        quiz_unlocked=all(s.state == "done" for s in states),
        quiz_passed=segment_passed(user_id, segment.id),
        best_quiz_score=best_segment_score(user_id, segment.id),
    )
