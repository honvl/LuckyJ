"""The book's pages hold together: every contents list reaches every chapter, and every link lands."""

import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
PAGES = ("index.html", "points.html", "ja.html", "honver.html")
# Anchors that app.js creates when it renders the replays, so they are not in the static page.
RENDERED_ANCHOR = re.compile(r"^point-\d{2}-example-\d{2}$")


class Page(HTMLParser):
    """The ids, links and elements of one page, each element with the elements that contain it."""

    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}

    def __init__(self, name):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.ids = []
        self.links = []
        self.elements = []
        self.feed((SITE / name).read_text(encoding="utf-8"))

    def handle_starttag(self, tag, attrs):
        self._element(tag, dict(attrs))
        if tag not in self.VOID:
            self.stack.append((tag, dict(attrs)))

    def handle_startendtag(self, tag, attrs):
        self._element(tag, dict(attrs))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def _element(self, tag, attrs):
        ancestors = list(self.stack)
        if attrs.get("id"):
            self.ids.append(attrs["id"])
        if tag == "a" and attrs.get("href"):
            self.links.append((attrs["href"], ancestors))
        self.elements.append((tag, attrs, ancestors))

    def find(self, tag, cls=None, id=None):
        return [
            (attrs, ancestors)
            for t, attrs, ancestors in self.elements
            if t == tag
            and (cls is None or cls in attrs.get("class", "").split())
            and (id is None or attrs.get("id") == id)
        ]

    def chapter_ids(self):
        return [attrs["id"] for attrs, _ in self.find("section", cls="point")]

    def links_inside(self, tag, id):
        return [href for href, ancestors in self.links if any(t == tag and a.get("id") == id for t, a in ancestors)]

    def chapters_containing(self, tag, cls):
        found = []
        for _, ancestors in self.find(tag, cls=cls):
            owner = [a.get("id") for t, a in ancestors if t == "section" and "point" in a.get("class", "").split()]
            if owner:
                found.append(owner[-1])
        return found


def page(name, cache={}):
    if name not in cache:
        cache[name] = Page(name)
    return cache[name]


class ContentsTests(unittest.TestCase):
    def test_home_contents_reach_every_point(self):
        points = page("points.html").chapter_ids()
        self.assertEqual(len(points), 16)
        listed = [href.split("#", 1)[1] for href in page("index.html").links_inside("nav", "contents")
                  if href.startswith("points.html#point-")]
        self.assertEqual(listed, points)

    def test_japanese_contents_reach_every_point(self):
        points = page("ja.html").chapter_ids()
        self.assertEqual(points, page("points.html").chapter_ids())
        listed = [href[1:] for href in page("ja.html").links_inside("nav", "contents") if href.startswith("#point-")]
        self.assertEqual(listed, points)

    def test_guide_chapter_list_reaches_every_chapter_in_order(self):
        guide = page("honver.html")
        listed = [href[1:] for href in guide.links_inside("nav", "chapters")]
        self.assertEqual(listed, guide.chapter_ids())

    def test_newest_guide_notice_is_marked(self):
        guide = page("honver.html")
        items = [attrs for attrs, ancestors in guide.find("li")
                 if any(t == "aside" and a.get("id") == "whats-new" for t, a in ancestors)]
        self.assertTrue(items)
        self.assertIn("is-latest", items[0].get("class", "").split())
        self.assertEqual(sum("is-latest" in item.get("class", "").split() for item in items), 1)


class ChapterTests(unittest.TestCase):
    def test_every_chapter_has_a_kicker_and_a_next_link(self):
        for name in ("points.html", "ja.html", "honver.html"):
            with self.subTest(page=name):
                book = page(name)
                chapters = book.chapter_ids()
                self.assertEqual(book.chapters_containing("p", "chapter-kicker"), chapters)
                self.assertEqual(book.chapters_containing("nav", "chapter-next"), chapters)

    def test_next_links_follow_the_chapter_order(self):
        for name in ("points.html", "ja.html", "honver.html"):
            with self.subTest(page=name):
                book = page(name)
                chapters = book.chapter_ids()
                targets = []
                for href, ancestors in book.links:
                    if any(t == "nav" and "chapter-next" in a.get("class", "").split() for t, a in ancestors):
                        targets.append(href[1:])
                self.assertEqual(len(targets), len(chapters))
                order = book.ids
                for chapter, target in zip(chapters, targets):
                    self.assertIn(target, order, chapter)
                    self.assertGreater(order.index(target), order.index(chapter), chapter)
                # a next link skips at most a divider: it never jumps past the following chapter
                for chapter, following, target in zip(chapters, chapters[1:], targets):
                    self.assertLessEqual(order.index(target), order.index(following), chapter)


class LinkTests(unittest.TestCase):
    def test_ids_are_unique(self):
        for name in PAGES:
            with self.subTest(page=name):
                ids = page(name).ids
                self.assertEqual(sorted(i for i in set(ids) if ids.count(i) > 1), [])

    def test_every_link_within_the_site_lands(self):
        for name in PAGES:
            for href, _ in page(name).links:
                match = re.match(r"^(?:(index|points|ja|honver)\.html)?#(.+)$", href)
                if not match:
                    continue
                target_page = f"{match.group(1)}.html" if match.group(1) else name
                anchor = match.group(2)
                if RENDERED_ANCHOR.match(anchor):
                    continue
                with self.subTest(page=name, href=href):
                    self.assertIn(anchor, page(target_page).ids)


if __name__ == "__main__":
    unittest.main()
