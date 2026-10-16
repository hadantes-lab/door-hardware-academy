import copy
import unittest
from pathlib import Path

import yaml

from app.content import ContentError, load_segments, parse_segment

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
STATIC = ROOT / "app" / "static"


class ShippedContentTests(unittest.TestCase):
    """Every content file in the repo must load cleanly and reference real images."""

    @classmethod
    def setUpClass(cls):
        cls.segments = load_segments(CONTENT)

    def test_hinges_segment_loads(self):
        seg = self.segments["hinges"]
        self.assertEqual(len(seg.lessons), 3)
        for lesson in seg.lessons:
            self.assertGreaterEqual(len(lesson.cards), 3, lesson.id)
            self.assertGreaterEqual(len(lesson.quiz), 3, lesson.id)

    def test_images_exist_and_have_alt_text(self):
        for seg in self.segments.values():
            for lesson in seg.lessons:
                for card in lesson.cards:
                    if card.image:
                        self.assertTrue((STATIC / card.image).is_file(), card.image)
                        self.assertTrue(card.alt.strip(), f"{card.image} needs alt text")

    def test_segment_quiz_can_be_filled(self):
        for seg in self.segments.values():
            self.assertLessEqual(seg.segment_quiz_size, len(seg.question_pool))


class ValidationTests(unittest.TestCase):
    def setUp(self):
        with (CONTENT / "hinges.yaml").open(encoding="utf-8") as fh:
            self.data = yaml.safe_load(fh)

    def broken(self, mutate):
        data = copy.deepcopy(self.data)
        mutate(data)
        with self.assertRaises(ContentError):
            parse_segment(data, "test.yaml")

    def test_answer_index_out_of_range(self):
        self.broken(lambda d: d["lessons"][0]["quiz"][0].update(answer=9))

    def test_duplicate_question_ids(self):
        self.broken(lambda d: d["lessons"][1]["quiz"][0].update(id=d["lessons"][0]["quiz"][0]["id"]))

    def test_missing_card_body(self):
        self.broken(lambda d: d["lessons"][0]["cards"][0].pop("body"))

    def test_quiz_size_larger_than_pool(self):
        self.broken(lambda d: d.update(segment_quiz_size=500))

    def test_answer_zero_is_valid(self):
        seg = parse_segment(copy.deepcopy(self.data), "test.yaml")
        self.assertEqual(seg.lessons[0].quiz[0].answer, 0)


if __name__ == "__main__":
    unittest.main()
