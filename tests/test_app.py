import os
import tempfile
import unittest
from datetime import date, timedelta

from app import create_app, progress


class AppTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "test",
            "DATABASE": os.path.join(self.tmp.name, "test.db"),
        })
        self.client = self.app.test_client()
        self.seg = self.app.config["SEGMENTS"]["hinges"]

    def tearDown(self):
        self.tmp.cleanup()

    def answers(self, questions, correct=True):
        return {q.id: str(q.answer if correct else (q.answer + 1) % len(q.options)) for q in questions}

    def pass_lesson(self, lesson):
        url = f"/s/hinges/l/{lesson.id}/quiz"
        return self.client.post(url, data=self.answers(lesson.quiz))

    def test_home_shows_first_lesson_as_today(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Today's lesson", r.data)
        self.assertIn(self.seg.lessons[0].title.encode(), r.data)

    def test_cards_walk_through_to_quiz(self):
        lesson = self.seg.lessons[0]
        last = self.client.get(f"/s/hinges/l/{lesson.id}/{len(lesson.cards)}")
        self.assertIn(b"Take the quiz", last.data)
        self.assertEqual(self.client.get(f"/s/hinges/l/{lesson.id}/99").status_code, 404)

    def test_card_text_is_escaped_but_bold_renders(self):
        r = self.client.get(f"/s/hinges/l/{self.seg.lessons[0].id}/1")
        self.assertIn(b"<strong>leaves</strong>", r.data)

    def test_later_lessons_and_segment_quiz_start_locked(self):
        r = self.client.get(f"/s/hinges/l/{self.seg.lessons[1].id}/")
        self.assertEqual(r.status_code, 302)
        r = self.client.get("/s/hinges/quiz")
        self.assertEqual(r.status_code, 302)

    def test_failing_does_not_unlock(self):
        lesson = self.seg.lessons[0]
        r = self.client.post(f"/s/hinges/l/{lesson.id}/quiz", data=self.answers(lesson.quiz, correct=False))
        self.assertIn(b"You need 70%", r.data)
        self.assertEqual(self.client.get(f"/s/hinges/l/{self.seg.lessons[1].id}/").status_code, 302)

    def test_full_segment_flow(self):
        for lesson in self.seg.lessons:
            r = self.pass_lesson(lesson)
            self.assertIn(b"Lesson complete", r.data)

        # Segment quiz is now open; answer exactly the questions it served.
        r = self.client.get("/s/hinges/quiz")
        self.assertEqual(r.status_code, 200)
        with self.client.session_transaction() as sess:
            ids = sess["segment_quiz:hinges"]
        pool = {q.id: q for q in self.seg.question_pool}
        served = [pool[i] for i in ids]
        r = self.client.post("/s/hinges/quiz", data=self.answers(served))
        self.assertIn(b"Segment complete", r.data)

        home = self.client.get("/")
        self.assertIn(b"All caught up", home.data)
        self.assertIn(b"1-day streak", home.data)

    def test_segment_quiz_post_without_serving_restarts(self):
        for lesson in self.seg.lessons:
            self.pass_lesson(lesson)
        r = self.client.post("/s/hinges/quiz", data={})
        self.assertEqual(r.status_code, 302)

    def test_unknown_segment_404(self):
        self.assertEqual(self.client.get("/s/nope/quiz").status_code, 404)


class StreakTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app({"TESTING": True, "DATABASE": os.path.join(self.tmp.name, "s.db")})

    def tearDown(self):
        self.tmp.cleanup()

    def test_streak_counts_consecutive_days(self):
        today = date(2026, 10, 15)
        with self.app.app_context():
            for back in (0, 1, 2, 4):  # gap on day 3 breaks the run
                progress.record_attempt("u", "hinges", "x", 1.0, True, today - timedelta(days=back))
            progress.record_attempt("u", "hinges", "x", 0.2, False, today - timedelta(days=3))
            self.assertEqual(progress.streak("u", today), 3)
            # Not yet practised today: yesterday's run still counts.
            self.assertEqual(progress.streak("u", today + timedelta(days=1)), 3)
            self.assertEqual(progress.streak("u", today + timedelta(days=2)), 0)


if __name__ == "__main__":
    unittest.main()
