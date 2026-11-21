"""Build the GitHub Pages site: one self-contained docs/index.html.

The Flask app needs a server; GitHub Pages only serves static files. This script
turns the same lesson content (content/*.yaml), diagrams (app/static/img) and
stylesheet (app/static/style.css) into a single page that runs entirely in the
browser, with progress saved in the browser's local storage.

    python scripts/build_site.py           # write docs/index.html
    python scripts/build_site.py --check   # exit 1 if docs/index.html is out of date

Run it after any change to content, diagrams or style.css, and commit docs/.
"""
from __future__ import annotations

import base64
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.content import load_segments  # noqa: E402  (validates every unit first)

CONTENT = ROOT / "content"
STATIC = ROOT / "app" / "static"
TEMPLATE = ROOT / "site" / "template.html"
OUT = ROOT / "docs" / "index.html"


def svg_data_uri(path: Path) -> str:
    svg = path.read_text(encoding="utf-8")
    # Drop embedded provenance metadata: it is large and not needed to draw the image.
    svg = re.sub(r"<metadata>.*?</metadata>", "", svg, flags=re.S)
    svg = re.sub(r'\s+xmlns:c2pa="[^"]*"', "", svg)
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


def course_data() -> list[dict]:
    ordered = load_segments(CONTENT)  # raises ContentError on bad content, sorted by `order`
    raw = {}
    for path in CONTENT.glob("*.yaml"):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        raw[data["id"]] = data
    course = []
    for seg_id, seg in ordered.items():
        data = raw[seg_id]
        course.append({
            "id": seg.id,
            "title": seg.title,
            "subtitle": seg.subtitle,
            "pass_mark": seg.pass_mark,
            "segment_quiz_size": seg.segment_quiz_size,
            "lessons": [{
                "id": lesson.id,
                "title": lesson.title,
                "minutes": lesson.minutes,
                "cards": [{
                    "title": c.title,
                    "body": c.body,
                    "image": svg_data_uri(STATIC / c.image) if c.image else None,
                    "alt": c.alt,
                } for c in lesson.cards],
                "quiz": [q_dict(q) for q in lesson.quiz],
            } for lesson in seg.lessons],
            "segment_quiz": [q_dict(q) for q in seg.segment_quiz],
        })
        assert data["id"] == seg.id
    return course


def q_dict(q) -> dict:
    return {"id": q.id, "prompt": q.prompt, "options": list(q.options), "answer": q.answer,
            "explain": q.explain}


def build() -> str:
    data = json.dumps(course_data(), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8")
    html = html.replace("/*__CSS__*/", (STATIC / "style.css").read_text(encoding="utf-8"))
    html = html.replace("/*__ICON__*/", svg_data_uri(STATIC / "icon.svg"))
    html = html.replace("/*__DATA__*/", data)
    return html


def main() -> int:
    html = build()
    if "--check" in sys.argv:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != html:
            print("docs/index.html is out of date. Run: python scripts/build_site.py")
            return 1
        print("docs/index.html is up to date.")
        return 0
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    (OUT.parent / ".nojekyll").write_text("", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)} ({len(html.encode('utf-8')) // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
