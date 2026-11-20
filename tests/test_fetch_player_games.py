import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import fetch_player_games as fpg  # noqa: E402


class NewestTests(unittest.TestCase):
    def test_keeps_the_most_recent_games_newest_first(self):
        records = [{"uuid": str(t), "start_time": t} for t in (5, 1, 9, 3, 7)]
        self.assertEqual([r["start_time"] for r in fpg.newest(records, 3)], [9, 7, 5])

    def test_zero_means_no_cap(self):
        records = [{"uuid": str(t), "start_time": t} for t in (2, 1, 3)]
        self.assertEqual([r["start_time"] for r in fpg.newest(records, 0)], [3, 2, 1])



class RefusedTests(unittest.TestCase):
    """Error 540 is the game's "log retrieval limit exceeded", a quota on the account. On 20 Nov
    2026 the fetch account was over it; fetch_many.js retried each game for 75 seconds and the
    onboarding job died at 30 minutes with nothing kept."""

    def row(self, status, error=None):
        return {"uuid": "g", "status": status, **({"error": error} if error else {})}

    def test_a_batch_cut_off_for_time_counts_as_refused(self):
        self.assertTrue(fpg.refused({"a": self.row("written")}, cut=True))

    def test_a_540_means_the_limit_is_in_force(self):
        self.assertTrue(fpg.refused({"a": self.row("error", '{"code":540}')}, cut=False))
        self.assertTrue(fpg.refused({"a": self.row("error", '{"code": 540}')}, cut=False))

    def test_a_540_after_written_games_stops_the_run_too(self):
        # The limit was reached partway: what was written is kept, and nothing more is asked for.
        status = {"a": self.row("written"), "b": self.row("error", '{"code":540}')}
        self.assertTrue(fpg.refused(status, cut=False))

    def test_other_errors_do_not_stop_the_run(self):
        self.assertFalse(fpg.refused({"a": self.row("error", "record not found")}, cut=False))

    def test_a_refused_batch_is_given_up_within_the_time_limit(self):
        self.assertLess(fpg.BATCH_SECONDS, fpg.TIME_LIMIT_MINUTES * 60)

    def test_the_first_request_is_one_game_and_short(self):
        self.assertLess(fpg.PROBE_SECONDS, 60)


LIMIT = '{"code":540}'


class Server:
    """A stand-in for fetch_many.js: each account gives `allowance[label]` logs, then 540s."""

    def __init__(self, allowance, dead=()):
        self.left = dict(allowance)
        self.dead = set(dead)
        self.calls = []

    def fetch(self, ids, out, seconds, env):
        label = env.get("ACCESS_TOKEN", "first")
        self.calls.append((label, len(ids), seconds))
        if label in self.dead:
            return {}, False, "login failed: error 109 for account 123456789"
        status = {}
        for uuid in ids:
            if self.left.get(label, 0) > 0:
                self.left[label] -= 1
                status[uuid] = {"uuid": uuid, "status": "written", "file": f"{out}/{uuid}.json"}
            else:
                status[uuid] = {"uuid": uuid, "status": "error", "error": LIMIT}
                break  # the real script would spend 75 s on each further game
        return status, False, ""


class DownloadTests(unittest.TestCase):
    def run_download(self, server, games=50, accounts=("first", "second", "third")):
        missing = [{"uuid": f"g{i:03d}", "start_time": 1000 - i} for i in range(games)]
        pool = [{"label": str(n + 1), "env": {} if n == 0 else {"ACCESS_TOKEN": name}} for n, name in enumerate(accounts)]
        manifest = {}
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(fpg.fms, "manifest_row", lambda r, account, file: {"uuid": r["uuid"], "start_time": r["start_time"], "file": str(file)}), \
                mock.patch("builtins.print"):
            path = Path(tmp) / "index.json"
            result = fpg.download(missing, Path(tmp), 1, manifest, path, pool, 15, fetch=server.fetch)
            index = json.loads(path.read_text())
        return result, manifest, index

    def test_one_account_under_its_limit_fetches_everything(self):
        (written, errors, stopped, gave), manifest, index = self.run_download(Server({"first": 999}))
        self.assertEqual((written, errors, stopped, gave), (50, 0, "", [50, 0, 0]))
        self.assertEqual(len(index), 50)

    def test_the_next_account_takes_over_when_one_reaches_its_limit(self):
        server = Server({"first": 12, "second": 999})
        (written, errors, stopped, gave), manifest, _ = self.run_download(server)
        self.assertEqual((written, errors, stopped), (50, 0, ""))
        self.assertEqual(gave, [12, 38, 0])
        self.assertEqual(len(manifest), 50)

    def test_an_account_over_its_limit_costs_one_short_request(self):
        server = Server({"first": 0, "second": 999})
        self.run_download(server)
        self.assertEqual(server.calls[0], ("first", 1, fpg.PROBE_SECONDS))
        self.assertEqual(server.calls[1], ("second", 1, fpg.PROBE_SECONDS))
        self.assertEqual([c[0] for c in server.calls].count("first"), 1)

    def test_it_keeps_what_it_has_when_every_account_is_over(self):
        server = Server({"first": 7, "second": 5, "third": 0})
        (written, errors, stopped, gave), manifest, index = self.run_download(server)
        self.assertEqual((written, errors, gave), (12, 0, [7, 5, 0]))
        self.assertIn("every fetch account", stopped)
        self.assertEqual(len(index), 12)
        # Newest first: the twelve kept are the twelve most recent.
        self.assertEqual(sorted(manifest), [f"g{i:03d}" for i in range(12)])

    def test_an_account_that_cannot_log_in_is_skipped(self):
        server = Server({"second": 999}, dead={"first"})
        (written, errors, stopped, gave), _, _ = self.run_download(server)
        self.assertEqual((written, errors, stopped, gave), (50, 0, "", [0, 50, 0]))

    def test_a_game_that_fails_for_another_reason_is_not_retried(self):
        class Flaky(Server):
            def fetch(self, ids, out, seconds, env):
                status, cut, failure = super().fetch(ids, out, seconds, env)
                if "g003" in status:
                    status["g003"] = {"uuid": "g003", "status": "error", "error": "record not found"}
                return status, cut, failure
        (written, errors, stopped, gave), manifest, _ = self.run_download(Flaky({"first": 999}), games=10)
        self.assertEqual((written, errors, stopped), (9, 1, ""))
        self.assertNotIn("g003", manifest)


class AccountsTests(unittest.TestCase):
    def test_numbered_slots_need_both_a_token_and_a_device_key(self):
        env = {"MJS_ACCESS_TOKEN_2": "t2", "MJS_RANDOM_KEY_2": "k2", "MJS_ACCESS_TOKEN_3": "t3",
               "MJS_ACCESS_TOKEN_5": "t5", "MJS_RANDOM_KEY_5": "k5"}
        with mock.patch.dict(os.environ, env, clear=True):
            pool = fpg.accounts()
        self.assertEqual([a["label"] for a in pool], ["1", "2", "5"])
        self.assertEqual(pool[0]["env"], {})
        self.assertEqual(pool[1]["env"], {"ACCESS_TOKEN": "t2", "MJS_RANDOM_KEY": "k2"})

    def test_errors_for_the_public_log_carry_no_ids_or_tokens(self):
        text = fpg.public("login failed for account 123456789 token eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9 game 261118-59a96483-0fdb-406a-ba39-7f7958f370f9")
        self.assertNotIn("123456789", text)
        self.assertNotIn("eyJhbGci", text)
        self.assertNotIn("59a96483", text)


if __name__ == "__main__":
    unittest.main()
