import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "examples" / "skills"
PRIVATE_PATTERNS = [
    re.compile(r"/Users/greenapple"),
    re.compile(r"\.agents"),
    re.compile(r"Terry", re.I),
    re.compile(r"Greenapple", re.I),
    re.compile(r"b14a4459"),
]


class TestScaffold(unittest.TestCase):
    def test_pyproject_has_no_runtime_dependencies(self):
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("dependencies = []", text)

    def test_example_skill_count_between_three_and_five(self):
        skill_files = list(SKILLS.glob("*/SKILL.md"))
        self.assertGreaterEqual(len(skill_files), 3)
        self.assertLessEqual(len(skill_files), 5)

    def test_each_example_skill_has_valid_frontmatter_name(self):
        for skill_md in sorted(SKILLS.glob("*/SKILL.md")):
            text = skill_md.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\n"), str(skill_md))
            name = skill_md.parent.name
            self.assertIn(f"name: {name}\n", text, str(skill_md))
            self.assertIn("description:", text, str(skill_md))
            self.assertIn("user-invocable:", text, str(skill_md))

    def test_roster_references_visible_example_skills(self):
        roster = json.loads((ROOT / "examples/roster.json").read_text(encoding="utf-8"))
        visible = {s["id"] for s in roster["skills"] if s.get("visible")}
        for skill_dir in SKILLS.iterdir():
            if not skill_dir.is_dir():
                continue
            if skill_dir.name == "internal-only-skill":
                continue
            self.assertIn(skill_dir.name, visible)

    def test_example_skills_are_public_safe(self):
        for path in ROOT.rglob("*"):
            if path.is_dir():
                continue
            if path.suffix not in {".md", ".json", ".toml"}:
                continue
            rel = str(path.relative_to(ROOT))
            if rel.startswith("tests/"):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for pat in PRIVATE_PATTERNS:
                self.assertIsNone(pat.search(text), f"{rel} matched {pat.pattern}")

    def test_scripts_directory_exists(self):
        for name in ("skills-doctor", "sync-skills", "audit-public-safety"):
            self.assertTrue((ROOT / "scripts" / name).is_file(), name)


if __name__ == "__main__":
    unittest.main()
