# Door Hardware Academy

A Duolingo-style web app for learning architectural door hardware. Each visit
serves one short lesson — a few illustrated cards — that ends in a quick quiz.
Pass every lesson in a segment and a bigger, cumulative segment quiz unlocks.

This first slice covers one segment, **Hanging the Door** (hinges, continuous
hinges and pivots), with three lessons, six original diagrams and a segment quiz.

## How it works

```
Home ──► Today's lesson ──► cards 1…n ──► lesson quiz (pass 70%) ──► next lesson unlocks
                                                         │
                         all lessons passed ─────────────┴──► segment quiz
```

- **Lessons unlock in order.** Later lessons and the segment quiz stay locked until the earlier ones are passed.
- **Segment quizzes build on everything.** Every scenario question written for the segment is included, then lesson questions fill the rest, with every lesson represented.
- **Streaks** count consecutive days with at least one passed quiz.
- **Progress** is stored per browser in a local SQLite file (`instance/progress.db`). There are no accounts yet.

## Run it locally

Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python run.py                    # open http://127.0.0.1:5000
```

Run the tests:

```bash
pytest -q
# or, without installing pytest:
python -m unittest discover -s tests -t .
```

For anything beyond local use, set a real `SECRET_KEY` environment variable.
`DATABASE` and `CONTENT_DIR` can also be overridden with environment variables.

## Project layout

```
app/
  __init__.py      app factory and template filters
  content.py       loads and validates YAML lessons
  quiz.py          grading and segment-quiz assembly (no Flask, easy to test)
  progress.py      SQLite attempts, unlocks and streaks
  routes.py        pages: home, lesson cards, quizzes
  templates/       Jinja templates
  static/          CSS and SVG diagrams
content/
  hinges.yaml      the Hanging the Door segment
tests/             unit and route tests
```

## Adding a segment

Lessons are plain YAML, so you can add content without touching Python.

1. Copy `content/hinges.yaml` to a new file, e.g. `content/exit-devices.yaml`.
2. Give it a unique `id` and, optionally, an `order` number to control where it appears.
3. Write 3–5 lessons. Each lesson has `cards` (title, body, optional `image` + `alt`) and a `quiz`.
4. Each question needs a unique `id`, a `prompt`, 2+ `options`, the `answer` (0-based index) and an `explain` line.
5. Add scenario questions under `segment_quiz` and set `segment_quiz_size`.
6. Put images in `app/static/img/` and run the tests: they check every image exists and has alt text, every answer index is valid and no question id repeats.

Use `**double asterisks**` in card text for bold key terms.

## Content accuracy and images

Lesson text is written in our own words and checked against ANSI/BHMA standards
and manufacturer catalogs. Before publishing, have an experienced hardware
consultant (for example, a DHI-certified AHC) review each segment.

The diagrams in `app/static/img/` are original drawings made for this project.
Manufacturer photos and catalog drawings are copyrighted: get written permission
before adding any to the app.

## Ideas for next steps

- Segments for locks, exit devices, closers, protection, keying and electrified hardware
- Accounts so progress follows the learner across devices
- Spaced repetition: resurface questions a learner missed in later sessions
- Image-identification questions ("which closer arm is this?")
