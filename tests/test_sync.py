import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "sync-skills"
DOCTOR = REPO / "scripts" / "skills-doctor"

PRIVATE_PATTERNS = ("/Users/greenapple", ".agents", "greenapple@")


def run_sync(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(REPO / "src")}
    cmd = [sys.executable, str(SCRIPT), *args]
    return subprocess.run(
        cmd,
        cwd=str(cwd or REPO),
        capture_output=True,
        text=True,
        env=env,
    )


def run_doctor(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(REPO / "src")}
    cmd = [sys.executable, str(DOCTOR), *args]
    return subprocess.run(
        cmd,
        cwd=str(cwd or REPO),
        capture_output=True,
        text=True,
        env=env,
    )


def write_skill(base: Path, skill_id: str) -> None:
    d = base / skill_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        f"""---
name: {skill_id}
description: Generic example skill.
user-invocable: true
---

# {skill_id}
""",
        encoding="utf-8",
    )


def roster_visible(*ids: str, hidden: str | None = None) -> dict:
    skills = [{"id": i, "visible": True, "userInvocable": True} for i in ids]
    if hidden:
        skills.append({"id": hidden, "visible": False, "userInvocable": False})
    return {"skills": skills}


class TestSyncCLI(unittest.TestCase):
    def test_help_exits_zero(self):
        r = run_sync("--help")
        self.assertEqual(r.returncode, 0)
        self.assertIn("--apply", r.stdout)
        self.assertIn("--dry-run", r.stdout)

    def test_dry_run_default_does_not_mutate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "skills"
            src.mkdir()
            write_skill(src, "alpha")
            disc = root / "disc"
            disc.mkdir()
            (root / "roster.json").write_text(
                json.dumps(roster_visible("alpha")), encoding="utf-8"
            )
            before = list(disc.iterdir())
            r = run_sync(
                "--root",
                str(root),
                "--roster",
                "roster.json",
                "--source",
                "skills",
                "--discovery-root",
                "disc",
                cwd=root,
            )
            self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
            self.assertIn("dry-run", r.stdout.lower())
            self.assertEqual(list(disc.iterdir()), before)

    def test_apply_creates_visible_symlinks_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "skills"
            src.mkdir()
            write_skill(src, "alpha")
            write_skill(src, "internal-only-skill")
            disc = root / "disc"
            (root / "roster.json").write_text(
                json.dumps(roster_visible("alpha", hidden="internal-only-skill")),
                encoding="utf-8",
            )
            r = run_sync(
                "--root",
                str(root),
                "--roster",
                "roster.json",
                "--source",
                "skills",
                "--discovery-root",
                "disc",
                "--apply",
                cwd=root,
            )
            self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
            self.assertTrue((disc / "alpha").is_symlink())
            self.assertFalse((disc / "internal-only-skill").exists())
            combined = r.stdout + r.stderr
            for pat in PRIVATE_PATTERNS:
                self.assertNotIn(pat, combined)

    def test_conflicting_dry_run_and_apply(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "skills"
            src.mkdir()
            write_skill(src, "alpha")
            disc = root / "disc"
            (root / "roster.json").write_text(
                json.dumps(roster_visible("alpha")), encoding="utf-8"
            )
            r = run_sync(
                "--root",
                str(root),
                "--roster",
                "roster.json",
                "--source",
                "skills",
                "--discovery-root",
                "disc",
                "--dry-run",
                "--apply",
                cwd=root,
            )
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("apply", r.stderr.lower())

    def test_missing_visible_source_errors_without_dangling_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "skills"
            src.mkdir()
            disc = root / "disc"
            disc.mkdir()
            (root / "roster.json").write_text(
                json.dumps(roster_visible("missing-skill")), encoding="utf-8"
            )
            r = run_sync(
                "--root",
                str(root),
                "--roster",
                "roster.json",
                "--source",
                "skills",
                "--discovery-root",
                "disc",
                "--apply",
                cwd=root,
            )
            self.assertNotEqual(r.returncode, 0)
            self.assertFalse((disc / "missing-skill").exists())

    def test_apply_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "skills"
            src.mkdir()
            write_skill(src, "alpha")
            (root / "roster.json").write_text(
                json.dumps(roster_visible("alpha")), encoding="utf-8"
            )
            base_args = [
                "--root",
                str(root),
                "--roster",
                "roster.json",
                "--source",
                "skills",
                "--discovery-root",
                "disc",
                "--apply",
            ]
            r1 = run_sync(*base_args, cwd=root)
            self.assertEqual(r1.returncode, 0)
            target1 = os.readlink(root / "disc" / "alpha")
            r2 = run_sync(*base_args, cwd=root)
            self.assertEqual(r2.returncode, 0)
            target2 = os.readlink(root / "disc" / "alpha")
            self.assertEqual(target1, target2)
            self.assertIn("noop", (r2.stdout + r2.stderr).lower())

    def test_stale_hidden_symlink_removed_on_apply(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "skills"
            src.mkdir()
            write_skill(src, "alpha")
            write_skill(src, "hidden-one")
            disc = root / "disc"
            disc.mkdir()
            (disc / "hidden-one").symlink_to("../skills/hidden-one")
            manifest = {
                "version": 1,
                "managed": ["hidden-one"],
            }
            (disc / ".agent-skill-ops-sync-manifest.json").write_text(
                json.dumps(manifest), encoding="utf-8"
            )
            (root / "roster.json").write_text(
                json.dumps(roster_visible("alpha", hidden="hidden-one")),
                encoding="utf-8",
            )
            r = run_sync(
                "--root",
                str(root),
                "--roster",
                "roster.json",
                "--source",
                "skills",
                "--discovery-root",
                "disc",
                "--apply",
                cwd=root,
            )
            self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
            self.assertFalse((disc / "hidden-one").exists())

    def test_unrelated_directory_conflict_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "skills"
            src.mkdir()
            write_skill(src, "alpha")
            disc = root / "disc"
            disc.mkdir()
            (disc / "alpha").mkdir()
            (root / "roster.json").write_text(
                json.dumps(roster_visible("alpha")), encoding="utf-8"
            )
            r = run_sync(
                "--root",
                str(root),
                "--roster",
                "roster.json",
                "--source",
                "skills",
                "--discovery-root",
                "disc",
                "--apply",
                cwd=root,
            )
            self.assertEqual(r.returncode, 0)
            self.assertTrue((disc / "alpha").is_dir())
            self.assertFalse((disc / "alpha").is_symlink())

    def test_doctor_passes_after_sync_on_temp_discovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "skills"
            src.mkdir()
            for sid in ("explain-error", "plan-task"):
                write_skill(src, sid)
            disc = root / "disc"
            roster = {
                "skills": [
                    {"id": "explain-error", "visible": True, "userInvocable": True},
                    {"id": "plan-task", "visible": True, "userInvocable": True},
                    {"id": "hidden-x", "visible": False, "userInvocable": False},
                ]
            }
            (root / "roster.json").write_text(json.dumps(roster), encoding="utf-8")
            (root / "settings.json").write_text('{"disabledSkills": []}', encoding="utf-8")
            r_sync = run_sync(
                "--root",
                str(root),
                "--roster",
                "roster.json",
                "--source",
                "skills",
                "--discovery-root",
                "disc",
                "--apply",
                cwd=root,
            )
            self.assertEqual(r_sync.returncode, 0, r_sync.stderr)
            r_doc = run_doctor(
                "--root",
                str(root),
                "--roster",
                "roster.json",
                "--source",
                "skills",
                "--discovery-root",
                "disc",
                "--settings",
                "settings.json",
                cwd=root,
            )
            self.assertEqual(r_doc.returncode, 0, r_doc.stderr)
            self.assertFalse((disc / "hidden-x").exists())


class TestSyncExamplesDryRun(unittest.TestCase):
    def test_examples_dry_run_from_repo(self):
        r = run_sync(
            "--root",
            ".",
            "--roster",
            "examples/roster.json",
            "--source",
            "examples/skills",
            "--discovery-root",
            "/tmp/agent-skill-ops-discovery-test",
            "--dry-run",
        )
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("dry-run", r.stdout.lower())



class TestSyncManifestGitignore(unittest.TestCase):
    def test_apply_manifest_is_gitignored(self):
        from agent_skill_ops.sync import MANIFEST_NAME

        gitignore = (REPO / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(MANIFEST_NAME, gitignore)


if __name__ == "__main__":
    unittest.main()
