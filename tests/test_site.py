import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("build_site", ROOT / "scripts" / "build_site.py")
build_site = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_site)


class SiteTests(unittest.TestCase):
    """The GitHub Pages page (docs/index.html) must match the lesson content."""

    def test_docs_page_is_up_to_date(self):
        built = build_site.build()
        on_disk = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        self.assertEqual(built, on_disk,
                         "docs/index.html is stale. Run: python scripts/build_site.py")

    def test_page_embeds_every_unit_and_image(self):
        html = build_site.build()
        data = json.loads(re.search(r"const COURSE = (.*?);\n", html).group(1).replace("<\\/", "</"))
        self.assertEqual([u["id"] for u in data], ["opening", "hinges"])
        for unit in data:
            for lesson in unit["lessons"]:
                for card in lesson["cards"]:
                    if card["image"]:
                        self.assertTrue(card["image"].startswith("data:image/svg+xml;base64,"))
        self.assertNotIn("c2pa", html)
        self.assertNotIn("/*__", html)


if __name__ == "__main__":
    unittest.main()
