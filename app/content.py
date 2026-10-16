"""Load and validate lesson content from YAML files in the content/ folder.

Each YAML file is one segment (a hardware family). Keeping content in data files
means subject-matter experts can edit lessons without touching Python.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


class ContentError(ValueError):
    """Raised when a content file is missing fields or contradicts itself."""


@dataclass(frozen=True)
class Question:
    id: str
    prompt: str
    options: tuple[str, ...]
    answer: int
    explain: str = ""

    @property
    def correct_text(self) -> str:
        return self.options[self.answer]


@dataclass(frozen=True)
class Card:
    title: str
    body: str
    image: str | None = None
    alt: str = ""


@dataclass(frozen=True)
class Lesson:
    id: str
    title: str
    minutes: int
    cards: tuple[Card, ...]
    quiz: tuple[Question, ...]


@dataclass(frozen=True)
class Segment:
    id: str
    title: str
    subtitle: str
    pass_mark: float
    segment_quiz_size: int
    lessons: tuple[Lesson, ...]
    segment_quiz: tuple[Question, ...] = field(default_factory=tuple)

    def lesson(self, lesson_id: str) -> Lesson | None:
        return next((l for l in self.lessons if l.id == lesson_id), None)

    @property
    def question_pool(self) -> tuple[Question, ...]:
        """Every question in the segment, used to build the cumulative quiz."""
        pool: list[Question] = list(self.segment_quiz)
        for lesson in self.lessons:
            pool.extend(lesson.quiz)
        return tuple(pool)


def _require(data: dict, key: str, where: str):
    if key not in data or data[key] in (None, "", []):
        raise ContentError(f"{where}: missing '{key}'")
    return data[key]


def _question(raw: dict, where: str) -> Question:
    qid = _require(raw, "id", where)
    where = f"{where} question {qid}"
    options = tuple(str(o) for o in _require(raw, "options", where))
    if len(options) < 2:
        raise ContentError(f"{where}: needs at least two options")
    answer = _require(raw, "answer", where)
    if isinstance(answer, bool) or not isinstance(answer, int) or not 0 <= answer < len(options):
        raise ContentError(f"{where}: answer {answer!r} is not a valid option index")
    return Question(
        id=str(qid),
        prompt=str(_require(raw, "prompt", where)),
        options=options,
        answer=answer,
        explain=str(raw.get("explain", "")),
    )


def parse_segment(data: dict, source: str = "segment") -> Segment:
    seg_id = _require(data, "id", source)
    where = f"{source} ({seg_id})"
    lessons = []
    for raw in _require(data, "lessons", where):
        lid = _require(raw, "id", where)
        lw = f"{where} lesson {lid}"
        cards = tuple(
            Card(
                title=str(_require(c, "title", lw)),
                body=str(_require(c, "body", lw)),
                image=c.get("image"),
                alt=str(c.get("alt", "")),
            )
            for c in _require(raw, "cards", lw)
        )
        quiz = tuple(_question(q, lw) for q in _require(raw, "quiz", lw))
        lessons.append(
            Lesson(
                id=str(lid),
                title=str(_require(raw, "title", lw)),
                minutes=int(raw.get("minutes", 5)),
                cards=cards,
                quiz=quiz,
            )
        )

    segment = Segment(
        id=str(seg_id),
        title=str(_require(data, "title", where)),
        subtitle=str(data.get("subtitle", "")),
        pass_mark=float(data.get("pass_mark", 0.7)),
        segment_quiz_size=int(data.get("segment_quiz_size", 8)),
        lessons=tuple(lessons),
        segment_quiz=tuple(_question(q, f"{where} segment quiz") for q in data.get("segment_quiz", [])),
    )

    ids = [q.id for q in segment.question_pool]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise ContentError(f"{where}: duplicate question ids {dupes}")
    lesson_ids = [l.id for l in segment.lessons]
    if len(set(lesson_ids)) != len(lesson_ids):
        raise ContentError(f"{where}: duplicate lesson ids")
    if not 0 < segment.pass_mark <= 1:
        raise ContentError(f"{where}: pass_mark must be between 0 and 1")
    if segment.segment_quiz_size > len(segment.question_pool):
        raise ContentError(f"{where}: segment_quiz_size is larger than the question pool")
    return segment


def load_segments(content_dir: str | Path) -> dict[str, Segment]:
    """Load every *.yaml file in content_dir, ordered by an optional `order` key, then filename."""
    content_dir = Path(content_dir)
    loaded = []
    for path in sorted(content_dir.glob("*.yaml")):
        with path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        loaded.append((data.get("order", 100), path.name, parse_segment(data, path.name)))
    if not loaded:
        raise ContentError(f"No content files found in {content_dir}")
    segments: dict[str, Segment] = {}
    for _, _, seg in sorted(loaded, key=lambda t: (t[0], t[1])):
        if seg.id in segments:
            raise ContentError(f"Duplicate segment id {seg.id}")
        segments[seg.id] = seg
    return segments
