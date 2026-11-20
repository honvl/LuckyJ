import sys
import unittest
from pathlib import Path

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
    """The record server answered 540 to every request on 20 Nov 2026; fetch_many.js retried each
    game for 75 seconds and the onboarding job died at 30 minutes with nothing kept."""

    def row(self, status, error=None):
        return {"uuid": "g", "status": status, **({"error": error} if error else {})}

    def test_a_batch_cut_off_for_time_counts_as_refused(self):
        self.assertTrue(fpg.refused({"a": self.row("written")}, cut=True))

    def test_only_540s_and_nothing_written_is_refused(self):
        self.assertTrue(fpg.refused({"a": self.row("error", '{"code":540}')}, cut=False))
        self.assertTrue(fpg.refused({"a": self.row("error", '{"code": 540}')}, cut=False))

    def test_a_540_among_written_games_is_a_blip(self):
        status = {"a": self.row("written"), "b": self.row("error", '{"code":540}')}
        self.assertFalse(fpg.refused(status, cut=False))

    def test_other_errors_do_not_stop_the_run(self):
        self.assertFalse(fpg.refused({"a": self.row("error", "record not found")}, cut=False))

    def test_a_refused_batch_is_given_up_within_the_time_limit(self):
        self.assertLess(fpg.BATCH_SECONDS, fpg.TIME_LIMIT_MINUTES * 60)


if __name__ == "__main__":
    unittest.main()
