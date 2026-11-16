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

    def test_web_tools_stay_off(self):
        self.assertIn('{"name": "web_fetch", "enabled": False}', CLIENT)
        self.assertIn('{"name": "web_search", "enabled": False}', CLIENT)

    def test_model_is_opus_5_5(self):
        self.assertIn('"id": "claude-opus-5-5"', CLIENT)

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
