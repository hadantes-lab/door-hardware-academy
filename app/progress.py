"""Learner progress stored in SQLite: profiles, quiz attempts, unlocks and daily streaks.

Every learner has a `learner_id` (a random hex string kept in the signed session
cookie). Guests have one too, so a guest's progress carries over when they create a
profile. `attempts.user_id` always holds a learner_id.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from flask import current_app, g
from werkzeug.security import check_password_hash, generate_password_hash

from .content import Lesson, Segment

SCHEMA = """
CREATE TABLE IF NOT EXISTS attempts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT    NOT NULL,   -- learner_id
    segment_id  TEXT    NOT NULL,
    lesson_id   TEXT,               -- NULL for the cumulative segment quiz
    score       REAL    NOT NULL,
    passed      INTEGER NOT NULL,
    taken_on    TEXT    NOT NULL,   -- ISO date, used for streaks
    created_at  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS attempts_user ON attempts (user_id, segment_id);

CREATE TABLE IF NOT EXISTS users (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    username       TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    display_name   TEXT    NOT NULL,
    role           TEXT    NOT NULL DEFAULT '',
    password_hash  TEXT    NOT NULL,
    learner_id     TEXT    NOT NULL UNIQUE,
    created_at     TEXT    NOT NULL
);
"""

ROLES = (
    "Architect or designer",
    "Hardware consultant or specifier",
    "Distributor or sales",
    "Contractor or installer",
    "Facilities or security",
    "Student",
    "Other",
)


@dataclass(frozen=True)
class User:
    id: int
    username: str
    display_name: str
    role: str
    learner_id: str
    created_at: str

    @property
    def initial(self) -> str:
        return (self.display_name or self.username)[:1].upper()

    @property
    def member_since(self) -> str:
        return datetime.fromisoformat(self.created_at).strftime("%B %Y")


def _user(row: sqlite3.Row | None) -> User | None:
    if row is None:
        return None
    return User(row["id"], row["username"], row["display_name"], row["role"],
                row["learner_id"], row["created_at"])


class UsernameTaken(ValueError):
    pass


def create_user(username: str, display_name: str, password: str, learner_id: str,
                role: str = "") -> User:
    db = get_db()
    try:
        db.execute(
            "INSERT INTO users (username, display_name, role, password_hash, learner_id, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (username, display_name, role, generate_password_hash(password), learner_id,
             datetime.now(timezone.utc).isoformat()),
        )
        db.commit()
    except sqlite3.IntegrityError as exc:
        db.rollback()
        raise UsernameTaken(username) from exc
    return user_by_learner(learner_id)


def user_by_learner(learner_id: str) -> User | None:
    return _user(get_db().execute("SELECT * FROM users WHERE learner_id = ?", (learner_id,)).fetchone())


def authenticate(username: str, password: str) -> User | None:
    row = get_db().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if row is None:
        # Hash anyway so a missing username takes as long as a wrong password.
        check_password_hash(generate_password_hash("timing"), password)
        return None
    return _user(row) if check_password_hash(row["password_hash"], password) else None


def update_profile(learner_id: str, display_name: str, role: str) -> None:
    db = get_db()
    db.execute("UPDATE users SET display_name = ?, role = ? WHERE learner_id = ?",
               (display_name, role, learner_id))
    db.commit()


def change_password(learner_id: str, new_password: str) -> None:
    db = get_db()
    db.execute("UPDATE users SET password_hash = ? WHERE learner_id = ?",
               (generate_password_hash(new_password), learner_id))
    db.commit()


def merge_progress(from_learner: str, to_learner: str) -> int:
    """Move a guest's attempts onto a signed-in profile. Returns rows moved."""
    if from_learner == to_learner:
        return 0
    db = get_db()
    cur = db.execute("UPDATE attempts SET user_id = ? WHERE user_id = ?", (to_learner, from_learner))
    db.commit()
    return cur.rowcount


def has_progress(learner_id: str) -> bool:
    return get_db().execute("SELECT 1 FROM attempts WHERE user_id = ? LIMIT 1",
                            (learner_id,)).fetchone() is not None


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
    number: int                  # unit number shown to learners, starting at 1
    unlocked: bool               # units open in order: the previous unit's quiz must be passed
    lessons: tuple[LessonState, ...]
    quiz_unlocked: bool
    quiz_passed: bool
    best_quiz_score: float | None

    @property
    def done_count(self) -> int:
        return sum(s.state == "done" for s in self.lessons)

    @property
    def next_lesson(self) -> Lesson | None:
        if not self.unlocked:
            return None
        return next((s.lesson for s in self.lessons if s.state == "next"), None)

    @property
    def fraction(self) -> float:
        """Share of the unit finished: each lesson and the unit quiz count once."""
        steps = len(self.lessons) + 1
        return (self.done_count + int(self.quiz_passed)) / steps


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


def segment_progress(user_id: str, segment: Segment, number: int = 1,
                     unlocked: bool = True) -> SegmentProgress:
    states = lesson_states(segment, passed_lessons(user_id, segment.id))
    if not unlocked:
        states = tuple(LessonState(s.lesson, "done" if s.state == "done" else "locked") for s in states)
    return SegmentProgress(
        segment=segment,
        number=number,
        unlocked=unlocked,
        lessons=states,
        quiz_unlocked=unlocked and all(s.state == "done" for s in states),
        quiz_passed=segment_passed(user_id, segment.id),
        best_quiz_score=best_segment_score(user_id, segment.id),
    )


def course_progress(user_id: str, segments) -> list[SegmentProgress]:
    """Progress for every unit in course order. Unit 1 is always open; each later
    unit opens once the unit before it has its unit quiz passed."""
    result: list[SegmentProgress] = []
    previous_passed = True
    for number, segment in enumerate(segments, start=1):
        sp = segment_progress(user_id, segment, number, unlocked=previous_passed)
        result.append(sp)
        previous_passed = sp.quiz_passed
    return result


@dataclass(frozen=True)
class Stats:
    lessons_done: int
    lessons_total: int
    units_done: int
    units_total: int
    quizzes_taken: int
    average_score: float | None
    days_practiced: int
    streak: int


def stats(user_id: str, course: list[SegmentProgress], today: date | None = None) -> Stats:
    row = get_db().execute(
        "SELECT COUNT(*) AS n, AVG(score) AS avg, COUNT(DISTINCT taken_on) AS days"
        " FROM attempts WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    return Stats(
        lessons_done=sum(sp.done_count for sp in course),
        lessons_total=sum(len(sp.lessons) for sp in course),
        units_done=sum(sp.quiz_passed for sp in course),
        units_total=len(course),
        quizzes_taken=row["n"],
        average_score=row["avg"],
        days_practiced=row["days"],
        streak=streak(user_id, today),
    )
