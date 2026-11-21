# Door Hardware Academy

A Duolingo-style web app for learning architectural door hardware. Each visit
serves one short lesson, a few illustrated cards, that ends in a quick quiz.
Pass every lesson in a unit and a bigger, cumulative unit quiz unlocks; pass that
and the next unit opens.

The course follows a 90-lesson outline in 18 units. Two units are built so far:

| Unit | Title | Lessons |
| --- | --- | --- |
| 1 | The Opening | What makes an opening · Door types and cores · Frames · Handing, swing and bevel · Fire-rated openings 101 |
| 2 | Hanging the Door | Anatomy of a butt hinge · Mounting types and alternatives · Handing and finishes |

## How it works

```
Home ──► Today's lesson ──► cards 1…n ──► lesson quiz (pass 70%) ──► next lesson unlocks
                                                         │
                         all lessons passed ─────────────┴──► unit quiz ──► next unit unlocks
```

- **Lessons and units unlock in order.** Later lessons, the unit quiz and later units stay locked until the earlier ones are passed.
- **Unit quizzes build on everything.** Every scenario question written for the unit is included, then lesson questions fill the rest, with every lesson represented.
- **Streaks** count consecutive days with at least one passed quiz.
- **Profiles** save progress. Anyone can start as a guest; creating a profile (name, username, password, optional role) keeps everything done so far. Signing in on another device brings progress along, and lessons finished as a guest are added to the profile on sign-in. The profile page shows streak, lessons and units completed, average score and per-unit progress, and lets learners edit their name and role or change their password.
- **Phone first.** Large touch targets, lesson and quiz buttons pinned to the bottom of the screen, safe-area padding for notched phones, dark mode, and a web app manifest so the site can be added to a home screen.

## Run it locally

Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python run.py                    # open http://127.0.0.1:5000
```

To try it on your phone, run `flask --app run run --host 0.0.0.0` and open
`http://<your computer's IP>:5000` on a phone on the same Wi-Fi.

Run the tests:

```bash
pytest -q
# or, without installing pytest:
python -m unittest discover -s tests -t .
```

### Settings

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | Signs the session cookie that keeps learners signed in. **Set a long random value anywhere beyond your own computer**, or anyone could forge a session. |
| `SESSION_COOKIE_SECURE=1` | Send the session cookie over HTTPS only. Turn on when deployed behind HTTPS. |
| `DATABASE` | Path to the SQLite file (default `instance/progress.db`). |
| `CONTENT_DIR` | Folder of unit YAML files (default `content/`). |

Passwords are stored as salted hashes (Werkzeug). Every form carries a CSRF token.

## Project layout

```
app/
  __init__.py      app factory, session settings, CSRF check, template filters
  auth.py          sign up, sign in, sign out, profile page
  content.py       loads and validates YAML lessons
  quiz.py          grading and unit-quiz assembly (no Flask, easy to test)
  progress.py      SQLite: profiles, attempts, unlocks, streaks, stats
  routes.py        pages: home, lesson cards, quizzes
  templates/       Jinja templates
  static/          CSS, SVG diagrams, app icon and manifest
content/
  opening.yaml     Unit 1: The Opening
  hinges.yaml      Unit 2: Hanging the Door
tests/             unit and route tests
```

## Adding a unit

Lessons are plain YAML, so you can add content without touching Python.

1. Copy `content/opening.yaml` to a new file, e.g. `content/locks.yaml`.
2. Give it a unique `id` and an `order` number; units appear and unlock in `order`.
3. Write the lessons. Each lesson has `cards` (title, body, optional `image` + `alt`) and a `quiz`.
4. Each question needs a unique `id`, a `prompt`, 2+ `options`, the `answer` (0-based index) and an `explain` line.
5. Add scenario questions under `segment_quiz` and set `segment_quiz_size`.
6. Put images in `app/static/img/` and run the tests: they check every image exists and has alt text, every answer index is valid and no question id repeats.

Use `**double asterisks**` in card text for bold key terms.

## Content accuracy and images

Lesson text is written in our own words and checked against standards and
manufacturer references (the sources for each unit are listed at the top of its
YAML file). Before publishing, have an experienced hardware consultant (for
example, a DHI-certified AHC) review each unit.

The diagrams in `app/static/img/` are original drawings made for this project.
Manufacturer photos and catalog drawings are copyrighted: get written permission
before adding any to the app.

## Ideas for next steps

- Units 3–18 from the course outline: locks, exit devices, closers, electrified hardware, codes, healthcare and behavioral health
- Password reset by email (needs an email service)
- Spaced repetition: resurface questions a learner missed in later sessions
- Image-identification questions ("which closer arm is this?")
- Deploy to a host (for example Render or Fly.io) with a persistent disk for the database
