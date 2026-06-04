import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "skills-doctor"


def run_doctor(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(REPO / "src")}
    cmd = [sys.executable, str(SCRIPT), *args]
    return subprocess.run(
        cmd,
        cwd=str(cwd or REPO),
        capture_output=True,
        text=True,
        env=env,
    )


def write_skill(base: Path, skill_id: str, body: str) -> None:
    d = base / skill_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(body, encoding="utf-8")


VALID_SKILL = """---
name: {name}
description: Generic teaching skill.
user-invocable: true
---

# Skill
"""


class TestDoctorCLI(unittest.TestCase):
    def test_help_exits_zero(self):
        r = run_doctor("--help")
        self.assertEqual(r.returncode, 0)
        self.assertIn("--roster", r.stdout)
        self.assertIn("--discovery-root", r.stdout)
        self.assertIn("--settings", r.stdout)
        self.assertIn("--dry-run", r.stdout)

    def test_examples_fixture_passes(self):
        r = run_doctor(
            "--root",
            ".",
            "--roster",
            "examples/roster.json",
            "--discovery-root",
            "examples/discovery",
            "--settings",
            "examples/harness-settings.json",
        )
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("no issues found", r.stdout)

    def test_without_settings_passes(self):
        r = run_doctor(
            "--root",
            ".",
            "--roster",
            "examples/roster.json",
            "--discovery-root",
            "examples/discovery",
        )
        self.assertEqual(r.returncode, 0)

    def test_missing_roster_is_config_error(self):
        r = run_doctor("--roster", "missing-roster.json")
        self.assertEqual(r.returncode, 2)
        self.assertIn("configuration error", r.stderr)

    def test_malformed_roster_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bad = root / "bad.json"
            bad.write_text("{not json", encoding="utf-8")
            r = run_doctor("--root", str(root), "--roster", str(bad))
            self.assertEqual(r.returncode, 2)
            self.assertIn("malformed JSON", r.stderr)

    def test_name_mismatch_in_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "skills"
            src.mkdir()
            write_skill(
                src,
                "alpha-skill",
                VALID_SKILL.format(name="not-alpha"),
            )
            roster = {
                "skills": [{"id": "alpha-skill", "visible": True, "userInvocable": True}]
            }
            (root / "roster.json").write_text(json.dumps(roster), encoding="utf-8")
            disc = root / "disc"
            disc.mkdir()
            r = run_doctor(
                "--root",
                str(root),
                "--roster",
                "roster.json",
                "--source",
                "skills",
                "--discovery-root",
                "disc",
            )
            self.assertEqual(r.returncode, 1)
            self.assertIn("alpha-skill", r.stderr)
            self.assertIn("name mismatch", r.stderr)

    def test_broken_symlink_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "skills"
            write_skill(src, "alpha-skill", VALID_SKILL.format(name="alpha-skill"))
            roster = {
                "skills": [{"id": "alpha-skill", "visible": True, "userInvocable": True}]
            }
            (root / "roster.json").write_text(json.dumps(roster), encoding="utf-8")
            disc = root / "disc"
            disc.mkdir()
            (disc / "alpha-skill").symlink_to(src / "missing")
            r = run_doctor(
                "--root",
                str(root),
                "--roster",
                "roster.json",
                "--source",
                "skills",
                "--discovery-root",
                "disc",
            )
            self.assertEqual(r.returncode, 1)
            self.assertIn("BROKEN_SYMLINK", r.stderr)

    def test_hidden_skill_in_discovery_leaks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "skills"
            write_skill(src, "alpha-skill", VALID_SKILL.format(name="alpha-skill"))
            write_skill(
                src,
                "internal-only-skill",
                VALID_SKILL.format(name="internal-only-skill"),
            )
            roster = {
                "skills": [
                    {"id": "alpha-skill", "visible": True, "userInvocable": True},
                    {
                        "id": "internal-only-skill",
                        "visible": False,
                        "userInvocable": False,
                    },
                ]
            }
            (root / "roster.json").write_text(json.dumps(roster), encoding="utf-8")
            disc = root / "disc"
            disc.mkdir()
            (disc / "internal-only-skill").symlink_to(src / "internal-only-skill")
            r = run_doctor(
                "--root",
                str(root),
                "--roster",
                "roster.json",
                "--source",
                "skills",
                "--discovery-root",
                "disc",
            )
            self.assertEqual(r.returncode, 1)
            self.assertIn("internal-only-skill", r.stderr)

    def test_disabled_visible_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "skills"
            write_skill(src, "alpha-skill", VALID_SKILL.format(name="alpha-skill"))
            roster = {
                "skills": [{"id": "alpha-skill", "visible": True, "userInvocable": True}]
            }
            (root / "roster.json").write_text(json.dumps(roster), encoding="utf-8")
            settings = {"disabledSkills": ["alpha-skill"]}
            (root / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
            disc = root / "disc"
            disc.mkdir()
            r = run_doctor(
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
            )
            self.assertEqual(r.returncode, 1)
            self.assertIn("DISABLED_VISIBLE", r.stderr)

    def test_disabled_hidden_leak(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "skills"
            src.mkdir()
            roster = {"skills": []}
            (root / "roster.json").write_text(json.dumps(roster), encoding="utf-8")
            settings = {"disabledSkills": ["internal-only-skill"]}
            (root / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
            disc = root / "disc"
            disc.mkdir()
            r = run_doctor(
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
            )
            self.assertEqual(r.returncode, 1)
            self.assertIn("DISABLED_HIDDEN_LEAK", r.stderr)

    def test_copied_directory_in_discovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "skills"
            write_skill(src, "alpha-skill", VALID_SKILL.format(name="alpha-skill"))
            roster = {
                "skills": [{"id": "alpha-skill", "visible": True, "userInvocable": True}]
            }
            (root / "roster.json").write_text(json.dumps(roster), encoding="utf-8")
            disc = root / "disc"
            disc.mkdir()
            import shutil

            shutil.copytree(src / "alpha-skill", disc / "alpha-skill")
            r = run_doctor(
                "--root",
                str(root),
                "--roster",
                "roster.json",
                "--source",
                "skills",
                "--discovery-root",
                "disc",
            )
            self.assertEqual(r.returncode, 1)
            self.assertIn("DISCOVERY_COPIED_DIR", r.stderr)

    def test_multiple_discovery_roots_second_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "skills"
            write_skill(src, "alpha-skill", VALID_SKILL.format(name="alpha-skill"))
            roster = {
                "skills": [{"id": "alpha-skill", "visible": True, "userInvocable": True}]
            }
            (root / "roster.json").write_text(json.dumps(roster), encoding="utf-8")
            good = root / "disc-good"
            good.mkdir()
            bad = root / "disc-bad"
            bad.mkdir()
            (bad / "internal-only-skill").mkdir()
            r = run_doctor(
                "--root",
                str(root),
                "--roster",
                "roster.json",
                "--source",
                "skills",
                "--discovery-root",
                "disc-good",
                "--discovery-root",
                "disc-bad",
            )
            self.assertEqual(r.returncode, 1)
            self.assertIn("disc-bad", r.stderr)

    def test_read_only_no_mtime_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "skills"
            write_skill(src, "alpha-skill", VALID_SKILL.format(name="alpha-skill"))
            roster = {
                "skills": [{"id": "alpha-skill", "visible": True, "userInvocable": True}]
            }
            roster_path = root / "roster.json"
            roster_path.write_text(json.dumps(roster), encoding="utf-8")
            disc = root / "disc"
            disc.mkdir()
            before = roster_path.stat().st_mtime_ns
            r = run_doctor(
                "--root",
                str(root),
                "--roster",
                "roster.json",
                "--source",
                "skills",
                "--discovery-root",
                "disc",
                "--dry-run",
            )
            after = roster_path.stat().st_mtime_ns
            self.assertEqual(r.returncode, 0)
            self.assertEqual(before, after)

    def test_stable_exit_code_on_invariant_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "skills"
            write_skill(
                src,
                "alpha-skill",
                "---\nname: alpha-skill\ndescription: ok\nuser-invocable: maybe\n---\n",
            )
            roster = {
                "skills": [{"id": "alpha-skill", "visible": True, "userInvocable": True}]
            }
            (root / "roster.json").write_text(json.dumps(roster), encoding="utf-8")
            disc = root / "disc"
            disc.mkdir()
            r1 = run_doctor(
                "--root",
                str(root),
                "--roster",
                "roster.json",
                "--source",
                "skills",
                "--discovery-root",
                "disc",
            )
            r2 = run_doctor(
                "--root",
                str(root),
                "--roster",
                "roster.json",
                "--source",
                "skills",
                "--discovery-root",
                "disc",
            )
            self.assertEqual(r1.returncode, 1)
            self.assertEqual(r1.returncode, r2.returncode)


if __name__ == "__main__":
    unittest.main()
