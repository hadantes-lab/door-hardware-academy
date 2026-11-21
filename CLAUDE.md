# Door Hardware Academy

Duolingo-style Flask app that teaches architectural door hardware. Each session is
one short lesson (illustrated cards) ending in a quiz; passing every lesson in a
unit unlocks a cumulative unit quiz, and passing that unlocks the next unit.
Learners can save a profile so progress follows them across devices.

Built so far: Unit 1 "The Opening" (`content/opening.yaml`, lessons 1–5 of the
course outline) and Unit 2 "Hanging the Door" (`content/hinges.yaml`).

In code and YAML a unit is called a "segment" (`segment_quiz`, `segment_id`, `/s/<id>/...`);
the UI calls it a unit.

## Commands

```bash
pip install -r requirements-dev.txt
python run.py                                   # dev server on http://127.0.0.1:5000
pytest -q                                       # tests
python -m unittest discover -s tests -t .       # same tests without pytest
```

Windows: activate the venv with `.venv\Scripts\activate`.

## Layout

- `app/__init__.py`: app factory, session settings (180-day cookie), CSRF check on every POST, `g.user`.
- `app/auth.py`: sign up, sign in, sign out (POST only), profile page (edit name/role, change password).
- `app/content.py`: loads and validates `content/*.yaml` into frozen dataclasses, sorted by `order`. Raises `ContentError` on bad data.
- `app/quiz.py`: grading and unit-quiz assembly. Pure functions, no Flask.
- `app/progress.py`: SQLite (`instance/progress.db`): users, attempts, ordered unlocks (`course_progress`), streaks, stats.
- `app/routes.py`: home, lesson cards, lesson quiz, unit quiz.
- `app/templates/`, `app/static/style.css`, `app/static/img/*.svg`: UI and original diagrams.
- `tests/`: unittest-style tests (pytest also runs them). `tests/test_app.py` has helpers
  (`post`, `pass_lesson`, `pass_unit`) that send the CSRF token.

## GitHub Pages version

`docs/index.html` is a generated, self-contained static copy of the app for GitHub Pages
(served from `main` → `/docs`). `scripts/build_site.py` fills `site/template.html` with
the validated YAML content, the SVGs as data URIs (provenance metadata stripped) and
`app/static/style.css`. Progress and the profile live in the browser's localStorage
(`door-hardware-academy-v1`); the profile page exports/imports a transfer code.
Unlock rules in the template's `course()` must match `progress.course_progress`.

**After any change to `content/`, `app/static/img/`, `app/static/style.css` or
`site/template.html`, run `python scripts/build_site.py` and commit `docs/`.**
`tests/test_site.py` fails when the page is stale. Never edit `docs/index.html` by hand.

## How identity works

Every visitor gets a random `learner_id` in the signed session cookie (`session["uid"]`).
`attempts.user_id` stores that learner_id. A profile (`users` row) points at a learner_id:
signing up attaches the profile to the guest's current id (progress kept); signing in
moves any guest attempts onto the profile (`merge_progress`). Sign out starts a fresh guest id.

## Conventions

- Lesson content is data. Add units as new YAML files in `content/`, never in Python.
  Copy `content/opening.yaml` as the template and give it the next `order` number.
  Question `answer` is a 0-based option index. Question ids must be unique within a unit.
- List the sources you checked at the top of each unit's YAML file.
- Card text supports `**bold**` only (escaped, then rendered by the `emphasis` filter).
- Every card image needs `alt` text; tests enforce this and check that the file exists.
- Diagrams are original SVGs drawn for this project, on a light ground (they sit on a
  light panel in dark mode too). Keep labels at 12px or larger in a ~560px-wide viewBox so they
  read on phones. Do not add manufacturer photos or catalog drawings without written
  permission: they are copyrighted.
- Every POST form needs `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`.
- Phone first: buttons at least 48px tall; lesson and quiz actions go in `.action-bar`,
  which is pinned to the bottom of the screen under 640px. Check new pages at 390px wide.
- Keep `quiz.py` free of Flask so it stays easy to unit test.
- Run the tests before committing. CI (`.github/workflows/tests.yml`) runs pytest on Python 3.11–3.13.

## Roadmap

The full plan is the "Door Hardware Academy: 90-Lesson Course Outline" doc on claude.ai
(18 units of 5 lessons). Unit 2 currently has 3 hinge lessons; the outline's Unit 2 adds
continuous hinges, pivots and hinge selection. Next up: Unit 3, Securing the door (lock
types, anatomy and functions).

Other ideas: password reset by email, spaced repetition of missed questions,
image-identification questions, deployment with a persistent database disk.

Planning notes and a manufacturer catalog list live in the
"Door Hardware Learning App: Sourcing Plan" doc on claude.ai.
