import os
import tempfile
import unittest
from datetime import date, timedelta

from app import create_app, progress

CSRF = "test-csrf-token"


class AppTestCase(unittest.TestCase):
    """Shared setup: a fresh database and helpers that send the CSRF token."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "test",
            "DATABASE": os.path.join(self.tmp.name, "test.db"),
        })
        self.client = self.new_client()
        self.unit1 = self.app.config["SEGMENTS"]["opening"]
        self.unit2 = self.app.config["SEGMENTS"]["hinges"]

    def tearDown(self):
        self.tmp.cleanup()

    def new_client(self):
        client = self.app.test_client()
        client.get("/")  # creates the guest session
        with client.session_transaction() as sess:
            sess["csrf"] = CSRF
        return client

    def post(self, url, data=None, client=None, **kw):
        data = dict(data or {}, csrf_token=CSRF)
        return (client or self.client).post(url, data=data, **kw)

    @staticmethod
    def answers(questions, correct=True):
        return {q.id: str(q.answer if correct else (q.answer + 1) % len(q.options)) for q in questions}

    def pass_lesson(self, seg, lesson, client=None):
        return self.post(f"/s/{seg.id}/l/{lesson.id}/quiz", self.answers(lesson.quiz), client=client)

    def pass_unit(self, seg, client=None):
        client = client or self.client
        for lesson in seg.lessons:
            self.pass_lesson(seg, lesson, client)
        client.get(f"/s/{seg.id}/quiz")
        with client.session_transaction() as sess:
            ids = sess[f"segment_quiz:{seg.id}"]
        pool = {q.id: q for q in seg.question_pool}
        return self.post(f"/s/{seg.id}/quiz", self.answers([pool[i] for i in ids]), client=client)


class LessonFlowTests(AppTestCase):
    def test_home_shows_unit_1_first_lesson_as_today(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Today's lesson", r.data)
        self.assertIn(b"Unit 1", r.data)
        self.assertIn(self.unit1.lessons[0].title.encode(), r.data)

    def test_cards_walk_through_to_quiz(self):
        lesson = self.unit1.lessons[0]
        last = self.client.get(f"/s/opening/l/{lesson.id}/{len(lesson.cards)}")
        self.assertIn(b"Take the quiz", last.data)
        self.assertEqual(self.client.get(f"/s/opening/l/{lesson.id}/99").status_code, 404)

    def test_card_text_is_escaped_but_bold_renders(self):
        r = self.client.get(f"/s/opening/l/{self.unit1.lessons[0].id}/1")
        self.assertIn(b"<strong>openings</strong>", r.data)

    def test_later_lessons_and_unit_quiz_start_locked(self):
        self.assertEqual(self.client.get(f"/s/opening/l/{self.unit1.lessons[1].id}/").status_code, 302)
        self.assertEqual(self.client.get("/s/opening/quiz").status_code, 302)

    def test_unit_2_opens_only_after_unit_1_quiz(self):
        first = self.unit2.lessons[0]
        r = self.client.get(f"/s/hinges/l/{first.id}/", follow_redirects=True)
        self.assertIn(b"Pass the Unit 1 quiz to unlock Unit 2", r.data)
        self.assertEqual(self.post(f"/s/hinges/l/{first.id}/quiz", self.answers(first.quiz)).status_code, 302)

        r = self.pass_unit(self.unit1)
        self.assertIn(b"Unit complete", r.data)
        self.assertEqual(self.client.get(f"/s/hinges/l/{first.id}/").status_code, 200)

    def test_failing_does_not_unlock(self):
        lesson = self.unit1.lessons[0]
        r = self.post(f"/s/opening/l/{lesson.id}/quiz", self.answers(lesson.quiz, correct=False))
        self.assertIn(b"You need 70%", r.data)
        self.assertEqual(self.client.get(f"/s/opening/l/{self.unit1.lessons[1].id}/").status_code, 302)

    def test_full_course_flow(self):
        self.pass_unit(self.unit1)
        r = self.pass_unit(self.unit2)
        self.assertIn(b"Unit complete", r.data)
        home = self.client.get("/")
        self.assertIn(b"All caught up", home.data)
        self.assertIn(b'</span> 1<span class="streak-word">-day streak', home.data)

    def test_unit_quiz_post_without_serving_restarts(self):
        for lesson in self.unit1.lessons:
            self.pass_lesson(self.unit1, lesson)
        self.assertEqual(self.post("/s/opening/quiz", {}).status_code, 302)

    def test_unknown_unit_404(self):
        self.assertEqual(self.client.get("/s/nope/quiz").status_code, 404)

    def test_post_without_csrf_token_is_rejected(self):
        lesson = self.unit1.lessons[0]
        r = self.client.post(f"/s/opening/l/{lesson.id}/quiz", data=self.answers(lesson.quiz))
        self.assertEqual(r.status_code, 400)


class ProfileTests(AppTestCase):
    def signup(self, username="jordan", password="hinges-and-hasps", client=None, **extra):
        data = {"username": username, "display_name": "Jordan", "password": password, **extra}
        return self.post("/signup", data, client=client)

    def test_signup_keeps_guest_progress(self):
        self.pass_lesson(self.unit1, self.unit1.lessons[0])
        r = self.signup(role="Architect or designer")
        self.assertEqual(r.status_code, 302)
        profile = self.client.get("/profile")
        self.assertEqual(profile.status_code, 200)
        self.assertIn(b"Jordan", profile.data)
        self.assertIn(b"Architect or designer", profile.data)
        self.assertIn(b"1<small>/", profile.data)  # one lesson done

    def test_signup_validation(self):
        r = self.signup(username="j", password="short")
        self.assertEqual(r.status_code, 400)
        self.assertIn(b"Usernames are 3", r.data)
        self.assertIn(b"at least 8 characters", r.data)

    def test_duplicate_username_is_case_insensitive(self):
        self.signup()
        other = self.new_client()
        r = self.signup(username="JORDAN", client=other)
        self.assertEqual(r.status_code, 400)
        self.assertIn(b"That username is taken", r.data)

    def test_progress_follows_the_profile_to_another_device(self):
        self.signup()
        self.pass_lesson(self.unit1, self.unit1.lessons[0])
        self.post("/logout")
        self.assertEqual(self.client.get("/profile").status_code, 302)  # signed out

        phone = self.new_client()
        r = self.post("/login", {"username": "jordan", "password": "hinges-and-hasps"}, client=phone)
        self.assertEqual(r.status_code, 302)
        home = phone.get("/")
        self.assertIn(self.unit1.lessons[1].title.encode(), home.data)
        self.assertIn(b"1 / 5 lessons", home.data)

    def test_login_merges_guest_progress(self):
        self.signup()
        self.post("/logout")
        guest = self.new_client()
        self.pass_lesson(self.unit1, self.unit1.lessons[0], client=guest)
        r = self.post("/login", {"username": "jordan", "password": "hinges-and-hasps"},
                      client=guest, follow_redirects=True)
        self.assertIn(b"finished as a guest were added", r.data)
        self.assertIn(b"1 / 5 lessons", guest.get("/").data)

    def test_wrong_password(self):
        self.signup()
        self.post("/logout")
        r = self.post("/login", {"username": "jordan", "password": "wrong-password"})
        self.assertEqual(r.status_code, 401)
        self.assertIn(b"don&#39;t match", r.data)

    def test_login_ignores_offsite_next(self):
        self.signup()
        self.post("/logout")
        r = self.post("/login?next=https://example.com/", {"username": "jordan", "password": "hinges-and-hasps"})
        self.assertEqual(r.headers["Location"], "/")

    def test_edit_profile_and_change_password(self):
        self.signup()
        r = self.post("/profile", {"action": "profile", "display_name": "Jordan R.", "role": "Student"},
                      follow_redirects=True)
        self.assertIn(b"Profile saved", r.data)
        self.assertIn(b"Jordan R.", r.data)
        bad = self.post("/profile", {"action": "profile", "display_name": "J", "role": "Wizard"})
        self.assertEqual(bad.status_code, 400)

        r = self.post("/profile", {"action": "password", "current_password": "hinges-and-hasps",
                                   "new_password": "closers-and-coordinators"}, follow_redirects=True)
        self.assertIn(b"Password changed", r.data)
        self.post("/logout")
        r = self.post("/login", {"username": "jordan", "password": "closers-and-coordinators"})
        self.assertEqual(r.status_code, 302)

    def test_logout_needs_post(self):
        self.signup()
        self.assertEqual(self.client.get("/logout").status_code, 405)

    def test_home_nudges_guests_to_save(self):
        self.assertIn(b"Create profile", self.client.get("/").data)
        self.signup()
        self.assertNotIn(b"Create profile", self.client.get("/").data)


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
