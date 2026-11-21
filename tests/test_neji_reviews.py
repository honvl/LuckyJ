"""Wind-Up Bird reviews: the fetch-and-cache script and the placement comparison built on its cache.

Nothing here touches the network: the API is replaced by a fake opener.
"""

import io
import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import fetch_neji_reviews as fetch  # noqa: E402
import neji_placement_check as check  # noqa: E402

TOKEN = "tok-not-a-real-one"


def review(seat=0, score=90.0, matched=180, graded=200, penalty=400.0, decisions=((0.5, 10.0), (0.0, 30.0))):
    grades = [{"graded": 0, "matched": 0, "score": 0, "penalty": 0, "letter": "—"} for _ in range(4)]
    grades[seat] = {"graded": graded, "matched": matched, "score": score, "penalty": penalty, "letter": "S"}
    hand = [None] + [{"actor": seat, "review": {"weight": w, "penalty": sev * w, "ev": {"loss": sev * 100}}}
                     for sev, w in decisions] + [{"actor": (seat + 1) % 4, "review": {"weight": 9.0, "penalty": 9.0}}]
    return {"model": "nejimakidori", "seat": seat, "rounds": [{}], "annotations": [hand], "grades": grades}


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeApi:
    """Answers each request with the next canned reply: a body string, or an HTTP status to raise."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []

    def __call__(self, req, timeout=None):
        self.requests.append(req)
        reply = self.replies.pop(0)
        if isinstance(reply, int):
            raise urllib.error.HTTPError(req.full_url, reply, "refused", {}, io.BytesIO(b"no"))
        return Response(reply.encode())


GAMES = [{"id": f"2611{d:02d}-aaaa", "date": f"2026-11-{d:02d} 10:00", "room": "Jade South", "placement": 1 + d % 4,
          "points": 0, "seat": d % 4} for d in range(20, 10, -1)]


class TokenTest(unittest.TestCase):
    def test_environment_wins_over_the_file(self):
        with tempfile.TemporaryDirectory() as d:
            env_file = Path(d) / ".env.local"
            env_file.write_text('OTHER=1\nNEJI_REPLAY_TOKEN="from-file"\n')
            self.assertEqual(fetch.read_tokens({"NEJI_REPLAY_TOKEN": " from-env "}, env_file), ["from-env"])
            self.assertEqual(fetch.read_tokens({}, env_file), ["from-file"])
            self.assertEqual(fetch.read_tokens({}, Path(d) / "missing"), [])
            self.assertEqual(fetch.read_tokens({"NEJI_REPLAY_TOKEN": "a, b c"}, env_file), ["a", "b", "c"])

    def test_the_cache_folder_is_gitignored(self):
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("data/neji_reviews/", ignore)
        self.assertIn(".env*", ignore)


class PickTest(unittest.TestCase):
    def test_newest_first_and_cached_games_are_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            cache = Path(d)
            fetch.store(review(GAMES[0]["seat"]), GAMES[0], cache)
            todo = fetch.pick(GAMES, cache, 3)
            self.assertEqual([g["id"] for g in todo], [g["id"] for g in GAMES[1:4]])
            self.assertEqual(fetch.pick(GAMES, cache, 2, "oldest")[0]["id"], GAMES[-1]["id"])

    def test_spread_covers_the_whole_span(self):
        with tempfile.TemporaryDirectory() as d:
            todo = fetch.pick(GAMES, Path(d), 5, "spread")
            self.assertEqual(len(todo), 5)
            dates = [g["date"] for g in todo]
            self.assertEqual(dates, sorted(dates, reverse=True))
            self.assertLess(dates[-1], GAMES[6]["date"])  # reaches the older half

    def test_named_and_rated_games(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual([g["id"] for g in fetch.pick(GAMES, Path(d), 24, ids=[GAMES[4]["id"]])], [GAMES[4]["id"]])
            only = {GAMES[2]["id"], GAMES[7]["id"]}
            self.assertEqual({g["id"] for g in fetch.pick(GAMES, Path(d), 24, only=only)}, only)
            with self.assertRaises(SystemExit):
                fetch.pick(GAMES, Path(d), 24, ids=["nope"])


class ParseTest(unittest.TestCase):
    def test_one_document_or_the_line_stream(self):
        r = review()
        self.assertEqual(fetch.parse_review(json.dumps(r))["grades"][0]["score"], 90.0)
        stream = "\n".join([json.dumps({"type": "progress", "message": "1 / 2"}),
                            json.dumps({"type": "complete", "game": r})]) + "\n"
        self.assertEqual(fetch.parse_review(stream)["model"], "nejimakidori")

    def test_a_body_without_a_review_is_refused(self):
        with self.assertRaises(ValueError):
            fetch.parse_review(json.dumps({"error": "busy"}))
        with self.assertRaises(ValueError):
            fetch.parse_review(json.dumps({"type": "progress"}) + "\n" + json.dumps({"type": "progress"}))


class FetchTest(unittest.TestCase):
    def run_fetch(self, replies, todo, tokens=TOKEN):
        self.cache_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.cache_dir.cleanup)
        api, lines = FakeApi(replies), []
        result = fetch.fetch(todo, tokens, Path(self.cache_dir.name), opener=api, out=lines.append)
        return result, api, lines, Path(self.cache_dir.name)

    def test_request_carries_the_bare_game_id_and_the_token_only_in_the_header(self):
        game = GAMES[0]
        result, api, lines, cache = self.run_fetch([json.dumps(review(game["seat"]))], [game])
        req = api.requests[0]
        self.assertEqual(req.full_url, fetch.API)
        self.assertEqual(req.get_header("Authorization"), f"Bearer {TOKEN}")
        body = json.loads(req.data)
        self.assertEqual(body, {"url": f"https://mahjongsoul.game.yo-star.com/?paipu={game['id']}", "seat": game["seat"]})
        self.assertNotIn("_a", body["url"].split("paipu=")[1])  # no account suffix
        self.assertEqual(result["fetched"], [game["id"]])
        self.assertFalse(any(TOKEN in line for line in lines))

    def test_stored_review_keeps_the_fetch_time_and_reads_back(self):
        game = GAMES[1]
        _, _, _, cache = self.run_fetch([json.dumps(review(game["seat"], score=77.5))], [game])
        doc = fetch.load(fetch.cache_path(game["id"], game["seat"], cache))
        self.assertEqual(doc["game_id"], game["id"])
        self.assertEqual(doc["placement"], game["placement"])
        self.assertRegex(doc["fetched_at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertEqual(doc["review"]["grades"][game["seat"]]["score"], 77.5)
        self.assertEqual(fetch.cached(cache), [fetch.cache_path(game["id"], game["seat"], cache)])

    def test_a_used_up_or_expired_token_stops_the_run(self):
        for status, word in ((429, "used up"), (401, "expired")):
            todo = GAMES[:3]
            result, api, _, cache = self.run_fetch([json.dumps(review(todo[0]["seat"])), status], todo)
            self.assertEqual(result["fetched"], [todo[0]["id"]])
            self.assertIn(word, result["stopped"])
            self.assertEqual(len(api.requests), 2)  # the third game is not tried
            self.assertNotIn(TOKEN, result["stopped"])

    def test_a_spent_token_hands_the_same_game_to_the_next_one(self):
        todo = GAMES[:3]
        replies = [json.dumps(review(todo[0]["seat"])), 429, json.dumps(review(todo[1]["seat"])),
                   json.dumps(review(todo[2]["seat"]))]
        result, api, lines, cache = self.run_fetch(replies, todo, ["first", "second"])
        self.assertEqual(result["fetched"], [g["id"] for g in todo])
        self.assertIsNone(result["stopped"])
        used = [r.get_header("Authorization") for r in api.requests]
        self.assertEqual(used, ["Bearer first", "Bearer first", "Bearer second", "Bearer second"])
        self.assertEqual(json.loads(api.requests[1].data), json.loads(api.requests[2].data))  # the same game again
        self.assertFalse(any("first" in line or "second" in line for line in lines))

    def test_the_run_stops_when_every_token_is_spent(self):
        todo = GAMES[:3]
        result, api, _, cache = self.run_fetch([429, 401], todo, ["first", "second"])
        self.assertEqual(result["fetched"], [])
        self.assertIn("expired", result["stopped"])
        self.assertEqual(len(api.requests), 2)

    def test_one_failed_game_does_not_end_the_run(self):
        todo = GAMES[:3]
        replies = [json.dumps(review(todo[0]["seat"])), 500, json.dumps(review(todo[2]["seat"]))]
        result, _, _, cache = self.run_fetch(replies, todo)
        self.assertEqual(result["fetched"], [todo[0]["id"], todo[2]["id"]])
        self.assertEqual([f["id"] for f in result["failed"]], [todo[1]["id"]])
        self.assertIsNone(result["stopped"])
        self.assertEqual(len(fetch.cached(cache)), 2)


class StatsTest(unittest.TestCase):
    def test_spearman_handles_ties_and_direction(self):
        self.assertAlmostEqual(check.spearman([1, 2, 3, 4], [1, 2, 3, 4]), 1.0)
        self.assertAlmostEqual(check.spearman([1, 2, 3, 4], [4, 3, 2, 1]), -1.0)
        self.assertAlmostEqual(check.spearman([1, 1, 2, 2], [1, 2, 3, 4]), 0.8944, places=3)
        self.assertTrue(np.isnan(check.spearman([1, 1, 1], [1, 2, 3])))

    def test_review_statistics_separate_importance_from_severity(self):
        # one half-wrong play on a light decision, one right play on a heavy one
        doc = {"seat": 2, "review": review(2, score=87.5, matched=1, graded=2, penalty=5.0,
                                           decisions=((0.5, 10.0), (0.0, 30.0)))}
        s = check.review_stats(doc)
        self.assertEqual(s["score (severity x importance)"], 87.5)
        self.assertEqual(s["match rate"], 0.5)
        self.assertAlmostEqual(s["flat severity (no importance)"], -0.25)  # the mean of 0.5 and 0, unweighted
        self.assertAlmostEqual(s["_importance"], 40.0)                     # the other seat's decision is left out
        self.assertAlmostEqual(s["total EV loss"], -50.0)
        self.assertIsNone(check.review_stats({"seat": 1, "review": review(2)}))  # that seat was not graded

    def test_compare_finds_the_grade_that_tracks_the_place(self):
        rng = np.random.default_rng(3)
        games = []
        for i in range(160):
            place = int(rng.integers(1, 5))
            good = -place + rng.normal(0, 1.0)   # tracks the place well
            weak = -place + rng.normal(0, 6.0)   # tracks it weakly
            games.append({"id": str(i), "seat": 0, "place": place,
                          "Wind-Up Bird": {"score (severity x importance)": good, "match rate": weak,
                                           "flat severity (no importance)": weak, "_importance": 1.0},
                          "Mortal-S42": {"mean Q loss": weak}, "Mortal policy": {"mean ln p": weak}})
        out = check.compare(games, boot=300)
        self.assertEqual(out["n"], 160)
        head = out["stats"]["Wind-Up Bird: score (severity x importance)"]
        self.assertLess(head["r"], -0.6)
        self.assertLess(head["hi"], out["stats"][out["best_mortal"]]["lo"])
        self.assertNotIn("Wind-Up Bird: _importance", out["stats"])
        diff = next(v for k, v in out["differences"].items() if out["best_mortal"] in k)
        self.assertLess(diff["hi"], 0)  # the interval of the difference excludes zero
        # the good grade still tracks the place once the weak one is known; the weak one adds nothing back
        adds, adds_back = out["partial"].values()
        self.assertLess(adds["hi"], -0.5)
        self.assertGreater(adds_back["hi"], 0)

    def test_partial_removes_a_shared_cause(self):
        rng = np.random.default_rng(1)
        z = rng.normal(size=400)
        x, y = z + rng.normal(0, 0.5, 400), z + rng.normal(0, 0.5, 400)
        self.assertGreater(check.spearman(x, y), 0.6)
        self.assertLess(abs(check.partial(x, y, z)), 0.12)

    def test_compare_declines_a_handful_of_games(self):
        games = [{"id": "x", "seat": 0, "place": 1, "Wind-Up Bird": {"score (severity x importance)": 1.0}}]
        out = check.compare(games)
        self.assertEqual((out["reviewed"], out["n"]), (1, 0))
        self.assertIn("too few", out["note"])

    def test_a_smaller_gap_needs_more_games(self):
        far = check.games_needed(-0.40, -0.15, 0.5, sims=800)
        near = check.games_needed(-0.25, -0.15, 0.5, sims=800)
        self.assertLess(far, near)
        self.assertLess(check.games_needed(-0.40, -0.15, 0.7, sims=800), far)  # closer cousins are easier to split
        self.assertGreater(far, 24)  # one token's worth cannot settle it
        with self.assertRaises(ValueError):
            check.games_needed(-0.9, 0.9, 0.9, sims=10)


if __name__ == "__main__":
    unittest.main()
