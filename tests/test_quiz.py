import random
import unittest
from pathlib import Path

from app.content import load_segments
from app.quiz import build_segment_quiz, grade, parse_answers

CONTENT = Path(__file__).resolve().parent.parent / "content"


class QuizTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seg = load_segments(CONTENT)["hinges"]
        cls.questions = cls.seg.lessons[0].quiz

    def test_all_correct_passes(self):
        answers = {q.id: q.answer for q in self.questions}
        result = grade(self.questions, answers, 0.7)
        self.assertEqual(result.correct, len(self.questions))
        self.assertTrue(result.passed)

    def test_pass_mark_boundary(self):
        # 3 of 4 = 75% passes a 70% mark; 2 of 4 = 50% does not.
        qs = self.questions[:4]
        three = {q.id: q.answer for q in qs[:3]}
        two = {q.id: q.answer for q in qs[:2]}
        self.assertTrue(grade(qs, three, 0.7).passed)
        self.assertFalse(grade(qs, two, 0.7).passed)

    def test_bad_form_input_counts_as_no_answer(self):
        form = {self.questions[0].id: "banana", self.questions[1].id: "99"}
        answers = parse_answers(form, self.questions)
        self.assertIsNone(answers[self.questions[0].id])
        result = grade(self.questions, answers, 0.7)
        self.assertEqual(result.feedback[0].chosen_text, "No answer")
        self.assertEqual(result.feedback[1].chosen_text, "No answer")
        self.assertEqual(result.correct, 0)

    def test_segment_quiz_size_and_coverage(self):
        for seed in range(25):
            picked = build_segment_quiz(self.seg, random.Random(seed))
            ids = [q.id for q in picked]
            self.assertEqual(len(picked), self.seg.segment_quiz_size)
            self.assertEqual(len(set(ids)), len(ids), "no repeated questions")
            for scenario in self.seg.segment_quiz:
                self.assertIn(scenario.id, ids, "scenario questions always included")
            for lesson in self.seg.lessons:
                lesson_ids = {q.id for q in lesson.quiz}
                self.assertTrue(lesson_ids & set(ids), f"{lesson.id} is represented")


if __name__ == "__main__":
    unittest.main()
