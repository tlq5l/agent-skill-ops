import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "audit-public-safety"


def run_audit(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(REPO / "src")}
    cmd = [sys.executable, str(SCRIPT), *args]
    return subprocess.run(
        cmd,
        cwd=str(cwd or REPO),
        capture_output=True,
        text=True,
        env=env,
    )


class TestAuditCLI(unittest.TestCase):
    def test_clean_repo_passes(self):
        r = run_audit("--root", ".")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("no unsafe findings", r.stdout)
        self.assertIn("categories checked:", r.stdout)
        for rule in (
            "PRIVATE_PATH",
            "PRIVATE_CORPUS",
            "MEMORIES",
            "SECURE_BACKUPS",
            "PUBLIC_GTM_LEAK",
            "OBVIOUS_SECRET",
        ):
            self.assertIn(rule, r.stdout, msg=f"missing category {rule}")

    def test_help_exits_zero(self):
        r = run_audit("--help")
        self.assertEqual(r.returncode, 0)
        self.assertIn("--root", r.stdout)

    def test_detects_private_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "leak.md").write_text(
                "see /Users/greenapple/.agents for more\n",
                encoding="utf-8",
            )
            r = run_audit("--root", str(root))
            self.assertEqual(r.returncode, 1)
            self.assertIn("PRIVATE_PATH", r.stderr)

    def test_detects_obvious_secret(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config.py").write_text(
                'TOKEN = "sk-abcdefghijklmnopqrstuvwxyz123456"\n',
                encoding="utf-8",
            )
            r = run_audit("--root", str(root))
            self.assertEqual(r.returncode, 1)
            self.assertIn("OBVIOUS_SECRET", r.stderr)

    def test_detects_private_corpus_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "notes.md").write_text(
                "copied from .agents/skill-db/foo\n",
                encoding="utf-8",
            )
            r = run_audit("--root", str(root))
            self.assertEqual(r.returncode, 1)
            self.assertIn("PRIVATE_CORPUS", r.stderr)

    def test_detects_public_gtm_language(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text(
                "7-day demand test with concierge CTA\n",
                encoding="utf-8",
            )
            r = run_audit("--root", str(root))
            self.assertEqual(r.returncode, 1)
            self.assertIn("PUBLIC_GTM_LEAK", r.stderr)

    def test_detects_banned_category_memories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ref.md").write_text("see .agents/memories/foo\n", encoding="utf-8")
            r = run_audit("--root", str(root))
            self.assertEqual(r.returncode, 1)
            self.assertIn("MEMORIES", r.stderr)

    def test_detects_banned_category_secure_backups(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ref.md").write_text("path secure-backups/archive\n", encoding="utf-8")
            r = run_audit("--root", str(root))
            self.assertEqual(r.returncode, 1)
            self.assertIn("SECURE_BACKUPS", r.stderr)

    def test_detects_mission_internals(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ref.md").write_text(".factory/missions/demo\n", encoding="utf-8")
            r = run_audit("--root", str(root))
            self.assertEqual(r.returncode, 1)
            self.assertIn("MISSION_INTERNALS", r.stderr)


if __name__ == "__main__":
    unittest.main()
