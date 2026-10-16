"""Quiz grading and assembly. Pure functions, no Flask, so they are easy to test."""
from __future__ import annotations

import random
from dataclasses import dataclass

from .content import Question, Segment


@dataclass(frozen=True)
class Feedback:
    question: Question
    chosen: int | None

    @property
    def correct(self) -> bool:
        return self.chosen == self.question.answer

    @property
    def chosen_text(self) -> str:
        if self.chosen is None or not 0 <= self.chosen < len(self.question.options):
            return "No answer"
        return self.question.options[self.chosen]


@dataclass(frozen=True)
class Result:
    feedback: tuple[Feedback, ...]
    pass_mark: float

    @property
    def total(self) -> int:
        return len(self.feedback)

    @property
    def correct(self) -> int:
        return sum(f.correct for f in self.feedback)

    @property
    def score(self) -> float:
        return self.correct / self.total if self.total else 0.0

    @property
    def passed(self) -> bool:
        return self.score >= self.pass_mark


def parse_answers(form: dict, questions: tuple[Question, ...] | list[Question]) -> dict[str, int | None]:
    """Turn submitted form values (strings) into option indexes; bad input counts as no answer."""
    answers: dict[str, int | None] = {}
    for q in questions:
        raw = form.get(q.id)
        try:
            answers[q.id] = int(raw) if raw is not None else None
        except (TypeError, ValueError):
            answers[q.id] = None
    return answers


def grade(questions, answers: dict[str, int | None], pass_mark: float) -> Result:
    return Result(
        feedback=tuple(Feedback(q, answers.get(q.id)) for q in questions),
        pass_mark=pass_mark,
    )


def build_segment_quiz(segment: Segment, rng: random.Random | None = None) -> list[Question]:
    """Pick questions for the cumulative quiz.

    Every scenario question written for the segment quiz is included, then the
    rest is filled with lesson questions, at least one per lesson when room allows,
    so the quiz builds on everything the learner covered.
    """
    rng = rng or random.Random()
    size = segment.segment_quiz_size
    chosen: list[Question] = list(segment.segment_quiz)[:size]

    lesson_pools = [list(l.quiz) for l in segment.lessons]
    for pool in lesson_pools:
        rng.shuffle(pool)
    # One from each lesson first, then round-robin until full.
    while len(chosen) < size and any(lesson_pools):
        for pool in lesson_pools:
            if pool and len(chosen) < size:
                chosen.append(pool.pop())
    rng.shuffle(chosen)
    return chosen
