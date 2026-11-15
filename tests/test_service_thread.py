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

    def test_tar_is_reproducible(self):
        import tempfile
        import thread
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "a.json"
            p.write_text("{}")
            first = thread.tar_gz([("a.json", p)])
            p.touch()
            self.assertEqual(thread.sha256(first), thread.sha256(thread.tar_gz([("a.json", p)])))


if __name__ == "__main__":
    unittest.main()
