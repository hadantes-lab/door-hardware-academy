# Door Hardware Academy

Duolingo-style Flask app that teaches architectural door hardware. Each session is
one short lesson (illustrated cards) ending in a quiz; passing every lesson in a
segment unlocks a cumulative segment quiz. Only the "Hanging the Door" (hinges)
segment exists so far.

## First-time setup (do this once, then delete this section)

This folder was copied over without its git history or CI workflow. To finish:

1. Move `setup/github-workflow-tests.yml` to `.github/workflows/tests.yml` and delete the `setup/` folder.
2. Create a venv, install `requirements-dev.txt`, run the tests and confirm they pass.
3. `git init -b main`, commit everything as "Initial slice: Hanging the Door segment".
4. If the user wants it on GitHub, create the repo (with `gh repo create` if available) and push.
5. Remove this section from CLAUDE.md and commit.

## Commands

```bash
pip install -r requirements-dev.txt
python run.py                                   # dev server on http://127.0.0.1:5000
pytest -q                                       # tests
python -m unittest discover -s tests -t .       # same tests without pytest
```

Windows: activate the venv with `.venv\Scripts\activate`.

## Layout

- `app/content.py`: loads and validates `content/*.yaml` into frozen dataclasses. Raises `ContentError` on bad data.
- `app/quiz.py`: grading and segment-quiz assembly. Pure functions, no Flask.
- `app/progress.py`: SQLite (`instance/progress.db`): attempts, ordered unlocks, streaks.
- `app/routes.py`: home, lesson cards, lesson quiz, segment quiz. Anonymous learner id in the session.
- `app/templates/`, `app/static/style.css`, `app/static/img/*.svg`: UI and original diagrams.
- `tests/`: unittest-style tests (pytest also runs them).

## Conventions

- Lesson content is data. Add segments as new YAML files in `content/`, never in Python.
  Copy `content/hinges.yaml` as the template. Question `answer` is a 0-based option index.
  Question ids must be unique within a segment.
- Card text supports `**bold**` only (escaped, then rendered by the `emphasis` filter).
- Every card image needs `alt` text; tests enforce this and check that the file exists.
- Diagrams are original SVGs drawn for this project. Do not add manufacturer photos or
  catalog drawings without written permission: they are copyrighted.
- Facts in lessons should be checked against ANSI/BHMA standards or manufacturer catalogs.
  The hinge facts were checked against the BEST General Hinge Brochure and ASSA ABLOY's
  ANSI Door Hinges General Information.
- Keep `quiz.py` free of Flask so it stays easy to unit test.
- Run the tests before committing. CI (`.github/workflows/tests.yml`) runs pytest on Python 3.11–3.13.

## Roadmap

Planned segments, in order: door basics (handing, frames, fire ratings), hinges (done),
locks and functions, exit devices, closers/holders/stops, protection and sealing,
keying, electrified hardware, codes and scenarios. Other ideas: accounts, spaced
repetition of missed questions, image-identification questions.

Planning notes and a manufacturer catalog list live in the
"Door Hardware Learning App: Sourcing Plan" doc on claude.ai.
