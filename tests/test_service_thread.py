"""Checks on the player-thread service: the agent prompt, the sandbox setup and the client agree."""

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "service"
sys.path.insert(0, str(SERVICE))

SYSTEM = (SERVICE / "agent/system.md").read_text(encoding="utf-8")
SETUP = (SERVICE / "sandbox/setup.sh").read_text(encoding="utf-8")
CLIENT = (SERVICE / "thread.py").read_text(encoding="utf-8")


class ServiceThreadTest(unittest.TestCase):
    def test_prompt_follows_the_voice_rules(self):
        self.assertNotIn("—", SYSTEM, "no em-dashes in the agent prompt")

    def test_setup_reads_every_mount_the_client_creates(self):
        mounts = set(re.findall(r'"(/(?:setup\.sh|mortal/[\w.]+|luckyj/[\w.]+|player/[\w.]+))"', CLIENT))
        self.assertEqual(mounts, {"/setup.sh", "/mortal/model.py", "/mortal/mortal.pth",
                                  "/luckyj/luckyj_tenhou.tar.gz", "/player/games.tar.gz"})
        for mount in mounts - {"/setup.sh"}:
            read_as = "/mortal" if mount.startswith("/mortal/") else mount  # linked as a folder
            self.assertIn("$U" + read_as, SETUP, f"setup.sh never reads {mount}")

    def test_setup_pins_the_local_mortal_commit(self):
        local = ROOT / "tmp/mortal/.git"
        if not local.exists():
            self.skipTest("no local Mortal checkout")
        import subprocess
        head = subprocess.run(["git", "-C", str(local.parent), "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
        self.assertIn(f"MORTAL_COMMIT={head}", SETUP)

    def test_web_tools_and_internet_on(self):
        self.assertIn('{"name": "web_fetch", "enabled": True}', CLIENT)
        self.assertIn('{"name": "web_search", "enabled": True}', CLIENT)
        self.assertIn('"networking": {"type": "unrestricted"}', CLIENT)
        self.assertIn('"permission_policy": {"type": "always_allow"}', CLIENT)

    def test_api_key_only_through_the_vault(self):
        import thread
        self.assertEqual(thread.AMAE_SECRET, "AMAE_KOROMO_TOKEN")
        self.assertIn("$AMAE_KOROMO_TOKEN", SYSTEM)
        self.assertIn("Never print, echo or store `$AMAE_KOROMO_TOKEN`", SYSTEM)
        self.assertIn("at most one request per 1.2 seconds", SYSTEM)
        self.assertNotIn("secret_value", SETUP)

    def test_prompt_keeps_players_out_of_searches(self):
        self.assertIn("Never put a player's in-game name, account id or game id in a search query or a URL", " ".join(SYSTEM.split()))

    def test_model_is_opus_5_5(self):
        self.assertIn('"id": "claude-opus-5-5"', CLIENT)

    def test_chapters_go_to_a_copy_of_the_coach(self):
        import thread
        roster = thread.MULTIAGENT["subagents"]
        self.assertEqual(roster["predefined_agents"], [{"type": "self"}])
        self.assertEqual(roster["inline_agents"], {"type": "disabled"})
        self.assertEqual(thread.MULTIAGENT["workflows"], {"type": "disabled"})
        self.assertIn("## Who builds a chapter", SYSTEM)
        self.assertIn("The copy sees none of this conversation", " ".join(SYSTEM.split()))
        self.assertIn("If you have no way to hand work to a copy (older threads), build the chapter here",
                      " ".join(SYSTEM.split()))

    def test_prompt_explains_thread_rollover(self):
        flat = " ".join(SYSTEM.split())
        self.assertIn("A thread that grows very long goes on in a fresh session", flat)
        schema = (SERVICE / "db/schema.sql").read_text(encoding="utf-8")
        self.assertIn("add column if not exists continues text", schema)
        self.assertIn("add column if not exists continued_by text", schema)

    def test_chapters_carry_a_topic_line(self):
        flat = " ".join(SYSTEM.split())
        self.assertIn("on the next line `Topic: <topic>`", flat)
        rules = (ROOT / "web/lib/books-rules.mjs").read_text(encoding="utf-8")
        self.assertIn("Topic|トピック", rules)
        self.assertIn("ranks", CLIENT)

    def test_chapter_archive_name_matches_the_client(self):
        name = re.search(r"/mnt/session/outputs/(chapter-<NN>-<slug>\.tar\.gz)", SYSTEM)
        self.assertIsNotNone(name, "the prompt names the chapter archive")
        pattern = re.search(r're\.fullmatch\(r"(chapter-[^"]+)"', CLIENT).group(1)
        self.assertRegex("chapter-52-riichi-rates.tar.gz", "^" + pattern + "$")

    def test_intro_names_the_player(self):
        import thread
        text = thread.intro("Akira", ["akira_jp"])
        self.assertIn("Akira", text)
        self.assertIn("akira_jp", text)

    def test_link_maps_an_email_to_one_player(self):
        import argparse
        import tempfile
        import thread
        with tempfile.TemporaryDirectory() as d:
            old, old_db = thread.STATE, thread.database_url
            thread.STATE = Path(d) / "state.json"
            thread.database_url = lambda: None  # never touch the site's real database
            try:
                thread.save_state({"players": {"A": {"threads": []}, "B": {"threads": []}}})
                thread.cmd_link(None, argparse.Namespace(player="A", email=" Me@Example.com "))
                self.assertEqual(thread.load_state()["players"]["A"]["emails"], ["me@example.com"])
                with self.assertRaises(SystemExit):
                    thread.cmd_link(None, argparse.Namespace(player="B", email="me@example.com"))
            finally:
                thread.STATE, thread.database_url = old, old_db

    def test_refresh_queues_instructions_after_a_waiting_intro(self):
        import tempfile
        import thread
        with tempfile.TemporaryDirectory() as d:
            old, old_db = thread.STATE, thread.database_url
            thread.STATE = Path(d) / "state.json"
            thread.database_url = lambda: None  # never touch the site's real database
            try:
                thread.save_state({"players": {"A": {"threads": [{"session_id": "s1", "intro": "who"}]}}})
                note = thread.instructions_update(9, "RULES")
                thread.queue_intro(thread.load_state(), "A", "s1", note)
                newer = thread.instructions_update(10, "RULES 2")
                thread.queue_intro(thread.load_state(), "A", "s1", newer)
                state = thread.load_state()
                self.assertEqual(thread.take_intro(state, "A", "s1"), "who\n\n" + newer)
                self.assertIn("agent version 9", note)
                self.assertTrue(note.endswith("RULES"))
            finally:
                thread.STATE, thread.database_url = old, old_db

    def test_prompt_asks_for_its_own_analysis(self):
        self.assertIn("# Answering a question", SYSTEM)
        self.assertIn("the repository's scripts are examples, not a menu", SYSTEM)

    def test_state_merge_keeps_what_another_run_added(self):
        import thread
        theirs = {"agent_id": "a1", "shared_files": {"/m": {"file_id": "f1"}},
                  "players": {"A": {"threads": [{"session_id": "s1", "intro": "x"}], "emails": ["a@x"]},
                              "B": {"threads": [{"session_id": "s2"}]}}}
        ours = {"agent_id": "a1", "shared_files": {"/c": {"file_id": "f2"}},
                "players": {"A": {"memory_store_id": "m", "threads": [{"session_id": "s1"}, {"session_id": "s3"}]},
                            "C": {"threads": [{"session_id": "s4"}]}}}
        m = thread.merge_state(ours, theirs)
        self.assertEqual(set(m["players"]), {"A", "B", "C"})
        self.assertEqual(set(m["shared_files"]), {"/m", "/c"})
        a = m["players"]["A"]
        self.assertEqual([t["session_id"] for t in a["threads"]], ["s1", "s3"])
        self.assertNotIn("intro", a["threads"][0], "our copy took the intro; it must stay taken")
        self.assertEqual((a["emails"], a["memory_store_id"]), (["a@x"], "m"))

    def test_scrub_hides_players_in_public_logs(self):
        import thread
        line = ("account 120182062: wrote 3 games; 251019-0a1b2c3d-1111-2222-3333-444455556666 failed"
                " for Honver x@y.com in /home/runner/work/LuckyJ/service/players/ms-120182062/games")
        out = thread.scrub(line, "x@y.com", "Honver", 120182062)
        for secret in ("120182062", "Honver", "x@y.com", "251019-", "runner"):
            self.assertNotIn(secret, out)
        self.assertIn("wrote 3 games", out)

    def test_web_and_agent_agree_on_game_references(self):
        markup = (ROOT / "web/lib/markup.mjs").read_text(encoding="utf-8")
        self.assertIn("[[game:<uuid> <round> t<turn>]]", SYSTEM)
        self.assertIn("game:([0-9]{6}-[0-9a-f-]{8,40}) ((?:East|South|West|North) \\d-\\d+) t(\\d{1,2})( call)?$", markup)

    def test_tar_is_reproducible(self):
        import tempfile
        import thread
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "a.json"
            p.write_text("{}")
            first = thread.tar_gz([("a.json", p)])
            self.assertEqual(first[4:8], b"\0\0\0\0", "gzip header carries no timestamp")
            p.touch()
            self.assertEqual(thread.sha256(first), thread.sha256(thread.tar_gz([("a.json", p)])))


if __name__ == "__main__":
    unittest.main()
